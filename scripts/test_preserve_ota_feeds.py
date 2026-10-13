from __future__ import annotations

import base64
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from scripts import build_site, ota_manifest, preserve_ota_feeds


NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
POLICY = build_site.read_json(build_site.OTA_POLICY_PATH)
CHANNEL_URLS = POLICY["channels"]
RELEASE = {
    "tag": "v1.1.51",
    "tagSha": "c" * 40,
    "title": "CarPaly v1.1.51",
    "publishedDate": "2026-10-10",
    "prerelease": False,
    "releaseUrl": "https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.51",
    "apkVerificationStatus": "PASS",
    "releaseNoteStateConflict": False,
    "apk": {
        "name": "CarPaly-XingyueL-v1.1.51.apk",
        "url": "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.51/CarPaly-XingyueL-v1.1.51.apk",
        "size": 16_900_000,
        "sha256": "a" * 64,
        "versionName": "1.1.51",
        "versionCode": 39,
        "signerSha256": POLICY["releaseSignerCertificateSha256"],
        "checksumUrl": "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.51/CarPaly-XingyueL-v1.1.51.apk.sha256",
        "checksumSize": 0,
    },
}
RELEASE["apk"]["checksumSize"] = len(
    f"{RELEASE['apk']['sha256']}  {RELEASE['apk']['name']}\n".encode("ascii")
)
SITE_STATE = {"stable": RELEASE, "beta": None, "publishedHistory": [RELEASE]}
BUILD_RECORD = {
    "tag": RELEASE["tag"],
    "tagSha": RELEASE["tagSha"],
    "title": RELEASE["title"],
    "publishedDate": RELEASE["publishedDate"],
    "prerelease": False,
    "draft": False,
    "htmlUrl": RELEASE["releaseUrl"],
    "apkVerificationStatus": "PASS",
    "releaseNoteStateConflict": False,
    "verifiedApk": {
        "name": RELEASE["apk"]["name"],
        "url": RELEASE["apk"]["url"],
        "size": RELEASE["apk"]["size"],
        "sha256": RELEASE["apk"]["sha256"],
        "versionName": RELEASE["apk"]["versionName"],
        "versionCode": RELEASE["apk"]["versionCode"],
        "signerSha256": RELEASE["apk"]["signerSha256"],
    },
    "assets": [{
        "name": RELEASE["apk"]["name"] + ".sha256",
        "url": RELEASE["apk"]["checksumUrl"],
        "size": RELEASE["apk"]["checksumSize"],
    }],
}


class FeedPreservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = ec.generate_private_key(ec.SECP256R1())
        cls.key_id = "synthetic-test-key"
        public_der = cls.private_key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        cls.trust = {
            "schemaVersion": 1,
            "keys": [{
                "keyId": cls.key_id,
                "algorithm": "SHA256withECDSA-P256",
                "status": "active",
                "publicKeyX509Base64": base64.b64encode(public_der).decode("ascii"),
            }],
        }

    def payload(self, channel: str = "stable", *, available: bool = True, **overrides) -> dict:
        value = {
            "schemaVersion": 1,
            "channel": channel,
            "available": available,
            "packageName": POLICY["applicationId"],
            "minimumSupportedVersionCode": POLICY["minimumSupportedVersionCode"],
            "manifestKeyId": self.key_id,
            "issuedAt": NOW.isoformat().replace("+00:00", "Z"),
            "expiresAt": (NOW + timedelta(days=30)).isoformat().replace("+00:00", "Z"),
        }
        if available:
            value.update({
                "versionName": "1.1.51",
                "versionCode": 39,
                "releaseTag": "v1.1.51",
                "sourceCommit": RELEASE["tagSha"],
                "releaseDate": "2026-10-10T00:00:00Z",
                "releaseNotesUrl": RELEASE["releaseUrl"],
                "apkUrl": RELEASE["apk"]["url"],
                "checksumUrl": RELEASE["apk"]["url"] + ".sha256",
                "checksumSize": RELEASE["apk"]["checksumSize"],
                "apkSize": RELEASE["apk"]["size"],
                "apkSha256": RELEASE["apk"]["sha256"],
                "signerCertSha256": RELEASE["apk"]["signerSha256"],
            })
        value.update(overrides)
        return value

    def signed(self, payload: dict) -> bytes:
        private_pem = self.private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode("ascii")
        envelope = ota_manifest.sign_payload(payload, self.key_id, private_pem, self.trust)
        return (json.dumps(envelope, separators=(",", ":")) + "\n").encode("utf-8")

    def fetcher(self, responses: dict[str, preserve_ota_feeds.FeedResponse]):
        return lambda url: responses[url]

    def get_feeds(self, responses, *, trust=None, site_state=None, previously_published=None):
        responses = dict(responses)
        selected_state = SITE_STATE if site_state is None else site_state
        for channel in ("stable", "beta"):
            feed_response = responses.get(CHANNEL_URLS[channel])
            if not feed_response or feed_response.status != 200:
                continue
            try:
                envelope = json.loads(feed_response.body.decode("utf-8"))
                payload = ota_manifest.verify_envelope(envelope, self.trust)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, ota_manifest.ManifestError):
                continue
            if payload.get("available") is not True:
                continue
            history = selected_state.get("publishedHistory", [])
            release = next((item for item in history if item.get("tag") == payload.get("releaseTag")), None)
            if release is None and payload.get("releaseTag") == RELEASE["tag"]:
                release = RELEASE
            if release is None:
                continue
            apk = release["apk"]
            checksum_url = payload.get("checksumUrl")
            if isinstance(checksum_url, str) and checksum_url not in responses:
                checksum_body = f"{apk['sha256']}  {apk['name']}\n".encode("ascii")
                responses[checksum_url] = preserve_ota_feeds.FeedResponse(
                    200, checksum_body, checksum_url,
                )
        return preserve_ota_feeds.fetch_validated_feeds(
            site_state=selected_state,
            urls=CHANNEL_URLS,
            trusted_keys=self.trust if trust is None else trust,
            policy=POLICY,
            previously_published=previously_published,
            fetcher=self.fetcher(responses),
            now=NOW,
        )

    def response(self, channel: str, body: bytes, *, status: int = 200, final_url: str | None = None):
        return preserve_ota_feeds.FeedResponse(
            status, body, final_url or CHANNEL_URLS[channel],
        )

    def checksum_response(self, release=RELEASE, *, body: bytes | None = None, final_url: str | None = None):
        apk = release["apk"]
        url = apk["checksumUrl"]
        payload = body if body is not None else f"{apk['sha256']}  {apk['name']}\n".encode("ascii")
        return preserve_ota_feeds.FeedResponse(200, payload, final_url or url)

    def deployment_state(self, history: dict[str, bool] | None = None):
        body = json.dumps({
            "schemaVersion": 1,
            "repository": "Qwy20040320/carpaly",
            "otaFeedEverPublished": history or {"stable": False, "beta": False},
        }).encode("utf-8")
        return {
            preserve_ota_feeds.SITE_ROOT_URL: preserve_ota_feeds.FeedResponse(
                200, b"<html>CarPaly</html>", preserve_ota_feeds.SITE_ROOT_URL,
            ),
            preserve_ota_feeds.SITE_STATE_URL: preserve_ota_feeds.FeedResponse(
                200, body, preserve_ota_feeds.SITE_STATE_URL,
            ),
        }

    def test_first_static_deploy_allows_only_explicit_404_and_creates_no_feed(self):
        feeds = {
            CHANNEL_URLS[channel]: self.response(channel, b"", status=404)
            for channel in ("stable", "beta")
        }
        output = self.get_feeds(feeds, trust={"schemaVersion": 1, "keys": []})
        self.assertEqual(output, {})
        responses = {
            preserve_ota_feeds.SITE_ROOT_URL: preserve_ota_feeds.FeedResponse(
                404, b"", preserve_ota_feeds.SITE_ROOT_URL,
            ),
            preserve_ota_feeds.SITE_STATE_URL: preserve_ota_feeds.FeedResponse(
                404, b"", preserve_ota_feeds.SITE_STATE_URL,
            ),
            **feeds,
        }
        with tempfile.TemporaryDirectory() as tmp:
            state = build_site.generate_site(
                content=build_site.read_json(build_site.CONTENT_PATH), records=[],
                output_dir=Path(tmp), base_url="https://qwy20040320.github.io/carpaly",
                preserve_existing_ota_feeds=True,
                allow_initial_static_bootstrap=True,
                feed_fetcher=self.fetcher(responses),
                now=NOW,
            )
            self.assertEqual(state["otaFeedStatus"], "unavailable")
            self.assertFalse((Path(tmp) / "updates" / "stable.json").exists())
            self.assertIn("在线更新暂不可用", (Path(tmp) / "zh-Hans/guide/index.html").read_text(encoding="utf-8"))

    def test_valid_stable_feed_is_copied_byte_for_byte_and_beta_404_is_not_fabricated(self):
        body = self.signed(self.payload("stable"))
        responses = self.deployment_state()
        responses.update({
            CHANNEL_URLS["stable"]: self.response("stable", body),
            CHANNEL_URLS["beta"]: self.response("beta", b"", status=404),
            RELEASE["apk"]["checksumUrl"]: self.checksum_response(),
        })
        with tempfile.TemporaryDirectory() as tmp:
            state = build_site.generate_site(
                content=build_site.read_json(build_site.CONTENT_PATH), records=[BUILD_RECORD],
                output_dir=Path(tmp), base_url="https://qwy20040320.github.io/carpaly",
                preserve_existing_ota_feeds=True, feed_fetcher=self.fetcher(responses), now=NOW,
                feed_policy=POLICY, feed_trusted_keys=self.trust,
            )
            self.assertEqual(state["otaFeedStatus"], "available")
            self.assertEqual(state["otaFeedChannels"], ["stable"])
            self.assertEqual(state["otaFeedEverPublished"], {"stable": True, "beta": False})
            self.assertEqual((Path(tmp) / "updates/stable.json").read_bytes(), body)
            self.assertFalse((Path(tmp) / "updates/beta.json").exists())
            self.assertIn("Stable", (Path(tmp) / "guide/index.html").read_text(encoding="utf-8"))

    def test_stable_and_beta_are_independently_verified_and_preserved(self):
        stable_body = self.signed(self.payload("stable"))
        beta_body = self.signed(self.payload("beta", available=False))
        feeds = self.get_feeds({
            CHANNEL_URLS["stable"]: self.response("stable", stable_body),
            CHANNEL_URLS["beta"]: self.response("beta", beta_body),
        })
        self.assertEqual(set(feeds), {"stable", "beta"})
        self.assertTrue(feeds["stable"].payload["available"])
        self.assertFalse(feeds["beta"].payload["available"])

    def test_valid_existing_feed_for_older_verified_release_survives_newer_site_catalog(self):
        older_feed = self.signed(self.payload("stable"))
        newer = {
            **RELEASE,
            "tag": "v1.1.52",
            "tagSha": "d" * 40,
            "releaseUrl": "https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.52",
            "apk": {
                **RELEASE["apk"],
                "name": "CarPaly-XingyueL-v1.1.52.apk",
                "url": "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.52/CarPaly-XingyueL-v1.1.52.apk",
                "versionName": "1.1.52",
                "versionCode": 40,
                "sha256": "b" * 64,
                "checksumUrl": "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.52/CarPaly-XingyueL-v1.1.52.apk.sha256",
            },
        }
        site_state = {"stable": newer, "beta": None, "publishedHistory": [newer, RELEASE]}
        feeds = self.get_feeds({
            CHANNEL_URLS["stable"]: self.response("stable", older_feed),
            CHANNEL_URLS["beta"]: self.response("beta", b"", status=404),
        }, site_state=site_state)
        self.assertEqual(feeds["stable"].payload["releaseTag"], "v1.1.51")

    def test_invalid_signature_untrusted_key_and_corrupt_json_fail_closed(self):
        valid = self.signed(self.payload("stable"))
        envelope = json.loads(valid.decode("utf-8"))
        signature = envelope["manifestSignature"]
        envelope["manifestSignature"] = ("A" if signature[0] != "A" else "B") + signature[1:]
        tampered = json.dumps(envelope).encode("utf-8")
        for body, trust in (
            (tampered, self.trust),
            (valid, {"schemaVersion": 1, "keys": []}),
            (b"not-json", self.trust),
        ):
            with self.subTest(body=body[:10]), self.assertRaises(preserve_ota_feeds.FeedPreservationError):
                self.get_feeds({
                    CHANNEL_URLS["stable"]: self.response("stable", body),
                    CHANNEL_URLS["beta"]: self.response("beta", b"", status=404),
                }, trust=trust)

    def test_expired_wrong_channel_or_release_mismatch_fails_closed(self):
        invalid_payloads = (
            self.payload("stable", expiresAt=(NOW - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")),
            self.payload("beta"),
            self.payload("stable", apkSha256="f" * 64),
            self.payload("stable", minimumSupportedVersionCode=1),
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload.get("channel"), sha=payload.get("apkSha256")), \
                    self.assertRaises(preserve_ota_feeds.FeedPreservationError):
                self.get_feeds({
                    CHANNEL_URLS["stable"]: self.response("stable", self.signed(payload)),
                    CHANNEL_URLS["beta"]: self.response("beta", b"", status=404),
                })

    def test_non_404_server_error_or_untrusted_redirect_blocks_deployment(self):
        cases = (
            self.response("stable", b"", status=503),
            self.response("stable", self.signed(self.payload()), final_url="https://evil.example/feed.json"),
        )
        for response in cases:
            with self.subTest(response=response), self.assertRaises(preserve_ota_feeds.FeedPreservationError):
                self.get_feeds({
                    CHANNEL_URLS["stable"]: response,
                    CHANNEL_URLS["beta"]: self.response("beta", b"", status=404),
                })

    def test_available_feed_requires_matching_published_checksum_sidecar(self):
        body = self.signed(self.payload("stable"))
        checksum_url = RELEASE["apk"]["checksumUrl"]
        valid = f"{RELEASE['apk']['sha256']}  {RELEASE['apk']['name']}\n".encode("ascii")
        cases = (
            preserve_ota_feeds.FeedResponse(200, b"0" * len(valid), checksum_url),
            preserve_ota_feeds.FeedResponse(200, valid, "https://evil.example/asset"),
            preserve_ota_feeds.FeedResponse(404, b"", checksum_url),
        )
        for checksum_response in cases:
            with self.subTest(response=checksum_response), self.assertRaises(
                    preserve_ota_feeds.FeedPreservationError):
                self.get_feeds({
                    CHANNEL_URLS["stable"]: self.response("stable", body),
                    CHANNEL_URLS["beta"]: self.response("beta", b"", status=404),
                    checksum_url: checksum_response,
                })

    def test_bad_beta_blocks_before_any_feed_can_be_carried_forward(self):
        stable_body = self.signed(self.payload("stable"))
        responses = self.deployment_state()
        responses.update({
            CHANNEL_URLS["stable"]: self.response("stable", stable_body),
            CHANNEL_URLS["beta"]: self.response("beta", b"corrupt"),
            RELEASE["apk"]["checksumUrl"]: self.checksum_response(),
        })
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            with self.assertRaises(preserve_ota_feeds.FeedPreservationError):
                build_site.generate_site(
                    content=build_site.read_json(build_site.CONTENT_PATH), records=[BUILD_RECORD], output_dir=output,
                    base_url="https://qwy20040320.github.io/carpaly", preserve_existing_ota_feeds=True,
                    feed_fetcher=self.fetcher(responses), now=NOW,
                    feed_policy=POLICY, feed_trusted_keys=self.trust,
                )
            self.assertFalse((output / "index.html").exists())
            self.assertFalse((output / "updates/stable.json").exists())

    def test_existing_local_feed_in_output_directory_is_never_silently_kept(self):
        responses = {CHANNEL_URLS[k]: self.response(k, b"", status=404) for k in ("stable", "beta")}
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "updates").mkdir()
            (output / "updates/stable.json").write_bytes(b"stale")
            with self.assertRaisesRegex(preserve_ota_feeds.FeedPreservationError, "fresh output directory"):
                build_site.generate_site(
                    content=build_site.read_json(build_site.CONTENT_PATH), records=[], output_dir=output,
                    base_url="https://qwy20040320.github.io/carpaly", preserve_existing_ota_feeds=True,
                    feed_fetcher=self.fetcher(responses), now=NOW,
                )

    def test_lost_previously_published_feed_blocks_even_when_the_other_channel_is_valid(self):
        stable_body = self.signed(self.payload("stable"))
        responses = {
            **self.deployment_state({"stable": True, "beta": False}),
            CHANNEL_URLS["stable"]: self.response("stable", b"", status=404),
            CHANNEL_URLS["beta"]: self.response("beta", b"", status=404),
        }
        with self.assertRaisesRegex(preserve_ota_feeds.FeedPreservationError, "(?i)previously deployed stable"):
            self.get_feeds(
                responses, trust=self.trust,
                previously_published={"stable": True, "beta": False},
            )

    def test_first_static_site_requires_explicit_confirmation_and_absent_feed_state(self):
        missing = {
            preserve_ota_feeds.SITE_ROOT_URL: preserve_ota_feeds.FeedResponse(
                404, b"", preserve_ota_feeds.SITE_ROOT_URL,
            ),
            preserve_ota_feeds.SITE_STATE_URL: preserve_ota_feeds.FeedResponse(
                404, b"", preserve_ota_feeds.SITE_STATE_URL,
            ),
            CHANNEL_URLS["stable"]: self.response("stable", b"", status=404),
            CHANNEL_URLS["beta"]: self.response("beta", b"", status=404),
        }
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(
                preserve_ota_feeds.FeedPreservationError, "explicit workflow_dispatch"):
            build_site.generate_site(
                content=build_site.read_json(build_site.CONTENT_PATH), records=[], output_dir=Path(tmp),
                base_url="https://qwy20040320.github.io/carpaly", preserve_existing_ota_feeds=True,
                feed_fetcher=self.fetcher(missing), now=NOW,
            )
        existing_home_without_marker = dict(missing)
        existing_home_without_marker[preserve_ota_feeds.SITE_ROOT_URL] = preserve_ota_feeds.FeedResponse(
            200, b"existing site", preserve_ota_feeds.SITE_ROOT_URL,
        )
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(
                preserve_ota_feeds.FeedPreservationError, "release-state marker is missing"):
            build_site.generate_site(
                content=build_site.read_json(build_site.CONTENT_PATH), records=[], output_dir=Path(tmp),
                base_url="https://qwy20040320.github.io/carpaly", preserve_existing_ota_feeds=True,
                allow_initial_static_bootstrap=True, feed_fetcher=self.fetcher(existing_home_without_marker), now=NOW,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
