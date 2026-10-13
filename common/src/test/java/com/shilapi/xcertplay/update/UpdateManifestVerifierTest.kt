package com.shilapi.xcertplay.update

import android.util.Base64
import com.shilapi.xcertplay.host.R
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.Signature
import java.security.AlgorithmParameters
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECFieldFp
import java.security.spec.ECParameterSpec
import java.security.spec.EllipticCurve
import java.util.Base64 as JcaBase64
import java.util.Date

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28])
class UpdateManifestVerifierTest {
    private lateinit var keyPair: KeyPair
    private lateinit var trustedKeys: Map<String, ByteArray>
    private val now = Date.from(java.time.Instant.parse("2026-10-12T12:00:00Z"))

    @Before
    fun setUp() {
        keyPair = KeyPairGenerator.getInstance("EC").apply {
            initialize(ECGenParameterSpec("secp256r1"))
        }.generateKeyPair()
        trustedKeys = mapOf(KEY_ID to keyPair.public.encoded)
        RuntimeEnvironment.getApplication().getSharedPreferences("carpaly_ota_replay_guard", 0)
            .edit().clear().commit()
    }

    @Test
    fun validManifestReturnsOnlyNewerVerifiedRelease() {
        val release = verify(signed(availablePayload()))
        assertEquals("v1.1.53", release?.tagName)
        assertEquals("CarPaly-XingyueL-v1.1.53.apk", release?.apkName)
        assertEquals(41L, release?.versionCode)
        assertEquals(UpdateChannel.STABLE, release?.channel)
    }

    @Test
    fun signedTombstoneMeansNoReleaseOnChannel() {
        assertNull(verify(signed(tombstonePayload())))
    }

    @Test
    fun alteredPayloadIsRejected() {
        val envelope = JSONObject(signed(availablePayload()))
        val bytes = Base64.decode(envelope.getString("signedPayload"), Base64.DEFAULT)
        val changed = String(bytes, Charsets.UTF_8).replace("1.1.53", "1.1.54").toByteArray()
        envelope.put("signedPayload", Base64.encodeToString(changed, Base64.NO_WRAP))
        assertThrows(UpdateManifestException::class.java) { verify(envelope.toString()) }
    }

    @Test
    fun wrongKeyAndWrongChannelAreRejected() {
        assertThrows(UpdateManifestException::class.java) {
            UpdateManifestVerifier.verify(signed(availablePayload()), UpdateChannel.STABLE, 40L, emptyMap(), now)
        }
        assertThrows(UpdateManifestException::class.java) {
            verify(signed(availablePayload().put("channel", "beta")))
        }
    }

    @Test
    fun expiredManifestIsRejected() {
        val payload = availablePayload().put("expiresAt", "2026-10-12T11:59:59Z")
        assertThrows(UpdateManifestException::class.java) { verify(signed(payload)) }
    }

    @Test
    fun downgradeAndNoncanonicalUrlAreRejected() {
        assertThrows(UpdateManifestException::class.java) {
            UpdateManifestVerifier.verify(signed(availablePayload()), UpdateChannel.STABLE, 41L, trustedKeys, now)
        }
        val payload = availablePayload().put("apkUrl", "https://example.invalid/update.apk")
        assertThrows(UpdateManifestException::class.java) { verify(signed(payload)) }
    }

    @Test
    fun appPinnedTrustStoreFailsClosedWhenNoProductionKeyIsProvisioned() {
        val context = RuntimeEnvironment.getApplication()
        val trustStore = JSONObject(context.resources.openRawResource(R.raw.ota_manifest_public_keys)
            .bufferedReader().use { it.readText() })
        assertEquals(0, trustStore.getJSONArray("keys").length())
        assertThrows(UpdateManifestException::class.java) { UpdateManifestVerifier.loadPinnedKeys(context) }
    }

    @Test
    fun onlyExactNistP256ParametersAreAccepted() {
        val p256 = AlgorithmParameters.getInstance("EC").run {
            init(ECGenParameterSpec("secp256r1"))
            getParameterSpec(ECParameterSpec::class.java)
        }
        val field = p256.curve.field as ECFieldFp
        val differentCurve = EllipticCurve(
            field,
            (p256.curve.a + java.math.BigInteger.ONE).mod(field.p),
            p256.curve.b,
            p256.curve.seed,
        )
        val sameSizeNonP256 = ECParameterSpec(
            differentCurve, p256.generator, p256.order, p256.cofactor,
        )
        assertEquals(256, sameSizeNonP256.curve.field.fieldSize)
        assertEquals(256, sameSizeNonP256.order.bitLength())
        assertFalse(UpdateManifestVerifier.isP256Curve(sameSizeNonP256))
    }

    @Test
    fun verifiesPythonEcdsaFixtureWithTheAndroidJcaVerifier() {
        val fixture = JSONObject(
            javaClass.getResourceAsStream("/ota_cross_language_vector.json")!!
                .bufferedReader().use { it.readText() },
        )
        val trust = mapOf(
            fixture.getString("keyId") to JcaBase64.getDecoder()
                .decode(fixture.getString("publicKeyX509Base64")),
        )
        val envelope = JSONObject()
            .put("schemaVersion", fixture.getInt("schemaVersion"))
            .put("manifestKeyId", fixture.getString("keyId"))
            .put("signedPayload", fixture.getString("signedPayload"))
            .put("manifestSignature", fixture.getString("manifestSignature"))
            .toString()

        val verified = UpdateManifestVerifier.verifyEnvelope(
            envelope, UpdateChannel.STABLE, 40L, trust,
            Date.from(java.time.Instant.parse("2026-10-13T12:00:00Z")),
        )
        assertEquals("phase11-cross-language-test", verified.keyId)
        assertEquals("stable", JSONObject(String(
            JcaBase64.getDecoder().decode(fixture.getString("signedPayload")), Charsets.UTF_8,
        )).getString("channel"))
    }

