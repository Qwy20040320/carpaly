package com.shilapi.xcertplay

import java.nio.file.Files
import org.junit.Assert.*
import org.junit.Test

class AsyncDiagnosticLogTest {
    @Test fun sessionLoggerStartsDisabledAndHonorsLiveToggleWithoutRecreation() {
        val folder = Files.createTempDirectory("diplay-toggle-log").toFile()
        val file = folder.resolve("diplay.log")
        var enabled = false
        try {
            SessionLogFile(file, loggingEnabled = { enabled }).use { log ->
                log.reset("header")
                log.append("not recorded")
                assertFalse(file.exists())

                enabled = true
                log.append("recorded after opt-in")
                assertTrue(file.readText().contains("recorded after opt-in"))

                enabled = false
                log.append("not recorded after opt-out")
                assertFalse(file.readText().contains("not recorded after opt-out"))
            }
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
}
