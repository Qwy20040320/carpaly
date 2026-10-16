package com.shilapi.xcertplay.transport

/** Pure decision boundary for an Android USB configuration switch blocked by a kernel driver. */
internal object UsbConfigurationSelection {
    data class Outcome(
        val target: Int,
        val selected: Boolean,
        val before: Int?,
        val after: Int?,
        val detachedInterfaces: List<Int>,
    ) {
        val wrongConfiguration: Boolean get() = after != null && after != target
        fun diagnostic(): String =
            "USB configuration target=$target selected=$selected before=${before ?: "unknown"} " +
                "after=${after ?: "unknown"} detached=$detachedInterfaces"
    }

    /**
     * Only a failed first switch attempts forced claims. A successful claim stays held until
     * [reopen] closes and reopens the connection; releaseInterface would reattach the driver.
     */
    fun select(
        target: Int,
        interfaceIds: List<Int>,
        setConfiguration: () -> Boolean,
        activeConfiguration: () -> Int?,
        detach: (Int) -> Boolean,
        reopen: () -> Unit,
    ): Outcome? {
        if (setConfiguration()) return null
        val before = activeConfiguration()
        if (before == target) return Outcome(target, false, before, before, emptyList())
        val detached = interfaceIds.distinct().sorted().filter(detach)
        if (detached.isNotEmpty()) reopen()
        val selected = setConfiguration()
        return Outcome(target, selected, before, activeConfiguration(), detached)
    }
}
