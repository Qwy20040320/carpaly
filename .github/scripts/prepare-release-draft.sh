#!/usr/bin/env bash
set -euo pipefail

required=(GH_TOKEN GH_REPO RELEASE_TAG RELEASE_COMMIT RELEASE_VERSION_CODE RELEASE_SIGNING_CERT_SHA256 RELEASE_PRERELEASE AUTO_CREATE_TAG)
for variable in "${required[@]}"; do
  if ! printenv "$variable" >/dev/null; then
    echo "Required environment variable is missing: $variable" >&2
    exit 1
  fi
done

[[ "$GH_REPO" == "Qwy20040320/carpaly" ]] || {
  echo "Release drafts may only be prepared in the CarPaly repository." >&2
  exit 1
}
[[ "$RELEASE_TAG" =~ ^v1\.[0-9]+\.[0-9]+$ ]] || {
  echo "Release draft tag must use a v1.x.y semantic-version tag." >&2
  exit 1
}
version="${RELEASE_TAG#v}"
[[ "$RELEASE_VERSION_CODE" =~ ^[1-9][0-9]*$ ]] || {
  echo "Release versionCode must be a positive integer." >&2
  exit 1
}
[[ "$RELEASE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || {
  echo "Release source must be a full lowercase commit SHA." >&2
  exit 1
}
[[ "$RELEASE_SIGNING_CERT_SHA256" =~ ^[0-9a-f]{64}$ ]] || {
  echo "Release signer must be a lowercase public certificate SHA-256." >&2
  exit 1
}
[[ "$RELEASE_PRERELEASE" == true || "$RELEASE_PRERELEASE" == false ]] || {
  echo "RELEASE_PRERELEASE must be true or false." >&2
  exit 1
}
[[ "$AUTO_CREATE_TAG" == true || "$AUTO_CREATE_TAG" == false ]] || {
  echo "AUTO_CREATE_TAG must be true or false." >&2
  exit 1
}

api_version="2022-11-28"
api() {
  gh api -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: $api_version" "$@"
}

tag_ref() {
  local refs status direct peeled
  if refs="$(git ls-remote --exit-code origin \
      "refs/tags/$RELEASE_TAG" "refs/tags/$RELEASE_TAG^{}" 2>&1)"; then
    status=0
  else
    status=$?
  fi
  if (( status == 2 )) && [[ -z "$refs" ]]; then
    return 1
  fi
  if (( status != 0 )); then
    echo "Could not safely inspect the remote tag (git ls-remote status $status)." >&2
    return 2
  fi
  direct="$(awk -v ref="refs/tags/$RELEASE_TAG" '$2 == ref { print $1; exit }' <<<"$refs")"
  peeled="$(awk -v ref="refs/tags/$RELEASE_TAG^{}" '$2 == ref { print $1; exit }' <<<"$refs")"
  printf '%s\n' "${peeled:-$direct}"
}

load_release() {
  local pages
  pages="$(api --paginate "repos/$GH_REPO/releases?per_page=100" | jq -s 'add')"
  jq -e 'type == "array"' <<<"$pages" >/dev/null || {
    echo "GitHub Releases API returned an invalid list; refusing draft creation." >&2
    return 1
  }
  local matches
  matches="$(jq -c --arg tag "$RELEASE_TAG" '[.[] | select(.tag_name == $tag)]' <<<"$pages")"
  [[ "$(jq 'length' <<<"$matches")" -le 1 ]] || {
    echo "GitHub returned duplicate Releases for the tag; refusing to choose one." >&2
    return 1
  }
  jq -c '.[0] // empty' <<<"$matches"
}

load_assets() {
  local release_id="$1" assets
  assets="$(api --paginate "repos/$GH_REPO/releases/$release_id/assets?per_page=100" | jq -s 'add')"
  jq -e 'type == "array"' <<<"$assets" >/dev/null || {
    echo "GitHub Release assets API returned an invalid list; refusing draft mutation." >&2
    return 1
  }
  printf '%s\n' "$assets"
}

verify_tag_commit() {
  local target="$1"
  [[ "$target" == "$RELEASE_COMMIT" ]] || {
    echo "The remote release tag does not point to the verified source commit." >&2
    return 1
  }
}

release_title="CarPaly v$version"
draft_marker="<!-- carpaly-release-draft-v1: metadata-only; reviewed-assets-required -->"
channel="Stable"
if [[ "$RELEASE_PRERELEASE" == true ]]; then
  channel="Beta"
fi
release_notes="$draft_marker

## CarPaly v$version — $channel draft

- Android versionCode: $RELEASE_VERSION_CODE
- Verified source commit: $RELEASE_COMMIT
- Android Release signer SHA-256: $RELEASE_SIGNING_CERT_SHA256
- Build and signature checks completed in the protected Release workflow.
- No APK, source archive, or other binary is attached to this draft.
- Do not publish this draft as a download: the current APK contains extractable authentication identity material and is withheld pending an approved distribution-safe design.
- CarPlay, vehicle audio, Siri/microphone, HUD, and instrument-cluster behavior remain NOT_TESTED unless independently documented for this exact build.

This draft is metadata-only. A maintainer must replace or amend these notes and attach only separately reviewed, distribution-safe assets before any manual publication."

release="$(load_release)"
tag_target=""
if tag_target="$(tag_ref)"; then
  verify_tag_commit "$tag_target"
  tag_exists=true
else
  status=$?
  if (( status == 1 )); then
    tag_exists=false
  else
    exit 1
  fi
fi

if [[ -n "$release" ]]; then
  [[ "$(jq -r '.tag_name // ""' <<<"$release")" == "$RELEASE_TAG" ]] || {
    echo "Existing Release tag does not match the requested version." >&2
    exit 1
  }
  if [[ "$tag_exists" != true ]]; then
    echo "GitHub has a Release without its expected remote tag; refusing to alter it." >&2
    exit 1
  fi
  if [[ "$(jq -r '.draft' <<<"$release")" == false ]]; then
    # Published releases, including their assets and hand-written notes, are immutable here.
    echo "RELEASE_DRAFT_STATUS=PUBLISHED_IMMUTABLE tag=$RELEASE_TAG url=$(jq -r '.html_url // ""' <<<"$release")"
    exit 0
  fi
  # Do not rewrite a pre-existing draft's channel, title, or hand-authored notes.
  # The exact tag target and empty-asset check below are the reuse boundary.
  [[ "$(jq -r '.prerelease' <<<"$release")" == "$RELEASE_PRERELEASE" ]] || {
    echo "Existing draft channel does not match the requested Stable/Beta channel; refusing to reuse it." >&2
    exit 1
  }
  jq -e --arg marker "$draft_marker" '(.body // "") | contains($marker)' <<<"$release" >/dev/null || {
    echo "Existing draft was not created by the metadata-only preparer; refusing to overwrite or reuse it." >&2
    exit 1
  }
  assets="$(load_assets "$(jq -er '.id' <<<"$release")")"
  [[ "$(jq 'length' <<<"$assets")" == 0 ]] || {
    echo "Existing draft has attachments; refusing to reuse or mutate it because public-distribution safety is unverified." >&2
    exit 1
  }
  [[ "$(jq -r '.draft' <<<"$release")" == true ]] || {
    echo "Release is no longer a draft; refusing to change its publication state." >&2
    exit 1
  }
  echo "RELEASE_DRAFT_STATUS=REUSED tag=$RELEASE_TAG url=$(jq -r '.html_url // ""' <<<"$release") assets=0"
  exit 0
fi

if [[ "$tag_exists" != true && "$AUTO_CREATE_TAG" != true ]]; then
  echo "Release tag is missing and this workflow is not authorized to create it." >&2
  exit 1
fi

create_args=(release create "$RELEASE_TAG" --draft --title "$release_title" --notes "$release_notes")
if [[ "$RELEASE_PRERELEASE" == true ]]; then
  create_args+=(--prerelease)
fi
if [[ "$tag_exists" == true ]]; then
  create_args+=(--verify-tag)
else
  create_args+=(--target "$RELEASE_COMMIT")
fi

if ! gh "${create_args[@]}"; then
  # A concurrent run may have created the same draft. Reuse only after rechecking
  # tag identity, draft state, release channel, and the absence of every asset.
  echo "Release draft creation did not complete; checking whether an identical draft won the race." >&2
fi

tag_target="$(tag_ref)" || {
  echo "No release tag is visible after draft preparation." >&2
  exit 1
}
verify_tag_commit "$tag_target"
release="$(load_release)"
[[ -n "$release" ]] || {
  echo "GitHub did not return the prepared Release draft." >&2
  exit 1
}
[[ "$(jq -r '.draft' <<<"$release")" == true ]] || {
  echo "Prepared Release is not a draft; refusing to report success." >&2
  exit 1
}
jq -e --arg marker "$draft_marker" '(.body // "") | contains($marker)' <<<"$release" >/dev/null || {
  echo "Prepared Release lacks the metadata-only marker; refusing to report success." >&2
  exit 1
}
expected_prerelease="$RELEASE_PRERELEASE"
[[ "$(jq -r '.tag_name // ""' <<<"$release")" == "$RELEASE_TAG" && \
   "$(jq -r '.prerelease' <<<"$release")" == "$expected_prerelease" ]] || {
  echo "Prepared Release metadata does not match the requested Beta tag." >&2
  exit 1
}
assets="$(load_assets "$(jq -er '.id' <<<"$release")")"
[[ "$(jq 'length' <<<"$assets")" == 0 ]] || {
  echo "Prepared draft unexpectedly contains an attachment; refusing to report success." >&2
  exit 1
}
echo "RELEASE_DRAFT_STATUS=CREATED tag=$RELEASE_TAG url=$(jq -r '.html_url // ""' <<<"$release") assets=0"
