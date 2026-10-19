package com.shilapi.xcertplay

/** Reports the first unmet startup prerequisite so a dismissed system dialog cannot fail silently. */
internal data class CarPlayStartupReadiness(
    val displayReady: Boolean,
    val transportReady: Boolean,
    val locationReady: Boolean,
    val microphonePermissionResolved: Boolean,
    val menuOpen: Boolean,
    val handshakeResetInProgress: Boolean,
    val displayResizePending: Boolean,
    val controllerPresent: Boolean,
)

internal object CarPlayStartupGate {
    fun blockingReason(state: CarPlayStartupReadiness): String? = when {
        !state.displayReady -> "display_surface_unavailable"
        !state.transportReady -> "transport_permission_unresolved"
        !state.locationReady -> "location_permission_unresolved"
        !state.microphonePermissionResolved -> "microphone_permission_unresolved"
        state.menuOpen -> "settings_menu_open"
        state.handshakeResetInProgress -> "previous_session_teardown"
        state.displayResizePending -> "display_resize_pending"
        state.controllerPresent -> "controller_already_present"
        else -> null
    }
}
