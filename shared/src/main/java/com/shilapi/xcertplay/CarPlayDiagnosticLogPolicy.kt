package com.shilapi.xcertplay

/** Centralizes safe text passed to Android logcat and the host diagnostic callback. */
internal object CarPlayDiagnosticLogPolicy {
    fun safeMessage(message: String): String? = DiagnosticRedactor.redact(message)

    /** Keep useful failure class/details while avoiding raw Throwable stack traces in app logs. */
    fun safeFailure(message: String, error: Throwable): String? {
        val errorClass = error.javaClass.simpleName.take(80).replace(Regex("[^A-Za-z0-9_$]"), "?")
        val detail = error.message?.let { " detail=$it" }.orEmpty()
        return DiagnosticRedactor.redact("$message error=$errorClass$detail")
    }
}
