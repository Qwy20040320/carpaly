package com.shilapi.xcertplay

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Queued entries retain only their exact file target and a redacted, bounded metadata string. */
internal object AsyncDiagnosticLog {
    private data class Entry(val target: SessionLogFile, val line: String)
    private val writer = BoundedDiagnosticWriter<Entry> { it.target.append(it.line) }

    fun append(target: SessionLogFile?, message: String, nowMillis: Long = System.currentTimeMillis()) {
        if (target == null) return
        val safe = DiagnosticRedactor.redact(message) ?: return
        val timestamp = SimpleDateFormat("HH:mm:ss.SSS", Locale.US).format(Date(nowMillis))
        enqueue(target, "$timestamp  $safe")
    }

    /** Appends an already timestamped structured event through the same bounded background queue. */
    internal fun appendStructured(target: SessionLogFile?, line: String) {
        if (target == null) return
        val safe = DiagnosticRedactor.redact(line) ?: return
        enqueue(target, safe)
    }

    private fun enqueue(target: SessionLogFile, line: String) {
        runCatching { writer.enqueue(Entry(target, line)) }
    }

    internal fun awaitIdle(timeoutMillis: Long): Boolean = writer.awaitIdle(timeoutMillis)
}
