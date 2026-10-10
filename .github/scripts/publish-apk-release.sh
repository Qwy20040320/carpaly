#!/usr/bin/env bash
set -euo pipefail

for variable in GH_TOKEN GH_REPO RELEASE_TAG APK_PATH APK_SHA256 APK_SIZE APK_VERSION_CODE GITHUB_RUN_ID GITHUB_RUN_ATTEMPT RUNNER_TEMP; do
  if ! printenv "$variable" >/dev/null; then
    echo "Required environment variable is missing: $variable" >&2
    exit 1
  fi
done

if [[ ! "$RELEASE_TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Release tags must use vMAJOR.MINOR.PATCH." >&2
  exit 1
fi

version="$(sed 's/^v//' <<< "$RELEASE_TAG")"
if [[ ! "$APK_VERSION_CODE" =~ ^[1-9][0-9]*$ ]]; then
  echo "APK_VERSION_CODE must be a positive integer." >&2
  exit 1
fi
canonical_name="CarPaly-XingyueL$version.apk"
escaped_version="$(sed 's/\./\\./g' <<< "$version")"
managed_asset_regex="^CarPaly-XingyueL$escaped_version-(upload|previous)-[0-9]+-[0-9]+\\.apk$"
previous_asset_regex="^CarPaly-XingyueL$escaped_version-previous-[0-9]+-[0-9]+\\.apk$"
api_version="2022-11-28"
release_endpoint="repos/$GH_REPO/releases/tags/$RELEASE_TAG"
release_title="CarPaly $RELEASE_TAG"
release_notes="Android versionName: $version
Android versionCode: $APK_VERSION_CODE
APK file: $canonical_name

Preview / Debug-HUD-test build; this is not a stable-signature package.
CI checks package structure and signature format only. MFi authentication inputs and Geely in-car validation are not included or claimed."

api() {
  gh api -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: $api_version" "$@"
}

list_assets() {
  api "repos/$GH_REPO/releases/$1/assets?per_page=100"
}

asset_count() {
  jq --arg name "$2" '[.[] | select(.name == $name)] | length' <<<"$1"
}

asset_row() {
  jq -r --arg name "$2" \
    '.[] | select(.name == $name) | [.id, .size, (.digest // ""), .state] | @tsv' \
    <<<"$1"
}

release_index="$(api "repos/$GH_REPO/releases?per_page=100")"
highest_version_code=0
existing_tag_version_code=""
while IFS= read -r encoded_release; do
  prior_release="$(base64 --decode <<<"$encoded_release")"
  prior_tag="$(jq -r '.tag_name // ""' <<<"$prior_release")"
  prior_body="$(jq -r '.body // ""' <<<"$prior_release")"
  prior_code="$(sed -nE 's/^Android versionCode: ([0-9]+)$/\1/p' <<<"$prior_body" | head -n 1)"
  case "$prior_tag" in
    v0.1.0)
      if [[ -z "$prior_code" ]]; then prior_code=34; fi
      ;;
    v0.2.16)
      if [[ -z "$prior_code" ]]; then prior_code=35; fi
      ;;
  esac
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
  if [[ "$APK_VERSION_CODE" != "$existing_tag_version_code" ]]; then
    echo "A rerun for $RELEASE_TAG must preserve versionCode $existing_tag_version_code." >&2
    exit 1
  fi
elif (( APK_VERSION_CODE <= highest_version_code )); then
  echo "APK versionCode $APK_VERSION_CODE must exceed the published maximum $highest_version_code." >&2
  exit 1
fi

verify_asset() {
  local assets="$1" name="$2" expected_size="$3" expected_sha="$4"
  local count row id size digest state
  count="$(asset_count "$assets" "$name")"
  [[ "$count" == "1" ]] || return 1
  row="$(asset_row "$assets" "$name")"
  IFS=$'\t' read -r id size digest state <<<"$row"
  [[ "$size" == "$expected_size" && "$digest" == "sha256:$expected_sha" && "$state" == "uploaded" ]]
}

reject_unmanaged_assets() {
  local assets="$1" unexpected
  unexpected="$(jq -r --arg canonical "$canonical_name" --arg managed "$managed_asset_regex" '
    .[]
    | select(.name != $canonical)
    | select((.name | test($managed)) | not)
    | .name
  ' <<<"$assets")"
  if [[ -n "$unexpected" ]]; then
    echo "Refusing to alter a release with unmanaged assets:" >&2
    printf '%s\n' "$unexpected" >&2
    return 1
  fi
}

patch_asset_name() {
  api --method PATCH "repos/$GH_REPO/releases/assets/$1" -f "name=$2" >/dev/null
}

delete_asset() {
  api --method DELETE "repos/$GH_REPO/releases/assets/$1" >/dev/null
}

release_json=""
if release_json="$(api "$release_endpoint" 2>/dev/null)"; then
  release_id="$(jq -er '.id | tostring' <<<"$release_json")"
