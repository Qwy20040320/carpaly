package com.shilapi.xcertplay.airplay

import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MicrophoneStartTest {
    @Test fun downlinkStartsOnlyOnce() {
        val starts = AtomicInteger()
        val microphone = MicrophoneStart { starts.incrementAndGet() }
        microphone.onDownlink()
        microphone.onDownlink()
        assertEquals(1, starts.get())
    }

    @Test fun inputOnlyStreamStartsWithoutDownlink() {
        val scheduler = Executors.newSingleThreadScheduledExecutor()
        try {
            val starts = AtomicInteger()
            val microphone = MicrophoneStart { starts.incrementAndGet() }
            microphone.scheduleSilentStart(scheduler, 0) { it() }
            scheduler.shutdown()
            assertTrue(scheduler.awaitTermination(2, TimeUnit.SECONDS))
            microphone.onDownlink()
            assertEquals(1, starts.get())
        } finally {
            scheduler.shutdownNow()
        }
    }

    @Test fun callsWaitForDownlink() {
        assertFalse(MicrophoneStart.startsWithoutDownlink("telephony"))
        assertTrue(MicrophoneStart.startsWithoutDownlink("speechrecognition"))
    }
}
