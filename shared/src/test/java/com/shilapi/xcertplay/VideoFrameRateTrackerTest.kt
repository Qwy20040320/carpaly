package com.shilapi.xcertplay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class VideoFrameRateTrackerTest {
    @Test fun rateComesFromRecentRenderedFrameTimestampsAndExpiresWithoutFrames() {
        VideoFrameRateTracker.reset()
        try {
            VideoFrameRateTracker.recordFrame(1_000)
            VideoFrameRateTracker.recordFrame(1_016)
            VideoFrameRateTracker.recordFrame(1_032)
            assertEquals(62.5, VideoFrameRateTracker.currentFps(1_032)!!, 0.001)
            assertNull(VideoFrameRateTracker.currentFps(3_000))
        } finally {
            VideoFrameRateTracker.reset()
        }
    }
}
