package com.shilapi.xcertplay

/** Insets applied to the receiver's video and touch viewport when Android/OEM bars remain visible. */
internal data class CarPlayContentInsets(
    val left: Int = 0,
    val top: Int = 0,
    val right: Int = 0,
    val bottom: Int = 0,
)

/** Combines only visible system bars with display cutouts; overlapping inset sources are not summed. */
internal object CarPlaySystemBarInsets {
    fun resolve(
        statusBarsVisible: Boolean,
        statusBars: CarPlayContentInsets,
        navigationBarsVisible: Boolean,
        navigationBars: CarPlayContentInsets,
        displayCutout: CarPlayContentInsets,
        hiddenStatusBarFallbackTop: Int = 0,
    ): CarPlayContentInsets = CarPlayContentInsets(
        left = maxOf(displayCutout.left, if (statusBarsVisible) statusBars.left else 0,
            if (navigationBarsVisible) navigationBars.left else 0),
        top = maxOf(displayCutout.top, if (statusBarsVisible) statusBars.top else hiddenStatusBarFallbackTop.coerceAtLeast(0),
            if (navigationBarsVisible) navigationBars.top else 0),
        right = maxOf(displayCutout.right, if (statusBarsVisible) statusBars.right else 0,
            if (navigationBarsVisible) navigationBars.right else 0),
        bottom = maxOf(displayCutout.bottom, if (statusBarsVisible) statusBars.bottom else 0,
            if (navigationBarsVisible) navigationBars.bottom else 0),
    )
}
