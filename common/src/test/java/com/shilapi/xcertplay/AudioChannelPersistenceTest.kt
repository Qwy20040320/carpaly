package com.shilapi.xcertplay

import android.content.Context
import android.media.AudioManager
import com.shilapi.xcertplay.host.R
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33], manifest = Config.NONE)
class AudioChannelPersistenceTest {
    private val context get() = RuntimeEnvironment.getApplication()
    private val prefs get() = context.getSharedPreferences("xcertplay_airplay", Context.MODE_PRIVATE)
    private val profilePrefs get() = context.getSharedPreferences("diplay", Context.MODE_PRIVATE)

    @Before fun clearPreferences() {
        prefs.edit().clear().apply()
        profilePrefs.edit().clear().apply()
    }

    @Test fun freshInstallUsesAutomaticRouting() {
        HeadUnitProfile.save(context, HeadUnitProfile.GENERIC)
        assertEquals(0, AirPlayPersistence.loadMediaAudioChannel(context))
        assertEquals(0, AirPlayPersistence.loadNavigationAudioChannel(context))
        assertEquals(AirPlayPersistence.CALL_AUDIO_AUTO, AirPlayPersistence.loadCallAudioChannel(context))
        org.junit.Assert.assertTrue(AirPlayPersistence.loadAudioFocusAutoYield(context))
    }

    @Test fun freshInstallUsesGeelyBrandingDefaults() {
        HeadUnitProfile.save(context, HeadUnitProfile.GENERIC)
        assertEquals("Geely", AirPlayPersistence.loadManufacturer(context))
        assertEquals("Xingyue L", AirPlayPersistence.loadModel(context))
        assertEquals("GEELY", AirPlayPersistence.loadOemLabel(context))
        assertEquals(R.drawable.ic_geely_auto_2023, CarPlayVehicleBranding.DEFAULT_ICON_RESOURCE)
    }

    @Test fun migratesOnlyTheCompleteLegacyDefaultBrandTuple() {
        prefs.edit().putString("manufacturer", "DiPlay")
            .putString("model", "DiPlay")
            .putString("oem_label", "BYD").commit()

        assertEquals("GEELY", AirPlayPersistence.loadOemLabel(context))
        assertEquals("Geely", AirPlayPersistence.loadManufacturer(context))
        assertEquals("Xingyue L", AirPlayPersistence.loadModel(context))
        assertEquals("GEELY", prefs.getString("oem_label", null))
    }

    @Test fun aStandaloneLegacyBydLabelIsPreservedAsUserData() {
        prefs.edit().putString("oem_label", "BYD").commit()
        assertEquals("BYD", AirPlayPersistence.loadOemLabel(context))
    }

    @Test fun userCanExplicitlySaveTheLegacyLabelWithoutFutureMigration() {
        AirPlayPersistence.saveOemLabel(context, "BYD")
        assertEquals("BYD", AirPlayPersistence.loadOemLabel(context))
    }

    @Test fun legacyDefaultMigrationDoesNotReplaceACustomIcon() {
        val customIcon = byteArrayOf(1, 3, 3, 7)
        AirPlayPersistence.saveCustomAirPlayIcon(context, customIcon)
        prefs.edit().putString("manufacturer", "DiPlay")
            .putString("model", "DiPlay")
            .putString("oem_label", "BYD").commit()

        try {
            assertEquals("GEELY", AirPlayPersistence.loadOemLabel(context))
            assertArrayEquals(customIcon, AirPlayPersistence.loadCustomAirPlayIconFile(context)!!.readBytes())
        } finally {
            AirPlayPersistence.clearCustomAirPlayIcon(context)
        }
    }

    @Test fun freshGeelyProfileRoutesNavigationGuidanceThroughMediaStream() {
        HeadUnitProfile.save(context, HeadUnitProfile.GEELY_XINGYUE_L)
        assertEquals(AudioManager.STREAM_MUSIC, AirPlayPersistence.loadNavigationAudioChannel(context))
    }

    @Test fun explicitAutomaticRoutingOverridesGeelyNavigationDefault() {
        HeadUnitProfile.save(context, HeadUnitProfile.GEELY_XINGYUE_L)
        AirPlayPersistence.saveNavigationAudioChannel(context, 0)
        assertEquals(0, AirPlayPersistence.loadNavigationAudioChannel(context))
    }

