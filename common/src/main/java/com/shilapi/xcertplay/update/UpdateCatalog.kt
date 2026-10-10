package com.shilapi.xcertplay.update

import org.json.JSONArray

/** The published release that a newer build can be downloaded from. */
internal data class UpdateRelease(
    val tagName: String,
    val apkName: String,
    val apkUrl: String,
    val releasePageUrl: String,
    val releaseNotes: String,
    val sizeBytes: Long,
    val isPrerelease: Boolean,
    val sha256: String,
)

internal object UpdateCatalog {
    internal const val APK_NAME = "CarPaly-XingyueL.apk"
    private const val RELEASE_DOWNLOAD_PREFIX = "/Qwy20040320/carpaly/releases/download/"
    private const val RELEASE_PAGE_PREFIX = "/Qwy20040320/carpaly/releases/tag/"
    private val sha256Digest = Regex("^sha256:([0-9a-fA-F]{64})$")

    /** Returns the newest non-draft release only when it carries the canonical APK and digest. */
    internal fun parse(json: String): UpdateRelease? {
        val releases = JSONArray(json)
        for (index in 0 until releases.length()) {
            val release = releases.optJSONObject(index) ?: continue
            if (release.optBoolean("draft")) continue
            val tag = release.optString("tag_name").takeIf { it.isNotBlank() } ?: return null
            val releasePageUrl = release.optString("html_url")
            val parsedPageUrl = runCatching { java.net.URL(releasePageUrl) }.getOrNull() ?: return null
            if (parsedPageUrl.protocol != "https" || parsedPageUrl.host != "github.com" ||
                parsedPageUrl.path != "$RELEASE_PAGE_PREFIX$tag") return null
            val assets = release.optJSONArray("assets") ?: return null
            var apkUrl: String? = null
            var sha256: String? = null
            var sizeBytes: Long? = null
            for (assetIndex in 0 until assets.length()) {
                val asset = assets.optJSONObject(assetIndex) ?: continue
                val name = asset.optString("name")
                if (name != APK_NAME) continue
                val url = asset.optString("browser_download_url")
                val parsedUrl = runCatching { java.net.URL(url) }.getOrNull() ?: continue
                if (parsedUrl.protocol != "https" || parsedUrl.host != "github.com" ||
                    parsedUrl.path != "$RELEASE_DOWNLOAD_PREFIX$tag/$APK_NAME") continue
                apkUrl = url
                sha256 = sha256Digest.find(asset.optString("digest"))?.groupValues?.get(1)?.lowercase()
                sizeBytes = asset.optLong("size").takeIf { it > 0 }
            }
            if (apkUrl != null && sha256 != null && sizeBytes != null) {
                return UpdateRelease(
                    tagName = tag,
                    apkName = APK_NAME,
                    apkUrl = apkUrl,
                    releasePageUrl = releasePageUrl,
                    releaseNotes = release.optString("body"),
                    sizeBytes = sizeBytes,
                    isPrerelease = release.optBoolean("prerelease"),
                    sha256 = sha256,
                )
            }
            // Never fall back to a stale, older release when the newest published entry is invalid.
            return null
        }
        return null
    }
}
