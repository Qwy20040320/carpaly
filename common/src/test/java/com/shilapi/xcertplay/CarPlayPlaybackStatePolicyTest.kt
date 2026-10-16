package com.shilapi.xcertplay

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CarPlayPlaybackStatePolicyTest {
    @Test fun explicitCarPlayPlaybackEventWinsOverStaleNowPlayingMetadata() {
        assertTrue(CarPlayPlaybackStatePolicy.isPlaying(
            explicitControllerState = true,
            hasNowPlayingState = true,
            nowPlayingState = false,
            audioTrackActive = false,
        ))
        assertFalse(CarPlayPlaybackStatePolicy.isPlaying(
            explicitControllerState = false,
            hasNowPlayingState = true,
            nowPlayingState = true,
            audioTrackActive = true,
        ))
    }

    @Test fun metadataAndTrackActivityAreFallbacksOnlyUntilAnExplicitEventArrives() {
        assertTrue(CarPlayPlaybackStatePolicy.isPlaying(null, true, true, false))
        assertFalse(CarPlayPlaybackStatePolicy.isPlaying(null, true, false, true))
        assertTrue(CarPlayPlaybackStatePolicy.isPlaying(null, false, false, true))
        assertFalse(CarPlayPlaybackStatePolicy.isPlaying(null, false, false, false))
    }
}
