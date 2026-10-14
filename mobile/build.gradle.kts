import java.io.ByteArrayInputStream
import java.io.FileInputStream
import java.nio.file.Files
import java.security.KeyFactory
import java.security.KeyStore
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.Signature
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import java.security.interfaces.ECPublicKey
import java.security.spec.PKCS8EncodedKeySpec
import org.gradle.api.tasks.Sync

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

// Optional local-only input. CI and ordinary source builds contain no accessory identity.
val localAuthenticationAssets = providers.environmentVariable("DIPLAY_AUTH_ASSETS_DIR")
    .orNull?.let { file(it).canonicalFile }
val stagedAuthenticationAssets = layout.buildDirectory.dir("generated/authenticationAssets")
val stageAuthenticationAssets by tasks.registering(Sync::class) {
    localAuthenticationAssets?.let { inputRoot ->
        from(inputRoot) {
            include("offline-mfi/identity.pk8", "offline-mfi/certificate.p7b")
        }
    }
    into(stagedAuthenticationAssets)
}
val distributionDebugKeystore = providers.environmentVariable("CARPALY_DEBUG_KEYSTORE_PATH")
    .orNull?.let { file(it).canonicalFile }
val gitCommit = providers.exec {
    commandLine("git", "rev-parse", "--short=12", "HEAD")
}.standardOutput.asText.map { it.trim() }

// v1.1.53 starts a new signing epoch at the user's explicit request. It cannot update
// v1.1.52 or earlier in place; the old signer remains recorded in the version ledger.
val CARPALY_RELEASE_CERT_SHA256 =
    "d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e"

fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
    .digest(bytes)
    .joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }

val verifyCarPalyReleaseSigning by tasks.registering {
    group = "verification"
    description = "Require the ledger-pinned v1.1.53+ Release signing identity before any Release build."
    notCompatibleWithConfigurationCache("Reads protected signing inputs only when a Release build is requested.")
    doLast {
        fun requiredSecret(name: String): String = providers.environmentVariable(name).orNull
            ?.takeIf { it.isNotBlank() }
            ?: error("Authorized Release signing input $name is not configured")

        val keystorePath = requiredSecret("ANDROID_KEYSTORE_PATH")
        val storePassword = requiredSecret("ANDROID_KEYSTORE_PASSWORD").toCharArray()
        val keyAlias = requiredSecret("ANDROID_KEY_ALIAS")
        val keyPassword = requiredSecret("ANDROID_KEY_PASSWORD").toCharArray()
        try {
            val keystoreFile = file(keystorePath).canonicalFile
            check(keystoreFile.isFile && keystoreFile.length() > 0L) {
                "Authorized Release keystore is missing or empty"
            }
            val keystore = KeyStore.getInstance("PKCS12")
            FileInputStream(keystoreFile).use { keystore.load(it, storePassword) }
            check(keystore.isKeyEntry(keyAlias)) { "Configured Release alias is not a private-key entry" }
            val certificate = keystore.getCertificate(keyAlias) as? X509Certificate
                ?: error("Configured Release alias has no X.509 signing certificate")
            check(keystore.getKey(keyAlias, keyPassword) != null) {
                "Configured Release key password does not unlock the signing key"
            }
            val actualFingerprint = sha256(certificate.encoded)
            check(actualFingerprint == CARPALY_RELEASE_CERT_SHA256) {
                "Release keystore does not match the active version-ledger signing certificate"
            }
            val configuredFingerprint = providers.environmentVariable("RELEASE_SIGNING_CERT_SHA256").orNull
                ?.filter(Char::isLetterOrDigit)
                ?.lowercase()
            check(configuredFingerprint == null || configuredFingerprint == CARPALY_RELEASE_CERT_SHA256) {
                "Configured Release certificate pin does not match the active version-ledger signing identity"
            }
            logger.lifecycle("SIGNING_CERTIFICATE_MATCH=PASS (active version-ledger certificate)")
        } catch (_: Exception) {
            error("Release signing identity could not be verified; no Release APK may be produced")
        } finally {
            storePassword.fill('\u0000')
            keyPassword.fill('\u0000')
        }
    }
}

