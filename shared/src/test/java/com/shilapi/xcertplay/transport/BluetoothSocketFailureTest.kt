package com.shilapi.xcertplay.transport

import java.io.IOException
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BluetoothSocketFailureTest {
    @Test fun detectsMissingManagerAcrossAndroidVersions() {
        assertTrue(BluetoothSocketFailure.missingSocketManager(NullPointerException("IBluetoothSocketManager is null")))
        assertTrue(BluetoothSocketFailure.missingSocketManager(IOException("bt get socket manager failed")))
        assertTrue(BluetoothSocketFailure.missingSocketManager(IOException("wrapper", IOException("get socket manager failed"))))
    }

    @Test fun ordinaryFailuresStayDistinct() {
        val refused = IOException("connection refused")
        assertFalse(BluetoothSocketFailure.missingSocketManager(refused))
        assertEquals("RFCOMM_CONNECT_FAILED", BluetoothSocketFailure.category(refused))
    }
}