    @Test
    fun replayGuardRejectsOlderValidFeedAfterNewerFeedWasAccepted() {
        val context = RuntimeEnvironment.getApplication()
        val newerPayload = availablePayload()
            .put("versionName", "1.1.54")
            .put("versionCode", 42)
            .put("releaseTag", "v1.1.54")
            .put("sourceCommit", "c".repeat(40))
            .put("releaseNotesUrl", "https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.54")
            .put("apkUrl", "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.54/CarPaly-XingyueL-v1.1.54.apk")
            .put("checksumUrl", "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.54/CarPaly-XingyueL-v1.1.54.apk.sha256")
            .put("issuedAt", "2026-10-12T11:00:00Z")
            .put("expiresAt", "2026-11-11T11:00:00Z")
        val newer = UpdateManifestVerifier.verifyEnvelope(
            signed(newerPayload), UpdateChannel.STABLE, 40L, trustedKeys, now,
        )
        UpdateManifestReplayGuard.accept(context, UpdateChannel.STABLE, newer)

        val older = UpdateManifestVerifier.verifyEnvelope(
            signed(availablePayload().put("issuedAt", "2026-10-11T12:00:00Z")
                .put("expiresAt", "2026-11-10T12:00:00Z")),
            UpdateChannel.STABLE, 40L, trustedKeys, now,
        )
        assertThrows(UpdateManifestException::class.java) {
            UpdateManifestReplayGuard.accept(context, UpdateChannel.STABLE, older)
        }
    }

    @Test
    fun identicalManifestIsIdempotentButSameTimestampDifferentPayloadIsRejected() {
        val context = RuntimeEnvironment.getApplication()
        val rawPayload = availablePayload()
        val original = UpdateManifestVerifier.verifyEnvelope(
            signed(rawPayload), UpdateChannel.STABLE, 40L, trustedKeys, now,
        )
        UpdateManifestReplayGuard.accept(context, UpdateChannel.STABLE, original)
        UpdateManifestReplayGuard.accept(context, UpdateChannel.STABLE, original)

        val conflicting = UpdateManifestVerifier.verifyEnvelope(
            signed(availablePayload().put("releaseNotes", "different content")),
            UpdateChannel.STABLE, 40L, trustedKeys, now,
        )
        assertThrows(UpdateManifestException::class.java) {
            UpdateManifestReplayGuard.accept(context, UpdateChannel.STABLE, conflicting)
        }
    }

    private fun verify(document: String): UpdateRelease? =
        UpdateManifestVerifier.verify(document, UpdateChannel.STABLE, 40L, trustedKeys, now)

    private fun signed(payload: JSONObject): String {
        payload.put("manifestKeyId", KEY_ID)
        val payloadBytes = payload.toString().toByteArray(Charsets.UTF_8)
        val signature = Signature.getInstance("SHA256withECDSA").run {
            initSign(keyPair.private)
            update(payloadBytes)
            sign()
        }
        return JSONObject()
            .put("schemaVersion", 1)
            .put("manifestKeyId", KEY_ID)
            .put("signedPayload", Base64.encodeToString(payloadBytes, Base64.NO_WRAP))
            .put("manifestSignature", Base64.encodeToString(signature, Base64.NO_WRAP))
            .toString()
    }

    private fun availablePayload(): JSONObject = JSONObject()
        .put("schemaVersion", 1)
        .put("channel", "stable")
        .put("available", true)
        .put("versionName", "1.1.53")
        .put("versionCode", 41)
        .put("packageName", UpdateManifestVerifier.APPLICATION_ID)
        .put("minimumSupportedVersionCode", 36)
        .put("releaseTag", "v1.1.53")
        .put("sourceCommit", "a".repeat(40))
        .put("releaseDate", "2026-10-11T12:00:00Z")
        .put("releaseNotesUrl", "https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.53")
        .put("releaseNotes", "OTA verification test")
        .put("apkUrl", "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.53/CarPaly-XingyueL-v1.1.53.apk")
        .put("apkSize", 16_000_000)
        .put("apkSha256", "b".repeat(64))
        .put("signerCertSha256", UpdateManifestVerifier.RELEASE_SIGNER_SHA256)
        .put("checksumUrl", "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.53/CarPaly-XingyueL-v1.1.53.apk.sha256")
        .put("checksumSize", 96)
        .put("issuedAt", "2026-10-12T00:00:00Z")
        .put("expiresAt", "2026-11-11T00:00:00Z")

    private fun tombstonePayload(): JSONObject = JSONObject()
        .put("schemaVersion", 1)
        .put("channel", "stable")
        .put("available", false)
        .put("packageName", UpdateManifestVerifier.APPLICATION_ID)
        .put("minimumSupportedVersionCode", 36)
        .put("issuedAt", "2026-10-12T00:00:00Z")
        .put("expiresAt", "2026-11-11T00:00:00Z")

    private companion object {
        const val KEY_ID = "test-ota-key"
    }
}
