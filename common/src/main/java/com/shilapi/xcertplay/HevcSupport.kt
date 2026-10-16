package com.shilapi.xcertplay

import android.media.MediaCodecList
import android.media.MediaFormat
import android.os.Build

/** Keep the session on H.264 unless a usable HEVC decoder is available. */
internal object HevcSupport {
    data class Decoder(val name: String, val hardware: Boolean)

    fun usable(requested: Boolean, softwareChosen: Boolean, decoders: List<Decoder>): Boolean =
        requested && (decoders.any { it.hardware } || (softwareChosen && decoders.isNotEmpty()))

    fun decoders(): List<Decoder> = runCatching {
        MediaCodecList(MediaCodecList.REGULAR_CODECS).codecInfos.filter { info ->
            !info.isEncoder && info.supportedTypes.any {
                it.equals(MediaFormat.MIMETYPE_VIDEO_HEVC, ignoreCase = true)
            }
        }.map { info ->
            Decoder(
                info.name,
                if (Build.VERSION.SDK_INT >= 29) info.isHardwareAccelerated
                else !info.name.startsWith("OMX.google.") && !info.name.startsWith("c2.android."),
            )
        }
    }.getOrDefault(emptyList())
}
