package com.shilapi.xcertplay

import android.os.SystemClock
import java.util.ArrayDeque

/** Measured renderer callbacks, distinct from the selected stream-rate preference. */
object VideoFrameRateTracker {
    private val frameTimes = ArrayDeque<Long>()

    @Synchronized
    fun recordFrame(elapsedRealtime: Long) {
        frameTimes.addLast(elapsedRealtime)
        while (frameTimes.peekFirst()?.let { elapsedRealtime - it > 2_000 } == true) frameTimes.removeFirst()
    }

    @Synchronized
    fun currentFps(nowElapsedRealtime: Long = SystemClock.elapsedRealtime()): Double? {
        while (frameTimes.peekFirst()?.let { nowElapsedRealtime - it > 2_000 } == true) frameTimes.removeFirst()
        if (frameTimes.size < 2) return null
        val first = frameTimes.peekFirst() ?: return null
        val last = frameTimes.peekLast() ?: return null
        if (nowElapsedRealtime - last > 1_500) return null
        val span = (last - first).coerceAtLeast(1L)
        return (frameTimes.size - 1) * 1_000.0 / span
    }

    @Synchronized
    fun reset() = frameTimes.clear()
}
