package com.shilapi.xcertplay

import android.content.Context
import java.io.File
import java.io.RandomAccessFile
import java.nio.charset.StandardCharsets
import java.util.concurrent.TimeUnit

/** Management for the existing private CarPlay session log files and structured event history. */
internal object DiagnosticLogManager {
    const val MAX_FILE_BYTES = 5L * 1024 * 1024
    const val MAX_TOTAL_BYTES = 50L * 1024 * 1024
    const val MAX_FILES = 20
    val RETENTION_MILLIS: Long = TimeUnit.DAYS.toMillis(7)

    private const val PREFS = "carpaly_diagnostic_log_settings"
    private const val ENABLED_KEY = "logging_enabled_v1"
    private const val LAST_EXPORT_KEY = "last_export_location_v1"
    private const val EXPORT_TAIL_BYTES = 64 * 1024

    data class Summary(
        val directoryPath: String,
        val fileCount: Int,
        val totalBytes: Long,
        val structuredEventCount: Int,
        val lastExportLocation: String?,
    )

    fun isEnabled(context: Context): Boolean = preferences(context).getBoolean(ENABLED_KEY, false)

    fun setEnabled(context: Context, enabled: Boolean) {
        preferences(context).edit().putBoolean(ENABLED_KEY, enabled).apply()
    }

    fun recordExportLocation(context: Context, location: String) {
        val safeLocation = DiagnosticRedactor.redact(location)?.take(512) ?: "用户选择的导出位置"
        preferences(context).edit().putString(LAST_EXPORT_KEY, safeLocation).apply()
    }

    fun summary(context: Context): Summary {
        val files = managedFiles(context).filter(File::isFile)
        val history = GeelyDiagnosticHistory.read(context)
        val historyBytes = history.sumOf { it.toString().toByteArray(StandardCharsets.UTF_8).size.toLong() }
        return Summary(
            directoryPath = displayPath(context),
            fileCount = files.size,
            totalBytes = files.sumOf { it.length() } + historyBytes,
            structuredEventCount = history.size,
            lastExportLocation = preferences(context).getString(LAST_EXPORT_KEY, null),
        )
    }

    /** Called when diagnostics opens/enables and after a file rotation, never from an AV callback. */
    fun prune(context: Context, nowMillis: Long = System.currentTimeMillis()): Summary {
        val active = File(File(context.filesDir, "logs"), "diplay.log")
        val current = managedFiles(context)
        val historyBytes = GeelyDiagnosticHistory.read(context)
            .sumOf { it.toString().toByteArray(StandardCharsets.UTF_8).size.toLong() }
        pruneFiles(current, active, nowMillis, maxTotalBytes = (MAX_TOTAL_BYTES - historyBytes).coerceAtLeast(0))
        return summary(context)
    }

    fun clearFiles(context: Context) {
        managedFiles(context).forEach { file -> runCatching { file.delete() } }
    }

    fun displayPath(context: Context): String =
        "${File(context.filesDir, "logs").absolutePath} 及 ${File(context.filesDir, "geely-diagnostics").absolutePath}"

    /** Include bounded, redacted tails in the user-requested ZIP without buffering all 50 MB. */
    fun exportRecentLogs(context: Context, perFileBytes: Int = EXPORT_TAIL_BYTES): String {
        val files = managedFiles(context).filter(File::isFile).sortedBy(File::lastModified)
        if (files.isEmpty()) return "暂无本机日志文件；日志默认关闭，须由用户手动开启。\n"
        return buildString {
            files.forEach { file ->
                append("--- ${file.name} · tail ≤${perFileBytes / 1024} KiB ---\n")
                readTail(file, perFileBytes).lineSequence()
                    .mapNotNull(DiagnosticRedactor::redact)
                    .forEach { append(it).append('\n') }
            }
        }
    }

    /** Pure file-list manager used by cleanup and tests; the current file is never selected for deletion. */
    internal fun pruneFiles(
        candidates: List<File>,
        activeFile: File?,
        nowMillis: Long,
        maxFiles: Int = MAX_FILES,
        maxTotalBytes: Long = MAX_TOTAL_BYTES,
        retentionMillis: Long = RETENTION_MILLIS,
    ): List<File> {
        val activePath = activeFile?.let(::normalizedPath)
        val existing = candidates.distinctBy(::normalizedPath).filter { it.isFile }.toMutableList()
        existing.toList().forEach { file ->
            val expired = nowMillis - file.lastModified() > retentionMillis
            if (expired && normalizedPath(file) != activePath) {
                runCatching { file.delete() }
            }
        }
        existing.removeAll { !it.isFile }

        while (existing.size > maxFiles || existing.sumOf { it.length() } > maxTotalBytes) {
            val oldest = existing
                .filter { normalizedPath(it) != activePath }
                .minByOrNull(File::lastModified) ?: break
            if (runCatching { oldest.delete() }.getOrDefault(false)) existing.remove(oldest) else break
        }
        return existing.sortedBy(File::lastModified)
    }

    private fun managedFiles(context: Context): List<File> {
        val logDir = File(context.filesDir, "logs")
        val crashFile = File(File(context.filesDir, "geely-diagnostics"), "crashes.log")
        return (SessionLogFile.REPORT_NAMES.map { File(logDir, it) } + crashFile).distinctBy(::normalizedPath)
    }

    private fun readTail(file: File, maxBytes: Int): String {
        if (maxBytes <= 0 || !file.isFile) return ""
        return runCatching {
            RandomAccessFile(file, "r").use { input ->
                val count = minOf(input.length(), maxBytes.toLong()).toInt()
                val offset = (input.length() - count).coerceAtLeast(0)
                val bytes = ByteArray(count)
                input.seek(offset)
                input.readFully(bytes)
                val decoded = String(bytes, StandardCharsets.UTF_8)
                if (offset == 0L) decoded else decoded.substringAfter('\n', "")
            }
        }.getOrDefault("")
    }

    private fun preferences(context: Context) =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private fun normalizedPath(file: File): String =
        runCatching { file.canonicalPath }.getOrDefault(file.absolutePath)
}
