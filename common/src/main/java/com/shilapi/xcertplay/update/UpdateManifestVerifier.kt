package com.shilapi.xcertplay.update

import android.content.Context
import android.util.Base64
import com.shilapi.xcertplay.host.R
import org.json.JSONObject
import java.io.IOException
import java.math.BigInteger
import java.net.URI
import java.security.KeyFactory
import java.security.MessageDigest
import java.security.Signature
import java.security.interfaces.ECKey
import java.security.spec.ECFieldFp
import java.security.spec.ECParameterSpec
import java.security.spec.X509EncodedKeySpec
import java.text.ParsePosition
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

internal class UpdateManifestException(message: String) : IOException(message)

/** Metadata that remains bound to the exact signed payload bytes. */
internal data class VerifiedUpdateManifest(
    val release: UpdateRelease?,
    val issuedAtMillis: Long,
    val keyId: String,
    val payloadSha256: String,
)

/** Verifies the signed payload before trusting any release metadata or download URL. */
internal object UpdateManifestVerifier {
    internal const val MANIFEST_BASE_URL = "https://qwy20040320.github.io/carpaly/updates/"
    internal const val APPLICATION_ID = "com.shihab.diplay.hudtest"
    internal const val RELEASE_SIGNER_SHA256 =
        "4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90"
    private const val REPOSITORY = "Qwy20040320/carpaly"
    private const val MAX_MANIFEST_BYTES = 32 * 1024
    private const val MAX_APK_BYTES = 50L * 1024L * 1024L
    private const val MAX_MANIFEST_LIFETIME_SECONDS = 45L * 24L * 60L * 60L
    private val versionPattern = Regex("^\\d+\\.\\d+\\.\\d+$")
    private val sha256Pattern = Regex("^[0-9a-f]{64}$")
    private val keyIdPattern = Regex("^[A-Za-z0-9._-]{1,64}$")

    internal fun channelUrl(channel: UpdateChannel): String =
        MANIFEST_BASE_URL + if (channel == UpdateChannel.STABLE) "stable.json" else "beta.json"

    internal fun loadPinnedKeys(context: Context): Map<String, ByteArray> {
        val root = try {
            JSONObject(context.resources.openRawResource(R.raw.ota_manifest_public_keys)
                .bufferedReader(Charsets.UTF_8).use { it.readText() })
        } catch (_: Exception) {
            throw UpdateManifestException("OTA trust store is unavailable")
        }
        if (root.optInt("schemaVersion", -1) != 1) throw UpdateManifestException("Unsupported OTA trust-store schema")
        val records = root.optJSONArray("keys") ?: throw UpdateManifestException("OTA trust store is malformed")
        val trusted = linkedMapOf<String, ByteArray>()
        val seenKeyIds = mutableSetOf<String>()
        for (index in 0 until records.length()) {
            val item = records.optJSONObject(index) ?: throw UpdateManifestException("OTA trust-store entry is malformed")
            val keyId = item.optString("keyId")
            val status = item.optString("status")
            if (!keyIdPattern.matches(keyId) || item.optString("algorithm") != "SHA256withECDSA-P256") {
                throw UpdateManifestException("OTA trust-store entry has unsupported key metadata")
            }
            if (!seenKeyIds.add(keyId)) throw UpdateManifestException("OTA trust store contains duplicate key ids")
            if (status == "revoked") continue
            if (status !in setOf("active", "retiring")) throw UpdateManifestException("OTA trust-store key status is invalid")
            val encoded = try {
                Base64.decode(item.getString("publicKeyX509Base64"), Base64.DEFAULT)
            } catch (_: Exception) {
                throw UpdateManifestException("OTA trust-store public key is malformed")
            }
            runCatching {
                val key = KeyFactory.getInstance("EC").generatePublic(X509EncodedKeySpec(encoded))
                require(key.algorithm.equals("EC", ignoreCase = true))
                val parameters = (key as? ECKey)?.params ?: error("Missing EC parameters")
                require(isP256Curve(parameters))
            }.onFailure { throw UpdateManifestException("OTA trust-store public key cannot be parsed") }
            trusted[keyId] = encoded
        }
        if (trusted.isEmpty()) throw UpdateManifestException("OTA updates are not provisioned: no app-pinned manifest key")
        return trusted
    }

    /** Returns null only for a correctly signed channel tombstone or a signed manifest with no newer version. */
    internal fun verify(
        document: String,
        channel: UpdateChannel,
        installedVersionCode: Long,
        trustedKeys: Map<String, ByteArray>,
        now: Date = Date(),
    ): UpdateRelease? = verifyEnvelope(document, channel, installedVersionCode, trustedKeys, now).release

