package com.shilapi.xcertplay

import java.io.Closeable
import java.io.File

/** Bounded, private diagnostics. Each write is redacted before touching storage. */
internal class SessionLogFile(
    val file: File,
    private val maxFileBytes: Long = MAX_BYTES,
) : Closeable {
    private val lock = Any()
    private val archiveNames = archiveNamesFor(file)
    private var closed = false

    init { require(maxFileBytes > 0) }

    fun reset(header: String) = synchronized(lock) {
        if (!closed) {
            file.parentFile?.mkdirs()
            rotate()
            file.writeText("")
            append(header)
        }
    }
    fun append(line: String) = synchronized(lock) {
        if (closed) return@synchronized
        val safe = DiagnosticRedactor.redact(line)?.take(MAX_LOG_LINE_CHARS) ?: return@synchronized
        runCatching {
            file.parentFile?.mkdirs()
            val bytes = (safe + "\n").toByteArray(Charsets.UTF_8)
            if (bytes.size > maxFileBytes) return@runCatching
            if (file.exists() && file.length() + bytes.size > maxFileBytes) {
                rotate()
                file.writeText("")
            }
            file.appendBytes(bytes)
        }
        Unit
    }
    private fun rotate() {
        if (!file.exists() || file.length() == 0L) return
        for (index in archiveNames.lastIndex downTo 1) {
            val source = File(file.parentFile, archiveNames[index - 1])
            val destination = File(file.parentFile, archiveNames[index])
            if (source.exists()) source.copyTo(destination, overwrite = true)
        }
        file.copyTo(File(file.parentFile, archiveNames.first()), overwrite = true)
    }
    override fun close() = synchronized(lock) { closed = true }

    companion object {
        const val MAX_BYTES = 512 * 1024L
        const val MAX_RUNTIME_BYTES = 256 * 1024L
        const val MAX_LOG_LINE_CHARS = 16 * 1024
        const val RETAINED_LOG_FILES_PER_FAMILY = 8
        const val MAX_RETAINED_LOG_BYTES =
            (MAX_BYTES + MAX_RUNTIME_BYTES) * RETAINED_LOG_FILES_PER_FAMILY
        private val LEGACY_ARCHIVE_NAMES = listOf("previous.log") + (2..7).map { "previous-$it.log" }
        private val RUNTIME_ARCHIVE_NAMES = listOf("app-runtime-previous.log") +
            (2..7).map { "app-runtime-previous-$it.log" }
        val REPORT_NAMES = LEGACY_ARCHIVE_NAMES.reversed() + "diplay.log" +
            RUNTIME_ARCHIVE_NAMES.reversed() + "app-runtime.log"

        private fun archiveNamesFor(file: File): List<String> = when (file.name) {
            "diplay.log" -> LEGACY_ARCHIVE_NAMES
            "app-runtime.log" -> RUNTIME_ARCHIVE_NAMES
            else -> {
                val prefix = file.nameWithoutExtension
                listOf("$prefix-previous.log") + (2..7).map { "$prefix-previous-$it.log" }
            }
        }
    }
}
