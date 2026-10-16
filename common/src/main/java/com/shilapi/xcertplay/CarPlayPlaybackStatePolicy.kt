package com.shilapi.xcertplay

/** Resolves Android MediaSession state without allowing stale Now Playing metadata to override a newer event. */
internal object CarPlayPlaybackStatePolicy {
    fun isPlaying(
        explicitControllerState: Boolean?,
        hasNowPlayingState: Boolean,
        nowPlayingState: Boolean,
        audioTrackActive: Boolean,
    ): Boolean = explicitControllerState
        ?: if (hasNowPlayingState) nowPlayingState else audioTrackActive
}