    internal fun verifyEnvelope(
        document: String,
        channel: UpdateChannel,
        installedVersionCode: Long,
        trustedKeys: Map<String, ByteArray>,
        now: Date = Date(),
    ): VerifiedUpdateManifest {
        if (document.toByteArray(Charsets.UTF_8).size > MAX_MANIFEST_BYTES) {
            throw UpdateManifestException("OTA update manifest exceeds the size limit")
        }
        val envelope = try {
            JSONObject(document)
        } catch (_: Exception) {
            throw UpdateManifestException("OTA update manifest is not valid JSON")
        }
        val expectedEnvelopeFields = setOf("schemaVersion", "manifestKeyId", "signedPayload", "manifestSignature")
        if (jsonKeys(envelope) != expectedEnvelopeFields || envelope.optInt("schemaVersion", -1) != 1) {
            throw UpdateManifestException("OTA manifest envelope has an unsupported schema")
        }
        val keyId = envelope.optString("manifestKeyId")
        if (!keyIdPattern.matches(keyId)) throw UpdateManifestException("OTA manifest key id is invalid")
        val publicKeyBytes = trustedKeys[keyId]
            ?: throw UpdateManifestException("OTA manifest signer is not trusted by this app")
        val payloadBytes = try {
            Base64.decode(envelope.getString("signedPayload"), Base64.DEFAULT)
        } catch (_: Exception) {
            throw UpdateManifestException("OTA signed payload is malformed")
        }
        val signatureBytes = try {
            Base64.decode(envelope.getString("manifestSignature"), Base64.DEFAULT)
        } catch (_: Exception) {
            throw UpdateManifestException("OTA manifest signature is malformed")
        }
        val signatureValid = runCatching {
            val publicKey = KeyFactory.getInstance("EC").generatePublic(X509EncodedKeySpec(publicKeyBytes))
            val parameters = (publicKey as? ECKey)?.params ?: error("Missing EC parameters")
            require(isP256Curve(parameters))
            Signature.getInstance("SHA256withECDSA").run {
                initVerify(publicKey)
                update(payloadBytes)
                verify(signatureBytes)
            }
        }.getOrDefault(false)
        if (!signatureValid) throw UpdateManifestException("OTA manifest signature verification failed")
        val payload = try {
            JSONObject(String(payloadBytes, Charsets.UTF_8))
        } catch (_: Exception) {
            throw UpdateManifestException("Signed OTA payload is not valid JSON")
        }
        if (payload.optInt("schemaVersion", -1) != 1 || payload.optString("manifestKeyId") != keyId) {
            throw UpdateManifestException("Signed OTA payload schema or key id is inconsistent")
        }
        val requestedChannel = if (channel == UpdateChannel.STABLE) "stable" else "beta"
        if (payload.optString("channel") != requestedChannel) {
            throw UpdateManifestException("Signed OTA payload is for a different update channel")
        }
        val issuedAt = validateFreshness(payload, now)
        val payloadSha256 = MessageDigest.getInstance("SHA-256").digest(payloadBytes).toHex()
        if (payload.optString("packageName") != APPLICATION_ID) {
            throw UpdateManifestException("OTA payload package does not match CarPaly")
        }
        val minimumVersionCode = exactLong(payload, "minimumSupportedVersionCode")
        if (minimumVersionCode < 1L || installedVersionCode < minimumVersionCode) {
            throw UpdateManifestException("This installed version is below the OTA channel's supported minimum")
        }
        val available = payload.optBoolean("available", false)
        if (!available) {
            if (jsonKeys(payload) != TOMBSTONE_FIELDS) throw UpdateManifestException("Unavailable-channel payload has unexpected fields")
            return VerifiedUpdateManifest(null, issuedAt.time, keyId, payloadSha256)
        }
        if (jsonKeys(payload) != AVAILABLE_FIELDS) throw UpdateManifestException("Available OTA payload has unexpected or missing fields")
        val versionName = payload.optString("versionName")
        val releaseTag = payload.optString("releaseTag")
        val sourceCommit = payload.optString("sourceCommit")
        val versionCode = exactLong(payload, "versionCode")
        val apkSize = exactLong(payload, "apkSize")
        val minimum = exactLong(payload, "minimumSupportedVersionCode")
        val digest = payload.optString("apkSha256")
        val signer = payload.optString("signerCertSha256")
        if (!versionPattern.matches(versionName) || releaseTag != "v$versionName" ||
            !Regex("^[0-9a-f]{40}$").matches(sourceCommit) || versionCode <= installedVersionCode) {
            throw UpdateManifestException("OTA version metadata is invalid or is not newer than this installation")
        }
        if (minimum != minimumVersionCode || versionCode < minimum || apkSize !in 1L..MAX_APK_BYTES) {
            throw UpdateManifestException("OTA package size or version floor is invalid")
        }
        if (!sha256Pattern.matches(digest) || signer != RELEASE_SIGNER_SHA256) {
            throw UpdateManifestException("OTA package digest or pinned Release signer metadata is invalid")
        }
        val apkName = "CarPaly-XingyueL-v$versionName.apk"
        val expectedApkUrl = "https://github.com/$REPOSITORY/releases/download/$releaseTag/$apkName"
        val expectedChecksumUrl = "$expectedApkUrl.sha256"
        val expectedReleaseUrl = "https://github.com/$REPOSITORY/releases/tag/$releaseTag"
        if (payload.optString("apkUrl") != expectedApkUrl ||
            payload.optString("checksumUrl") != expectedChecksumUrl ||
            payload.optString("releaseNotesUrl") != expectedReleaseUrl) {
            throw UpdateManifestException("OTA URLs do not match the canonical CarPaly Release")
        }
        if (payload.optString("releaseNotes").length > 8_000 ||
            payload.optLong("checksumSize", -1) !in 1L..256L) {
            throw UpdateManifestException("OTA release notes or checksum metadata exceeds its limits")
        }
        parseInstant(payload.optString("releaseDate"), "release date")
        val checksumSize = exactLong(payload, "checksumSize")
        return VerifiedUpdateManifest(
            release = UpdateRelease(
                tagName = releaseTag,
                versionName = versionName,
                apkName = apkName,
                apkUrl = expectedApkUrl,
                checksumUrl = expectedChecksumUrl,
                checksumSizeBytes = checksumSize,
                releasePageUrl = expectedReleaseUrl,
                releaseNotes = payload.optString("releaseNotes"),
                sizeBytes = apkSize,
                isPrerelease = requestedChannel == "beta",
                sha256 = digest,
                versionCode = versionCode,
                releaseDate = payload.optString("releaseDate"),
                channel = channel,
                minimumSupportedVersionCode = minimum,
                signerCertSha256 = signer,
            ),
            issuedAtMillis = issuedAt.time,
            keyId = keyId,
            payloadSha256 = payloadSha256,
        )
    }

