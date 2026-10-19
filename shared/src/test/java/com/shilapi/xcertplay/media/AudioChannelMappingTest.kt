package com.shilapi.xcertplay.media

import android.media.AudioManager
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AudioChannelMappingTest {
    @Test
    fun protocolAudioClassificationOnlyClaimsExplicitTypes() {
        assertEquals(
            AudioTypeClassification(CarPlayAudioClass.MUSIC, "protocol_audio_type"),
            AudioTypeClassifier.classify("media"),
        )
        assertEquals(
            AudioTypeClassification(CarPlayAudioClass.NAVIGATION, "protocol_audio_type"),
            AudioTypeClassifier.classify("navigation"),
        )
        assertEquals(
            AudioTypeClassification(CarPlayAudioClass.SIRI, "protocol_audio_type"),
            AudioTypeClassifier.classify("speechRecognition"),
        )
        assertEquals(
            AudioTypeClassification(CarPlayAudioClass.CALL, "protocol_audio_type"),
            AudioTypeClassifier.classify("telephony"),
        )
        assertEquals(
            AudioTypeClassification(CarPlayAudioClass.SYSTEM, "protocol_audio_type"),
            AudioTypeClassifier.classify("system"),
        )
    }

    @Test
    fun ambiguousOrMissingProtocolTypesRemainUnknown() {
        listOf(null, "", "default", "alert", "compatibility", "future-type").forEach { type ->
            assertEquals(
                AudioTypeClassification(
                    CarPlayAudioClass.UNKNOWN,
                    "unmapped_or_missing_protocol_audio_type",
                ),
                AudioTypeClassifier.classify(type),
            )
        }
    }

    @Test
    fun mobileCompatibleMappingMatchesTheOriginalRouting() {
        assertMapped(
            mode = AudioChannelMappingMode.MOBILE_COMPATIBLE,
            audioType = "telephony",
            payloadType = 100,
            channel = AudioChannel.PHONE,
            contentType = AudioContentType.SPEECH,
        )
        assertMapped(
            mode = AudioChannelMappingMode.MOBILE_COMPATIBLE,
            audioType = "speechRecognition",
            payloadType = 100,
            channel = AudioChannel.ASSISTANT,
            contentType = AudioContentType.SPEECH,
        )
        assertMapped(
            mode = AudioChannelMappingMode.MOBILE_COMPATIBLE,
            audioType = "media",
            payloadType = 100,
            channel = AudioChannel.MEDIA,
            contentType = AudioContentType.MUSIC,
        )
        listOf("default", "alert", "compatibility").forEach { audioType ->
            assertMapped(
                mode = AudioChannelMappingMode.MOBILE_COMPATIBLE,
                audioType = audioType,
                payloadType = 100,
                channel = AudioChannel.NAVIGATION,
                contentType = AudioContentType.SPEECH,
                streamType = AudioChannelMapper.DEFAULT_NAVIGATION_STREAM_TYPE,
            )
        }
    }

    @Test
    fun automotiveMappingUsesTheBusSpecificCarPlayTypes() {
        listOf("media", "compatibility").forEach { audioType ->
            assertMapped(
                mode = AudioChannelMappingMode.AUTOMOTIVE_BUS,
                audioType = audioType,
                payloadType = 100,
                channel = AudioChannel.MEDIA,
                contentType = AudioContentType.MUSIC,
            )
        }
        assertMapped(
            mode = AudioChannelMappingMode.AUTOMOTIVE_BUS,
            audioType = "telephony",
            payloadType = 100,
            channel = AudioChannel.PHONE,
            contentType = AudioContentType.SPEECH,
        )
        assertMapped(
            mode = AudioChannelMappingMode.AUTOMOTIVE_BUS,
            audioType = "speechRecognition",
            payloadType = 100,
            channel = AudioChannel.ASSISTANT,
            contentType = AudioContentType.SPEECH,
        )
        listOf("default", "alert").forEach { audioType ->
            assertMapped(
                mode = AudioChannelMappingMode.AUTOMOTIVE_BUS,
                audioType = audioType,
                payloadType = 100,
                channel = AudioChannel.NAVIGATION,
                contentType = AudioContentType.SPEECH,
                streamType = AudioChannelMapper.DEFAULT_NAVIGATION_STREAM_TYPE,
            )
        }
    }

    @Test
    fun unknownTypesKeepTheMainHighAudioFallback() {
        assertMapped(
            mode = AudioChannelMappingMode.MOBILE_COMPATIBLE,
            audioType = "unknown",
            payloadType = AudioChannelMapper.STREAM_TYPE_MAIN_HIGH_AUDIO,
            channel = AudioChannel.MEDIA,
            contentType = AudioContentType.MUSIC,
        )
        assertMapped(
            mode = AudioChannelMappingMode.AUTOMOTIVE_BUS,
            audioType = "unknown",
            payloadType = 100,
            channel = AudioChannel.NAVIGATION,
            contentType = AudioContentType.SPEECH,
            streamType = AudioChannelMapper.DEFAULT_NAVIGATION_STREAM_TYPE,
        )
    }

    @Test
    fun navigationStreamTypeIsOnlyAppliedToGuidanceChannels() {
        val custom = 7
        assertEquals(
            AudioChannelSelection(AudioChannel.NAVIGATION, AudioContentType.SPEECH, custom),
            AudioChannelMapper.map("alert", 100, AudioChannelMappingMode.MOBILE_COMPATIBLE, custom),
        )
        assertEquals(
            AudioChannelSelection(AudioChannel.NAVIGATION, AudioContentType.SPEECH, custom),
            AudioChannelMapper.map("default", 100, AudioChannelMappingMode.AUTOMOTIVE_BUS, custom),
        )
        assertEquals(
            AudioChannelSelection(AudioChannel.MEDIA, AudioContentType.MUSIC, AudioManager.STREAM_MUSIC),
            AudioChannelMapper.map("media", 100, AudioChannelMappingMode.AUTOMOTIVE_BUS, custom),
        )
    }

    @Test
    fun mediaNavigationAndCallRouteOverridesStayIndependent() {
        val overrides = AudioChannelOverrides(media = 3, navigation = 14, call = AudioManager.STREAM_VOICE_CALL)
        assertEquals(3, overrides.forChannel(AudioChannel.MEDIA))
        assertEquals(14, overrides.forChannel(AudioChannel.NAVIGATION))
        assertEquals(AudioManager.STREAM_VOICE_CALL, overrides.forChannel(AudioChannel.PHONE))
        assertEquals(0, overrides.forChannel(AudioChannel.ASSISTANT))
        assertEquals(CALL_AUDIO_AUTO, AudioChannelOverrides().forChannel(AudioChannel.PHONE))
    }

    @Test
    fun voiceCallStreamZeroRemainsDistinctFromAutomaticUsageRouting() {
        assertTrue(usesUsageBasedAudioRouting(AudioChannel.PHONE, CALL_AUDIO_AUTO))
        assertFalse(usesUsageBasedAudioRouting(AudioChannel.PHONE, AudioManager.STREAM_VOICE_CALL))
        assertTrue(usesUsageBasedAudioRouting(AudioChannel.MEDIA, 0))
        assertTrue(usesUsageBasedAudioRouting(AudioChannel.NAVIGATION, 0))
        assertTrue(usesUsageBasedAudioRouting(AudioChannel.ASSISTANT, AudioManager.STREAM_MUSIC))
        assertFalse(usesUsageBasedAudioRouting(AudioChannel.NAVIGATION, 14))
    }

    private fun assertMapped(
        mode: AudioChannelMappingMode,
        audioType: String,
        payloadType: Int,
        channel: AudioChannel,
        contentType: AudioContentType,
        streamType: Int = AudioManager.STREAM_MUSIC,
    ) {
        assertEquals(
            AudioChannelSelection(channel, contentType, streamType),
            AudioChannelMapper.map(audioType, payloadType, mode),
        )
    }
}
