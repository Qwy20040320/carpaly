package com.shilapi.xcertplay.orchestration

/** Avoid reusing the iPhone's stale CarPlay-mode USB enumeration after our own session ended. */
internal object WiredConfigurationAction {
    fun retryModeOnSameNode(
        configurationFound: Boolean,
        carPlayMode: Boolean,
        previousSessionOnNode: Boolean,
        transitionsTried: Int,
    ): Boolean = configurationFound && carPlayMode && previousSessionOnNode && transitionsTried == 0
}
