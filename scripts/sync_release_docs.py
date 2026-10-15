#!/usr/bin/env python3
"""Synchronize only explicitly marked CarPaly release-documentation regions.

Published GitHub Release metadata is authoritative for public release state,
dates, tags, assets, and downloadable links. The Android version ledger remains
authoritative for reserved local versionCode allocations. Release notes and
repository About are written only when explicitly requested and only under the
guard conditions implemented below.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

if __package__:
    from .validate_release_metadata import MetadataError, validate_metadata
else:  # Support direct invocation as `python scripts/sync_release_docs.py`.
    from validate_release_metadata import MetadataError, validate_metadata


ROOT = Path(__file__).resolve().parents[1]
METADATA_PATH = Path("config/release-documentation.json")
LEDGER_PATH = Path("config/android-version-ledger.json")
README_PATH = Path("README.md")
CHANGELOG_PATH = Path("CHANGELOG.md")
API_ROOT = "https://api.github.com"
USER_AGENT = "CarPaly-release-doc-sync"
TIMEOUT_SECONDS = 20
MAX_VERIFICATION_JSON_BYTES = 256 * 1024
MAX_GITHUB_PAGE_COUNT = 100
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
TAG_VERSION = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


class SyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarkerRegion:
    start: str
    end: str
    content: str


def marker_region(marker: str, content: str) -> MarkerRegion:
    return MarkerRegion(f"<!-- {marker}:START -->", f"<!-- {marker}:END -->", content.strip("\r\n"))


def replace_marker_region(text: str, marker: str, content: str) -> str:
    """Replace one managed region; absent, duplicated, or reversed markers fail closed."""
    region = marker_region(marker, content)
    start_count = text.count(region.start)
    end_count = text.count(region.end)
    if start_count != 1 or end_count != 1:
        raise SyncError(
            f"{marker} requires exactly one START and one END marker; no file content was changed."
        )
    start = text.index(region.start)
    content_start = start + len(region.start)
    end = text.index(region.end)
    if end < content_start:
        raise SyncError(f"{marker} markers are out of order; no file content was changed.")
    replacement = f"\n{region.content}\n" if region.content else "\n"
    return text[:content_start] + replacement + text[end:]


def _parse_iso(value: str) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def public_releases(releases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Keep only published, non-draft Releases and sort newest first."""
    selected: list[dict[str, Any]] = []
    for release in releases:
        if release.get("draft") is True or not release.get("published_at"):
            continue
        published = _parse_iso(str(release.get("published_at", "")))
        if published is None:
            continue
        tag = str(release.get("tag_name", ""))
        if not tag:
            continue
        selected.append(dict(release))
    selected.sort(key=lambda item: _parse_iso(str(item["published_at"])), reverse=True)
    return selected


