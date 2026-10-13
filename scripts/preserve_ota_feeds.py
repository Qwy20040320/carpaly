#!/usr/bin/env python3
"""Validate and carry forward already-published signed OTA feeds during Pages builds."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

if __package__:
    from . import ota_manifest
else:
    import ota_manifest


MAX_FEED_BYTES = 128 * 1024
MAX_CHECKSUM_BYTES = 256
ALLOWED_HOST = "qwy20040320.github.io"
ALLOWED_ASSET_REDIRECT_HOSTS = {
    "github.com",
    "release-assets.githubusercontent.com",
    "objects.githubusercontent.com",
}
SITE_ROOT_URL = "https://qwy20040320.github.io/carpaly/"
SITE_ROOT_PATH = "/carpaly/"
SITE_STATE_URL = "https://qwy20040320.github.io/carpaly/data/releases.json"
SITE_STATE_PATH = "/carpaly/data/releases.json"
ALLOWED_PATHS = {
    "stable": "/carpaly/updates/stable.json",
    "beta": "/carpaly/updates/beta.json",
}


class FeedPreservationError(ValueError):
    """A deployed feed cannot be safely preserved; do not publish a replacement site."""


@dataclass(frozen=True)
class FeedResponse:
    status: int
    body: bytes
    final_url: str


@dataclass(frozen=True)
class VerifiedFeed:
    body: bytes
    payload: Mapping[str, Any]


FeedFetcher = Callable[[str], FeedResponse]


def _parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise FeedPreservationError(f"Signed OTA feed has no valid {field}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FeedPreservationError(f"Signed OTA feed has invalid {field}") from exc
    if parsed.tzinfo is None:
        raise FeedPreservationError(f"Signed OTA feed {field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _validate_url(channel: str, url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST or parsed.port not in (None, 443) \
            or parsed.username or parsed.password or parsed.path != ALLOWED_PATHS[channel] \
            or parsed.fragment:
        raise FeedPreservationError(f"Configured {channel} OTA feed URL is not the canonical HTTPS endpoint")


def _verify_path_url(url: str, path: str, label: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST or parsed.port not in (None, 443) \
            or parsed.username or parsed.password or parsed.path != path or parsed.fragment:
        raise FeedPreservationError(f"Deployed {label} redirected to an untrusted URL")


def fetch_site_deployment_state(fetcher: FeedFetcher | None = None) -> dict[str, bool] | None:
    """Return persisted per-channel history; None means the target Pages path is still uninitialized."""
    fetcher = fetcher or fetch_url
    root = fetcher(SITE_ROOT_URL)
    if root.status not in {200, 404}:
        raise FeedPreservationError(f"Could not confirm the deployed site state (HTTP {root.status})")
    _verify_path_url(root.final_url, SITE_ROOT_PATH, "Pages home")
    state = fetcher(SITE_STATE_URL)
    if state.status not in {200, 404}:
        raise FeedPreservationError(f"Could not confirm the deployed feed-history state (HTTP {state.status})")
    _verify_path_url(state.final_url, SITE_STATE_PATH, "Pages release-state marker")
    if state.status == 404:
        if root.status == 200:
            raise FeedPreservationError("Pages is deployed but its release-state marker is missing")
        return None
    if root.status != 200:
        raise FeedPreservationError("Pages release-state marker exists while the site home is unavailable")
    if len(state.body) > MAX_FEED_BYTES:
        raise FeedPreservationError("Deployed Pages release-state marker exceeds the size limit")
    try:
        value = json.loads(state.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FeedPreservationError("Deployed Pages release-state marker is malformed") from exc
    if not isinstance(value, dict) or value.get("schemaVersion") != 1 \
            or value.get("repository") != "Qwy20040320/carpaly":
        raise FeedPreservationError("Deployed Pages release-state marker has an unsupported repository or schema")
    history = value.get("otaFeedEverPublished")
    if not isinstance(history, dict) or any(not isinstance(history.get(c), bool) for c in ("stable", "beta")):
        raise FeedPreservationError("Deployed Pages release-state marker has no trustworthy per-channel feed history")
    return {channel: history[channel] for channel in ("stable", "beta")}


def fetch_url(url: str) -> FeedResponse:
    """Fetch without cache reuse. Only an explicit 404 means that a feed has never been deployed."""
    separator = "&" if "?" in url else "?"
    request_url = f"{url}{separator}carpaly_cache_bust={time.time_ns()}"
    request = urllib.request.Request(
        request_url,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache, no-store, max-age=0",
            "Pragma": "no-cache",
            "User-Agent": "CarPaly-Pages-feed-preserver",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read(MAX_FEED_BYTES + 1)
            return FeedResponse(int(response.status), body, response.geturl())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return FeedResponse(404, b"", exc.geturl())
        raise FeedPreservationError(f"Could not confirm the deployed OTA feed state (HTTP {exc.code})") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FeedPreservationError("Could not confirm the deployed OTA feed state") from exc


def _verify_response_url(channel: str, url: str) -> None:
    _verify_path_url(url, ALLOWED_PATHS[channel], f"{channel} OTA feed")


def validate_feed(
    *, channel: str,
    body: bytes,
    site_state: Mapping[str, Any],
    trusted_keys: Mapping[str, Any],
    policy: Mapping[str, Any],
    now: datetime | None = None,
) -> VerifiedFeed:
    if not 1 <= len(body) <= MAX_FEED_BYTES:
        raise FeedPreservationError(f"Deployed {channel} OTA feed is empty or exceeds the size limit")
    try:
        envelope = json.loads(body.decode("utf-8"))
        if not isinstance(envelope, dict):
            raise ValueError("envelope is not an object")
        payload = ota_manifest.verify_envelope(envelope, trusted_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, ota_manifest.ManifestError) as exc:
        raise FeedPreservationError(f"Deployed {channel} OTA feed is malformed, unsigned, or untrusted") from exc

    if payload.get("channel") != channel or payload.get("packageName") != policy.get("applicationId") \
            or payload.get("manifestKeyId") != envelope.get("manifestKeyId"):
        raise FeedPreservationError(f"Deployed {channel} OTA feed has conflicting channel, package, or key identity")
    issued = _parse_time(payload.get("issuedAt"), "issuedAt")
    expires = _parse_time(payload.get("expiresAt"), "expiresAt")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if issued > current + timedelta(minutes=5) or expires <= current or expires <= issued \
            or expires - issued > timedelta(days=31):
        raise FeedPreservationError(f"Deployed {channel} OTA feed is expired or has an invalid validity window")

    available = payload.get("available")
    if not isinstance(available, bool):
        raise FeedPreservationError(f"Deployed {channel} OTA feed has no boolean availability state")
    if available:
        history = site_state.get("publishedHistory")
        if isinstance(history, list):
            candidates = [
                item for item in history
                if isinstance(item, Mapping)
                and item.get("tag") == payload.get("releaseTag")
                and item.get("prerelease") is (channel == "beta")
            ]
        else:
            candidate = site_state.get(channel)
            candidates = [candidate] if isinstance(candidate, Mapping) \
                and candidate.get("tag") == payload.get("releaseTag") else []
        if len(candidates) != 1:
            raise FeedPreservationError(
                f"Deployed {channel} OTA feed references no unique published Release in the current catalog"
            )
        current_release = candidates[0]
        apk = current_release.get("apk") if isinstance(current_release, Mapping) else None
        if not isinstance(apk, Mapping) or current_release.get("apkVerificationStatus") != "PASS":
            raise FeedPreservationError(
                f"Deployed {channel} OTA feed references a Release absent from the verified public catalog"
            )
        comparisons = {
            "releaseTag": current_release.get("tag"),
            "sourceCommit": current_release.get("tagSha"),
            "versionName": apk.get("versionName"),
            "versionCode": apk.get("versionCode"),
            "apkSha256": apk.get("sha256"),
            "apkSize": apk.get("size"),
            "apkUrl": apk.get("url"),
            "checksumUrl": apk.get("checksumUrl"),
            "checksumSize": apk.get("checksumSize"),
            "minimumSupportedVersionCode": policy.get("minimumSupportedVersionCode"),
            "signerCertSha256": apk.get("signerSha256"),
            "releaseNotesUrl": current_release.get("releaseUrl"),
        }
        if any(payload.get(name) != value for name, value in comparisons.items()) \
                or str(payload.get("signerCertSha256", "")).lower() != str(
                    policy.get("releaseSignerCertificateSha256", "")
                ).lower():
            raise FeedPreservationError(
                f"Deployed {channel} OTA feed does not match the current verified Release and APK evidence"
            )
    return VerifiedFeed(body=body, payload=payload)


def _verify_release_checksum(payload: Mapping[str, Any], *, fetcher: FeedFetcher) -> None:
    """Re-fetch the published checksum sidecar before preserving an available OTA feed."""
    tag = payload.get("releaseTag")
    apk_name = payload.get("apkUrl")
    apk_url = urllib.parse.urlsplit(apk_name) if isinstance(apk_name, str) else None
    match = re.fullmatch(r"v(\d+\.\d+\.\d+)", tag) if isinstance(tag, str) else None
    if not match or apk_url is None:
        raise FeedPreservationError("Signed OTA feed does not reference a canonical versioned Release APK")
    expected_name = f"CarPaly-XingyueL-v{match.group(1)}.apk"
    expected_apk_url = f"https://github.com/Qwy20040320/carpaly/releases/download/{tag}/{expected_name}"
    expected_checksum_url = expected_apk_url + ".sha256"
    if apk_name != expected_apk_url or payload.get("checksumUrl") != expected_checksum_url:
        raise FeedPreservationError("Signed OTA feed Release APK or checksum URL is not canonical")
    expected_sha256 = payload.get("apkSha256")
    checksum_size = payload.get("checksumSize")
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256) \
            or type(checksum_size) is not int or not 1 <= checksum_size <= MAX_CHECKSUM_BYTES:
        raise FeedPreservationError("Signed OTA feed has invalid APK checksum metadata")

    response = fetcher(expected_checksum_url)
    if response.status != 200:
        raise FeedPreservationError("Published Release APK checksum sidecar is unavailable")
    final = urllib.parse.urlsplit(response.final_url)
    if final.scheme != "https" or final.hostname not in ALLOWED_ASSET_REDIRECT_HOSTS \
            or final.port not in (None, 443) or final.username or final.password:
        raise FeedPreservationError("Published Release APK checksum redirected to an untrusted host")
    if not ota_manifest.checksum_sidecar_matches(
            response.body, apk_name=expected_name, expected_sha256=expected_sha256,
            expected_size=checksum_size):
        raise FeedPreservationError("Published Release APK checksum sidecar does not match the verified OTA feed")


def fetch_validated_feeds(
    *, site_state: Mapping[str, Any],
    urls: Mapping[str, Any],
    trusted_keys: Mapping[str, Any],
    policy: Mapping[str, Any],
    previously_published: Mapping[str, bool] | None = None,
    fetcher: FeedFetcher = fetch_url,
    now: datetime | None = None,
) -> dict[str, VerifiedFeed]:
    """Read and verify both channels before returning either, so a bad feed blocks the whole deploy."""
    result: dict[str, VerifiedFeed] = {}
    previous = previously_published or {"stable": False, "beta": False}
    for channel in ("stable", "beta"):
        url = urls.get(channel)
        if not isinstance(url, str):
            raise FeedPreservationError(f"Configured {channel} OTA feed URL is missing")
        _validate_url(channel, url)
        response = fetcher(url)
        if response.status == 404:
            if previous.get(channel) is True:
                raise FeedPreservationError(
                    f"Previously deployed {channel} OTA feed now returns 404; refusing to erase a valid feed"
                )
            continue
        if response.status != 200:
            raise FeedPreservationError(f"Could not confirm the deployed {channel} OTA feed (HTTP {response.status})")
        _verify_response_url(channel, response.final_url)
        verified = validate_feed(
            channel=channel, body=response.body, site_state=site_state,
            trusted_keys=trusted_keys, policy=policy, now=now,
        )
        if verified.payload.get("available") is True:
            _verify_release_checksum(verified.payload, fetcher=fetcher)
        result[channel] = verified
    return result
