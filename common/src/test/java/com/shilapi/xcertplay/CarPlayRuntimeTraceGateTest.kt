package com.shilapi.xcertplay

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CarPlayRuntimeTraceGateTest {
    @Test fun identicalInsetsAndGeometrySnapshotsAreSuppressedIndependently() {
        val gate = CarPlayRuntimeTraceGate()

        assertTrue(gate.shouldReportInsets("status=true;top=64"))
        assertFalse(gate.shouldReportInsets("status=true;top=64"))
        assertTrue(gate.shouldReportGeometry("viewport=1800x656"))
        assertFalse(gate.shouldReportGeometry("viewport=1800x656"))
        assertTrue(gate.shouldReportInsets("status=false;top=0"))
        assertFalse(gate.shouldReportGeometry("viewport=1800x656"))
    }

    @Test fun playbackTraceEmitsOnlyStateTransitionsAndCanResetForANewSession() {
        val gate = CarPlayPlaybackTransitionGate()

        assertTrue(gate.update(false))
        assertFalse(gate.update(false))
        assertTrue(gate.update(true))
        assertFalse(gate.update(true))
        assertTrue(gate.update(false))
        gate.reset()
        assertTrue(gate.update(false))
    }
}
