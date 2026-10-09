package com.shilapi.xcertplay

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/** App-private bounded event history. The JSON line schema is stable and never contains payloads. */
internal object GeelyDiagnosticHistory {
    private const val PREFS = "carpaly_geely_diagnostic_history"
    private const val KEY = "events_v1"
    private const val MAX_ENTRIES = 300

    @Synchronized
    fun append(
        context: Context,
        message: String,
        eventType: String = "diagnostic_event",
        module: String = "diagnostic",
        severity: String = "INFO",
        correlationSessionId: String? = null,
    ) {
        if (!DiagnosticLogManager.isEnabled(context)) return
        val safeMessage = DiagnosticRedactor.redact(message) ?: return
        val preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val existing = read(context).takeLast(MAX_ENTRIES - 1)
        val event = JSONObject().apply {
            put("timestamp", nowIso())
            put("event_type", eventType.take(80))
            put("module", module.take(80))
            put("severity", severity.take(16))
            put("correlation_session_id", correlationSessionId)
            put("message", safeMessage)
        }
        val events = JSONArray().apply {
            existing.forEach(::put)
            put(event)
        }
        preferences.edit().putString(KEY, events.toString()).apply()
    }

    @Synchronized
    fun read(context: Context): List<JSONObject> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, null)
            ?: return emptyList()
        return runCatching {
            val array = JSONArray(raw)
            (0 until array.length()).mapNotNull { array.optJSONObject(it) }.takeLast(MAX_ENTRIES)
        }.getOrElse {
            // Tolerate the newline-only history written by older diagnostic builds.
            raw.lineSequence().filter(String::isNotBlank).toList().takeLast(MAX_ENTRIES).mapNotNull { line ->
                DiagnosticRedactor.redact(line)?.let { safe ->
                    JSONObject().put("timestamp", nowIso()).put("event_type", "legacy_event")
                        .put("module", "diagnostic").put("severity", "INFO")
                        .put("correlation_session_id", JSONObject.NULL).put("message", safe)
                }
            }.toList()
        }
    }

    fun asJson(context: Context, module: String? = null): JSONArray = JSONArray().apply {
        read(context).filter { module == null || it.optString("module") == module }.forEach(::put)
    }

    fun displayLines(context: Context): List<String> = read(context).map { event ->
        "${event.optString("timestamp")} [${event.optString("module")}/${event.optString("severity")}] ${event.optString("message")}"
    }

    @Synchronized
    fun clear(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().remove(KEY).apply()
    }

    private fun nowIso(): String = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US)
        .apply { timeZone = TimeZone.getTimeZone("UTC") }.format(Date())
}
