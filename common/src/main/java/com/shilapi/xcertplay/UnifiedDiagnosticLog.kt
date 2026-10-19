package com.shilapi.xcertplay

import android.app.Activity
import android.app.Application
import android.content.Context
import android.os.Build
import android.os.Bundle
import android.os.Process
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID
import java.util.concurrent.atomic.AtomicLong

/** Stable, privacy-filtered event envelopes used by the existing single diagnostic export. */
internal object DiagnosticEventFormatter {
    private val token = Regex("[^A-Za-z0-9_.:+/-]")

    fun format(
        timestamp: String,
        level: String,
        module: String,
        thread: String,
        runId: String,
        sessionId: String,
        eventId: Long,
        faultId: String,
        event: String,
        result: String,
        state: String,
        reason: String,
        recovery: String,
        detail: String,
    ): String? {
        val safeDetail = DiagnosticRedactor.redact(detail) ?: return null
        val line = listOf(
            "ts=${field(timestamp)}",
            "level=${field(level)}",
            "module=${field(module)}",
            "thread=${field(thread)}",
            "run=${field(runId)}",
            "session=${field(sessionId)}",
            "eventId=E${eventId.toString().padStart(8, '0')}",
            "faultId=${field(faultId)}",
            "event=${field(event)}",
            "result=${field(result)}",
            "state=${field(state)}",
            "reason=${field(reason)}",
            "recovery=${field(recovery)}",
            "detail=${field(safeDetail)}",
        ).joinToString(" ")
        return DiagnosticRedactor.redact(line)?.take(SessionLogFile.MAX_LOG_LINE_CHARS)
    }

    private fun field(value: String): String = token.replace(value.trim().take(160).ifBlank { "none" }, "_")
}

/**
 * Process-wide bounded event log. The old per-connection log remains unchanged; this parallel
 * file preserves process/startup history and gives the existing export a stable searchable view.
 */
internal object UnifiedDiagnosticLog {
    private val lock = Any()
    private val eventSequence = AtomicLong()
    private val connectionSequence = AtomicLong()
    private val repeatedLegacyEvents = DiagnosticRepeatGate()
    private val runId = "r${UUID.randomUUID().toString().replace("-", "").take(12)}"
    @Volatile private var target: SessionLogFile? = null
    @Volatile private var connectionSessionId: String = "none"
    private var lifecycleRegistered = false

    fun initialize(context: Context) {
        val appContext = context.applicationContext
        synchronized(lock) {
            if (target != null) return
            target = SessionLogFile(
                java.io.File(java.io.File(appContext.filesDir, "logs"), "app-runtime.log"),
                maxFileBytes = SessionLogFile.MAX_RUNTIME_BYTES,
            )
            val info = runCatching { appContext.packageManager.getPackageInfo(appContext.packageName, 0) }.getOrNull()
            val versionName = info?.versionName ?: "unknown"
            @Suppress("DEPRECATION")
            val legacyVersionCode = info?.versionCode?.toLong() ?: -1L
            val versionCode = if (Build.VERSION.SDK_INT >= 28) info?.longVersionCode ?: -1L else legacyVersionCode
            record(
                level = "INFO", module = "APP", event = "PROCESS_START", result = "STARTED",
                state = "RUNNING", detail = "version=$versionName versionCode=$versionCode " +
                    "package=${appContext.packageName} api=${Build.VERSION.SDK_INT} " +
                    "manufacturer=${Build.MANUFACTURER} model=${Build.MODEL} pid=${Process.myPid()}",
            )
            (appContext as? Application)?.let(::registerLifecycleCallbacks)
        }
    }

    fun beginConnectionSession(reason: String = "START_REQUESTED"): String {
        val id = "cp${connectionSequence.incrementAndGet().toString().padStart(5, '0')}"
        connectionSessionId = id
        record(level = "INFO", module = "SESSION", event = "CONNECTION_SESSION_START", result = "STARTED",
            state = "CONNECTING", reason = reason, detail = "connection session opened")
        return id
    }

    fun endConnectionSession(reason: String) {
        record(level = "INFO", module = "SESSION", event = "CONNECTION_SESSION_END", result = "ENDED",
            state = "STOPPED", reason = reason, detail = "connection session closed")
        connectionSessionId = "none"
    }

