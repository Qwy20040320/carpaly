#!/usr/bin/env bash
set -euo pipefail

required=(GH_TOKEN GH_REPO RELEASE_TAG APK_PATH APK_NAME APK_SHA256 APK_SIZE APK_VERSION_CODE \
  SOURCE_ZIP_PATH SOURCE_ZIP_NAME SOURCE_ZIP_SHA256 SOURCE_ZIP_SIZE \
  SHA256SUMS_PATH SHA256SUMS_SHA256 SHA256SUMS_SIZE RUNNER_TEMP)
for variable in "${required[@]}"; do
  if ! printenv "$variable" >/dev/null; then
    echo "Required environment variable is missing: $variable" >&2
    exit 1
  fi
done

[[ "$RELEASE_TAG" =~ ^v1\.[0-9]+\.[0-9]+$ ]] || {
  echo "Authenticated CarPaly releases must use v1.x.y semantic-version tags." >&2
  exit 1
}
version="${RELEASE_TAG#v}"
canonical_apk="CarPaly-XingyueL${version}.apk"
canonical_source="${canonical_apk%.apk}-source.zip"
canonical_sums="SHA256SUMS.txt"
[[ "$APK_NAME" == "$canonical_apk" ]] || {
  echo "APK filename does not match the release tag." >&2
  exit 1
}
[[ "$(basename "$APK_PATH")" == "$canonical_apk" ]] || {
  echo "APK path does not have the canonical versioned filename." >&2
  exit 1
}
[[ "$SOURCE_ZIP_NAME" == "$canonical_source" && "$(basename "$SOURCE_ZIP_PATH")" == "$canonical_source" ]] || {
  echo "Source ZIP filename does not match the release tag." >&2
  exit 1
}
[[ "$(basename "$SHA256SUMS_PATH")" == "$canonical_sums" ]] || {
  echo "Checksum manifest must be named SHA256SUMS.txt." >&2
  exit 1
}
for digest in "$APK_SHA256" "$SOURCE_ZIP_SHA256" "$SHA256SUMS_SHA256"; do
  [[ "$digest" =~ ^[0-9a-f]{64}$ ]] || {
    echo "Release artifact SHA-256 values must be lowercase 64-digit digests." >&2
    exit 1
  }
done
[[ "$APK_VERSION_CODE" =~ ^[1-9][0-9]*$ ]] || {
  echo "APK_VERSION_CODE must be a positive integer." >&2
  exit 1
}
[[ -s "$APK_PATH" && -s "$SOURCE_ZIP_PATH" && -s "$SHA256SUMS_PATH" ]] || {
  echo "Verified APK, source ZIP, or checksum manifest is missing." >&2
  exit 1
}
[[ "$(stat -c '%s' "$APK_PATH")" == "$APK_SIZE" ]] || {
  echo "APK size differs from the verified build output." >&2
  exit 1
}
[[ "$(stat -c '%s' "$SOURCE_ZIP_PATH")" == "$SOURCE_ZIP_SIZE" ]] || {
  echo "Source ZIP size differs from the verified package output." >&2
  exit 1
}
[[ "$(stat -c '%s' "$SHA256SUMS_PATH")" == "$SHA256SUMS_SIZE" ]] || {
  echo "SHA256SUMS.txt size differs from the verified manifest." >&2
  exit 1
}
printf '%s  %s\n%s  %s\n' "$APK_SHA256" "$canonical_apk" "$SOURCE_ZIP_SHA256" "$canonical_source" | cmp -s - "$SHA256SUMS_PATH" || {
  echo "SHA256SUMS.txt does not list exactly the verified APK and source ZIP." >&2
  exit 1
}
[[ "$(sha256sum "$APK_PATH" | awk '{print $1}')" == "$APK_SHA256" ]] || {
  echo "APK changed after verification." >&2
  exit 1
}
[[ "$(sha256sum "$SOURCE_ZIP_PATH" | awk '{print $1}')" == "$SOURCE_ZIP_SHA256" ]] || {
  echo "Source ZIP changed after verification." >&2
  exit 1
}
[[ "$(sha256sum "$SHA256SUMS_PATH" | awk '{print $1}')" == "$SHA256SUMS_SHA256" ]] || {
  echo "SHA256SUMS.txt changed after verification." >&2
  exit 1
}
unzip -tq "$SOURCE_ZIP_PATH"
(cd "$(dirname "$SHA256SUMS_PATH")" && sha256sum --check --status "$canonical_sums")

api_version="2022-11-28"
api() {
  gh api -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: $api_version" "$@"
}

