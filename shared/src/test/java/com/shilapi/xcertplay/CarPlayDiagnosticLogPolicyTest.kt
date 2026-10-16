package com.shilapi.xcertplay

import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CarPlayDiagnosticLogPolicyTest {
    @Test fun safeMessageRedactsIdentifiersBeforeItCanReachLogcat() {
        val safe = CarPlayDiagnosticLogPolicy.safeMessage(
            "connected peer=C0:A6:00:29:58:0A ip=192.168.31.71",
        )

        assertNotNull(safe)
        assertTrue(safe!!.contains("connected"))
        assertFalse(safe.contains("C0:A6:00:29:58:0A"))
        assertFalse(safe.contains("192.168.31.71"))
    }

    @Test fun privatePhoneAndProtocolTraceLinesAreRejected() {
        assertNull(CarPlayDiagnosticLogPolicy.safeMessage("PHONE iap2d private details"))
        assertNull(CarPlayDiagnosticLogPolicy.safeMessage("TRACE iAP2 payload=private"))
    }

    @Test fun failureDetailsAreSanitizedAndDoNotIncludeStackTrace() {
        val safe = CarPlayDiagnosticLogPolicy.safeFailure(
            "USB open failed",
            IllegalStateException("peer=C0:A6:00:29:58:0A ip=192.168.31.71"),
        )

        assertNotNull(safe)
        assertTrue(safe!!.contains("error=IllegalStateException"))
        assertFalse(safe.contains("C0:A6:00:29:58:0A"))
        assertFalse(safe.contains("192.168.31.71"))
    }

    @Test fun credentialBearingFailureIsNotLogged() {
        assertNull(CarPlayDiagnosticLogPolicy.safeFailure(
            "authentication failed",
            IllegalStateException("pairRecord=private"),
        ))
    }
}
