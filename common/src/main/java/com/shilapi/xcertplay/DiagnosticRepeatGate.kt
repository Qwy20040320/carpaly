package com.shilapi.xcertplay

/** Suppresses only byte-for-byte repeated, already-redacted diagnostic lines within a short window. */
internal class DiagnosticRepeatGate(
    private val windowMillis: Long = DEFAULT_WINDOW_MILLIS,
    private val maxKeys: Int = DEFAULT_MAX_KEYS,
) {
    private data class State(var lastEmittedAtMillis: Long, var suppressed: Int = 0)
    private val states = LinkedHashMap<String, State>(maxKeys, 0.75f, true)

    init {
        require(windowMillis >= 0)
        require(maxKeys > 0)
    }

    @Synchronized
    fun observe(key: String, nowMillis: Long): Decision {
        val state = states[key]
        if (state == null) {
            states[key] = State(nowMillis)
            trim()
            return Decision.Emit(suppressedSincePrevious = 0)
        }
        if (nowMillis - state.lastEmittedAtMillis < windowMillis) {
            state.suppressed++
            return Decision.Suppress
        }
        val suppressed = state.suppressed
        state.lastEmittedAtMillis = nowMillis
        state.suppressed = 0
        return Decision.Emit(suppressed)
    }

    private fun trim() {
        while (states.size > maxKeys) states.entries.iterator().run {
            next()
            remove()
        }
    }

    sealed interface Decision {
        data object Suppress : Decision
        data class Emit(val suppressedSincePrevious: Int) : Decision
    }

    private companion object {
        const val DEFAULT_WINDOW_MILLIS = 2_000L
        const val DEFAULT_MAX_KEYS = 128
    }
}
