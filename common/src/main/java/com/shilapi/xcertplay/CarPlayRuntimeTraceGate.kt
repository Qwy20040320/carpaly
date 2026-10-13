package com.shilapi.xcertplay

/** Suppresses repeated diagnostic snapshots without affecting receiver behavior. */
internal class CarPlayRuntimeTraceGate {
    private var lastInsets: String? = null
    private var lastGeometry: String? = null

    fun shouldReportInsets(snapshot: String): Boolean {
        if (snapshot == lastInsets) return false
        lastInsets = snapshot
        return true
    }

    fun shouldReportGeometry(snapshot: String): Boolean {
        if (snapshot == lastGeometry) return false
        lastGeometry = snapshot
        return true
    }
}

/** Reports source playback transitions once; it never sends a media command or changes focus. */
internal class CarPlayPlaybackTransitionGate {
    private var lastPlaying: Boolean? = null

    fun update(playing: Boolean): Boolean {
        if (playing == lastPlaying) return false
        lastPlaying = playing
        return true
    }

    fun reset() {
        lastPlaying = null
    }
}