else
  # Only create when the tag itself is present and readable. This avoids
  # treating permission, network, or API errors as a missing release.
  if ! api "repos/$GH_REPO/git/ref/tags/$RELEASE_TAG" >/dev/null 2>&1; then
    echo "Could not read an existing release or verify the pushed tag." >&2
    exit 1
  fi
  gh release create "$RELEASE_TAG" "$APK_PATH" \
    --verify-tag \
    --title "$release_title" \
    --notes "$release_notes" \
    --prerelease
  release_json="$(api "$release_endpoint")"
  release_id="$(jq -er '.id | tostring' <<<"$release_json")"
  assets="$(list_assets "$release_id")"
  if ! verify_asset "$assets" "$canonical_name" "$APK_SIZE" "$APK_SHA256"; then
    echo "New release APK asset does not match the verified build." >&2
    exit 1
  fi
  if [[ "$(jq 'length' <<<"$assets")" != "1" ]]; then
    echo "New release must contain exactly one APK asset." >&2
    exit 1
  fi
  echo "Created $RELEASE_TAG with one verified APK asset."
  exit 0
fi

assets="$(list_assets "$release_id")"
reject_unmanaged_assets "$assets"

canonical_count="$(asset_count "$assets" "$canonical_name")"
if (( canonical_count > 1 )); then
  echo "Release contains duplicate canonical APK assets; refusing to update." >&2
  exit 1
fi

# Recover an interrupted replacement if the prior APK was renamed to a
# backup but the new APK had not yet received the canonical name.
if (( canonical_count == 0 )); then
  previous_count="$(jq --arg previous "$previous_asset_regex" '[.[] | select(.name | test($previous))] | length' <<<"$assets")"
  if (( previous_count > 1 )); then
    echo "Multiple previous APK backups exist and need manual review." >&2
    exit 1
  elif (( previous_count == 1 )); then
    previous_row="$(jq -r --arg previous "$previous_asset_regex" '.[] | select(.name | test($previous)) | [.id, .name] | @tsv' <<<"$assets")"
    IFS=$'\t' read -r previous_id previous_name <<<"$previous_row"
    patch_asset_name "$previous_id" "$canonical_name"
    assets="$(list_assets "$release_id")"
    canonical_count="$(asset_count "$assets" "$canonical_name")"
  fi
fi

run_suffix="$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
temporary_name="CarPaly-XingyueL$version-upload-$run_suffix.apk"
temporary_path="$RUNNER_TEMP/$temporary_name"
temporary_count="$(asset_count "$assets" "$temporary_name")"
if (( temporary_count > 1 )); then
  echo "Duplicate temporary APK uploads exist; refusing to update." >&2
  exit 1
elif (( temporary_count == 0 )); then
  cp "$APK_PATH" "$temporary_path"
  gh release upload "$RELEASE_TAG" "$temporary_path"
  assets="$(list_assets "$release_id")"
fi

if ! verify_asset "$assets" "$temporary_name" "$APK_SIZE" "$APK_SHA256"; then
  echo "Temporary release upload does not match the verified APK; the current release asset was left untouched." >&2
  exit 1
fi
temporary_id="$(asset_row "$assets" "$temporary_name" | cut -f1)"

canonical_count="$(asset_count "$assets" "$canonical_name")"
old_asset_id=""
backup_name="CarPaly-XingyueL$version-previous-$run_suffix.apk"
if (( canonical_count == 1 )); then
  old_asset_id="$(asset_row "$assets" "$canonical_name" | cut -f1)"
  if (( $(asset_count "$assets" "$backup_name") != 0 )); then
    echo "The unique backup asset name is already in use; refusing to overwrite it." >&2
    exit 1
  fi
  if ! patch_asset_name "$old_asset_id" "$backup_name"; then
    echo "Could not stage the existing APK for a safe replacement." >&2
    exit 1
  fi
fi

if ! patch_asset_name "$temporary_id" "$canonical_name"; then
  if [[ -n "$old_asset_id" ]]; then
    patch_asset_name "$old_asset_id" "$canonical_name" || true
  fi
  echo "Could not promote the verified upload; attempted to restore the previous APK." >&2
  exit 1
fi

assets="$(list_assets "$release_id")"
if ! verify_asset "$assets" "$canonical_name" "$APK_SIZE" "$APK_SHA256"; then
  patch_asset_name "$temporary_id" "$temporary_name" || true
  if [[ -n "$old_asset_id" ]]; then
    patch_asset_name "$old_asset_id" "$canonical_name" || true
  fi
  echo "Promoted APK failed server-side verification; attempted to restore the previous APK." >&2
  exit 1
fi

# Keep the previous APK until the replacement is uploaded and verified. Only
# then remove workflow-managed temporary/backup assets from this release.
while IFS=$'\t' read -r asset_id asset_name; do
  [[ -n "$asset_id" ]] || continue
  [[ "$asset_name" == "$canonical_name" ]] && continue
  if [[ "$asset_name" =~ $managed_asset_regex ]]; then
    delete_asset "$asset_id"
  else
    echo "Refusing to delete unmanaged release asset: $asset_name" >&2
    exit 1
  fi
done < <(jq -r '.[] | [.id, .name] | @tsv' <<<"$assets")

assets="$(list_assets "$release_id")"
if [[ "$(jq 'length' <<<"$assets")" != "1" ]] || \
   ! verify_asset "$assets" "$canonical_name" "$APK_SIZE" "$APK_SHA256"; then
  echo "Release did not settle to exactly one verified APK asset." >&2
  exit 1
fi

# Also publish an existing draft release only after its new APK is verified.
api --method PATCH "repos/$GH_REPO/releases/$release_id" \
  -f "name=$release_title" \
  -f "body=$release_notes" \
  -F draft=false \
  -F prerelease=true >/dev/null

echo "Updated $RELEASE_TAG with exactly one verified APK asset ($APK_SIZE bytes, SHA-256 $APK_SHA256)."
