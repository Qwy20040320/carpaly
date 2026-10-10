package com.shilapi.xcertplay

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DiagnosticLogManagerTest {
    @Test fun cleanupEnforcesAgeCountAndTotalSizeWithoutDeletingActiveFile() {
        val directory = Files.createTempDirectory("carpaly-log-retention").toFile()
        try {
            val now = System.currentTimeMillis()
            val active = write(directory, "diplay.log", "active bytes", now - DiagnosticLogManager.RETENTION_MILLIS * 2)
            val olderRecent = write(directory, "previous.log", "0123456789", now - 2_000)
            val newest = write(directory, "previous-2.log", "newer", now - 1_000)
            val expired = write(directory, "crashes.log", "expired", now - DiagnosticLogManager.RETENTION_MILLIS * 2)

            val kept = DiagnosticLogManager.pruneFiles(
                candidates = listOf(active, olderRecent, newest, expired),
                activeFile = active,
                nowMillis = now,
                maxFiles = 2,
                maxTotalBytes = 25,
                retentionMillis = DiagnosticLogManager.RETENTION_MILLIS,
            )

            assertTrue(active.exists())
            assertFalse(expired.exists())
            assertFalse(olderRecent.exists())
            assertTrue(newest.exists())
            assertEquals(listOf(active, newest).map { it.canonicalPath }.toSet(), kept.map { it.canonicalPath }.toSet())
            assertTrue(kept.size <= 2)
            assertTrue(kept.sumOf(File::length) <= 25)
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test fun defaultsMatchPublishedLogManagementLimits() {
        assertEquals(5L * 1024 * 1024, DiagnosticLogManager.MAX_FILE_BYTES)
        assertEquals(50L * 1024 * 1024, DiagnosticLogManager.MAX_TOTAL_BYTES)
        assertEquals(20, DiagnosticLogManager.MAX_FILES)
        assertEquals(7L * 24 * 60 * 60 * 1000, DiagnosticLogManager.RETENTION_MILLIS)
    }

    private fun write(directory: File, name: String, content: String, timestamp: Long): File =
        File(directory, name).apply {
            writeText(content)
            setLastModified(timestamp)
        }
}
