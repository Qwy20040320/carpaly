#!/usr/bin/env bash
set -euo pipefail

required=(GH_TOKEN GH_REPO RELEASE_TAG APK_PATH APK_NAME CHECKSUM_PATH APK_SHA256 APK_SIZE APK_VERSION_CODE RUNNER_TEMP)
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
canonical_checksum="${canonical_apk}.sha256"
[[ "$APK_NAME" == "$canonical_apk" ]] || {
  echo "APK filename does not match the release tag." >&2
  exit 1
}
[[ "$(basename "$APK_PATH")" == "$canonical_apk" ]] || {
  echo "APK path does not have the canonical versioned filename." >&2
  exit 1
}
[[ "$(basename "$CHECKSUM_PATH")" == "$canonical_checksum" ]] || {
  echo "Checksum filename does not match the APK filename." >&2
  exit 1
}
[[ "$APK_SHA256" =~ ^[0-9a-f]{64}$ ]] || {
  echo "APK_SHA256 must be a lowercase SHA-256 digest." >&2
  exit 1
}
[[ "$APK_VERSION_CODE" =~ ^[1-9][0-9]*$ ]] || {
  echo "APK_VERSION_CODE must be a positive integer." >&2
  exit 1
}
[[ -s "$APK_PATH" && -s "$CHECKSUM_PATH" ]] || {
  echo "Verified APK or checksum file is missing." >&2
  exit 1
}
[[ "$(stat -c '%s' "$APK_PATH")" == "$APK_SIZE" ]] || {
  echo "APK size differs from the verified build output." >&2
  exit 1
}
printf '%s  %s\n' "$APK_SHA256" "$canonical_apk" | cmp -s - "$CHECKSUM_PATH" || {
  echo "Checksum sidecar does not match the APK identity." >&2
  exit 1
}
[[ "$(sha256sum "$APK_PATH" | awk '{print $1}')" == "$APK_SHA256" ]] || {
  echo "APK changed after verification." >&2
  exit 1
}

api_version="2022-11-28"
api() {
  gh api -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: $api_version" "$@"
}

release_endpoint="repos/$GH_REPO/releases/tags/$RELEASE_TAG"
release_title="CarPaly $RELEASE_TAG — Geely Xingyue L"
release_notes="## 中文

- 版本：$version（Android versionCode: $APK_VERSION_CODE）
- Android versionCode: $APK_VERSION_CODE
- APK：$canonical_apk
- SHA-256：$APK_SHA256
- 认证资源已按单独审核的授权范围包含在 APK 中；APK 内私钥可被提取。
- Android Release 签名预览版；不代表 Apple/吉利认证。
- 已安装旧 Debug 测试包可能因签名不同而不能覆盖安装；卸载会清除应用私有数据，请先备份，且勿假设数据迁移可用。
- Android 运行时认证和星越 L 实车功能：NOT_TESTED。

## English

- Version: $version (Android versionCode $APK_VERSION_CODE)
- Android versionCode: $APK_VERSION_CODE
- APK: $canonical_apk
- SHA-256: $APK_SHA256
- Authentication assets are bundled under a separately reviewed grant; the private key is extractable from the APK.
- Android Release-signed preview; not Apple or Geely certified.
- An older Debug-signed test APK may not accept an in-place update. Uninstalling erases app-private data; back it up first and do not assume data migration is available.
- Android runtime authentication and Geely in-vehicle functions: NOT_TESTED."

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
checksum_count="$(jq --arg name "$canonical_checksum" '[.[] | select(.name == $name)] | length' <<<"$assets")"
(( apk_count <= 1 && checksum_count <= 1 )) || {
  echo "Duplicate canonical assets exist; refusing to modify the release." >&2
  exit 1
}
unexpected="$(jq -r --arg apk "$canonical_apk" --arg checksum "$canonical_checksum" \
  '.[] | select(.name != $apk and .name != $checksum) | .name' <<<"$assets")"
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

if (( apk_count == 1 )); then
  verify_asset "$assets" "$canonical_apk" "$APK_SIZE" "$APK_SHA256" || {
    echo "An existing APK with different bytes is attached; preserving it and refusing replacement." >&2
    exit 1
  }
