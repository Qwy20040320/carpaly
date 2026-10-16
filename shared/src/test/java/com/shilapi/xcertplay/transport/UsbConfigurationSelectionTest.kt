package com.shilapi.xcertplay.transport

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class UsbConfigurationSelectionTest {
    @Test fun successfulFirstSwitchDoesNotDetachOrReopen() {
        val outcome = UsbConfigurationSelection.select(6, listOf(1), { true }, { 6 },
            { error("detach must not run") }, { error("reopen must not run") })
        assertNull(outcome)
    }

    @Test fun alreadySelectedConfigurationDoesNotDisturbDriver() {
        val outcome = UsbConfigurationSelection.select(6, listOf(1), { false }, { 6 },
            { error("detach must not run") }, { error("reopen must not run") })!!
        assertFalse(outcome.wrongConfiguration)
        assertEquals(emptyList<Int>(), outcome.detachedInterfaces)
    }

    @Test fun failedSwitchDetachesOnceThenReopensBeforeRetry() {
        val events = mutableListOf<String>()
        var selected = false
        val outcome = UsbConfigurationSelection.select(6, listOf(3, 1, 3), {
            events += "set"
            if (events.count { it == "set" } == 2) selected = true
            selected
        }, { if (selected) 6 else 2 }, { id -> events += "detach:$id"; true },
            { events += "reopen" })!!
        assertEquals(listOf("set", "detach:1", "detach:3", "reopen", "set"), events)
        assertTrue(outcome.selected)
        assertEquals(listOf(1, 3), outcome.detachedInterfaces)
    }

    @Test fun refusedSwitchPreservesFailureForCaller() {
        val outcome = UsbConfigurationSelection.select(6, listOf(1), { false }, { 2 },
            { false }, { error("no claimed interface: must not reopen") })!!
        assertTrue(outcome.wrongConfiguration)
    }
}
