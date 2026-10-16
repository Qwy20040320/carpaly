package com.shilapi.xcertplay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class CarPlayStartupGateTest {
    private val ready = CarPlayStartupReadiness(
        displayReady = true,
        transportReady = true,
        locationReady = true,
        microphonePermissionResolved = true,
        menuOpen = false,
        handshakeResetInProgress = false,
        displayResizePending = false,
        controllerPresent = false,
    )

    @Test fun reportsEachFirstUnmetStartupPrerequisite() {
        assertEquals("display_surface_unavailable", CarPlayStartupGate.blockingReason(ready.copy(displayReady = false)))
        assertEquals("transport_permission_unresolved", CarPlayStartupGate.blockingReason(ready.copy(transportReady = false)))
        assertEquals("location_permission_unresolved", CarPlayStartupGate.blockingReason(ready.copy(locationReady = false)))
        assertEquals("microphone_permission_unresolved", CarPlayStartupGate.blockingReason(ready.copy(microphonePermissionResolved = false)))
        assertEquals("settings_menu_open", CarPlayStartupGate.blockingReason(ready.copy(menuOpen = true)))
        assertEquals("previous_session_teardown", CarPlayStartupGate.blockingReason(ready.copy(handshakeResetInProgress = true)))
        assertEquals("display_resize_pending", CarPlayStartupGate.blockingReason(ready.copy(displayResizePending = true)))
        assertEquals("controller_already_present", CarPlayStartupGate.blockingReason(ready.copy(controllerPresent = true)))
    }

    @Test fun readyStateHasNoBlockReason() {
        assertNull(CarPlayStartupGate.blockingReason(ready))
    }
}
