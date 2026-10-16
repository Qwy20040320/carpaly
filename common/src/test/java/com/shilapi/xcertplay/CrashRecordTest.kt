package com.shilapi.xcertplay

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CrashRecordTest {
    @Test fun doesNotPersistExceptionMessage() {
        val error = IllegalStateException("VIN-LIKE-PRIVATE-PAYLOAD")
        val record = CrashRecord.format("main", error, 123L)
        assertTrue(record.contains("IllegalStateException"))
        assertTrue(record.contains("atEpochMs=123"))
        assertFalse(record.contains("VIN-LIKE-PRIVATE-PAYLOAD"))
    }
}
