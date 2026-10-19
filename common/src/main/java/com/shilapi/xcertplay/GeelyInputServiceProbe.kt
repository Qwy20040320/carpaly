package com.shilapi.xcertplay

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager

internal enum class GeelyInputServiceProbeState {
    NOT_QUERIED,
    NOT_FOUND,
    DISABLED,
    NOT_EXPORTED,
    PERMISSION_REQUIRED,
    STATIC_EVIDENCE_ONLY,
    QUERY_UNAVAILABLE,
}

internal data class GeelyInputServiceProbeResult(
    val state: GeelyInputServiceProbeState,
    val declaredPermission: String? = null,
) {
    fun diagnosticEvidence(): String = when (state) {
        GeelyInputServiceProbeState.NOT_QUERIED -> "service was not queried"
        GeelyInputServiceProbeState.NOT_FOUND -> "the explicit OneOS InputService component is not visible"
        GeelyInputServiceProbeState.DISABLED -> "the explicit OneOS InputService component or package is disabled"
        GeelyInputServiceProbeState.NOT_EXPORTED -> "the explicit OneOS InputService is not exported to this application"
        GeelyInputServiceProbeState.PERMISSION_REQUIRED ->
            "the explicit OneOS InputService requires an ungranted permission"
        GeelyInputServiceProbeState.STATIC_EVIDENCE_ONLY ->
            "the explicit component is visible and its declared permission is granted or absent; no bind/register was attempted"
        GeelyInputServiceProbeState.QUERY_UNAVAILABLE -> "package visibility or service query failed; no bind/register was attempted"
    }
}

/** Read-only package/permission probe for the public Geely InputService contract. Never binds Binder. */
internal object GeelyInputServiceProbe {
    const val PACKAGE_NAME = "com.geely.inputservice"
    const val CLASS_NAME = "com.geely.inputservice.InputService"

    fun inspect(context: Context): GeelyInputServiceProbeResult {
        return try {
            val component = ComponentName(PACKAGE_NAME, CLASS_NAME)
            val info = context.packageManager.resolveService(Intent().setComponent(component), 0)?.serviceInfo
            when {
                info == null -> GeelyInputServiceProbeResult(GeelyInputServiceProbeState.NOT_FOUND)
                info.packageName != PACKAGE_NAME || info.name != CLASS_NAME ->
                    GeelyInputServiceProbeResult(GeelyInputServiceProbeState.QUERY_UNAVAILABLE)
                !info.enabled || info.applicationInfo?.enabled != true ->
                    GeelyInputServiceProbeResult(GeelyInputServiceProbeState.DISABLED, info.permission)
                !info.exported -> GeelyInputServiceProbeResult(GeelyInputServiceProbeState.NOT_EXPORTED, info.permission)
                else -> {
                    val permission = info.permission
                    if (!permission.isNullOrBlank() &&
                        context.checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED
                    ) {
                        GeelyInputServiceProbeResult(GeelyInputServiceProbeState.PERMISSION_REQUIRED, permission)
                    } else {
                        GeelyInputServiceProbeResult(GeelyInputServiceProbeState.STATIC_EVIDENCE_ONLY, permission)
                    }
                }
            }
        } catch (_: SecurityException) {
            GeelyInputServiceProbeResult(GeelyInputServiceProbeState.QUERY_UNAVAILABLE)
        } catch (_: RuntimeException) {
            GeelyInputServiceProbeResult(GeelyInputServiceProbeState.QUERY_UNAVAILABLE)
        }
    }
}
