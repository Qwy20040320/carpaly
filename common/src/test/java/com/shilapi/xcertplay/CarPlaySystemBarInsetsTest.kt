package com.shilapi.xcertplay

import org.junit.Assert.assertEquals
import org.junit.Test

class CarPlaySystemBarInsetsTest {
    @Test fun hiddenBarsDoNotInsetReceiverViewport() {
        assertEquals(
            CarPlayContentInsets(),
            CarPlaySystemBarInsets.resolve(
                statusBarsVisible = false,
                statusBars = CarPlayContentInsets(top = 48),
                navigationBarsVisible = false,
                navigationBars = CarPlayContentInsets(bottom = 32),
                displayCutout = CarPlayContentInsets(),
            ),
        )
    }

    @Test fun visibleBarsInsetViewportAndCutoutIsAlwaysRespected() {
        assertEquals(
            CarPlayContentInsets(left = 12, top = 48, right = 10, bottom = 32),
            CarPlaySystemBarInsets.resolve(
                statusBarsVisible = true,
                statusBars = CarPlayContentInsets(top = 48),
                navigationBarsVisible = true,
                navigationBars = CarPlayContentInsets(left = 12, right = 10, bottom = 32),
                displayCutout = CarPlayContentInsets(left = 6, top = 20, right = 10),
            ),
        )
    }

    @Test fun overlappingInsetSourcesUseTheLargestInsetInsteadOfAddingThem() {
        assertEquals(
            CarPlayContentInsets(top = 48, bottom = 28),
            CarPlaySystemBarInsets.resolve(
                statusBarsVisible = true,
                statusBars = CarPlayContentInsets(top = 48),
                navigationBarsVisible = true,
                navigationBars = CarPlayContentInsets(top = 24, bottom = 28),
                displayCutout = CarPlayContentInsets(top = 18),
            ),
        )
    }
}
