package com.shilapi.xcertplay.transport

import java.io.IOException

/** Classifies firmware failures without logging the phone address or exception payload. */
internal object BluetoothSocketFailure {
    fun missingSocketManager(failure: Throwable): Boolean =
        generateSequence(failure) { it.cause }.take(4).any { cause ->
            val message = cause.message.orEmpty()
            (cause is NullPointerException && "IBluetoothSocketManager" in message) ||
                (cause is IOException && "get socket manager failed" in message)
        }

    fun category(failure: Throwable): String =
        if (missingSocketManager(failure)) "SOCKET_MANAGER_UNAVAILABLE" else "RFCOMM_CONNECT_FAILED"
}
