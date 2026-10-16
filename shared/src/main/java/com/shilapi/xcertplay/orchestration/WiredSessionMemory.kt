package com.shilapi.xcertplay.orchestration

/** A USB node on which this process already started a wired CarPlay session. */
internal object WiredSessionMemory {
    @Volatile private var lastStartedNode: String? = null

    fun started(deviceName: String) { lastStartedNode = deviceName }
    fun startedOn(deviceName: String): Boolean = lastStartedNode == deviceName
    internal fun clear() { lastStartedNode = null }
}
