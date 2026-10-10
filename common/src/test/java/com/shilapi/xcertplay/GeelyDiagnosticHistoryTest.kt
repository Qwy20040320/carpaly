package com.shilapi.xcertplay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [29])
class GeelyDiagnosticHistoryTest {
    @Test fun eventRecordsHaveUtcTimestampModuleSeverityAndSessionCorrelation() {
        val context = RuntimeEnvironment.getApplication()
        DiagnosticLogManager.setEnabled(context, true)
        GeelyDiagnosticHistory.clear(context)
        GeelyDiagnosticHistory.append(context, "USB attached VID=0x05AC", "device_attached", "usb", "INFO", "session-123")
        val event = GeelyDiagnosticHistory.read(context).single()
        assertTrue(event.getString("timestamp").matches(Regex("\\d{4}-\\d{2}-\\d{2}T.*Z")))
        assertEquals("device_attached", event.getString("event_type"))
        assertEquals("usb", event.getString("module"))
        assertEquals("INFO", event.getString("severity"))
        assertEquals("session-123", event.getString("correlation_session_id"))
    }

    @Test fun sensitiveMessageIsDroppedAndPrivateAddressIsRedacted() {
        val context = RuntimeEnvironment.getApplication()
        DiagnosticLogManager.setEnabled(context, true)
        GeelyDiagnosticHistory.clear(context)
        GeelyDiagnosticHistory.append(context, "password=hunter2", module = "network")
        GeelyDiagnosticHistory.append(context, "network disconnected ip=192.168.1.4", module = "network")
        val events = GeelyDiagnosticHistory.read(context)
        assertEquals(1, events.size)
        assertTrue(events.single().getString("message").contains("[ip]"))
        assertTrue(!events.single().getString("message").contains("192.168.1.4"))
    }

    @Test fun loggingDefaultsOffAndManualStatePersistsAcrossAppReads() {
        val context = RuntimeEnvironment.getApplication()
        DiagnosticLogManager.setEnabled(context, false)
        GeelyDiagnosticHistory.clear(context)

        assertEquals(false, DiagnosticLogManager.isEnabled(context))
        GeelyDiagnosticHistory.append(context, "must not be recorded", module = "diagnostic")
        assertTrue(GeelyDiagnosticHistory.read(context).isEmpty())

        DiagnosticLogManager.setEnabled(context, true)
        assertEquals(true, DiagnosticLogManager.isEnabled(context))
        GeelyDiagnosticHistory.append(context, "opt-in event", module = "diagnostic")
        DiagnosticLogManager.setEnabled(context, false)
        GeelyDiagnosticHistory.append(context, "must not follow opt-out", module = "diagnostic")

        assertEquals(1, GeelyDiagnosticHistory.read(context).size)
        assertEquals("opt-in event", GeelyDiagnosticHistory.read(context).single().getString("message"))
    }
}
