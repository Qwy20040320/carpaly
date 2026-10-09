package com.shilapi.xcertplay

import android.content.Context
import android.util.AtomicFile
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/** Best-effort, app-private crash tail; installed only after the user opens vehicle diagnostics. */
internal object GeelyDiagnosticCrashRecorder {
    private const val MAX_BYTES = 64 * 1024
    @Volatile private var installed = false

    @Synchronized
    fun install(context: Context) {
        if (installed || !DiagnosticLogManager.isEnabled(context)) return
        val delegate = Thread.getDefaultUncaughtExceptionHandler()
        val file = AtomicFile(File(context.filesDir, "geely-diagnostics/crashes.log"))
        Thread.setDefaultUncaughtExceptionHandler { thread, error ->
            if (DiagnosticLogManager.isEnabled(context)) runCatching {
                file.baseFile.parentFile?.mkdirs()
                val previous = if (file.baseFile.exists()) file.openRead().use { it.readBytes().takeLast(MAX_BYTES).toByteArray() } else byteArrayOf()
                val entry = ByteArrayOutputStream().apply {
                    val timestamp = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US)
                        .apply { timeZone = TimeZone.getTimeZone("UTC") }.format(Date())
                    write("$timestamp uncaught ${error.javaClass.name} thread=${thread.name}\n".toByteArray())
                    error.stackTraceToString().lines().takeLast(120).forEach { line ->
                        DiagnosticRedactor.redact(line)?.let { write((it + "\n").toByteArray(Charsets.UTF_8)) }
                    }
                }.toByteArray()
                val retained = (previous + entry).takeLast(MAX_BYTES).toByteArray()
                val stream: FileOutputStream = file.startWrite()
                try {
                    stream.write(retained)
                    stream.fd.sync()
                    file.finishWrite(stream)
                } catch (failure: Exception) {
                    file.failWrite(stream)
                    throw failure
                }
            }
            delegate?.uncaughtException(thread, error)
        }
        installed = true
    }
}
