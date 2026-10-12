#!/usr/bin/env python3
"""Build bilingual CarPaly Pages from published GitHub Releases and their APK proof records."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__:
    from . import sync_release_docs as release_docs
else:
    import sync_release_docs as release_docs


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
CONTENT_PATH = SITE / "content.json"
METADATA_PATH = ROOT / "config/release-documentation.json"
LEDGER_PATH = ROOT / "config/android-version-ledger.json"
USER_AGENT = "CarPaly-Pages-builder"
API_ROOT = "https://api.github.com"
MAX_API_BYTES = 8 * 1024 * 1024

TEXT: dict[str, dict[str, str]] = {
    "nav_home": {"en": "Home", "zh-Hans": "首页"},
    "nav_downloads": {"en": "Downloads", "zh-Hans": "下载"},
    "nav_compatibility": {"en": "Compatibility", "zh-Hans": "兼容性"},
    "nav_guide": {"en": "Install & update", "zh-Hans": "安装与更新"},
    "nav_history": {"en": "Version history", "zh-Hans": "版本历史"},
    "stable": {"en": "Latest stable", "zh-Hans": "最新稳定版"},
    "beta": {"en": "Latest beta", "zh-Hans": "最新测试版"},
    "not_available": {"en": "No verified public APK is available for this channel yet.",
                      "zh-Hans": "此通道目前没有经过发布校验的公开 APK。"},
    "download_apk": {"en": "Download APK", "zh-Hans": "下载 APK"},
    "view_release": {"en": "Release notes", "zh-Hans": "版本说明"},
    "project": {"en": "Project", "zh-Hans": "项目"},
    "compatibility": {"en": "Compatibility status", "zh-Hans": "兼容性状态"},
    "guide": {"en": "Install and update", "zh-Hans": "安装与更新"},
    "history": {"en": "Published version history", "zh-Hans": "已发布版本历史"},
    "features": {"en": "Project scope", "zh-Hans": "项目范围"},
    "not_tested": {"en": "NOT_TESTED", "zh-Hans": "未实车验证"},
    "verified": {"en": "Release APK verified", "zh-Hans": "发布 APK 已校验"},
    "not_verified": {"en": "No verified APK link", "zh-Hans": "无已校验 APK 下载链接"},
    "date": {"en": "Published", "zh-Hans": "发布日期"},
    "size": {"en": "APK size", "zh-Hans": "APK 大小"},
    "sha256": {"en": "APK SHA-256", "zh-Hans": "APK SHA-256"},
    "package": {"en": "Package", "zh-Hans": "应用包名"},
    "source": {"en": "GitHub repository", "zh-Hans": "GitHub 源码仓库"},
    "issues": {"en": "Report an issue", "zh-Hans": "反馈问题"},
    "upstream": {"en": "Upstream DiPlay project", "zh-Hans": "DiPlay 上游项目"},
    "install_steps": {"en": [
        "Download a Release APK from this site or the linked GitHub Release.",
        "Install it on the Android head unit, not on the iPhone. Android may ask you to allow this app to install packages.",
        "For an in-place update, keep the same package and signing identity. Do not uninstall the existing app or clear its data to work around a signature error.",
        "Android always shows its package installer and asks the user to confirm. CarPaly does not silently install or roll back packages.",
        "Only start installation when safely parked. Current firmware does not expose a validated stationary-state signal to CarPaly, so automatic installer launch is disabled.",
    ], "zh-Hans": [
        "从本网站或所链接的 GitHub Release 下载正式发布 APK。",
        "将 APK 安装到 Android 车机，而不是 iPhone。Android 可能要求允许 CarPaly 安装应用。",
        "覆盖更新必须保持相同包名与签名身份。签名错误时，不要通过卸载旧版或清除数据绕过。",
        "Android 始终显示系统安装界面并要求用户确认；CarPaly 不静默安装，也不承诺静默回滚。",
        "只在安全驻车后安装。当前固件尚无经过验证的车辆静止状态信号，因此 CarPaly 禁止自动跳转到安装器。",
    ]},
    "questions": {"en": [
        ("Can every Xingyue L use this?", "No. Year/trim profiles are candidates; real vehicle compatibility is not established by source code or unit tests."),
        ("Is a preview APK a stable release?", "No. Beta and stable feeds are separate. Drafts, unverified assets, and local candidates are never downloadable OTA versions."),
        ("Why can update check be unavailable?", "The OTA feed requires a signed manifest and an app-pinned verification key. Until that key is provisioned and a signed feed is deployed, the app fails closed."),
        ("Does update checking interrupt CarPlay?", "Checks run on a background thread and do not request audio focus. Downloading is user-started; installer launch is blocked without trusted parked-state evidence and while a CarPlay session is active."),
    ], "zh-Hans": [
        ("所有星越 L 都兼容吗？", "不能这样保证。年款/配置文件只是软件候选；源码和单元测试不能代替实车验证。"),
        ("测试版就是稳定版吗？", "不是。Beta 与 Stable 通道分离；草稿、未校验资产和本地候选不会进入 OTA 下载。"),
        ("为什么更新检查可能不可用？", "OTA 必须有经过签名的清单及应用内固定验签公钥。密钥与签名清单尚未配置前，应用会拒绝更新。"),
        ("检查更新会中断 CarPlay 吗？", "检查在后台线程运行且不申请音频焦点。下载须由用户发起；没有可信驻车证据或 CarPlay 会话仍在运行时，不会打开安装器。"),
    ]},
}

VEHICLES = [
    ("星越 L 2021 / Xingyue L 2021", "KX11_2021", "NOT_TESTED"),
    ("星越 L 2022 / Xingyue L 2022", "KX11_2022", "NOT_TESTED"),
    ("星越 L 2023 / Xingyue L 2023", "KX11_2023", "NOT_TESTED"),
    ("星越 L 2024 / Xingyue L 2024", "KX11_2024", "NOT_TESTED"),
    ("星越 L 2024 天际版 / 2024 Tianji", "KX11_2024_TIANJI", "NOT_TESTED"),
    ("星越 L 2025 / Xingyue L 2025", "KX11_2025", "NOT_TESTED"),
    ("星越 L 2026 / Xingyue L 2026", "KX11_2026", "NOT_TESTED"),
    ("KX11 Generic", "KX11_GENERIC", "NOT_TESTED"),
]


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read {path}: {exc}") from exc


def github_json(url: str) -> Any:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    token = os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read(MAX_API_BYTES + 1)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise ValueError(f"GitHub API request failed for {urllib.parse.urlsplit(url).path}") from exc
    if len(raw) > MAX_API_BYTES:
        raise ValueError("GitHub API response exceeds the configured size limit")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("GitHub API returned malformed JSON") from exc


def fetch_releases(repository: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    url = f"{API_ROOT}/repos/{repository}/releases?per_page=100"
    for _ in range(10):
        page = github_json(url)
        if not isinstance(page, list):
            raise ValueError("GitHub Releases API response is not an array")
        result.extend(item for item in page if isinstance(item, dict))
        if len(page) < 100:
            return result
        url = f"{API_ROOT}/repos/{repository}/releases?per_page=100&page={len(result) // 100 + 1}"
    raise ValueError("Release history exceeds the safe pagination limit")


def require_readable_verification_assets(releases: Sequence[Mapping[str, Any]],
                                         verifications: Mapping[str, Any]) -> None:
    for release in release_docs.public_releases(releases):
        tag = str(release.get("tag_name", ""))
        assets = release.get("assets", [])
        has_proof_asset = isinstance(assets, list) and any(
            isinstance(asset, Mapping) and str(asset.get("name", "")).endswith(".apk.verification.json")
            for asset in assets
        )
        if has_proof_asset and verifications.get(tag) is None:
            raise ValueError(f"Release verification evidence could not be read for {tag}; preserving the last Pages deployment")


def version_code(record: Mapping[str, Any]) -> int:
    apk = record.get("verifiedApk")
    return int(apk.get("versionCode", 0)) if isinstance(apk, Mapping) else 0


def select_release(records: Sequence[Mapping[str, Any]], prerelease: bool) -> Mapping[str, Any] | None:
    eligible = [
        item for item in records
        if item.get("prerelease") is prerelease
        and item.get("draft") is not True
        and item.get("apkVerificationStatus") == "PASS"
        and isinstance(item.get("verifiedApk"), Mapping)
    ]
    return max(eligible, key=version_code, default=None)


def display_size(value: Any) -> str:
    try:
        size = int(value)
    except (TypeError, ValueError):
        return "—"
    return f"{size / (1024 * 1024):.1f} MiB" if size > 0 else "—"


def e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def asset_summary(record: Mapping[str, Any], lang: str, repository: str) -> str:
    apk = record.get("verifiedApk")
    if not isinstance(apk, Mapping):
        return f'<span class="status unavailable">{e(TEXT["not_verified"][lang])}</span>'
    return (
        f'<a class="button" href="{e(apk["url"])}">{e(TEXT["download_apk"][lang])}</a>'
        f'<dl class="proof"><dt>{e(TEXT["date"][lang])}</dt><dd>{e(record.get("publishedDate", "—"))}</dd>'
        f'<dt>{e(TEXT["size"][lang])}</dt><dd>{e(display_size(apk.get("size")))}</dd>'
        f'<dt>{e(TEXT["package"][lang])}</dt><dd><code>com.shihab.diplay.hudtest</code></dd>'
        f'<dt>{e(TEXT["sha256"][lang])}</dt><dd><code>{e(apk.get("sha256", ""))}</code></dd></dl>'
    )


def release_card(record: Mapping[str, Any] | None, lang: str, title: str,
                 unavailable: str | None = None) -> str:
    if record is None:
        return f'<article class="card"><p class="eyebrow">{e(title)}</p><p>{e(unavailable or TEXT["not_available"][lang])}</p></article>'
    apk = record["verifiedApk"]
    warning = ""
    if record.get("releaseNoteStateConflict"):
        warning = (
            '<p class="warning">' +
            e("GitHub classifies this Release as stable, but its hand-written notes contain preview wording. "
              "The original notes are preserved for maintainer review." if lang == "en"
              else "GitHub 元数据将此版本标记为正式版，但人工说明仍含预发布措辞；原说明保持不变，等待维护者审核。")
            + "</p>"
        )
    return (
        f'<article class="card"><p class="eyebrow">{e(title)}</p><h2>{e(record.get("tag", ""))}</h2>'
        f'<p>{e(TEXT["verified"][lang])} · {e(record.get("publishedDate", "—"))}</p>'
        f'<p>{e(display_size(apk.get("size")))} · versionCode {e(apk.get("versionCode"))}</p>'
        f'{warning}{asset_summary(record, lang, "")}'
        f'<p><a href="{e(record.get("htmlUrl", ""))}">{e(TEXT["view_release"][lang])}</a></p></article>'
    )


def history_table(records: Sequence[Mapping[str, Any]], lang: str) -> str:
    rows = []
    for record in records:
        apk = record.get("verifiedApk")
        label = "Beta" if record.get("prerelease") else "Stable"
        download = (f'<a href="{e(apk["url"])}">{e(apk["name"])}</a>'
                    if isinstance(apk, Mapping) else e(TEXT["not_verified"][lang]))
        rows.append(
            "<tr>"
            f'<td><a href="{e(record.get("htmlUrl", ""))}">{e(record.get("tag", ""))}</a></td>'
            f"<td>{e(label)}</td><td>{e(record.get('publishedDate', '—'))}</td>"
            f"<td>{download}</td><td>{e(display_size(apk.get('size')) if isinstance(apk, Mapping) else '—')}</td>"
            "</tr>"
        )
    if not rows:
        rows.append(f'<tr><td colspan="5">{e(TEXT["not_available"][lang])}</td></tr>')
    return (
        f'<div class="table-scroll"><table><thead><tr><th>Tag</th><th>Channel</th>'
        f'<th>{e(TEXT["date"][lang])}</th><th>APK</th><th>{e(TEXT["size"][lang])}</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def compatibility_table(lang: str) -> str:
    heading = "Code profile" if lang == "en" else "代码配置"
    status = "Vehicle test" if lang == "en" else "实车状态"
    rows = "".join(
        f"<tr><td>{e(name)}</td><td><code>{e(profile)}</code></td>"
        f'<td><span class="status unavailable">{e(TEXT["not_tested"][lang])}</span></td></tr>'
        for name, profile, _ in VEHICLES
    )
    return f'<div class="table-scroll"><table><thead><tr><th>Vehicle</th><th>{heading}</th><th>{status}</th></tr></thead><tbody>{rows}</tbody></table></div>'


def nav_links(base: str, lang: str, route: str) -> str:
    entries = [
        ("", "nav_home"), ("downloads/", "nav_downloads"), ("compatibility/", "nav_compatibility"),
        ("guide/", "nav_guide"), ("history/", "nav_history"),
    ]
    prefix = "zh-Hans/" if lang == "zh-Hans" else ""
    return "".join(
        f'<a href="{e(base.rstrip("/") + "/" + prefix + suffix)}">{e(TEXT[key][lang])}</a>'
        for suffix, key in entries
    )


def page_url(base: str, lang: str, route: str) -> str:
    prefix = base + ("/zh-Hans" if lang == "zh-Hans" else "")
    return prefix + ("/" + route if route else "/")


def render_page(*, content: Mapping[str, Any], records: Sequence[Mapping[str, Any]],
                stable: Mapping[str, Any] | None, beta: Mapping[str, Any] | None,
                base: str, lang: str, route: str) -> str:
    is_zh = lang == "zh-Hans"
    title = content["name"] if not route else TEXT[{"downloads": "nav_downloads", "compatibility": "nav_compatibility",
                                                    "guide": "nav_guide", "history": "nav_history"}[route]][lang]
    common = (
        f'<header><a class="brand" href="{e(page_url(base, lang, ""))}"><span class="mark">C</span>'
        f'<span><strong>{e(content["name"])}</strong><small>{e(content["tagline"][lang])}</small></span></a>'
        f'<nav>{nav_links(base, lang, route)}</nav>'
        f'<div class="languages"><a href="{e(page_url(base, "en", route))}#content" lang="en">EN</a>'
        f'<a href="{e(page_url(base, "zh-Hans", route))}#content" lang="zh-Hans">简体中文</a></div></header>'
    )
    footer = (
        f'<footer><a href="{e(content["repository"])}">{e(TEXT["source"][lang])}</a>'
        f'<a href="{e(content["upstream"])}">{e(TEXT["upstream"][lang])}</a>'
        f'<a href="{e(content["issues"])}">{e(TEXT["issues"][lang])}</a>'
        f'<p>{e(content["scopeNotice"][lang])}</p><p>GPL-3.0 · © original DiPlay/xcertplay contributors as stated in the source notices.</p></footer>'
    )
    if route == "":
        content_html = (
            f'<section class="hero"><span class="eyebrow">ANDROID · CARPLAY · KX11</span>'
            f'<h1>{e(content["name"])}</h1><h2>{e(content["tagline"][lang])}</h2>'
            f'<p class="lead">{e(content["description"][lang])}</p>'
            f'<div class="actions"><a class="button" href="{e(page_url(base, lang, "downloads"))}#stable">{e(TEXT["stable"][lang])}</a>'
            f'<a class="button secondary" href="{e(content["repository"])}">GitHub</a></div>'
            f'<p class="warning">{e(content["scopeNotice"][lang])}</p></section>'
            f'<section id="stable"><h2>{e(TEXT["stable"][lang])}</h2>{release_card(stable, lang, TEXT["stable"][lang])}</section>'
            f'<section id="beta"><h2>{e(TEXT["beta"][lang])}</h2>{release_card(beta, lang, TEXT["beta"][lang])}</section>'
            f'<section><h2>{e(TEXT["features"][lang])}</h2>'
            f'<div class="grid"><article class="card"><h3>CarPlay</h3><p>{"有线/无线接收链路在源码中存在，仍需逐车型实测。" if is_zh else "Wired/wireless receiver code exists; validation remains device-specific."}</p>'
            f'<p>{e(TEXT["not_tested"][lang])}</p></article><article class="card"><h3>HUD / DIM / steering / fuel</h3>'
            f'<p>{"有接口研究线索，未达到可宣称实车支持的证据等级。" if is_zh else "Interface research exists; evidence is insufficient to claim in-vehicle support."}</p>'
            f'<p>{e(TEXT["not_tested"][lang])}</p></article></div></section>'
        )
    elif route == "downloads":
        content_html = (
            f'<section class="hero compact"><h1>{e(TEXT["nav_downloads"][lang])}</h1>'
            f'<p>{e("Only published Releases with a matching verification record receive an APK link." if not is_zh else "只有已发布且具有匹配验证记录的 Release 才显示 APK 下载链接。")}</p></section>'
            f'<section id="stable"><h2>{e(TEXT["stable"][lang])}</h2>{release_card(stable, lang, TEXT["stable"][lang])}</section>'
            f'<section id="beta"><h2>{e(TEXT["beta"][lang])}</h2>{release_card(beta, lang, TEXT["beta"][lang])}</section>'
            f'<section><h2>{e(TEXT["history"][lang])}</h2>{history_table(records, lang)}</section>'
        )
    elif route == "compatibility":
        content_html = (
            f'<section class="hero compact"><h1>{e(TEXT["compatibility"][lang])}</h1>'
            f'<p>{e("A profile or passing unit test is not proof of real vehicle compatibility." if not is_zh else "代码存在车型配置或单测通过，不等于已验证实车兼容。")}</p></section>'
            f'<section>{compatibility_table(lang)}</section>'
            f'<section class="card"><h2>{"功能状态 / Feature status"}</h2>'
            f'<ul><li>{"CarPlay: 代码实现，设备实测状态以实际反馈为准。" if is_zh else "CarPlay: implementation exists; use per-device test evidence."}</li>'
            f'<li>{"音乐、导航、Siri、麦克风：存在用户报告问题，未由维护者独立复测。" if is_zh else "Media, navigation, Siri and microphone: user reports exist; not independently reproduced."}</li>'
            f'<li>{"HUD、仪表、方向盘、燃油：NOT_TESTED。" if is_zh else "HUD, cluster, steering and fuel: NOT_TESTED."}</li></ul></section>'
        )
    elif route == "guide":
        steps = "".join(f"<li>{e(step)}</li>" for step in TEXT["install_steps"][lang])
        faq = "".join(f"<article class=\"card\"><h3>{e(question)}</h3><p>{e(answer)}</p></article>"
                      for question, answer in TEXT["questions"][lang])
        content_html = (
            f'<section class="hero compact"><h1>{e(TEXT["guide"][lang])}</h1>'
            f'<p>{"Android 7.1 (API 25)+; package install permission must be permitted by the head unit." if not is_zh else "要求 Android 7.1（API 25）以上，且车机允许安装 APK。"}</p></section>'
            f'<section class="card"><ol>{steps}</ol></section><section><h2>FAQ</h2><div class="grid">{faq}</div></section>'
            f'<section class="card"><h2>{"Update security" if not is_zh else "更新安全"}</h2>'
            f'<p>{e("The app checks a signed manifest using an app-pinned public key, then verifies the APK SHA-256, package, version and actual Android signing certificate. The OTA signing key is not bundled in the app." if not is_zh else "应用使用内置固定公钥验证签名清单，再验证 APK SHA-256、包名、版本和 Android 实际签名证书。OTA 清单私钥不会打包进应用。")}</p>'
            f'<p>{e("The production manifest trust key is not yet provisioned; OTA downloads therefore remain fail-closed." if not is_zh else "生产验签公钥尚未配置，OTA 下载当前保持 fail-closed。")}</p></section>'
        )
    else:
        content_html = f'<section class="hero compact"><h1>{e(TEXT["history"][lang])}</h1></section><section>{history_table(records, lang)}</section>'
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} · CarPaly</title><meta name="description" content="{e(content["description"][lang])}">
<meta name="theme-color" content="#101820"><link rel="stylesheet" href="{e(base)}/assets/site.css">
<link rel="canonical" href="{e(page_url(base, lang, route))}"></head>
<body><main>{common}<div id="content">{content_html}</div>{footer}</main>
<script>
document.querySelectorAll('.languages a').forEach(function(a) {{
  a.addEventListener('click', function() {{
    var target = new URL(a.href); target.search = location.search; target.hash = location.hash || '#content'; a.href = target.href;
  }});
}});
</script></body></html>
"""


