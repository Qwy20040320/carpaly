package com.shilapi.xcertplay

import android.Manifest
import android.os.Build
import com.shilapi.xcertplay.orchestration.WirelessHotspotMode

/** Runtime permissions a wireless CarPlay session needs on each Android release. */
internal object WirelessPermissions {
    fun required(hotspotMode: WirelessHotspotMode, sdkInt: Int): List<String> = when {
        hotspotMode == WirelessHotspotMode.EXISTING_WIFI ->
            if (sdkInt >= Build.VERSION_CODES.S) listOf(Manifest.permission.BLUETOOTH_CONNECT) else emptyList()
        sdkInt >= Build.VERSION_CODES.TIRAMISU -> listOf(
            Manifest.permission.BLUETOOTH_CONNECT,
            Manifest.permission.NEARBY_WIFI_DEVICES,
        )
        sdkInt >= Build.VERSION_CODES.S -> listOf(
            Manifest.permission.BLUETOOTH_CONNECT,
            Manifest.permission.ACCESS_COARSE_LOCATION,
            Manifest.permission.ACCESS_FINE_LOCATION,
        )
        else -> listOf(
            Manifest.permission.ACCESS_COARSE_LOCATION,
            Manifest.permission.ACCESS_FINE_LOCATION,
        )
    }.let { permissions ->
        if (sdkInt >= Build.VERSION_CODES.CINNAMON_BUN) {
            permissions + Manifest.permission.ACCESS_LOCAL_NETWORK
        } else {
            permissions
        }
    }
}