release_endpoint="repos/$GH_REPO/releases/tags/$RELEASE_TAG"
release_title="CarPaly Xingyue L v$version — Public Preview"
release_notes="## 中文

- 版本：$version（Android versionCode: $APK_VERSION_CODE）
- 车型配置：包含 KX11 Generic 回退及星越 L 配置；配置存在不等于实车兼容已验证。
- Android：最低 API 25（Android 7.1），targetSdk 37；仅表示清单配置，不代表所有系统版本均已验收。
- 有线 CarPlay、无线 CarPlay、iPhone 发现：NOT_TESTED（尚无真实 iPhone 与车机连接证据）。
- 原车音频、Siri、麦克风、HUD/仪表：NOT_TESTED。
- 认证：实验性离线 MFi 资源；非 Apple 官方认证，APK 内资源可被提取，未来 iOS 接受度不保证。
- 安装：在 Android 车机启用本次安装来源的应用安装权限后安装 APK；更新必须保持相同 applicationId 和签名证书。
- 升级：此预览使用 Release 签名，旧 Debug 测试包可能无法覆盖安装；卸载会清除应用私有数据，请先备份。
- 诊断：可在应用诊断中心手动生成/导出报告；提交 GitHub Issue 前请审查脱敏内容。日志不会自动上传。
- 已知限制：没有真实车辆、iPhone、音频、Siri/麦克风或 HUD 实车验收；请仅在安全停车状态下测试。
- APK：$canonical_apk
- APK SHA-256：$APK_SHA256
- 对应源码：$canonical_source（从发布 Commit 生成；排除普通 Markdown 报告及凭据）
- 源码 ZIP SHA-256：$SOURCE_ZIP_SHA256
- 校验清单：$canonical_sums（列出 APK 与源码 ZIP 哈希）
- 校验清单文件 SHA-256：$SHA256SUMS_SHA256
- 反馈：请通过 GitHub Issues 提交车型/固件、iOS 版本、连接方式、复现步骤和手动导出的脱敏诊断报告。

## English

- Version: $version (Android versionCode $APK_VERSION_CODE)
- Vehicle profiles: KX11 Generic fallback and Xingyue L configurations are included; configuration presence is not in-car compatibility evidence.
- Android: minimum API 25 (Android 7.1), targetSdk 37; these manifest values do not mean every OS version has been validated.
- Wired CarPlay, wireless CarPlay, and iPhone discovery: NOT_TESTED (no real iPhone/head-unit connection evidence).
- Factory audio, Siri, microphone, HUD/instrument cluster: NOT_TESTED.
- Authentication: experimental offline MFi assets; not Apple-certified, extractable from the APK, and future iOS acceptance is not guaranteed.
- Install: allow app installation from the selected source on the Android head unit, then install the APK; upgrades require the same applicationId and signing certificate.
- Upgrade: this preview uses a Release signer and may not update a Debug-signed test build. Uninstalling removes app-private data; back it up first.
- Diagnostics: reports can be manually generated/exported in the app. Review redacted content before attaching it to a GitHub Issue; logs are not uploaded automatically.
- Known limitation: no real vehicle, iPhone, audio, Siri/microphone, or HUD acceptance has been completed. Test only while safely parked.
- APK: $canonical_apk
- APK SHA-256: $APK_SHA256
- Matching source: $canonical_source (built from the release commit; excludes ordinary Markdown reports and credentials)
- Source ZIP SHA-256: $SOURCE_ZIP_SHA256
- Checksum manifest: $canonical_sums (lists APK and source ZIP digests)
- SHA256SUMS.txt SHA-256: $SHA256SUMS_SHA256
- Feedback: use GitHub Issues with vehicle/firmware, iOS version, connection mode, reproduction steps, and a manually exported redacted report."

release_json=""
release_exists=true
if ! release_json="$(api "$release_endpoint" 2>/dev/null)"; then
  release_exists=false
fi

release_index="$(api "repos/$GH_REPO/releases?per_page=100")"
highest_version_code=0
existing_tag_version_code=""
while IFS= read -r encoded_release; do
  prior_release="$(base64 --decode <<<"$encoded_release")"
  prior_tag="$(jq -r '.tag_name // ""' <<<"$prior_release")"
  prior_body="$(jq -r '.body // ""' <<<"$prior_release")"
  prior_code="$(sed -nE 's/^Android versionCode: ([0-9]+)$/\1/p' <<<"$prior_body" | head -n 1)"
  if [[ -z "$prior_code" ]]; then
    case "$prior_tag" in
      v0.1.0) prior_code=34 ;;
      v0.2.16) prior_code=35 ;;
    esac
  fi
  [[ "$prior_code" =~ ^[1-9][0-9]*$ ]] || continue
  if [[ "$prior_tag" == "$RELEASE_TAG" ]]; then
    existing_tag_version_code="$prior_code"
    continue
  fi
  if (( prior_code > highest_version_code )); then
    highest_version_code="$prior_code"
  fi
