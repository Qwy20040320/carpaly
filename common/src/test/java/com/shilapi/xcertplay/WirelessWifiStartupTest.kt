package com.shilapi.xcertplay

import com.shilapi.xcertplay.orchestration.WirelessHotspotMode
import org.junit.Assert.assertEquals
import org.junit.Test

class WirelessWifiStartupTest {
    @Test
    fun stationRadioRequiredOnlyByP2pAndExistingWifiModes() {
        assertEquals(true, WirelessWifiStartup.requiresStationRadio(true, WirelessHotspotMode.WIFI_P2P))
        assertEquals(true, WirelessWifiStartup.requiresStationRadio(true, WirelessHotspotMode.EXISTING_WIFI))
        assertEquals(false, WirelessWifiStartup.requiresStationRadio(true, WirelessHotspotMode.LOCAL_ONLY_HOTSPOT))
        assertEquals(false, WirelessWifiStartup.requiresStationRadio(true, WirelessHotspotMode.MANUAL))
        assertEquals(false, WirelessWifiStartup.requiresStationRadio(false, WirelessHotspotMode.WIFI_P2P))
    }

    @Test
    fun enabledRadioContinuesAndTransitionStatesWait() {
        assertEquals(
            WirelessWifiStartupAction.CONTINUE,
            WirelessWifiStartup.action(true, WirelessHotspotMode.WIFI_P2P, WirelessWifiRadioState.ENABLED, false),
        )
        listOf(WirelessWifiRadioState.ENABLING, WirelessWifiRadioState.DISABLING).forEach { state ->
            assertEquals(
                WirelessWifiStartupAction.WAIT_FOR_WIFI,
                WirelessWifiStartup.action(true, WirelessHotspotMode.WIFI_P2P, state, false),
            )
        }
    }

    @Test
    fun disabledRadioUsesPrivilegedRequestOnlyWhenPlatformAllowsIt() {
        assertEquals(
            WirelessWifiStartupAction.REQUEST_PRIVILEGED_ENABLE,
            WirelessWifiStartup.action(true, WirelessHotspotMode.WIFI_P2P, WirelessWifiRadioState.DISABLED, true),
        )
        assertEquals(
            WirelessWifiStartupAction.OPEN_USER_SETTINGS,
            WirelessWifiStartup.action(true, WirelessHotspotMode.WIFI_P2P, WirelessWifiRadioState.DISABLED, false),
        )
    }

    @Test
    fun unknownRadioFailsClosedToUserSettingsAndHotspotModesContinue() {
        assertEquals(
            WirelessWifiStartupAction.OPEN_USER_SETTINGS,
            WirelessWifiStartup.action(true, WirelessHotspotMode.EXISTING_WIFI, WirelessWifiRadioState.UNKNOWN, true),
        )
        assertEquals(
            WirelessWifiStartupAction.CONTINUE,
            WirelessWifiStartup.action(true, WirelessHotspotMode.LOCAL_ONLY_HOTSPOT, WirelessWifiRadioState.UNKNOWN, false),
        )
    }
}
