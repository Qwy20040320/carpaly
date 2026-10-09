package com.shilapi.xcertplay

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.util.zip.ZipInputStream
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [29])
class GeelyDiagnosticArchiveTest {
    @Test fun archiveContainsRequiredFlatEntriesAndValidJson() {
        val names = DiagnosticArchive.REQUIRED_ENTRIES
        val files = names.associateWith { name ->
            when {
                name == "manifest.json" -> "" // Filled once the regular entries are assembled below.
                name.endsWith(".json") -> "{}"
                name == "test_summary.md" -> "# Summary\n"
                else -> "NO_DATA\n"
            }
        }.toMutableMap()
        files["manifest.json"] = JSONObject().put("files", org.json.JSONArray().apply { names.sorted().forEach(::put) }).toString()

        val bytes = ByteArrayOutputStream()
        DiagnosticArchive.write(bytes, files)
        val entries = ZipInputStream(ByteArrayInputStream(bytes.toByteArray())).use { zip ->
            buildSet {
                while (true) {
                    val entry = zip.nextEntry ?: break
                    add(entry.name)
                    if (entry.name.endsWith(".json")) JSONObject(zip.readBytes().toString(Charsets.UTF_8))
                    zip.closeEntry()
                }
            }
        }
        assertEquals(names, entries)
    }

    @Test fun malformedManifestAndTraversalAreRejectedBeforeWriting() {
        val files = DiagnosticArchive.REQUIRED_ENTRIES.associateWith { name ->
            if (name.endsWith(".json")) "{}" else "NO_DATA"
        }.toMutableMap()
        files["manifest.json"] = JSONObject().put("files", org.json.JSONArray().put("../secrets")).toString()
        runCatching { DiagnosticArchive.write(ByteArrayOutputStream(), files) }
            .onSuccess { fail("manifest mismatch must be rejected") }
        files["manifest.json"] = JSONObject().put("files", org.json.JSONArray().apply { files.keys.sorted().forEach(::put) }).toString()
        files["../private.key"] = "not allowed"
        runCatching { DiagnosticArchive.write(ByteArrayOutputStream(), files) }
            .onSuccess { fail("traversal entry must be rejected") }
    }
}