done < <(jq -r '.[] | @base64' <<<"$release_index")

if [[ -n "$existing_tag_version_code" ]]; then
  [[ "$APK_VERSION_CODE" == "$existing_tag_version_code" ]] || {
    echo "A rerun for $RELEASE_TAG must preserve versionCode $existing_tag_version_code." >&2
    exit 1
  }
elif (( APK_VERSION_CODE <= highest_version_code )); then
  echo "APK versionCode $APK_VERSION_CODE must exceed the published maximum $highest_version_code." >&2
  exit 1
fi

if [[ "$release_exists" == false ]]; then
  # Validate the tag and version sequence before creating even a draft release.
  api "repos/$GH_REPO/git/ref/tags/$RELEASE_TAG" >/dev/null
  gh release create "$RELEASE_TAG" --verify-tag --draft --prerelease \
    --title "$release_title" --notes "$release_notes"
  release_json="$(api "$release_endpoint")"
fi

release_id="$(jq -er '.id | tostring' <<<"$release_json")"
is_draft="$(jq -r '.draft' <<<"$release_json")"

assets_endpoint="repos/$GH_REPO/releases/$release_id/assets?per_page=100"
assets="$(api "$assets_endpoint")"
apk_count="$(jq --arg name "$canonical_apk" '[.[] | select(.name == $name)] | length' <<<"$assets")"
source_count="$(jq --arg name "$canonical_source" '[.[] | select(.name == $name)] | length' <<<"$assets")"
sums_count="$(jq --arg name "$canonical_sums" '[.[] | select(.name == $name)] | length' <<<"$assets")"
(( apk_count <= 1 && source_count <= 1 && sums_count <= 1 )) || {
  echo "Duplicate canonical assets exist; refusing to modify the release." >&2
  exit 1
}
unexpected="$(jq -r --arg apk "$canonical_apk" --arg source "$canonical_source" --arg sums "$canonical_sums" \
  '.[] | select(.name != $apk and .name != $source and .name != $sums) | .name' <<<"$assets")"
[[ -z "$unexpected" ]] || {
  echo "Unmanaged release assets exist; refusing to alter them:" >&2
  printf '%s\n' "$unexpected" >&2
  exit 1
}

verify_asset() {
  local current="$1" name="$2" expected_size="$3" expected_sha="$4"
  local count row size digest state
  count="$(jq --arg name "$name" '[.[] | select(.name == $name)] | length' <<<"$current")"
  [[ "$count" == 1 ]] || return 1
  row="$(jq -r --arg name "$name" \
    '.[] | select(.name == $name) | [.size, (.digest // ""), .state] | @tsv' <<<"$current")"
  IFS=$'\t' read -r size digest state <<<"$row"
  [[ "$size" == "$expected_size" && "$digest" == "sha256:$expected_sha" && "$state" == uploaded ]]
}

for entry in \
  "$canonical_apk|$APK_SIZE|$APK_SHA256|$apk_count" \
  "$canonical_source|$SOURCE_ZIP_SIZE|$SOURCE_ZIP_SHA256|$source_count" \
  "$canonical_sums|$SHA256SUMS_SIZE|$SHA256SUMS_SHA256|$sums_count"; do
  IFS='|' read -r name size digest count <<<"$entry"
  if (( count == 1 )); then
    verify_asset "$assets" "$name" "$size" "$digest" || {
      echo "An existing asset with different bytes is attached ($name); preserving it and refusing replacement." >&2
      exit 1
    }
  fi
done

if [[ "$is_draft" != true && ( "$apk_count" != 1 || "$source_count" != 1 || "$sums_count" != 1 ) ]]; then
  echo "A published release is missing an asset; refusing to mutate public downloads." >&2
  exit 1
fi

if (( apk_count == 0 )); then
  gh release upload "$RELEASE_TAG" "$APK_PATH"
fi
assets="$(api "$assets_endpoint")"
if (( source_count == 0 )); then
  gh release upload "$RELEASE_TAG" "$SOURCE_ZIP_PATH"
