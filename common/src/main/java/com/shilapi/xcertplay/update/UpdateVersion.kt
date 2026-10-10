package com.shilapi.xcertplay.update

internal object UpdateVersion {
    private val VERSION = Regex("^v?(\\d+)\\.(\\d+)\\.(\\d+)(?:[-+][0-9A-Za-z.-]+)?$")
    private val RELEASE_TAG = Regex("^v(\\d+\\.\\d+\\.\\d+)$")

    internal fun parse(value: String): Triple<Int, Int, Int>? {
        val match = VERSION.matchEntire(value.trim()) ?: return null
        val major = match.groupValues[1].toIntOrNull() ?: return null
        val minor = match.groupValues[2].toIntOrNull() ?: return null
        val patch = match.groupValues[3].toIntOrNull() ?: return null
        return Triple(major, minor, patch)
    }

    /** Only plain vX.Y.Z tags are valid release identifiers; suffixes remain APK-only legacy data. */
    internal fun releaseVersion(tag: String): String? =
        RELEASE_TAG.matchEntire(tag)?.groupValues?.get(1)?.takeIf { parse(it) != null }

    internal fun isNewer(remote: String, installed: String): Boolean {
        val target = parse(remote) ?: return false
        val current = parse(installed) ?: return true
        if (target.first != current.first) return target.first > current.first
        if (target.second != current.second) return target.second > current.second
        return target.third > current.third
    }
}
