package com.shilapi.xcertplay

import java.io.Closeable
import java.io.File

/** Bounded, private diagnostics. Each write is redacted before touching storage. */
internal class SessionLogFile(
    val file: File,
    private val loggingEnabled: () -> Boolean = { true },
    private val maxFileBytes: Long = DiagnosticLogManager.MAX_FILE_BYTES,
    private val onRotation: () -> Unit = {},
) : Closeable {
    private val lock = Any()
    private var closed = false

    init { require(maxFileBytes > 0) }

    fun isLoggingEnabled(): Boolean = synchronized(lock) { !closed && enabled() }

    fun reset(header: String) = synchronized(lock) {
        if (!closed && enabled()) {
            file.parentFile?.mkdirs()
            rotate()
            file.writeText("")
            append(header)
            runCatching(onRotation)
        }
    }
    fun append(line: String) = synchronized(lock) {
        if (closed || !enabled()) return@synchronized
        val safe = DiagnosticRedactor.redact(line)?.take(MAX_LOG_LINE_CHARS) ?: return@synchronized
        runCatching {
            file.parentFile?.mkdirs()
            val bytes = (safe + "\n").toByteArray(Charsets.UTF_8)
            if (bytes.size > maxFileBytes) return@runCatching
            var rotated = false
            if (file.exists() && file.length() + bytes.size > maxFileBytes) {
                rotate()
                file.writeText("")
                rotated = true
            }
            file.appendBytes(bytes)
            if (rotated) runCatching(onRotation)
        }
        Unit
    }
    private fun rotate() {
        if (!file.exists() || file.length() == 0L) return
        for (index in ARCHIVE_NAMES.lastIndex downTo 1) {
            val source = File(file.parentFile, ARCHIVE_NAMES[index - 1])
            val destination = File(file.parentFile, ARCHIVE_NAMES[index])
            if (source.exists()) source.copyTo(destination, overwrite = true)
        }
        file.copyTo(File(file.parentFile, ARCHIVE_NAMES.first()), overwrite = true)
    }
    override fun close() = synchronized(lock) { closed = true }

    private fun enabled(): Boolean = runCatching(loggingEnabled).getOrDefault(false)

    companion object {
        const val MAX_BYTES = DiagnosticLogManager.MAX_FILE_BYTES
        const val MAX_LOG_LINE_CHARS = 16 * 1024
        private val ARCHIVE_NAMES = listOf("previous.log") + (2..19).map { "previous-$it.log" }
        val REPORT_NAMES = ARCHIVE_NAMES.reversed() + "diplay.log"
    }
}