def render_legacy_redirect(base: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="robots" content="noindex"><meta http-equiv="refresh" content="0;url=../">'
        f'<link rel="canonical" href="{e(base)}/"></head><body><a href="../">CarPaly</a>'
        '<script>location.replace("../"+location.search+location.hash)</script></body></html>'
    )


def generate_site(*, content: Mapping[str, Any], records: Sequence[Mapping[str, Any]],
                  output_dir: Path, base_url: str) -> dict[str, Any]:
    base = base_url.rstrip("/")
    stable = select_release(records, prerelease=False)
    beta = select_release(records, prerelease=True)
    state = {
        "schemaVersion": 1,
        "repository": str(content["repository"]),
        "generatedFrom": "public GitHub Releases API + matching APK verification assets",
        "stable": _release_json(stable),
        "beta": _release_json(beta),
        "publishedHistory": [_release_json(item) for item in records],
    }
    pages = ["", "downloads", "compatibility", "guide", "history"]
    # Render in memory before replacing any prior site files. API/config errors never publish partial data.
    rendered: dict[Path, str] = {}
    for lang in ("en", "zh-Hans"):
        for route in pages:
            page_path = Path(lang if lang == "zh-Hans" else "")
            if route:
                page_path = page_path / route
            file_path = output_dir / page_path / "index.html"
            rendered[file_path] = render_page(
                content=content, records=records, stable=stable, beta=beta,
                base=base, lang=lang, route=route,
            )
    for locale in ("ar", "es", "ru", "uk", "zh-Hant"):
        rendered[output_dir / locale / "index.html"] = render_legacy_redirect(base)
    rendered[output_dir / "data" / "releases.json"] = json.dumps(
        state, ensure_ascii=False, indent=2
    ) + "\n"
    for path, text in rendered.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)
    return state


