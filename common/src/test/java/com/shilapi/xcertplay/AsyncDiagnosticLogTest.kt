package com.shilapi.xcertplay

import java.nio.file.Files
import org.junit.Assert.*
import org.junit.Test

class AsyncDiagnosticLogTest {
    @Test fun sessionLoggerWritesUntilItIsClosed() {
        val folder = Files.createTempDirectory("diplay-session-log").toFile()
        val file = folder.resolve("diplay.log")
        try {
            SessionLogFile(file).use { log ->
                log.reset("header")
                log.append("recorded diagnostic")
                assertTrue(file.readText().contains("recorded diagnostic"))
            }
            val closedContents = file.readText()
            SessionLogFile(file).apply { close(); append("ignored after close") }
            assertEquals(closedContents, file.readText())
        } finally {
            folder.deleteRecursively()
        }
    }

    @Test fun queuedEvidenceIsRedactedAndTimestampedBeforeUsingItsCapturedFileTarget() {
        val folder = Files.createTempDirectory("diplay-async-log").toFile()
        val old = SessionLogFile(folder.resolve("old.log"))
        val current = SessionLogFile(folder.resolve("current.log"))
        try {
            old.reset("old session"); current.reset("current session")
            AsyncDiagnosticLog.append(old, "CONNECTION_DIAGNOSTIC attempt=1 teardown end elapsedMs=117", 0)
            AsyncDiagnosticLog.append(old, "Microphone: start type=telephony codec=OPUS peer=192.168.49.1", 0)
            AsyncDiagnosticLog.append(old, "CONNECTION_DIAGNOSTIC token=private-token", 0)
            AsyncDiagnosticLog.append(old, "Microphone: payload=private-audio", 0)
            assertTrue(AsyncDiagnosticLog.awaitIdle(2_000))
            val evidence = old.file.readText()
            assertTrue(evidence.contains("teardown end elapsedMs=117"))
            assertTrue(evidence.contains("Microphone: start type=telephony codec=OPUS peer=[ip]"))
            assertFalse(evidence.contains("192.168.49.1"))
            assertFalse(evidence.contains("private-token")); assertFalse(evidence.contains("private-audio"))
            assertFalse(current.file.readText().contains("teardown end"))
            assertEquals(4, evidence.lineSequence().count())
        } finally {
            old.close(); current.close(); folder.deleteRecursively()
        }
    }

    @Test fun structuredEventsKeepStableFieldsAndRedactIdentifiers() {
        val line = DiagnosticEventFormatter.format(
            timestamp = "2026-10-15T09:10:11.123+0800",
            level = "WARN",
            module = "WIRELESS",
            thread = "CarPlay-Worker",
            runId = "r123456789abc",
            sessionId = "cp00001",
            eventId = 42,
            faultId = "F00000042",
            event = "RFCOMM_CONNECT_FAILED",
            result = "FAILED",
            state = "RETRY_PENDING",
            reason = "CONNECT_TIMEOUT",
            recovery = "RETRY_SCHEDULED",
            detail = "peerMac=aa:bb:cc:dd:ee:ff elapsedMs=1200",
        )!!

        assertTrue(line.contains("ts=2026-10-15T09:10:11.123+0800"))
        assertTrue(line.contains("level=WARN module=WIRELESS thread=CarPlay-Worker"))
        assertTrue(line.contains("run=r123456789abc session=cp00001 eventId=E00000042 faultId=F00000042"))
        assertTrue(line.contains("event=RFCOMM_CONNECT_FAILED result=FAILED state=RETRY_PENDING"))
        assertFalse(line.contains("aa:bb:cc:dd:ee:ff"))
        assertTrue(line.contains("_address_"))
    }

    @Test fun structuredEventsRejectSecretBearingDetails() {
        assertEquals(null, DiagnosticEventFormatter.format(
            timestamp = "2026-10-15T09:10:11.123+0800", level = "INFO", module = "UPDATE",
            thread = "main", runId = "r123", sessionId = "none", eventId = 1, faultId = "none",
            event = "CHECK", result = "OBSERVED", state = "CHECKING", reason = "none", recovery = "none",
            detail = "token=must-not-appear",
        ))
    }

    @Test fun runtimeLogRotationIsSeparateAndBothFamiliesFitTheRetentionBudget() {
        val folder = Files.createTempDirectory("diplay-runtime-log").toFile()
        val file = folder.resolve("app-runtime.log")
        try {
            val log = SessionLogFile(file, maxFileBytes = 40)
            log.append("first-event-record")
            log.append("second-event-record")
            log.append("third-event-record")
            assertTrue(folder.resolve("app-runtime-previous.log").isFile)
            assertFalse(folder.resolve("previous.log").exists())
            assertTrue(SessionLogFile.REPORT_NAMES.contains("app-runtime.log"))
            assertTrue(SessionLogFile.MAX_RETAINED_LOG_BYTES <= 6 * 1024 * 1024L)
            log.close()
        } finally {
            folder.deleteRecursively()
        }
    }

    @Test fun duplicateLegacyEventsAreRateLimitedAndSummarizedWithoutGrowingTheKeySet() {
        val gate = DiagnosticRepeatGate(windowMillis = 2_000, maxKeys = 2)
        assertEquals(DiagnosticRepeatGate.Decision.Emit(0), gate.observe("same", 100))
        assertEquals(DiagnosticRepeatGate.Decision.Suppress, gate.observe("same", 500))
        assertEquals(DiagnosticRepeatGate.Decision.Suppress, gate.observe("same", 1_000))
        assertEquals(DiagnosticRepeatGate.Decision.Emit(2), gate.observe("same", 2_100))
        assertEquals(DiagnosticRepeatGate.Decision.Emit(0), gate.observe("other", 2_200))
        assertEquals(DiagnosticRepeatGate.Decision.Emit(0), gate.observe("third", 2_300))
        assertEquals(DiagnosticRepeatGate.Decision.Emit(0), gate.observe("same", 2_400))
    }
}