fi
assets="$(api "$assets_endpoint")"
if (( sums_count == 0 )); then
  gh release upload "$RELEASE_TAG" "$SHA256SUMS_PATH"
fi
assets="$(api "$assets_endpoint")"

[[ "$(jq 'length' <<<"$assets")" == 3 ]] || {
  echo "Release must contain exactly one APK, one source ZIP, and SHA256SUMS.txt." >&2
  exit 1
}
verify_asset "$assets" "$canonical_apk" "$APK_SIZE" "$APK_SHA256" || {
  echo "GitHub APK attachment does not match the verified build." >&2
  exit 1
}
verify_asset "$assets" "$canonical_source" "$SOURCE_ZIP_SIZE" "$SOURCE_ZIP_SHA256" || {
  echo "GitHub source ZIP attachment does not match the verified archive." >&2
  exit 1
}
verify_asset "$assets" "$canonical_sums" "$SHA256SUMS_SIZE" "$SHA256SUMS_SHA256" || {
  echo "GitHub SHA256SUMS.txt attachment does not match the verified manifest." >&2
  exit 1
}

# Download every remote asset and verify its bytes before publishing or reporting success.
download_dir="$RUNNER_TEMP/carpaly-release-remote"
mkdir -p "$download_dir"
gh release download "$RELEASE_TAG" --pattern "$canonical_apk" --pattern "$canonical_source" --pattern "$canonical_sums" --dir "$download_dir"
cmp -s "$APK_PATH" "$download_dir/$canonical_apk"
cmp -s "$SOURCE_ZIP_PATH" "$download_dir/$canonical_source"
cmp -s "$SHA256SUMS_PATH" "$download_dir/$canonical_sums"
[[ "$(stat -c '%s' "$download_dir/$canonical_apk")" == "$APK_SIZE" ]]
[[ "$(sha256sum "$download_dir/$canonical_apk" | awk '{print $1}')" == "$APK_SHA256" ]]
[[ "$(sha256sum "$download_dir/$canonical_source" | awk '{print $1}')" == "$SOURCE_ZIP_SHA256" ]]
[[ "$(sha256sum "$download_dir/$canonical_sums" | awk '{print $1}')" == "$SHA256SUMS_SHA256" ]]
(cd "$download_dir" && sha256sum --check --status "$canonical_sums")

api --method PATCH "repos/$GH_REPO/releases/$release_id" \
  -f "name=$release_title" \
  -f "body=$release_notes" \
  -F draft=false \
  -F prerelease=true >/dev/null

final_release="$(api "$release_endpoint")"
[[ "$(jq -r '.draft' <<<"$final_release")" == false ]]
[[ "$(jq -r '.prerelease' <<<"$final_release")" == true ]]
final_assets="$(api "$assets_endpoint")"
[[ "$(jq 'length' <<<"$final_assets")" == 3 ]]
verify_asset "$final_assets" "$canonical_apk" "$APK_SIZE" "$APK_SHA256"
verify_asset "$final_assets" "$canonical_source" "$SOURCE_ZIP_SIZE" "$SOURCE_ZIP_SHA256"
verify_asset "$final_assets" "$canonical_sums" "$SHA256SUMS_SIZE" "$SHA256SUMS_SHA256"
published_download_dir="$RUNNER_TEMP/carpaly-release-published"
mkdir -p "$published_download_dir"
gh release download "$RELEASE_TAG" --pattern "$canonical_apk" --pattern "$canonical_source" --pattern "$canonical_sums" --dir "$published_download_dir"
cmp -s "$APK_PATH" "$published_download_dir/$canonical_apk"
cmp -s "$SOURCE_ZIP_PATH" "$published_download_dir/$canonical_source"
cmp -s "$SHA256SUMS_PATH" "$published_download_dir/$canonical_sums"
[[ "$(sha256sum "$published_download_dir/$canonical_apk" | awk '{print $1}')" == "$APK_SHA256" ]]
[[ "$(stat -c '%s' "$published_download_dir/$canonical_apk")" == "$APK_SIZE" ]]
[[ "$(sha256sum "$published_download_dir/$canonical_source" | awk '{print $1}')" == "$SOURCE_ZIP_SHA256" ]]
[[ "$(sha256sum "$published_download_dir/$canonical_sums" | awk '{print $1}')" == "$SHA256SUMS_SHA256" ]]
(cd "$published_download_dir" && sha256sum --check --status "$canonical_sums")
echo "Published and remotely verified $RELEASE_TAG: APK $canonical_apk, source $canonical_source, and $canonical_sums."
