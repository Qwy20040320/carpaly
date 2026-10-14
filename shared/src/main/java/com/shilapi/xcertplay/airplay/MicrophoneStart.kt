package com.shilapi.xcertplay.airplay

import java.util.concurrent.Future
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/** Starts a microphone at most once, even for input-only streams with no downlink audio. */
internal class MicrophoneStart(private val start: () -> Unit) {
    private val claimed = AtomicBoolean()
    @Volatile private var silentStart: Future<*>? = null

    fun onDownlink() {
        silentStart?.cancel(false)
        if (claimed.compareAndSet(false, true)) start()
    }

    fun scheduleSilentStart(
        scheduler: ScheduledExecutorService,
        delayMillis: Long,
        whileCurrent: (startNow: () -> Boolean) -> Unit,
    ) {
        silentStart = scheduler.schedule({
            whileCurrent {
                if (claimed.compareAndSet(false, true)) {
                    start()
                    true
                } else false
            }
        }, delayMillis, TimeUnit.MILLISECONDS)
    }

    companion object {
        const val SILENT_START_MILLIS = 500L
        fun startsWithoutDownlink(audioType: String): Boolean = audioType != "telephony"
    }
}
