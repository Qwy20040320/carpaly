package com.shilapi.xcertplay

import android.content.ContentResolver
import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import androidx.annotation.RequiresApi
import androidx.core.content.FileProvider
import java.io.File
import java.io.IOException
import java.io.OutputStream

/** Saves an app-owned report without depending on an OEM's document-picker activity. */
internal object DiagnosticExportStore {
    data class SavedReport(
        val uri: Uri,
        val savedInApp: Boolean = false,
        val savedPath: String? = null,
    )

    /** Android 9 and OEMs without working Downloads storage can still export privately. */
    fun saveWithoutPicker(context: Context, fileName: String, report: String): SavedReport {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            try {
                return SavedReport(saveToDownloads(context.contentResolver, fileName, report))
            } catch (_: Exception) {
                // Preserve the report even when the OEM's public storage provider is absent.
            }
        }
        try {
            // Use Android's package-specific directory, including debug application IDs.
            // No storage permission or document-picker activity is needed.
            val externalFiles = context.getExternalFilesDir(null)
            if (externalFiles != null) {
                return saveInDirectory(context, File(externalFiles, "diagnostic-reports"), fileName, report)
            }
        } catch (_: Exception) {
            // A missing, read-only or full external volume must not prevent export.
        }
        return saveInDirectory(context, File(context.filesDir, "diagnostic-reports"), fileName, report, savedInApp = true)
    }

    /** Saves a user-requested ZIP when an OEM has no working SAF document picker. */
    fun saveArchiveWithoutPicker(context: Context, fileName: String, writeArchive: (OutputStream) -> Unit): SavedReport {
        require(fileName.matches(Regex("[A-Za-z0-9_.-]{1,120}\\.zip")) && ".." !in fileName) {
            "Invalid export file name"
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            try {
                val uri = saveArchiveToDownloads(context.contentResolver, fileName, writeArchive)
                return SavedReport(uri)
            } catch (_: Exception) {
                // Fall back to a package-owned directory when the OEM Downloads provider is absent.
            }
        }
        val externalFiles = runCatching { context.getExternalFilesDir(null) }.getOrNull()
        if (externalFiles != null) {
            runCatching { return saveArchiveInDirectory(context, File(externalFiles, "diagnostic-reports"), fileName, writeArchive) }
        }
        return saveArchiveInDirectory(context, File(context.filesDir, "diagnostic-reports"), fileName, writeArchive, savedInApp = true)
    }

    @RequiresApi(Build.VERSION_CODES.Q)
    private fun saveArchiveToDownloads(resolver: ContentResolver, fileName: String,
        writeArchive: (OutputStream) -> Unit): Uri {
        val values = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, fileName)
            put(MediaStore.Downloads.MIME_TYPE, "application/zip")
            put(MediaStore.Downloads.RELATIVE_PATH, "${Environment.DIRECTORY_DOWNLOADS}/CarPaly")
            put(MediaStore.Downloads.IS_PENDING, 1)
        }
        val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
            ?: throw IOException("Downloads could not create the archive")
        try {
            val stream = resolver.openOutputStream(uri, "w") ?: throw IOException("Downloads output is unavailable")
            stream.use(writeArchive)
            val published = resolver.update(uri, ContentValues().apply {
                put(MediaStore.Downloads.IS_PENDING, 0)
            }, null, null)
            if (published != 1) throw IOException("Downloads could not publish the archive")
            return uri
        } catch (error: Exception) {
            runCatching { resolver.delete(uri, null, null) }
            throw error
        }
    }

    private fun saveArchiveInDirectory(context: Context, directory: File, fileName: String,
        writeArchive: (OutputStream) -> Unit,
        savedInApp: Boolean = false): SavedReport {
        if (!directory.isDirectory && !directory.mkdirs()) throw IOException("Archive storage is unavailable")
        val target = uniqueArchiveFile(directory, fileName)
        try {
            target.outputStream().use(writeArchive)
            val uri = FileProvider.getUriForFile(context, "${context.packageName}.diagnostic-reports", target)
            directory.listFiles()?.filter { it != target && it.isFile && it.extension.equals("zip", ignoreCase = true) }
                ?.sortedByDescending { it.lastModified() }?.drop(7)?.forEach { it.delete() }
            return SavedReport(uri, savedInApp = savedInApp, savedPath = if (savedInApp) null else target.absolutePath)
        } catch (error: Exception) {
            target.delete()
            throw error
        }
    }

    private fun uniqueArchiveFile(directory: File, fileName: String): File {
        val base = fileName.removeSuffix(".zip")
        var index = 0
        while (true) {
            val candidate = File(directory, if (index == 0) fileName else "$base-$index.zip")
            if (!candidate.exists()) return candidate
            index++
        }
    }

    private fun saveInDirectory(
        context: Context,
        directory: File,
        fileName: String,
        report: String,
        savedInApp: Boolean = false,
    ): SavedReport {
        if (!directory.isDirectory && !directory.mkdirs()) throw IOException("Report storage is unavailable")
        // Each export has a new URI: an earlier share grant cannot read a later report.
        val file = File.createTempFile(fileName.removeSuffix(".txt") + "-", ".txt", directory)
        try {
            file.writeText(report, Charsets.UTF_8)
            val uri = FileProvider.getUriForFile(context, "${context.packageName}.diagnostic-reports", file)
            // Retain only the newest eight reports; never prune the export being returned.
            directory.listFiles()?.filter { it != file && it.isFile }
                ?.sortedByDescending { it.lastModified() }?.drop(7)?.forEach { it.delete() }
            return SavedReport(uri, savedInApp = savedInApp, savedPath = if (savedInApp) null else file.absolutePath)
        } catch (error: Exception) {
            file.delete()
            throw error
        }
    }

    @RequiresApi(Build.VERSION_CODES.Q)
    fun saveToDownloads(resolver: ContentResolver, fileName: String, report: String): Uri {
        val values = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, fileName)
            put(MediaStore.Downloads.MIME_TYPE, "text/plain")
            put(MediaStore.Downloads.RELATIVE_PATH, "${Environment.DIRECTORY_DOWNLOADS}/CarPaly")
            put(MediaStore.Downloads.IS_PENDING, 1)
        }
        val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
            ?: throw IOException("Downloads could not create the report")
        try {
            write(resolver, uri, report)
            val published = resolver.update(uri, ContentValues().apply {
                put(MediaStore.Downloads.IS_PENDING, 0)
            }, null, null)
            if (published != 1) throw IOException("Downloads could not publish the report")
            return uri
        } catch (error: Exception) {
            // Only remove the entry created by this call; never leave a partial report behind.
            runCatching { resolver.delete(uri, null, null) }
            throw error
        }
    }

    fun write(resolver: ContentResolver, uri: Uri, report: String) {
        val stream = resolver.openOutputStream(uri, "wt")
            ?: throw IOException("Report destination is unavailable")
        stream.bufferedWriter(Charsets.UTF_8).use { it.write(report) }
    }
}
