package com.shilapi.xcertplay

import android.content.ContentProvider
import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.net.Uri
import java.io.File
import java.util.Collections
import java.util.IdentityHashMap

/** Stores only exception class and bounded stack frames; exception messages may contain private data. */
internal object CrashRecord {
    private const val FILE = "logs/last-crash.txt"
    @Volatile private var installed = false

    @Synchronized fun install(context: Context) {
        if (installed) return
        installed = true
        val file = File(context.applicationContext.filesDir, FILE)
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, error ->
            runCatching {
                file.parentFile?.mkdirs()
                file.writeText(format(thread.name, error, System.currentTimeMillis()))
            }
            previous?.uncaughtException(thread, error)
        }
    }

    internal fun format(threadName: String, error: Throwable, atMillis: Long): String = buildString {
        appendLine("crash atEpochMs=$atMillis thread=${threadName.take(40)}")
        val seen = Collections.newSetFromMap(IdentityHashMap<Throwable, Boolean>())
        var current: Throwable? = error
        while (current != null && seen.size < 4 && seen.add(current)) {
            appendLine(current.javaClass.name)
            val frames = current.stackTrace
            frames.take(12).forEach { frame ->
                appendLine("  at ${frame.className}.${frame.methodName}(${frame.fileName}:${frame.lineNumber})")
            }
            if (frames.size > 12) appendLine("  ... ${frames.size - 12} more")
            current = current.cause
        }
    }

    fun report(context: Context): String {
        val file = File(context.filesDir, FILE)
        if (!file.isFile) return "No crash recorded by this version."
        return runCatching { file.readLines().mapNotNull(DiagnosticRedactor::redact).joinToString("\n") }
            .getOrElse { "Crash record unreadable: ${it.javaClass.simpleName}" }
    }
}

/** Starts crash capture before an Activity, Receiver, or Service can fail. */
class CrashRecordInstaller : ContentProvider() {
    override fun onCreate(): Boolean {
        context?.let(CrashRecord::install)
        return true
    }
    override fun query(uri: Uri, projection: Array<out String>?, selection: String?,
        selectionArgs: Array<out String>?, sortOrder: String?): Cursor? = null
    override fun getType(uri: Uri): String? = null
    override fun insert(uri: Uri, values: ContentValues?): Uri? = null
    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = 0
    override fun update(uri: Uri, values: ContentValues?, selection: String?,
        selectionArgs: Array<out String>?): Int = 0
}
