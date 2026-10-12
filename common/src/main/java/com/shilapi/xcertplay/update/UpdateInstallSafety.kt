package com.shilapi.xcertplay.update

/** No validated Geely stationary-state provider is currently integrated. */
internal enum class TrustedVehicleMotion {
    PARKED,
    MOVING,
    UNKNOWN,
}

internal object UpdateInstallSafety {
    internal fun mayLaunchInstaller(
        motion: TrustedVehicleMotion,
        carPlaySessionActive: Boolean,
        userConfirmedUnknownParked: Boolean = false,
    ): Boolean = !carPlaySessionActive && when (motion) {
        TrustedVehicleMotion.PARKED -> true
        TrustedVehicleMotion.MOVING -> false
        TrustedVehicleMotion.UNKNOWN -> userConfirmedUnknownParked
    }
}
