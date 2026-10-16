package com.shilapi.xcertplay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class VpnConsentLaunchGuardTest {
    @Test
    fun launchesTheConsentIntentWithoutChangingItsContents() {
        val consent = "vpn-consent-intent"
        var launched: String? = null
        var unavailableCalls = 0

        val result = VpnConsentLaunchGuard.launch(
            input = consent,
            launch = { launched = it },
            onUnavailable = { unavailableCalls++ },
        )

        assertTrue(result)
        assertEquals(consent, launched)
        assertEquals(0, unavailableCalls)
    }

    @Test
    fun reportsMissingSystemConsentActivityWithoutSwallowingOrBypassingConsent() {
        var unavailableCalls = 0

        val result = VpnConsentLaunchGuard.launch(
            input = "vpn-consent-intent",
            launch = { throw MissingActivityException() },
            onUnavailable = { unavailableCalls++ },
            isUnavailable = { it is MissingActivityException },
        )

        assertFalse(result)
        assertEquals(1, unavailableCalls)
    }

    @Test
    fun propagatesUnrelatedLaunchFailures() {
        var unavailableCalls = 0
        try {
            VpnConsentLaunchGuard.launch(
                input = "vpn-consent-intent",
                launch = { throw IllegalStateException("unrelated launch failure") },
                onUnavailable = { unavailableCalls++ },
                isUnavailable = { it is MissingActivityException },
            )
            throw AssertionError("Expected unrelated failure to be rethrown")
        } catch (_: IllegalStateException) {
            assertEquals(0, unavailableCalls)
        }
    }

    private class MissingActivityException : RuntimeException()
}
