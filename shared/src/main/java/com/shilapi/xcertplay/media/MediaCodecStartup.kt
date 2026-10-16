package com.shilapi.xcertplay.media

/** A failed configure/start still owns the created codec and must release it before propagating. */
internal object MediaCodecStartup {
    data class Candidate<T : Any>(
        val name: String,
        val shouldAttempt: () -> Boolean = { true },
        val create: () -> T,
    )

    data class Started<T : Any>(val candidateName: String, val value: T)

    fun <T> create(
        create: () -> T,
        configure: (T) -> Unit,
        start: (T) -> Unit,
        release: (T) -> Unit,
    ): T {
        val candidate = create()
        try {
            configure(candidate)
            start(candidate)
            return candidate
        } catch (failure: Throwable) {
            // Driver cleanup can fail too; preserve the original configure/start failure.
            runCatching { release(candidate) }
            throw failure
        }
    }

    /**
     * Tries codec candidates in order and continues after a candidate cannot be created, configured,
     * or started. Any instance that was created but rejected is released exactly once. VM/linkage
     * errors are cleaned up and rethrown rather than being treated as a recoverable codec fallback.
     */
    fun <T : Any> createWithFallback(
        candidates: List<Candidate<T>>,
        configure: (T) -> Unit,
        start: (T) -> Unit,
        release: (T) -> Unit,
        onFailure: (candidateName: String, failure: Exception) -> Unit = { _, _ -> },
    ): Started<T> {
        require(candidates.isNotEmpty()) { "At least one codec candidate is required" }
        val failures = mutableListOf<Pair<String, Exception>>()
        for (candidate in candidates) {
            if (!candidate.shouldAttempt()) continue
            var instance: T? = null
            try {
                instance = candidate.create()
                configure(instance)
                start(instance)
                return Started(candidate.name, instance)
            } catch (failure: Throwable) {
                instance?.let { rejected -> runCatching { release(rejected) } }
                if (failure !is Exception) throw failure
                failures += candidate.name to failure
                runCatching { onFailure(candidate.name, failure) }
            }
        }

        if (failures.isEmpty()) {
            throw IllegalStateException("All codec candidates were skipped")
        }
        val terminal = failures.last().second
        failures.dropLast(1).forEach { (_, previous) ->
            if (previous !== terminal) terminal.addSuppressed(previous)
        }
        throw terminal
    }
}
