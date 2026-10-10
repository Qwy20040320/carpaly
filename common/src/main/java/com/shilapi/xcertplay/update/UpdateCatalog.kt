package com.shilapi.xcertplay.update

import org.json.JSONArray

internal enum class UpdateChannel {
    PREVIEW,
    STABLE;

    companion object {
        internal fun fromPreference(value: String?): UpdateChannel =
            entries.firstOrNull { it.name.equals(value, ignoreCase = true) } ?: PREVIEW
    }
}

/** The published CarPaly release that a newer build can be downloaded from. */
internal data class UpdateRelease(
    val tagName: String,
    val versionName: String,
    val apkName: String,
    val apkUrl: String,
    val releasePageUrl: String,
    val releaseNotes: String,
    val sizeBytes: Long,
    val isPrerelease: Boolean,
    val sha256: String,
)

internal object UpdateCatalog {
    private const val REPOSITORY = "Qwy20040320/carpaly"
    private val sha256Digest = Regex("^sha256:([0-9a-fA-F]{64})$")

    internal fun apkName(versionName: String): String = "CarPaly-XingyueL$versionName.apk"

    /** Returns the newest valid release allowed by [channel], skipping drafts and malformed assets. */
    internal fun parse(json: String, channel: UpdateChannel = UpdateChannel.PREVIEW): UpdateRelease? {
        val releases = JSONArray(json)
        var newestValid: UpdateRelease? = null
        for (index in 0 until releases.length()) {
            val release = releases.optJSONObject(index) ?: continue
            if (release.optBoolean("draft")) continue

            val isPrerelease = release.optBoolean("prerelease")
            if (channel == UpdateChannel.STABLE && isPrerelease) continue

            val tag = release.optString("tag_name").takeIf { it.isNotBlank() } ?: continue
            val versionName = UpdateVersion.releaseVersion(tag) ?: continue
            val expectedName = apkName(versionName)
            val expectedPage = "https://github.com/$REPOSITORY/releases/tag/$tag"
            if (release.optString("html_url") != expectedPage) continue

            val expectedAssetUrl = "https://github.com/$REPOSITORY/releases/download/$tag/$expectedName"
            val assets = release.optJSONArray("assets") ?: continue
            for (assetIndex in 0 until assets.length()) {
                val asset = assets.optJSONObject(assetIndex) ?: continue
                if (asset.optString("name") != expectedName ||
                    asset.optString("browser_download_url") != expectedAssetUrl) continue
                val digest = sha256Digest.matchEntire(asset.optString("digest"))
                    ?.groupValues?.get(1)?.lowercase() ?: continue
                val sizeBytes = asset.optLong("size", -1).takeIf { it > 0 } ?: continue

                val candidate = UpdateRelease(
                    tagName = tag,
                    versionName = versionName,
                    apkName = expectedName,
                    apkUrl = expectedAssetUrl,
                    releasePageUrl = expectedPage,
                    releaseNotes = release.optString("body"),
                    sizeBytes = sizeBytes,
                    isPrerelease = isPrerelease,
                    sha256 = digest,
                )
                val current = newestValid
                if (current == null || UpdateVersion.isNewer(candidate.versionName, current.versionName) ||
                    (candidate.versionName == current.versionName && current.isPrerelease && !candidate.isPrerelease)) {
                    newestValid = candidate
                }
            }
        }
        return newestValid
    }
}