def _release_json(record: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    verified_apk = record.get("verifiedApk")
    safe_apk = None
    if isinstance(verified_apk, Mapping):
        safe_apk = {
            "name": verified_apk.get("name"),
            "url": verified_apk.get("url"),
            "size": verified_apk.get("size"),
            "sha256": verified_apk.get("sha256"),
            "versionName": verified_apk.get("versionName"),
            "versionCode": verified_apk.get("versionCode"),
            "signerSha256": verified_apk.get("signerSha256"),
        }
    return {
        "tag": record.get("tag"),
        "title": record.get("title"),
        "publishedDate": record.get("publishedDate"),
        "prerelease": bool(record.get("prerelease")),
        "releaseUrl": record.get("htmlUrl"),
        "apkVerificationStatus": record.get("apkVerificationStatus"),
        "releaseNoteStateConflict": bool(record.get("releaseNoteStateConflict")),
        "apk": safe_apk,
    }


def write_release_snapshot(path: Path, repository: str, releases: Sequence[Mapping[str, Any]],
                           verifications: Mapping[str, Any]) -> None:
    """Atomically save the public Release/API evidence shared with the OTA signer in one workflow run."""
    snapshot = {
        "schemaVersion": 1,
        "repository": repository,
        "releases": list(releases),
        "verifications": dict(verifications),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n",
                         encoding="utf-8")
    os.replace(temporary, path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--releases-json", type=Path, help="offline release fixture; skips all network requests")
    parser.add_argument("--verifications-json", type=Path, help="offline per-tag verification records")
    parser.add_argument("--snapshot-out", type=Path,
                        help="write the exact Release and verification snapshot for the OTA signer")
    parser.add_argument("--output-dir", type=Path, default=SITE)
    parser.add_argument("--base-url", default="https://qwy20040320.github.io/carpaly")
    args = parser.parse_args(argv)
    try:
        content = read_json(CONTENT_PATH)
        metadata = read_json(METADATA_PATH)
        ledger = read_json(LEDGER_PATH)
        repository = str(metadata["repository"]["slug"])
        if args.releases_json:
            releases = read_json(args.releases_json)
            if not isinstance(releases, list) or not all(isinstance(item, dict) for item in releases):
                raise ValueError("Release fixture must be an array of objects")
            verifications = read_json(args.verifications_json) if args.verifications_json else {}
            if not isinstance(verifications, dict):
                raise ValueError("Verification fixture must be an object indexed by Release tag")
        else:
            releases = fetch_releases(repository)
            verifications = release_docs.fetch_verifications(releases, repository)
            require_readable_verification_assets(releases, verifications)
        if args.snapshot_out:
            write_release_snapshot(args.snapshot_out, repository, releases, verifications)
        records = release_docs._released_records(releases, [], repository, ledger, verifications)
        state = generate_site(content=content, records=records, output_dir=args.output_dir, base_url=args.base_url)
    except (ValueError, KeyError, TypeError, release_docs.SyncError) as exc:
        print(f"SITE_BUILD_STATUS=FAIL: {exc}", file=sys.stderr)
        return 2
    print(f"SITE_BUILD_STATUS=PASS")
    print(f"SITE_RELEASE_HISTORY_COUNT={len(state['publishedHistory'])}")
    print(f"SITE_STABLE_VERSION={state['stable']['tag'] if state['stable'] else 'NONE'}")
    print(f"SITE_BETA_VERSION={state['beta']['tag'] if state['beta'] else 'NONE'}")
    print("OTA_MANIFEST_STATUS=NOT_GENERATED_BY_SITE_BUILDER")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