    private fun validateFreshness(payload: JSONObject, now: Date): Date {
        val issued = parseInstant(payload.optString("issuedAt"), "issued time")
        val expires = parseInstant(payload.optString("expiresAt"), "expiry")
        if (issued.time > now.time + 300_000L || expires.time <= now.time || expires.time <= issued.time ||
            expires.time - issued.time > MAX_MANIFEST_LIFETIME_SECONDS * 1_000L) {
            throw UpdateManifestException("OTA manifest has expired or has an invalid validity window")
        }
        return issued
    }

    private fun parseInstant(value: String, label: String): Date {
        val parser = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.ROOT).apply {
            isLenient = false
            timeZone = TimeZone.getTimeZone("UTC")
        }
        val position = ParsePosition(0)
        val parsed = parser.parse(value, position)
        if (parsed == null || position.index != value.length) throw UpdateManifestException("OTA $label is invalid")
        return parsed
    }

    private fun exactLong(json: JSONObject, field: String): Long {
        val value = json.opt(field)
        val result = when (value) {
            is Int -> value.toLong()
            is Long -> value
            else -> throw UpdateManifestException("OTA field $field must be an integer")
        }
        return result
    }

    private fun jsonKeys(json: JSONObject): Set<String> = buildSet {
        val names = json.keys()
        while (names.hasNext()) add(names.next())
    }

    /** Require the named NIST P-256 domain parameters, not merely any 256-bit EC curve. */
    internal fun isP256Curve(parameters: ECParameterSpec): Boolean = runCatching {
        val actualField = parameters.curve.field as? ECFieldFp ?: return false
        actualField.p == P256_P &&
            parameters.curve.a == P256_A &&
            parameters.curve.b == P256_B &&
            parameters.generator.affineX == P256_GX &&
            parameters.generator.affineY == P256_GY &&
            parameters.order == P256_N &&
            parameters.cofactor == 1
    }.getOrDefault(false)

    private val P256_P = BigInteger("FFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF", 16)
    private val P256_A = BigInteger("FFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFC", 16)
    private val P256_B = BigInteger("5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B", 16)
    private val P256_GX = BigInteger("6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296", 16)
    private val P256_GY = BigInteger("4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5", 16)
    private val P256_N = BigInteger("FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551", 16)

    private fun ByteArray.toHex(): String = joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }

    private val TOMBSTONE_FIELDS = setOf(
        "schemaVersion", "channel", "available", "packageName", "minimumSupportedVersionCode",
        "manifestKeyId", "issuedAt", "expiresAt",
    )
    private val AVAILABLE_FIELDS = setOf(
        "schemaVersion", "channel", "available", "versionName", "versionCode", "packageName",
        "minimumSupportedVersionCode", "releaseTag", "sourceCommit", "releaseDate", "releaseNotesUrl", "releaseNotes",
        "apkUrl", "apkSize", "apkSha256", "signerCertSha256", "checksumUrl", "checksumSize",
        "manifestKeyId", "issuedAt", "expiresAt",
    )
}
