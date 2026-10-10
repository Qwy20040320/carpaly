package com.shilapi.xcertplay

import org.json.JSONArray
import org.json.JSONObject
import java.io.OutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** Validates the privacy-safe, flat ZIP schema before writing it through the user's SAF Uri. */
internal object DiagnosticArchive {
    val REQUIRED_ENTRIES = setOf(
        "device_info.json",
        "display_info.json",
        "usb_events.json",
        "network_events.json",
        "carplay_session.json",
        "audio_events.json",
        "vehicle_events.json",
        "errors.txt",
        "app_logs.txt",
        "test_summary.md",
        "manifest.json",
    )

    fun write(output: OutputStream, files: Map<String, String>) {
        require(files.keys.containsAll(REQUIRED_ENTRIES)) { "诊断包缺少必需文件" }
        require(files.keys.all { it.isNotBlank() && '/' !in it && '\\' !in it && it != "." && it != ".." }) {
            "诊断包文件名无效"
        }
        for ((name, contents) in files) {
            if (name.endsWith(".json")) parseJson(contents)
        }
        val manifest = JSONObject(files.getValue("manifest.json"))
        val actualEntries = files.keys.sorted()
        val listedEntries = manifest.optJSONArray("files")?.strings()?.sorted()
        require(listedEntries != null && listedEntries.size == actualEntries.size && listedEntries.toSet() == actualEntries.toSet()) {
            "manifest.json 与 ZIP 条目不一致（listed=${listedEntries?.joinToString()} actual=${actualEntries.joinToString()}）"
        }

        ZipOutputStream(output).use { zip ->
            for ((name, contents) in files.toSortedMap()) {
                zip.putNextEntry(ZipEntry(name))
                zip.write(contents.toByteArray(Charsets.UTF_8))
                zip.closeEntry()
            }
        }
    }

    private fun parseJson(contents: String) {
        val value = contents.trimStart().firstOrNull()
        when (value) {
            '{' -> JSONObject(contents)
            '[' -> JSONArray(contents)
            else -> error("诊断 JSON 根节点无效")
        }
    }

    private fun JSONArray.strings(): List<String> = (0 until length()).map { getString(it) }
}
