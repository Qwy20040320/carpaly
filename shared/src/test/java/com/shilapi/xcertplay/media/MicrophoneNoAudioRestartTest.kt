package com.shilapi.xcertplay.media

import android.Manifest
import android.media.AudioRecord
import com.shilapi.xcertplay.airplay.MicrophoneConfig
import java.net.InetAddress
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.atomic.AtomicInteger
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowAudioRecord

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [25, 29], manifest = Config.NONE)
class MicrophoneNoAudioRestartTest {
    private val diagnostics = CopyOnWriteArrayList<String>()
    private val reads = AtomicInteger()
    private var uplink: MicrophoneUplink? = null

    @Before fun setUp() {
        shadowOf(RuntimeEnvironment.getApplication()).grantPermissions(Manifest.permission.RECORD_AUDIO)
    }

    @After fun tearDown() {
        uplink?.close()
        ShadowAudioRecord.clearSource()
    }

    @Test fun zeroByteRecorderRestartsAtMostThreeTimesWithoutBusyLoop() {
        provide { 0 }
        start()
        Thread.sleep(650)
        val restarts = diagnostics.filter { it.startsWith("Microphone: recording restarted") }
        assertEquals(diagnostics.joinToString("\n"), 3, restarts.size)
        assertTrue(restarts.all { "reason=no-audio" in it })
        assertTrue("reads=${reads.get()}", reads.get() < 300)
    }

    @Test fun validSilentPcmDoesNotTriggerRestart() {
        provide { size -> Thread.sleep(5); size }
        start()
        Thread.sleep(250)
        assertTrue(diagnostics.joinToString("\n"),
            diagnostics.none { it.startsWith("Microphone: recording restarted") })
    }

    private fun provide(read: (Int) -> Int) {
        ShadowAudioRecord.setSourceProvider { _ ->
            object : ShadowAudioRecord.AudioRecordSource {
                override fun readInByteArray(buffer: ByteArray, offset: Int, size: Int, blocking: Boolean): Int {
                    reads.incrementAndGet()
                    return read(size)
                }
            }
        }
    }

    private fun start() {
        val next = MicrophoneUplink(config(), onDiagnostic = diagnostics::add, noAudioRestartMillis = 50)
        uplink = next
        assertTrue(next.start())
    }

    private fun config() = MicrophoneConfig(
        audioType = "speechrecognition",
        sampleRate = 16_000,
        channels = 1,
        payloadType = 100,
        frameMillis = 20,
        host = InetAddress.getLoopbackAddress(),
        port = 9,
        key = ByteArray(32),
    )
}
