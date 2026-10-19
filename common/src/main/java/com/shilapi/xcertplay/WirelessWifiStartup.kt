package com.shilapi.xcertplay

import android.app.admin.DevicePolicyManager
import android.content.Context
import android.content.pm.ApplicationInfo
import android.net.wifi.WifiManager
import com.shilapi.xcertplay.orchestration.WirelessHotspotMode

internal enum class WirelessWifiRadioState {
    ENABLED,
    ENABLING,
    DISABLED,
    DISABLING,
    UNKNOWN,
}

internal enum class WirelessWifiStartupAction {
    CONTINUE,
    WAIT_FOR_WIFI,
    REQUEST_PRIVILEGED_ENABLE,
    OPEN_USER_SETTINGS,
}

/**
 * Wi-Fi startup policy. Android 10+ does not allow ordinary apps to toggle the station radio;
 * callers must use the system settings panel when the app is not an authorized system/owner app.
 */
internal object WirelessWifiStartup {
    fun requiresStationRadio(wireless: Boolean, mode: WirelessHotspotMode): Boolean =
        wireless && (mode == WirelessHotspotMode.WIFI_P2P || mode == WirelessHotspotMode.EXISTING_WIFI)

    fun action(
        wireless: Boolean,
        mode: WirelessHotspotMode,
        state: WirelessWifiRadioState,
        appMayControlRadio: Boolean,
    ): WirelessWifiStartupAction {
        if (!requiresStationRadio(wireless, mode)) return WirelessWifiStartupAction.CONTINUE
        return when (state) {
            WirelessWifiRadioState.ENABLED -> WirelessWifiStartupAction.CONTINUE
            WirelessWifiRadioState.ENABLING, WirelessWifiRadioState.DISABLING ->
                WirelessWifiStartupAction.WAIT_FOR_WIFI
            WirelessWifiRadioState.DISABLED -> if (appMayControlRadio) {
                WirelessWifiStartupAction.REQUEST_PRIVILEGED_ENABLE
            } else {
                WirelessWifiStartupAction.OPEN_USER_SETTINGS
            }
            WirelessWifiRadioState.UNKNOWN -> WirelessWifiStartupAction.OPEN_USER_SETTINGS
        }
    }

    fun radioState(context: Context): WirelessWifiRadioState = runCatching {
        val wifi = context.applicationContext.getSystemService(WifiManager::class.java)
            ?: return WirelessWifiRadioState.UNKNOWN
        when (wifi.wifiState) {
            WifiManager.WIFI_STATE_ENABLED -> WirelessWifiRadioState.ENABLED
            WifiManager.WIFI_STATE_ENABLING -> WirelessWifiRadioState.ENABLING
            WifiManager.WIFI_STATE_DISABLED -> WirelessWifiRadioState.DISABLED
            WifiManager.WIFI_STATE_DISABLING -> WirelessWifiRadioState.DISABLING
            else -> WirelessWifiRadioState.UNKNOWN
        }
    }.getOrDefault(WirelessWifiRadioState.UNKNOWN)

    fun appMayControlRadio(context: Context): Boolean {
        val packageManager = context.packageManager
        val systemApp = runCatching {
            @Suppress("DEPRECATION")
            val flags = packageManager.getApplicationInfo(context.packageName, 0).flags
            flags and (ApplicationInfo.FLAG_SYSTEM or ApplicationInfo.FLAG_UPDATED_SYSTEM_APP) != 0
        }.getOrDefault(false)
        if (systemApp) return true

        val deviceOwner = runCatching {
            context.getSystemService(DevicePolicyManager::class.java)?.isDeviceOwnerApp(context.packageName) == true
        }.getOrDefault(false)
        if (deviceOwner) return true

        return runCatching {
            context.getSystemService(DevicePolicyManager::class.java)?.isProfileOwnerApp(context.packageName) == true
        }.getOrDefault(false)
    }

    /** Returns false unless the platform identifies this app as privileged to change the radio. */
    @Suppress("DEPRECATION")
    fun requestEnableIfAuthorized(context: Context): Boolean {
        if (!appMayControlRadio(context)) return false
        return runCatching {
            val wifi = context.applicationContext.getSystemService(WifiManager::class.java) ?: return false
            wifi.isWifiEnabled || wifi.setWifiEnabled(true)
        }.getOrDefault(false)
    }
}
