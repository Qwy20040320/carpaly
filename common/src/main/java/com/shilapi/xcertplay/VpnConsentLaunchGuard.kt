package com.shilapi.xcertplay

import android.content.ActivityNotFoundException

/** Keeps a ROM without the VPN approval activity from crashing the CarPlay host. */
internal object VpnConsentLaunchGuard {
    /** Returns false only when Android's consent intent has no launchable activity. */
    fun <T> launch(
        input: T,
        launch: (T) -> Unit,
        onUnavailable: () -> Unit,
        isUnavailable: (RuntimeException) -> Boolean = { it is ActivityNotFoundException },
    ): Boolean = try {
        launch(input)
        true
    } catch (failure: RuntimeException) {
        if (isUnavailable(failure)) {
            onUnavailable()
            false
        } else {
            throw failure
        }
    }
}