def latest_formal_release(releases: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Latest is the newest published non-prerelease Release, not a local candidate."""
    stable = [item for item in public_releases(releases) if item.get("prerelease") is not True]
    return stable[0] if stable else None


def safe_asset_url(repository: str, tag: str, asset: Mapping[str, Any]) -> str | None:
    name = str(asset.get("name", ""))
    url = str(asset.get("browser_download_url", ""))
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        return None
    parsed = urllib.parse.urlparse(url)
    expected_prefix = f"/{repository}/releases/download/{urllib.parse.quote(tag, safe='')}/"
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        return None
    if not parsed.path.startswith(expected_prefix):
        return None
    actual_name = urllib.parse.unquote(parsed.path[len(expected_prefix):])
    if actual_name != name:
        return None
    return url


def asset_digest(asset: Mapping[str, Any]) -> str | None:
    digest = str(asset.get("digest", ""))
    if not digest.startswith("sha256:"):
        return None
    value = digest[7:].lower()
    return value if SHA256.fullmatch(value) else None


def release_assets(release: Mapping[str, Any], repository: str) -> list[dict[str, Any]]:
    tag = str(release.get("tag_name", ""))
    result: list[dict[str, Any]] = []
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        return result
    for raw in assets:
        if not isinstance(raw, Mapping):
            continue
        name = str(raw.get("name", ""))
        url = safe_asset_url(repository, tag, raw)
        if not url:
            continue
        size = raw.get("size")
        if not isinstance(size, int) or size < 0:
            size = None
        result.append(
            {
                "name": name,
                "url": url,
                "size": size,
                "sha256": asset_digest(raw),
            }
        )
    return result


def release_tag_commits(tags: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for tag in tags:
        name = str(tag.get("name", ""))
        commit = tag.get("commit", {})
        sha = str(commit.get("sha", "")).lower() if isinstance(commit, Mapping) else ""
        if name and COMMIT_SHA.fullmatch(sha):
            result[name] = sha
    return result


def _safe_release_title(release: Mapping[str, Any]) -> str:
    title = str(release.get("name") or release.get("tag_name") or "Release")
    return re.sub(r"[\r\n|]", " ", title).strip()


def _date_text(value: str) -> str:
    parsed = _parse_iso(value)
    return parsed.date().isoformat() if parsed else "unknown date"


def _verified_release_record(
    release: Mapping[str, Any],
    repository: str,
    verification: Mapping[str, Any] | None,
    signer_sha256: str,
    application_id: str,
) -> dict[str, Any]:
    assets = release_assets(release, repository)
    apk_assets = [asset for asset in assets if asset["name"].lower().endswith(".apk")]
    proof_status = "NOT_AVAILABLE"
    verified_apk: dict[str, Any] | None = None
    if verification is not None:
        candidate_name = str(verification.get("apk", ""))
        asset = next((item for item in apk_assets if item["name"] == candidate_name), None)
        apk_hash = str(verification.get("apkSha256", "")).lower()
        checks = verification.get("checks", {})
        checks_ok = isinstance(checks, Mapping) and all(
            checks.get(name) == "PASS"
            for name in (
                "APK_SIGNATURE",
                "PACKAGE_NAME_MATCH",
                "SIGNING_CERTIFICATE_MATCH",
                "APK_ZIP_INTEGRITY",
                "RELEASE_VARIANT_NOT_DEBUGGABLE",
            )
        )
        version_match = str(verification.get("versionName", "")) == str(release.get("tag_name", "")).removeprefix("v")
        if (
            asset
            and checks_ok
            and verification.get("status") == "PASS"
            and version_match
            and verification.get("packageName") == application_id
            and str(verification.get("signerCertificateSha256", "")).lower() == signer_sha256
            and asset["sha256"] == apk_hash
        ):
            proof_status = "PASS"
            version_code = verification.get("versionCode")
            if not isinstance(version_code, int) or version_code < 1:
                proof_status = "FAIL"
            else:
                verified_apk = {
                    **asset,
                    "versionName": str(verification.get("versionName")),
                    "versionCode": version_code,
                    "signerSha256": signer_sha256,
                    "minSdk": verification.get("minSdk"),
                    "abis": verification.get("abis", []),
                }
        else:
            proof_status = "FAIL"
    elif apk_assets:
        proof_status = "NOT_VERIFIED"
    return {
        "tag": str(release.get("tag_name", "")),
        "title": _safe_release_title(release),
        "publishedDate": _date_text(str(release.get("published_at", ""))),
        "prerelease": release.get("prerelease") is True,
        "draft": release.get("draft") is True,
        "htmlUrl": str(release.get("html_url", "")),
        "tagSha": None,
        "assets": assets,
        "apkAssets": apk_assets,
        "apkVerificationStatus": proof_status,
        "verifiedApk": verified_apk,
        "releaseNoteStateConflict": release_note_state_conflict(release),
    }


def _released_records(
    releases: Sequence[Mapping[str, Any]],
    tags: Sequence[Mapping[str, Any]],
    repository: str,
    ledger: Mapping[str, Any],
    verifications: Mapping[str, Mapping[str, Any] | None] | None = None,
) -> list[dict[str, Any]]:
    tag_shas = release_tag_commits(tags)
    verifications = verifications or {}
    signer = str(ledger.get("releaseCertificateSha256", "")).lower()
    app_id = str(ledger.get("applicationId", ""))
    records = [
        _verified_release_record(
            release,
            repository,
            verifications.get(str(release.get("tag_name", ""))),
            signer,
            app_id,
        )
        for release in public_releases(releases)
    ]
    for record in records:
        record["tagSha"] = tag_shas.get(record["tag"])
    return records


def render_release_summary(records: Sequence[Mapping[str, Any]]) -> str:
    formal = next((record for record in records if record.get("prerelease") is not True), None)
    if formal is None:
        latest = "当前没有已发布的正式 Release。"
    else:
        verified = formal.get("verifiedApk")
        if verified:
            download = f"[下载 APK]({verified['url']})"
            proof = (
                f"已核对包名 `{verified['versionName']}` / versionCode `{verified['versionCode']}`、"
                f"签名指纹及 GitHub 资产 SHA-256 `{verified['sha256']}`。"
            )
        else:
            download = "该 Release 暂无可验证 APK 下载附件。"
            proof = f"APK 验证状态：`{formal.get('apkVerificationStatus', 'NOT_VERIFIED')}`。"
        latest = (
            f"GitHub 最新正式 Release：[{formal['tag']}]({formal['htmlUrl']})，"
            f"发布于 {formal['publishedDate']}。{download} {proof}"
        )
    lines = ["### GitHub 发布状态（自动同步）", "", latest, "", "最近已发布的版本：", "", "| 标签 | 类型 | 日期 | APK 附件 | 源码提交 |", "| --- | --- | --- | --- | --- |"]
    if formal and formal.get("releaseNoteStateConflict"):
        lines.insert(
            3,
            "**说明状态冲突：** GitHub 将该 Release 标记为正式版，但人工说明仍写有预发布措辞；自动同步保留原说明，不擅自改写。",
        )
    for record in list(records)[:10]:
        release_type = "预发布" if record.get("prerelease") else "正式"
        verified_apk = record.get("verifiedApk")
        apk_text = (
            f"[{verified_apk['name']}]({verified_apk['url']})"
            if verified_apk
            else ("有 APK 附件（未验证，不提供链接）" if record.get("apkAssets") else "无 APK 附件")
        )
        sha = record.get("tagSha")
        source = f"`{sha[:12]}`" if sha else "未知"
        tag_url = record.get("htmlUrl") or ""
        lines.append(
            f"| [{record['tag']}]({tag_url}) | {release_type} | {record['publishedDate']} | {apk_text} | {source} |"
        )
    if not records:
        lines.append("| — | — | — | 无公开附件 | — |")
    return "\n".join(lines)


def render_candidate(
    metadata: Mapping[str, Any], ledger: Mapping[str, Any], released_tags: set[str], known_tags: set[str],
    records: Sequence[Mapping[str, Any]] = (),
) -> str:
    candidate = metadata["candidate"]
    version = str(candidate["versionName"])
    tag = f"v{version}"
    current = ledger["current"]
    if tag in released_tags:
        record = next((item for item in records if item.get("tag") == tag), None)
        if record:
            channel = "预发布" if record.get("prerelease") else "正式版"
            verification = str(record.get("apkVerificationStatus", "NOT_VERIFIED"))
            conflict = bool(record.get("releaseNoteStateConflict"))
            note = "Release 正文仍含预发布措辞，状态不一致；自动同步不会改写人工正文。" if conflict else ""
            download = "可验证 APK 下载尚未建立。" if not record.get("verifiedApk") else "APK 验证记录已匹配。"
            return (
                f"**v{version} 已由 GitHub 标记为已发布（{channel}）。** "
                f"本地版本台账仍保留候选阶段记录；GitHub APK 验证状态为 `{verification}`，"
                f"因此不在此处推导可验证下载链接。{note}{download} "
                "后续版本按台账高水位递增；`v1.1.6` 是未来序列目标，不代表已分配或发布。"
            )
        return (
            f"**{tag} 已存在 GitHub Release。** 请先补齐 `{METADATA_PATH.as_posix()}` 中的发布说明资料后再同步候选状态。"
        )
    if tag in known_tags:
        return (
            f"**{tag} Git 标签已存在，但当前没有已发布的 Release。** "
            "不提供公开下载链接；请检查是否为草稿或不完整发布状态。"
        )
    return (
        f"**本地候选：v{version} / versionCode {current['versionCode']}。** "
        f"尚无公开标签或 Release；不提供公开下载链接。{candidate['summaryZh']}"
    )


def render_vehicle_feedback(metadata: Mapping[str, Any]) -> str:
    labels = {
        "USER_REPORTED_PASS": "用户反馈通过（未独立复现）",
        "USER_REPORTED_FAIL": "用户反馈失败",
        "USER_REPORTED_ISSUE": "用户反馈问题",
        "NOT_TESTED": "NOT_TESTED",
        "PASS": "PASS",
        "FAIL": "FAIL",
        "BLOCKED": "BLOCKED",
    }
    lines = ["| 功能 | 近期实车反馈 | 证据说明 |", "| --- | --- | --- |"]
    for item in metadata.get("vehicleFeedback", []):
        detail = str(item["detailZh"]).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {item['labelZh']} | {labels[item['status']]} | {detail} |")
    lines.append("")
    lines.append("以上是用户反馈，不等于维护者验证；测试 APK 版本和连接模式未记录的结果不会外推到全系车型。")
    return "\n".join(lines)


def render_english_vehicle_feedback(metadata: Mapping[str, Any]) -> str:
    labels = {
        "USER_REPORTED_PASS": "User reported pass (not independently reproduced)",
        "USER_REPORTED_FAIL": "User reported fail",
        "USER_REPORTED_ISSUE": "User reported issue",
        "NOT_TESTED": "NOT_TESTED",
        "PASS": "PASS",
        "FAIL": "FAIL",
        "BLOCKED": "BLOCKED",
    }
    lines = ["| Feature | Reported status | Evidence note |", "| --- | --- | --- |"]
    for item in metadata.get("vehicleFeedback", []):
        detail = str(item["detailEn"]).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {item['labelEn']} | {labels[item['status']]} | {detail} |")
    lines.append("")
    lines.append("The tested APK version is not recorded for this report; do not infer full-model or connection-mode compatibility.")
    return "\n".join(lines)


def render_downloads(records: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any], ledger: Mapping[str, Any]) -> str:
    latest = next((item for item in records if item.get("prerelease") is not True), None)
    lines: list[str] = []
    if latest and latest.get("verifiedApk"):
        apk = latest["verifiedApk"]
        lines.append(
            f"- **最新正式 APK：** [{apk['name']}]({apk['url']})；版本 `{apk['versionName']}` / "
            f"versionCode `{apk['versionCode']}`，GitHub 资产 SHA-256 `{apk['sha256']}`。"
        )
        lines.append(f"- **Release 页面：** [{latest['tag']}]({latest['htmlUrl']})。")
    elif latest:
        lines.append(f"- **最新正式 Release：** [{latest['tag']}]({latest['htmlUrl']})；APK 未通过验证记录核对，不提供直链。")
    else:
        lines.append("- 当前没有已发布的正式 Release APK。")
    candidate = metadata["candidate"]
    current = ledger["current"]
    candidate_tag = f"v{candidate['versionName']}"
    candidate_release = next((record for record in records if record.get("tag") == candidate_tag), None)
    if candidate_release:
        channel = "预发布" if candidate_release.get("prerelease") else "正式版"
        proof = candidate_release.get("apkVerificationStatus", "NOT_VERIFIED")
        lines.append(
            f"- **候选台账版本 v{candidate['versionName']} 已在 GitHub 发布（{channel}）：** "
            f"APK 验证状态 `{proof}`；未通过验证记录时不提供 APK 直链。"
        )
        if candidate_release.get("releaseNoteStateConflict"):
            lines.append("- **发布元数据冲突：** GitHub 状态与人工 Release 正文的预发布措辞不一致；正文保持原样。")
    else:
        lines.append(
            f"- **本地候选：** v{candidate['versionName']} / versionCode {current['versionCode']}，尚未公开发布，不提供下载链接。"
        )
    lines.append("- 预发布及历史附件仅在各自 Release 页面标示，不代表当前正式推荐版本。")
    return "\n".join(lines)


def render_english_releases(records: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any], ledger: Mapping[str, Any]) -> str:
    latest = next((record for record in records if record.get("prerelease") is not True), None)
    if latest is None:
        summary = "No formal GitHub Release is currently published."
    else:
        verified = latest.get("verifiedApk")
        if verified:
            summary = (
                f"Latest formal Release: [{latest['tag']}]({latest['htmlUrl']}) ({latest['publishedDate']}); "
                f"[download APK]({verified['url']}) — package/version metadata, pinned signer, and uploaded asset digest verified."
            )
        else:
            summary = f"Latest formal Release: [{latest['tag']}]({latest['htmlUrl']}); no verified APK link is available."
    candidate = metadata["candidate"]
    current = ledger["current"]
    candidate_release = next((record for record in records if record.get("tag") == f"v{candidate['versionName']}"), None)
    if candidate_release:
        channel = "pre-release" if candidate_release.get("prerelease") else "formal Release"
        candidate_line = (
            f"Ledger candidate `v{candidate['versionName']}` / code `{current['versionCode']}` is already published "
            f"by GitHub as a {channel}; APK proof status is `{candidate_release.get('apkVerificationStatus', 'NOT_VERIFIED')}`."
        )
        if candidate_release.get("releaseNoteStateConflict"):
            candidate_line += " GitHub state conflicts with pre-release wording in the hand-written notes; the notes are preserved."
    else:
        candidate_line = (
            f"Local candidate: `v{candidate['versionName']}` / versionCode `{current['versionCode']}`; "
            "it has no public tag or Release and no public download URL."
        )
    return (
        f"{summary}\n\n"
        + (
            "Release metadata conflict: GitHub marks the latest item as formal, but its hand-written notes still describe a pre-release; the notes are preserved.\n\n"
            if latest and latest.get("releaseNoteStateConflict")
            else ""
        )
        +
        f"{candidate_line}\n\n"
        "Vehicle notes below are user-reported only; no unverified feature is presented as independently tested."
    )


def render_english_downloads(records: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any], ledger: Mapping[str, Any]) -> str:
    latest = next((record for record in records if record.get("prerelease") is not True), None)
    if latest and latest.get("verifiedApk"):
        apk = latest["verifiedApk"]
        line = (
            f"Download the [latest formal APK]({apk['url']}) (`{apk['versionName']}`, code `{apk['versionCode']}`; "
            f"SHA-256 `{apk['sha256']}`) or view the [{latest['tag']} Release]({latest['htmlUrl']})."
        )
    elif latest:
        line = f"See the [latest formal Release]({latest['htmlUrl']}); no APK is linked until its verification record matches."
    else:
        line = "No formal Release APK is currently available."
    current = ledger["current"]
    candidate = metadata["candidate"]
    candidate_release = next((record for record in records if record.get("tag") == f"v{candidate['versionName']}"), None)
    if candidate_release:
        channel = "pre-release" if candidate_release.get("prerelease") else "formal Release"
        state = f"Ledger candidate `v{candidate['versionName']}` / code `{current['versionCode']}` is already published as a {channel}."
        if candidate_release.get("releaseNoteStateConflict"):
            state += " Its hand-written notes conflict with GitHub channel metadata; the notes are preserved."
    else:
        state = f"Local candidate `v{candidate['versionName']}` / code `{current['versionCode']}` is not public."
    return f"{line} {state}"


def render_changelog(records: Sequence[Mapping[str, Any]], metadata: Mapping[str, Any], ledger: Mapping[str, Any]) -> str:
    lines = ["# CarPaly release history (automatically synchronized)", ""]
    latest = next((record for record in records if record.get("prerelease") is not True), None)
    if latest:
        verified = latest.get("verifiedApk")
        evidence = (
            f"APK `{verified['name']}` matched the GitHub digest, application id, version, and pinned signer."
            if verified
            else f"APK metadata proof: `{latest.get('apkVerificationStatus', 'NOT_VERIFIED')}`."
        )
        lines.append(f"Latest formal Release: [{latest['tag']}]({latest['htmlUrl']}) ({latest['publishedDate']}). {evidence}")
        if latest.get("releaseNoteStateConflict"):
            lines.append("Release state wording conflict: GitHub marks this as formal while the hand-written notes still say pre-release; original notes are preserved.")
    else:
        lines.append("No published formal Release is currently listed by GitHub.")
    lines.extend(["", "## Published Releases", "", "| Tag | Channel | Published | APK assets | Source commit |", "| --- | --- | --- | --- | --- |"])
    for record in list(records)[:10]:
        channel = "Pre-release" if record.get("prerelease") else "Formal"
        apk_names = ", ".join(asset["name"] for asset in record.get("apkAssets", [])) or "none"
        commit = record.get("tagSha")
        source = f"`{commit}`" if commit else "unknown"
        lines.append(
            f"| [{record['tag']}]({record['htmlUrl']}) | {channel} | {record['publishedDate']} | `{apk_names}` | {source} |"
        )
    if not records:
        lines.append("| — | — | — | none | — |")
    current = ledger["current"]
    candidate = metadata["candidate"]
    candidate = metadata["candidate"]
    current = ledger["current"]
    candidate_release = next((record for record in records if record.get("tag") == f"v{candidate['versionName']}"), None)
    if candidate_release:
        section_title = "## Recorded Candidate Allocation (GitHub Release Exists)"
        channel = "Pre-release" if candidate_release.get("prerelease") else "Formal Release"
        section_body = (
            f"`v{candidate['versionName']}` / versionCode `{current['versionCode']}` — GitHub reports a published {channel}; "
            f"APK verification status: `{candidate_release.get('apkVerificationStatus', 'NOT_VERIFIED')}`."
        )
        if candidate_release.get("releaseNoteStateConflict"):
            section_body += " Release notes contain conflicting pre-release wording and were not changed."
    else:
        section_title = "## Local Candidate (Not Published)"
        section_body = (
            f"`v{candidate['versionName']}` / versionCode `{current['versionCode']}` — local-only metadata; "
            "no GitHub tag, Release, or download link."
        )
    lines.extend(
        [
            "",
            section_title,
            "",
            section_body,
            candidate["summaryZh"] if candidate_release is None else "Vehicle validation remains separate from publication status; do not infer feature validation from the Release.",
            "",
            "Vehicle validation is separate from software release status. See the root README; user feedback is labeled and unverified features remain NOT_TESTED.",
        ]
    )
    return "\n".join(lines)


def render_release_notes_managed_block(record: Mapping[str, Any]) -> str:
    verified = record.get("verifiedApk")
    if verified:
        build = (
            f"- APK verification record: PASS (`{verified['versionName']}` / code `{verified['versionCode']}`, "
            f"SHA-256 `{verified['sha256']}`, signer `{verified['signerSha256']}`)."
        )
    else:
        build = f"- APK verification record: `{record.get('apkVerificationStatus', 'NOT_VERIFIED')}`."
    channel = "pre-release" if record.get("prerelease") else "formal Release"
    source = record.get("tagSha")
    source_line = f"- Tag commit: `{source}`." if source else "- Tag commit: not available from the current GitHub tag listing."
    return "\n".join(
        [
            "## Machine-managed publication facts",
            "",
            f"- GitHub channel: {channel}; published {record['publishedDate']}.",
            source_line,
            build,
            "- Vehicle/CarPlay functions not listed as independently verified in this block remain NOT_TESTED unless separately evidenced.",
        ]
    )


def _replace_if_managed(body: str, marker: str, rendered: str) -> tuple[str, str]:
    start = f"<!-- {marker}:START -->"
    end = f"<!-- {marker}:END -->"
    if start not in body and end not in body:
        return body, "UNMANAGED_PRESERVED"
    return replace_marker_region(body, marker, rendered), "MANAGED"


def release_note_state_conflict(release: Mapping[str, Any]) -> bool:
    """Detect the common stable-vs-pre-release wording conflict without editing prose."""
    if release.get("prerelease") is True:
        return False
    body = str(release.get("body") or "")
    return bool(re.search(r"(?i)(?:发布类型\s*[：:]?\s*[^\n]{0,30}预发布|预发布测试版|\bpre-release\b|\bprerelease\b)", body))


class GitHubApiError(SyncError):
    def __init__(self, status: int, operation: str) -> None:
        self.status = status
        self.operation = operation
        super().__init__(f"GitHub API {operation} failed with HTTP {status}; response body was not logged.")


class GitHubClient:
    """Small standard-library REST client with injectable transport for tests."""

    def __init__(
        self,
        repository: str,
        token: str | None = None,
        *,
        transport: Callable[[urllib.request.Request, int], Any] | None = None,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise SyncError("repository must be owner/name")
        self.repository = repository
        self.token = token
        self.transport = transport or (
            lambda request, timeout: urllib.request.urlopen(request, timeout=timeout)
        )

    def request(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> Any:
        if not path.startswith("/") or ".." in path.split("/"):
            raise SyncError("GitHub API path is not a safe relative API path")
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(API_ROOT + path, data=data, headers=headers, method=method)
        operation = f"{method} {path.split('?')[0]}"
        try:
            with self.transport(request, TIMEOUT_SECONDS) as response:
                raw = response.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise GitHubApiError(error.code, operation) from None
        except urllib.error.URLError:
            raise SyncError(f"GitHub API {operation} timed out or could not connect; no local files were changed.") from None
        except TimeoutError:
            raise SyncError(f"GitHub API {operation} timed out; no local files were changed.") from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise SyncError(f"GitHub API {operation} returned invalid JSON; no local files were changed.") from None

    def list_releases(self) -> list[dict[str, Any]]:
        result = self.request("GET", f"/repos/{self.repository}/releases?per_page={MAX_GITHUB_PAGE_COUNT}")
        if not isinstance(result, list):
            raise SyncError("GitHub Releases endpoint returned an unexpected response")
        return [item for item in result if isinstance(item, dict)]

    def list_tags(self) -> list[dict[str, Any]]:
        result = self.request("GET", f"/repos/{self.repository}/tags?per_page={MAX_GITHUB_PAGE_COUNT}")
        if not isinstance(result, list):
            raise SyncError("GitHub tags endpoint returned an unexpected response")
        return [item for item in result if isinstance(item, dict)]

    def get_repo(self) -> dict[str, Any]:
        result = self.request("GET", f"/repos/{self.repository}")
        if not isinstance(result, dict):
            raise SyncError("GitHub repository endpoint returned an unexpected response")
        return result


def download_small_json(url: str, *, opener: Callable[..., Any] = urllib.request.urlopen) -> Mapping[str, Any] | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        return None
    request = urllib.request.Request(url, headers={"Accept": "application/octet-stream", "User-Agent": USER_AGENT})
    try:
        with opener(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_VERIFICATION_JSON_BYTES + 1)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None
    if len(raw) > MAX_VERIFICATION_JSON_BYTES:
        return None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, Mapping) else None


def fetch_verifications(
    releases: Sequence[Mapping[str, Any]], repository: str,
    downloader: Callable[[str], Mapping[str, Any] | None] = download_small_json,
) -> dict[str, Mapping[str, Any] | None]:
    results: dict[str, Mapping[str, Any] | None] = {}
    for release in public_releases(releases):
        tag = str(release.get("tag_name", ""))
        asset = next(
            (
                item
                for item in release.get("assets", [])
                if isinstance(item, Mapping) and str(item.get("name", "")).endswith(".apk.verification.json")
            ),
            None,
        )
        url = safe_asset_url(repository, tag, asset) if asset else None
        results[tag] = downloader(url) if url else None
    return results


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SyncError(f"Could not load {path.as_posix()}: {error}") from error
    if not isinstance(value, dict):
        raise SyncError(f"Expected a JSON object in {path.as_posix()}")
    return value


def render_blocks(
    *, metadata: Mapping[str, Any], ledger: Mapping[str, Any], releases: Sequence[Mapping[str, Any]],
    tags: Sequence[Mapping[str, Any]], verifications: Mapping[str, Mapping[str, Any] | None],
) -> dict[str, str]:
    repository = str(metadata["repository"]["slug"])
    records = _released_records(releases, tags, repository, ledger, verifications)
    released_tags = {record["tag"] for record in records}
    known_tags = {str(item.get("name", "")) for item in tags}
    markers = metadata["managedMarkers"]
    return {
        markers["readmeReleases"]: render_release_summary(records),
        markers["readmeCandidate"]: render_candidate(metadata, ledger, released_tags, known_tags, records),
        markers["readmeVehicleFeedback"]: render_vehicle_feedback(metadata),
        markers["readmeDownloads"]: render_downloads(records, metadata, ledger),
        markers["readmeEnglishReleases"]: render_english_releases(records, metadata, ledger),
        markers["readmeEnglishVehicleFeedback"]: render_english_vehicle_feedback(metadata),
        markers["readmeEnglishDownloads"]: render_english_downloads(records, metadata, ledger),
        markers["changelog"]: render_changelog(records, metadata, ledger),
        # Kept in the set only for future Release-note templates; never written into README/CHANGELOG.
        markers["releaseNotes"]: "",
    }


def prepare_document_updates(
    root: Path, metadata: Mapping[str, Any], blocks: Mapping[str, str]
) -> dict[Path, str]:
    marker_owners = {
        "README.md": [
            metadata["managedMarkers"]["readmeReleases"],
            metadata["managedMarkers"]["readmeCandidate"],
            metadata["managedMarkers"]["readmeVehicleFeedback"],
            metadata["managedMarkers"]["readmeDownloads"],
            metadata["managedMarkers"]["readmeEnglishReleases"],
            metadata["managedMarkers"]["readmeEnglishVehicleFeedback"],
            metadata["managedMarkers"]["readmeEnglishDownloads"],
        ],
        "CHANGELOG.md": [metadata["managedMarkers"]["changelog"]],
    }
    updates: dict[Path, str] = {}
    for relative, markers in marker_owners.items():
        path = root / relative
        try:
            original = path.read_text(encoding="utf-8")
        except OSError as error:
            raise SyncError(f"Cannot read {relative}: {error}") from error
        updated = original
        for marker in markers:
            if marker not in blocks:
                raise SyncError(f"No rendered data is available for managed marker {marker}")
            updated = replace_marker_region(updated, marker, blocks[marker])
        if updated != original:
            updates[path] = updated
    return updates


def write_updates(updates: Mapping[Path, str]) -> None:
    for path, updated in updates.items():
        path.write_text(updated, encoding="utf-8", newline="\n")


def update_release_notes(
    client: GitHubClient, releases: Sequence[Mapping[str, Any]], records: Mapping[str, Mapping[str, Any]], marker: str
) -> list[str]:
    statuses: list[str] = []
    for release in public_releases(releases):
        body = str(release.get("body") or "")
        try:
            updated, status = _replace_if_managed(
                body, marker, render_release_notes_managed_block(records[str(release["tag_name"])])
            )
        except (SyncError, KeyError) as error:
            statuses.append(f"{release.get('tag_name')}: BLOCKED ({error})")
            continue
        if status == "UNMANAGED_PRESERVED":
            suffix = "_STATUS_CONFLICT" if release_note_state_conflict(release) else ""
            statuses.append(f"{release.get('tag_name')}: UNMANAGED_PRESERVED{suffix}")
            continue
        if updated == body:
            statuses.append(f"{release.get('tag_name')}: IN_SYNC")
            continue
        client.request(
            "PATCH",
            f"/repos/{client.repository}/releases/{release['id']}",
            {"body": updated},
        )
        statuses.append(f"{release.get('tag_name')}: UPDATED")
    return statuses


def preview_release_note_updates(
    releases: Sequence[Mapping[str, Any]],
    records: Mapping[str, Mapping[str, Any]],
    marker: str,
) -> list[str]:
    """Report managed-note changes without calling a write endpoint."""
    statuses: list[str] = []
    for release in public_releases(releases):
        tag = str(release.get("tag_name", ""))
        body = str(release.get("body") or "")
        try:
            updated, status = _replace_if_managed(body, marker, render_release_notes_managed_block(records[tag]))
        except (SyncError, KeyError) as error:
            statuses.append(f"{tag}: BLOCKED ({error})")
            continue
        if status == "UNMANAGED_PRESERVED":
            suffix = "_STATUS_CONFLICT" if release_note_state_conflict(release) else ""
            statuses.append(f"{tag}: UNMANAGED_PRESERVED{suffix}")
        elif updated == body:
            statuses.append(f"{tag}: IN_SYNC")
        else:
            statuses.append(f"{tag}: WOULD_UPDATE")
    return statuses


def sync_repository_description(
    read_client: GitHubClient, desired: str, admin_token: str | None, *, allow_write: bool
) -> str:
    repo = read_client.get_repo()
    current = repo.get("description") or ""
    if current == desired:
        return "IN_SYNC"
    if not allow_write:
        return "PROPOSED_ONLY"
    if not admin_token:
        return "BLOCKED_ADMIN_TOKEN_MISSING"
    write_client = GitHubClient(read_client.repository, admin_token)
    write_client.request("PATCH", f"/repos/{read_client.repository}", {"description": desired})
    return "UPDATED_DESCRIPTION_ONLY"


def ensure_docs_pull_request(
    client: GitHubClient, branch: str, base: str, title: str, body: str
) -> str:
    owner = client.repository.split("/", 1)[0]
    query = urllib.parse.urlencode({"state": "open", "head": f"{owner}:{branch}", "base": base})
    result = client.request("GET", f"/repos/{client.repository}/pulls?{query}")
    if not isinstance(result, list):
        raise SyncError("GitHub Pull Request query returned an unexpected response")
    if result:
        pull = result[0]
        number = pull.get("number")
        if pull.get("title") == title and pull.get("body") == body:
            return f"UNCHANGED #{number}"
        client.request(
            "PATCH", f"/repos/{client.repository}/pulls/{number}", {"title": title, "body": body}
        )
        return f"UPDATED #{number}"
    pull = client.request(
        "POST", f"/repos/{client.repository}/pulls", {"head": branch, "base": base, "title": title, "body": body}
    )
    return f"CREATED #{pull.get('number')}"


def _diff_for_updates(updates: Mapping[Path, str], root: Path) -> str:
    chunks: list[str] = []
    for path, updated in updates.items():
        original = path.read_text(encoding="utf-8")
        chunks.extend(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile=f"a/{path.relative_to(root).as_posix()}",
                tofile=f"b/{path.relative_to(root).as_posix()}",
            )
        )
    return "".join(chunks)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--repository", default="Qwy20040320/carpaly")
    parser.add_argument("--write", action="store_true", help="Write only marker-delimited README/CHANGELOG blocks")
    note_group = parser.add_mutually_exclusive_group()
    note_group.add_argument("--sync-release-notes", action="store_true", help="Update only GitHub Release bodies with valid markers")
    note_group.add_argument("--preview-release-notes", action="store_true", help="Preview managed Release-note updates without writing")
    parser.add_argument("--sync-about", action="store_true", help="Compare About description and update only when a scoped admin token is configured")
    parser.add_argument("--open-pr", action="store_true", help="Create or update an automation PR after files are committed/pushed")
    parser.add_argument("--docs-branch", default="automation/release-docs-sync")
    parser.add_argument("--base-branch", default="main")
    parser.add_argument("--pr-title", default="docs: sync README and release history")
    args = parser.parse_args(argv)

    errors = validate_metadata(args.root)
    if errors:
        print("RELEASE_METADATA_STATUS=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    metadata = _load_json(args.root / METADATA_PATH)
    ledger = _load_json(args.root / LEDGER_PATH)
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    client = GitHubClient(args.repository, token)
    try:
        releases = client.list_releases()
        tags = client.list_tags()
        verifications = fetch_verifications(releases, args.repository)
        blocks = render_blocks(
            metadata=metadata, ledger=ledger, releases=releases, tags=tags, verifications=verifications
        )
        updates = prepare_document_updates(args.root, metadata, blocks)
        print(f"PUBLISHED_RELEASE_COUNT={len(public_releases(releases))}")
        formal = latest_formal_release(releases)
        print(f"LATEST_FORMAL_RELEASE={formal.get('tag_name') if formal else 'NONE'}")
        candidate_tag = f"v{metadata['candidate']['versionName']}"
        known_tags = {str(tag.get("name", "")) for tag in tags}
        if candidate_tag in known_tags and not any(item.get("tag_name") == candidate_tag for item in public_releases(releases)):
            print(f"CANDIDATE_TAG_STATUS=TAG_EXISTS_WITHOUT_PUBLISHED_RELEASE ({candidate_tag})")
        else:
            print(f"CANDIDATE_TAG_STATUS={'PUBLISHED' if candidate_tag in known_tags else 'LOCAL_ONLY'}")

        if args.sync_about:
            about = sync_repository_description(
                client,
                str(metadata["repository"]["description"]),
                os.environ.get("CARPALY_REPO_ADMIN_TOKEN"),
                allow_write=True,
            )
            print(f"REPOSITORY_ABOUT_STATUS={about}")
        else:
            print("REPOSITORY_ABOUT_STATUS=READ_ONLY_NOT_REQUESTED")

        if args.write:
            write_updates(updates)
            print(f"LOCAL_DOC_SYNC_STATUS=UPDATED ({', '.join(path.relative_to(args.root).as_posix() for path in updates) or 'already in sync'})")
        elif updates:
            print("LOCAL_DOC_SYNC_STATUS=DIFF_AVAILABLE")
            print(_diff_for_updates(updates, args.root))
        else:
            print("LOCAL_DOC_SYNC_STATUS=PASS")

        note_statuses: list[str] = []
        if args.sync_release_notes or args.preview_release_notes:
            records = {
                record["tag"]: record
                for record in _released_records(releases, tags, args.repository, ledger, verifications)
            }
            if args.preview_release_notes:
                note_statuses = preview_release_note_updates(
                    releases, records, str(metadata["managedMarkers"]["releaseNotes"])
                )
            else:
                note_statuses = update_release_notes(
                    client, releases, records, str(metadata["managedMarkers"]["releaseNotes"])
                )
            print("RELEASE_NOTES_STATUS=" + ("; ".join(note_statuses) if note_statuses else "NO_RELEASES"))
        else:
            print("RELEASE_NOTES_STATUS=READ_ONLY_NOT_REQUESTED")

        if args.open_pr:
            body = (
                "Synchronizes only managed README/CHANGELOG blocks from public GitHub Release metadata and the local version ledger.\n\n"
                "No APK was built; this workflow does not access Release keystore or MFi authentication secrets. "
                "No branch protection is bypassed, and this PR is not auto-merged."
            )
            result = ensure_docs_pull_request(
                client, args.docs_branch, args.base_branch, args.pr_title, body
            )
            print(f"DOCS_PULL_REQUEST_STATUS={result}")
        return 0
    except (SyncError, MetadataError) as error:
        print(f"RELEASE_DOC_SYNC_STATUS=BLOCKED ({error})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