fun verifyMfiIdentity(directory: java.io.File): Map<String, String> {
    val identityFile = directory.resolve("offline-mfi/identity.pk8")
    val certificateFile = directory.resolve("offline-mfi/certificate.p7b")
    require(identityFile.isFile && identityFile.length() in 1..16_384) {
        "Local MFi PKCS#8 identity is missing, empty, or too large"
    }
    require(certificateFile.isFile && certificateFile.length() in 1..16_384) {
        "Local MFi certificate bundle is missing, empty, or too large"
    }

    val identityBytes = identityFile.readBytes()
    val privateKey = try {
        KeyFactory.getInstance("EC").generatePrivate(PKCS8EncodedKeySpec(identityBytes))
    } finally {
        identityBytes.fill(0)
    }
    require(privateKey.algorithm.equals("EC", ignoreCase = true)) {
        "Local MFi identity is not an EC PKCS#8 private key"
    }

    val certificateBytes = certificateFile.readBytes()
    val parsedCertificates = ByteArrayInputStream(certificateBytes).use { encoded ->
        CertificateFactory.getInstance("X.509").generateCertificates(encoded)
    }
    require(parsedCertificates.size == 1) { "Expected exactly one X.509 certificate in the P7B bundle" }
    val certificate = parsedCertificates.single() as? X509Certificate
        ?: error("Local MFi P7B does not contain an X.509 certificate")
    val publicKey = certificate.publicKey as? ECPublicKey
        ?: error("Expected an EC accessory certificate")
    require(publicKey.params.order.toString(16).equals(
        "ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551",
        ignoreCase = true,
    )) { "Expected a P-256 accessory certificate" }

    val random = SecureRandom()
    repeat(6) {
        val challenge = ByteArray(32).also(random::nextBytes)
        val signature = Signature.getInstance("NONEwithECDSA").run {
            initSign(privateKey)
            update(challenge)
            sign()
        }
        val verified = Signature.getInstance("NONEwithECDSA").run {
            initVerify(publicKey)
            update(challenge)
            verify(signature)
        }
        require(verified) { "Local MFi private key does not match its X.509 certificate" }
    }

    return mapOf(
        "identity.pk8" to sha256(identityFile.readBytes()),
        "certificate.p7b" to sha256(certificateBytes),
    )
}

