package com.shilapi.xcertplay.update

import org.json.JSONArray

internal enum class UpdateChannel {
    BETA,
    STABLE;

    companion object {
        internal fun fromPreference(value: String?): UpdateChannel =
            when {
                value.equals("PREVIEW", ignoreCase = true) -> BETA
                else -> entries.firstOrNull { it.name.equals(value, ignoreCase = true) } ?: STABLE
            }
    }
}

/** The published CarPaly release that a newer build can be downloaded from. */
internal data class UpdateRelease(
    val tagName: String,
    val versionName: String,
    val apkName: String,
    val apkUrl: String,
    val checksumUrl: String,
    val checksumSizeBytes: Long,
    val releasePageUrl: String,
    val releaseNotes: String,
    val sizeBytes: Long,
    val isPrerelease: Boolean,
    val sha256: String,
    val versionCode: Long = 0L,
    val releaseDate: String = "",
    val channel: UpdateChannel = if (isPrerelease) UpdateChannel.BETA else UpdateChannel.STABLE,
    val minimumSupportedVersionCode: Long = 36L,
    val signerCertSha256: String = "",
)

internal object UpdateCatalog {
    private const val REPOSITORY = "Qwy20040320/carpaly"
    private const val FIRST_AUTHENTICATED_VERSION = "1.1.4"
    private val sha256Digest = Regex("^sha256:([0-9a-fA-F]{64})$")

    internal fun apkName(versionName: String): String = "CarPaly-XingyueL-v$versionName.apk"

    private fun legacyApkName(versionName: String): String = "CarPaly-XingyueL$versionName.apk"

    /** Returns the newest valid release allowed by [channel], skipping drafts and malformed assets. */
    internal fun parse(json: String, channel: UpdateChannel = UpdateChannel.STABLE): UpdateRelease? {
        val releases = JSONArray(json)
        var newestValid: UpdateRelease? = null
        for (index in 0 until releases.length()) {
            val release = releases.optJSONObject(index) ?: continue
            if (release.optBoolean("draft")) continue

            val isPrerelease = release.optBoolean("prerelease")
            if (channel == UpdateChannel.STABLE && isPrerelease) continue

            val tag = release.optString("tag_name").takeIf { it.isNotBlank() } ?: continue
            val versionName = UpdateVersion.releaseVersion(tag) ?: continue
            // Historical v1.1.1-v1.1.3 assets predate the authenticated distribution pipeline.
            if (UpdateVersion.isNewer(FIRST_AUTHENTICATED_VERSION, versionName)) continue
            // The unsigned Releases API parser remains for legacy tests only. OTA uses the
            // signed manifest verifier and the canonical CarPaly-XingyueL-v{version}.apk name.
            val expectedName = legacyApkName(versionName)
            val expectedPage = "https://github.com/$REPOSITORY/releases/tag/$tag"
            if (release.optString("html_url") != expectedPage) continue

            val expectedAssetUrl = "https://github.com/$REPOSITORY/releases/download/$tag/$expectedName"
            val expectedChecksumName = "$expectedName.sha256"
            val expectedChecksumUrl = "$expectedAssetUrl.sha256"
            val assets = release.optJSONArray("assets") ?: continue
            if (assets.length() != 2) continue
            var apkAsset: org.json.JSONObject? = null
            var checksumAsset: org.json.JSONObject? = null
            var hasDuplicateCanonicalAssets = false
            for (assetIndex in 0 until assets.length()) {
                val asset = assets.optJSONObject(assetIndex) ?: continue
                when {
                    asset.optString("name") == expectedName -> {
                        if (asset.optString("browser_download_url") != expectedAssetUrl || apkAsset != null) {
                            hasDuplicateCanonicalAssets = true
                        } else {
                            apkAsset = asset
                        }
                    }
                    asset.optString("name") == expectedChecksumName -> {
                        if (asset.optString("browser_download_url") != expectedChecksumUrl || checksumAsset != null) {
                            hasDuplicateCanonicalAssets = true
                        } else {
                            checksumAsset = asset
                        }
                    }
                }
            }
            if (hasDuplicateCanonicalAssets) continue
            val apk = apkAsset ?: continue
            val checksum = checksumAsset ?: continue
            val digest = sha256Digest.matchEntire(apk.optString("digest"))
                ?.groupValues?.get(1)?.lowercase() ?: continue
            val sizeBytes = apk.optLong("size", -1)
                .takeIf { it > 0L && it <= UpdateApkDownloader.MAX_APK_BYTES } ?: continue
            val checksumSizeBytes = checksum.optLong("size", -1).takeIf { it in 1L..256L } ?: continue

            val candidate = UpdateRelease(
                tagName = tag,
                versionName = versionName,
                apkName = expectedName,
                apkUrl = expectedAssetUrl,
                checksumUrl = expectedChecksumUrl,
                checksumSizeBytes = checksumSizeBytes,
                releasePageUrl = expectedPage,
                releaseNotes = release.optString("body"),
                sizeBytes = sizeBytes,
                isPrerelease = isPrerelease,
                sha256 = digest,
                channel = if (isPrerelease) UpdateChannel.BETA else UpdateChannel.STABLE,
            )
            val current = newestValid
            if (current == null || UpdateVersion.isNewer(candidate.versionName, current.versionName) ||
                (candidate.versionName == current.versionName && current.isPrerelease && !candidate.isPrerelease)) {
                newestValid = candidate
            }
        }
        return newestValid
    }
}
