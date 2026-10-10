package com.shilapi.xcertplay.update

/** Persistent keys and timing policy for optional launch-time release metadata checks. */
internal object UpdateCheckPolicy {
    internal const val AUTO_CHECK_ENABLED_KEY = "update_auto_check_enabled"
    internal const val LAST_CHECK_AT_KEY = "update_last_check_at"
    internal const val INTERVAL_MILLIS = 24L * 60L * 60L * 1000L

    internal fun isDue(enabled: Boolean, lastCheckAtMillis: Long, nowMillis: Long): Boolean {
        if (!enabled) return false
        if (lastCheckAtMillis <= 0L) return true
        return nowMillis >= lastCheckAtMillis && nowMillis - lastCheckAtMillis >= INTERVAL_MILLIS
    }
}