fi
checksum_size="$(stat -c '%s' "$CHECKSUM_PATH")"
checksum_sha="$(sha256sum "$CHECKSUM_PATH" | awk '{print $1}')"
if (( checksum_count == 1 )); then
  verify_asset "$assets" "$canonical_checksum" "$checksum_size" "$checksum_sha" || {
    echo "An existing checksum file differs; preserving it and refusing replacement." >&2
    exit 1
  }
fi

if [[ "$is_draft" != true && ( "$apk_count" != 1 || "$checksum_count" != 1 ) ]]; then
  echo "A published release is missing an asset; refusing to mutate public downloads." >&2
  exit 1
fi

if (( apk_count == 0 )); then
  gh release upload "$RELEASE_TAG" "$APK_PATH"
fi
assets="$(api "$assets_endpoint")"
if (( checksum_count == 0 )); then
  gh release upload "$RELEASE_TAG" "$CHECKSUM_PATH"
fi
assets="$(api "$assets_endpoint")"

[[ "$(jq 'length' <<<"$assets")" == 2 ]] || {
  echo "Release must contain exactly one APK and one SHA-256 sidecar." >&2
  exit 1
}
verify_asset "$assets" "$canonical_apk" "$APK_SIZE" "$APK_SHA256" || {
  echo "GitHub APK attachment does not match the verified build." >&2
  exit 1
}
verify_asset "$assets" "$canonical_checksum" "$checksum_size" "$checksum_sha" || {
  echo "GitHub SHA-256 attachment does not match the verified sidecar." >&2
  exit 1
}

# Download both remote assets and verify their bytes before publishing or reporting success.
download_dir="$RUNNER_TEMP/carpaly-release-remote"
mkdir -p "$download_dir"
gh release download "$RELEASE_TAG" --pattern "$canonical_apk" --pattern "$canonical_checksum" --dir "$download_dir"
cmp -s "$APK_PATH" "$download_dir/$canonical_apk"
cmp -s "$CHECKSUM_PATH" "$download_dir/$canonical_checksum"
[[ "$(stat -c '%s' "$download_dir/$canonical_apk")" == "$APK_SIZE" ]]
[[ "$(sha256sum "$download_dir/$canonical_apk" | awk '{print $1}')" == "$APK_SHA256" ]]
(cd "$download_dir" && sha256sum --check --status "$canonical_checksum")

api --method PATCH "repos/$GH_REPO/releases/$release_id" \
  -f "name=$release_title" \
  -f "body=$release_notes" \
  -F draft=false \
  -F prerelease=true >/dev/null

final_release="$(api "$release_endpoint")"
[[ "$(jq -r '.draft' <<<"$final_release")" == false ]]
[[ "$(jq -r '.prerelease' <<<"$final_release")" == true ]]
final_assets="$(api "$assets_endpoint")"
[[ "$(jq 'length' <<<"$final_assets")" == 2 ]]
verify_asset "$final_assets" "$canonical_apk" "$APK_SIZE" "$APK_SHA256"
verify_asset "$final_assets" "$canonical_checksum" "$checksum_size" "$checksum_sha"
published_download_dir="$RUNNER_TEMP/carpaly-release-published"
mkdir -p "$published_download_dir"
gh release download "$RELEASE_TAG" --pattern "$canonical_apk" --pattern "$canonical_checksum" --dir "$published_download_dir"
cmp -s "$APK_PATH" "$published_download_dir/$canonical_apk"
cmp -s "$CHECKSUM_PATH" "$published_download_dir/$canonical_checksum"
[[ "$(sha256sum "$published_download_dir/$canonical_apk" | awk '{print $1}')" == "$APK_SHA256" ]]
[[ "$(stat -c '%s' "$published_download_dir/$canonical_apk")" == "$APK_SIZE" ]]
(cd "$published_download_dir" && sha256sum --check --status "$canonical_checksum")
echo "Published and remotely verified $RELEASE_TAG: $canonical_apk ($APK_SIZE bytes, SHA-256 $APK_SHA256) plus $canonical_checksum."
