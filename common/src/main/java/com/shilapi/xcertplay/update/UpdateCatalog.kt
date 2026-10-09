package com.shilapi.xcertplay.update

import org.json.JSONArray

/** The published release that a newer build can be downloaded from. */
internal data class UpdateRelease(
    val tagName: String,
    val apkName: String,
    val apkUrl: String,
    val sha256: String,
)

internal object UpdateCatalog {
    internal const val APK_NAME = "CarPaly-XingyueL.apk"
    private const val RELEASE_DOWNLOAD_PREFIX = "/Qwy20040320/carpaly/releases/download/"
    private val sha256Digest = Regex("^sha256:([0-9a-fA-F]{64})$")

    /** Returns the newest non-draft release only when it carries the canonical APK and digest. */
    internal fun parse(json: String): UpdateRelease? {
        val releases = JSONArray(json)
        for (index in 0 until releases.length()) {
            val release = releases.optJSONObject(index) ?: continue
            if (release.optBoolean("draft")) continue
            val tag = release.optString("tag_name").takeIf { it.isNotBlank() } ?: return null
            val assets = release.optJSONArray("assets") ?: return null
            var apkUrl: String? = null
            var sha256: String? = null
            for (assetIndex in 0 until assets.length()) {
                val asset = assets.optJSONObject(assetIndex) ?: continue
                val name = asset.optString("name")
                if (name != APK_NAME) continue
                val url = asset.optString("browser_download_url")
                val parsedUrl = runCatching { java.net.URL(url) }.getOrNull() ?: continue
                if (parsedUrl.protocol != "https" || parsedUrl.host != "github.com" ||
                    !parsedUrl.path.startsWith(RELEASE_DOWNLOAD_PREFIX)) continue
                apkUrl = url
                sha256 = sha256Digest.find(asset.optString("digest"))?.groupValues?.get(1)?.lowercase()
            }
            if (apkUrl != null && sha256 != null) return UpdateRelease(tag, APK_NAME, apkUrl, sha256)
            // Never fall back to a stale, older release when the newest published entry is invalid.
            return null
        }
        return null
    }
}