    /** Mirrors an existing, already-redacted diagnostic message without changing its old log format. */
    fun recordLegacy(message: String) {
        val safe = DiagnosticRedactor.redact(message) ?: return
        val module = when {
            safe.contains("usb", true) || safe.contains("iap2", true) || safe.contains("ncm", true) -> "USB_IAP2"
            safe.contains("audio", true) || safe.contains("opus", true) || safe.contains("pcm", true) ||
                safe.contains("microphone", true) || safe.contains("siri", true) || safe.contains("track", true) ||
                safe.contains("media playback", true) -> "AUDIO"
            safe.contains("video", true) || safe.contains("surface", true) || safe.contains("insets", true) ||
                safe.contains("viewport", true) || safe.contains("decoder", true) -> "VIDEO_DISPLAY"
            safe.contains("bluetooth", true) || safe.contains("wifi", true) || safe.contains("rfcomm", true) -> "WIRELESS"
            safe.contains("hud", true) || safe.contains("dim", true) || safe.contains("geely", true) ||
                safe.contains("vehicle", true) || safe.contains("wheel", true) -> "VEHICLE"
            safe.contains("update", true) || safe.contains("manifest", true) || safe.contains("installer", true) -> "UPDATE"
            safe.contains("airplay", true) || safe.contains("carplay", true) || safe.contains("connection", true) ||
                safe.contains("reconnect", true) || safe.contains("iap", true) -> "SESSION"
            else -> "APP"
        }
        val failed = listOf("failed", "failure", "error", "unavailable", "refused", "timeout").any {
            safe.contains(it, true)
        }
        val repeat = repeatedLegacyEvents.observe("$module|$safe", System.currentTimeMillis())
        if (repeat == DiagnosticRepeatGate.Decision.Suppress) return
        val suppressed = (repeat as DiagnosticRepeatGate.Decision.Emit).suppressedSincePrevious
        record(
            level = if (failed) "WARN" else "INFO",
            module = module,
            event = "RUNTIME_STATE",
            result = if (failed) "FAILED_OR_DEGRADED" else "OBSERVED",
            state = "RECORDED",
            reason = if (failed) "SOURCE_DETAIL_REDACTED" else "none",
            recovery = if (safe.contains("retry", true) || safe.contains("recover", true)) "ATTEMPTED" else "none",
            detail = if (suppressed == 0) safe else "$safe repeatedSuppressed=$suppressed windowMs=2000",
        )
    }

    fun record(
        level: String,
        module: String,
        event: String,
        result: String = "UNKNOWN",
        state: String = "UNKNOWN",
        reason: String = "none",
        recovery: String = "none",
        detail: String = "none",
    ) {
        val currentTarget = target ?: return
        val id = eventSequence.incrementAndGet()
        val now = System.currentTimeMillis()
        val timestamp = synchronized(lock) {
            SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", Locale.US).format(Date(now))
        }
        val faultId = if (level == "WARN" || level == "ERROR") "F${id.toString().padStart(8, '0')}" else "none"
        val line = DiagnosticEventFormatter.format(
            timestamp = timestamp,
            level = level,
            module = module,
            thread = Thread.currentThread().name,
            runId = runId,
            sessionId = connectionSessionId,
            eventId = id,
            faultId = faultId,
            event = event,
            result = result,
            state = state,
            reason = reason,
            recovery = recovery,
            detail = detail,
        ) ?: return
        AsyncDiagnosticLog.appendStructured(currentTarget, line)
    }

    private fun registerLifecycleCallbacks(application: Application) {
        if (lifecycleRegistered) return
        lifecycleRegistered = true
        application.registerActivityLifecycleCallbacks(object : Application.ActivityLifecycleCallbacks {
            override fun onActivityCreated(activity: Activity, state: Bundle?) = lifecycle(activity, "CREATED")
            override fun onActivityStarted(activity: Activity) = lifecycle(activity, "STARTED")
            override fun onActivityResumed(activity: Activity) = lifecycle(activity, "RESUMED")
            override fun onActivityPaused(activity: Activity) = lifecycle(activity, "PAUSED")
            override fun onActivityStopped(activity: Activity) = lifecycle(activity, "STOPPED")
            override fun onActivitySaveInstanceState(activity: Activity, state: Bundle) = Unit
            override fun onActivityDestroyed(activity: Activity) = lifecycle(activity, "DESTROYED")
        })
    }

    private fun lifecycle(activity: Activity, state: String) {
        record(level = "INFO", module = "LIFECYCLE", event = "ACTIVITY_$state", result = "OBSERVED",
            state = state, detail = "activity=${activity.javaClass.simpleName}")
    }
}