    @Test fun audioFocusAutoYieldCanBeSavedAndRestored() {
        AirPlayPersistence.saveAudioFocusAutoYield(context, false)
        org.junit.Assert.assertFalse(AirPlayPersistence.loadAudioFocusAutoYield(context))
        AirPlayPersistence.saveAudioFocusAutoYield(context, true)
        org.junit.Assert.assertTrue(AirPlayPersistence.loadAudioFocusAutoYield(context))
    }

    @Test fun legacyNavigationChannelIsInheritedWithoutChangingMedia() {
        AirPlayPersistence.saveNavigationStreamType(context, 15)
        assertEquals(15, AirPlayPersistence.loadNavigationAudioChannel(context))
        assertEquals(0, AirPlayPersistence.loadMediaAudioChannel(context))
    }

    @Test fun explicitNavigationChannelTakesPrecedenceOverLegacySetting() {
        AirPlayPersistence.saveNavigationStreamType(context, 14)
        AirPlayPersistence.saveNavigationAudioChannel(context, 15)
        assertEquals(15, AirPlayPersistence.loadNavigationAudioChannel(context))
    }

    @Test fun explicitAutomaticRoutingTakesPrecedenceOverLegacySetting() {
        AirPlayPersistence.saveNavigationStreamType(context, 15)
        AirPlayPersistence.saveNavigationAudioChannel(context, 0)
        assertEquals(0, AirPlayPersistence.loadNavigationAudioChannel(context))
    }

    @Test fun extendedChannelsCanBeSavedForMediaAndNavigation() {
        for (channel in listOf(11, 14, 15, 20)) {
            AirPlayPersistence.saveMediaAudioChannel(context, channel)
            AirPlayPersistence.saveNavigationAudioChannel(context, channel)
            assertEquals(channel, AirPlayPersistence.loadMediaAudioChannel(context))
            assertEquals(channel, AirPlayPersistence.loadNavigationAudioChannel(context))
        }
    }

    @Test fun existingExtendedChannelsRemainAvailable() {
        prefs.edit().putInt("media_audio_channel", 15).putInt("navigation_audio_channel", 15).apply()
        assertEquals(15, AirPlayPersistence.loadMediaAudioChannel(context))
        assertEquals(15, AirPlayPersistence.loadNavigationAudioChannel(context))
    }

    @Test fun invalidSavedChannelsUseAutomaticRouting() {
        for (channel in listOf(-1, 21)) {
            AirPlayPersistence.saveMediaAudioChannel(context, channel)
            AirPlayPersistence.saveNavigationAudioChannel(context, channel)
            assertEquals(0, AirPlayPersistence.loadMediaAudioChannel(context))
            assertEquals(0, AirPlayPersistence.loadNavigationAudioChannel(context))
        }
    }

    @Test fun invalidStoredChannelsUseAutomaticRouting() {
        AirPlayPersistence.saveNavigationStreamType(context, 15)
        for (channel in listOf(-1, 21)) {
            prefs.edit().putInt("media_audio_channel", channel).putInt("navigation_audio_channel", channel).apply()
            assertEquals(0, AirPlayPersistence.loadMediaAudioChannel(context))
            assertEquals(0, AirPlayPersistence.loadNavigationAudioChannel(context))
        }
        for (channel in listOf(-2, 21)) {
            AirPlayPersistence.saveCallAudioChannel(context, channel)
            assertEquals(AirPlayPersistence.CALL_AUDIO_AUTO, AirPlayPersistence.loadCallAudioChannel(context))
        }
    }

    @Test fun mediaNavigationAndCallStreamsPersistIndependently() {
        AirPlayPersistence.saveMediaAudioChannel(context, 3)
        AirPlayPersistence.saveNavigationAudioChannel(context, 14)
        AirPlayPersistence.saveCallAudioChannel(context, AudioManager.STREAM_VOICE_CALL)

        assertEquals(3, AirPlayPersistence.loadMediaAudioChannel(context))
        assertEquals(14, AirPlayPersistence.loadNavigationAudioChannel(context))
        assertEquals(AudioManager.STREAM_VOICE_CALL, AirPlayPersistence.loadCallAudioChannel(context))
    }

    @Test fun invalidLegacyChannelUsesAutomaticRouting() {
        AirPlayPersistence.saveNavigationStreamType(context, 21)
        assertEquals(0, AirPlayPersistence.loadNavigationAudioChannel(context))
    }
}