android {
    namespace = "com.shilapi.xcertplay"
    compileSdk {
        version = release(37)
    }

    defaultConfig {
        applicationId = "com.shihab.diplay.hudtest"
        minSdk = 25
        targetSdk = 37
        versionCode = 42
        versionName = "1.1.54"
        buildConfigField("String", "GIT_COMMIT", "\"${gitCommit.get()}\"")

    }


    // Stage only the two selected runtime inputs and expose them to Release only.
    // DIPLAY_AUTH_ASSETS_DIR may be the repository root, so never register that parent directory itself.
    localAuthenticationAssets?.let {
        sourceSets.getByName("release").assets.directories.add(stagedAuthenticationAssets.get().asFile.absolutePath)
    }

    signingConfigs {
        create("release") {
            storeFile = file(
                providers.environmentVariable("ANDROID_KEYSTORE_PATH")
                    .getOrElse("missing-release-keystore.jks"),
            )
            storePassword = providers.environmentVariable("ANDROID_KEYSTORE_PASSWORD").getOrElse("")
            keyAlias = providers.environmentVariable("ANDROID_KEY_ALIAS").getOrElse("")
            keyPassword = providers.environmentVariable("ANDROID_KEY_PASSWORD").getOrElse("")
            storeType = "PKCS12"
        }
        create("distributionDebug") {
            storeFile = distributionDebugKeystore ?: file("missing-distribution-debug-keystore.jks")
            storePassword = providers.environmentVariable("CARPALY_DEBUG_KEYSTORE_PASSWORD").getOrElse("")
            keyAlias = providers.environmentVariable("CARPALY_DEBUG_KEY_ALIAS").getOrElse("")
            keyPassword = providers.environmentVariable("CARPALY_DEBUG_KEY_PASSWORD").getOrElse("")
        }
    }

    buildTypes {
        debug {
            if (distributionDebugKeystore != null) {
                signingConfig = signingConfigs.getByName("distributionDebug")
            }
        }
        release {
            optimization {
                enable = false
            }
            signingConfig = signingConfigs.getByName("release")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

// A Release APK must never silently fall back to the developer/debug signer.
tasks.matching { it.name == "preReleaseBuild" }.configureEach {
    dependsOn(verifyCarPalyReleaseSigning)
}

dependencies {
    implementation(platform(libs.androidx.compose.bom))
    implementation(project(":common"))
    implementation(project(":shared"))
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.app.projected)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    debugImplementation(libs.androidx.compose.ui.tooling)
}

// No implicit import. Only the two explicitly selected local runtime assets are allowed.
val credentialAssets = files(android.sourceSets.flatMap { source ->
    source.assets.directories.map { directory ->
        fileTree(directory) {
            include("**/offline-mfi/**", "**/*.pk8", "**/*.p7b", "**/*.key",
                "**/*.pem", "**/*.p12", "**/*.pfx", "**/*.jks", "**/*.keystore")
        }
    }
})
val rejectBundledCredentials by tasks.registering {
    group = "verification"
    description = "Reject unexpected credential files in APK assets."
    val filesToCheck = credentialAssets
    val allowed = localAuthenticationAssets?.let {
        listOf("identity.pk8", "certificate.p7b")
            .map { name -> stagedAuthenticationAssets.get().file("offline-mfi/$name").asFile.canonicalFile }
            .toSet()
    } ?: emptySet()
    if (localAuthenticationAssets != null) dependsOn(stageAuthenticationAssets)
    inputs.files(filesToCheck)
    doLast {
        check(allowed.all { it.isFile }) { "Explicit local authentication assets are incomplete" }
        val unexpected = filesToCheck.files.filter { it.canonicalFile !in allowed }
        check(unexpected.isEmpty()) { "Unexpected credential files in APK assets" }
    }
}
tasks.named("preBuild") { dependsOn(rejectBundledCredentials) }

// Only user-facing Release builds may receive explicit runtime authentication assets.
val verifyStandaloneAuthentication by tasks.registering {
    group = "verification"
    description = "Validate the explicit runtime authentication inputs for a user Release APK."
    notCompatibleWithConfigurationCache("Validates local authentication material without serializing it into the configuration cache.")
    val directory = localAuthenticationAssets
    doLast {
        check(directory != null) {
            "Authenticated Release builds require DIPLAY_AUTH_ASSETS_DIR; Debug builds stay identity-free."
        }
        val authDirectory = directory.resolve("offline-mfi")
        val expectedPaths = setOf(
            "offline-mfi/identity.pk8",
            "offline-mfi/certificate.p7b",
        )
        check(authDirectory.isDirectory && !Files.isSymbolicLink(authDirectory.toPath())) {
            "Authentication asset directory must contain an offline-mfi folder"
        }
        val actualPaths = authDirectory.walkTopDown()
            .filter { it.isFile || Files.isSymbolicLink(it.toPath()) }
            .map { it.relativeTo(directory).invariantSeparatorsPath }
            .toSet()
        check(actualPaths == expectedPaths) {
            "Authentication asset directory must contain exactly identity.pk8 and certificate.p7b"
        }
        check(authDirectory.walkTopDown().none { Files.isSymbolicLink(it.toPath()) }) {
            "Authentication asset directory cannot contain symbolic links"
        }
        verifyMfiIdentity(directory)
        logger.lifecycle(
            "MFi identity validated as PKCS#8 + one P-256 X.509 certificate; 6 challenge signatures verified.",
        )
    }
}
if (localAuthenticationAssets != null) {
    tasks.matching { it.name == "preReleaseBuild" }.configureEach {
        dependsOn(verifyStandaloneAuthentication)
    }
}
