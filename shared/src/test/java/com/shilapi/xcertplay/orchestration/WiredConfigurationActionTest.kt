package com.shilapi.xcertplay.orchestration

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WiredConfigurationActionTest {
    @Test fun staleCarPlayModeRequestsOneTransition() {
        assertTrue(WiredConfigurationAction.retryModeOnSameNode(true, true, true, 0))
        assertFalse(WiredConfigurationAction.retryModeOnSameNode(true, true, true, 1))
    }

    @Test fun otherUsbConfigurationsAreReused() {
        assertFalse(WiredConfigurationAction.retryModeOnSameNode(true, false, true, 0))
        assertFalse(WiredConfigurationAction.retryModeOnSameNode(true, true, false, 0))
        assertFalse(WiredConfigurationAction.retryModeOnSameNode(false, true, true, 0))
    }
}
