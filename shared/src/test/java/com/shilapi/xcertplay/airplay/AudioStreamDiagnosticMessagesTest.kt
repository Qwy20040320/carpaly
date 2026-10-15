package com.shilapi.xcertplay.airplay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class AudioStreamDiagnosticMessagesTest {
    @Test
    fun decryptFailureReportsOnlyPacketMetadata() {
        val message = AudioStreamDiagnosticMessages.decryptFailure(
            streamType = 100,
            packetNumber = 1,
            wireBytes = 84,
            errorType = "AEADBadTagException",
        )

        assertEquals(
            "audio stream type=100 first decrypt failure packet=1 wireBytes=84 error=AEADBadTagException",
            message,
        )
        assertFalse(message.contains("payload"))
        assertFalse(message.contains("wire="))
    }

    @Test
    fun decryptedPacketReportsLengthsWithoutLoggingAudioContent() {
        val message = AudioStreamDiagnosticMessages.decryptedPacket(
            streamType = 100,
            packetNumber = 1,
            sample = 48_000,
            wireBytes = 84,
            payloadBytes = 48,
        )

        assertEquals(
            "audio stream type=100 packet=1 sample=48000 wireBytes=84 payloadBytes=48",
            message,
        )
        assertFalse(message.contains("payloadHead"))
        assertFalse(message.contains("hex"))
    }
}
