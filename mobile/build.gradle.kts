import java.io.ByteArrayInputStream
import java.security.KeyFactory
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.Signature
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import java.security.interfaces.ECPublicKey
import java.security.spec.PKCS8EncodedKeySpec
import java.util.zip.ZipFile

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

// Optional local-only input. CI and ordinary source builds contain no accessory identity.
val localAuthenticationAssets = providers.environmentVariable("DIPLAY_AUTH_ASSETS_DIR")
    .orNull?.let { file(it).canonicalFile }
val distributionDebugKeystore = providers.environmentVariable("CARPALY_DEBUG_KEYSTORE_PATH")
    .orNull?.let { file(it).canonicalFile }
val gitCommit = providers.exec {
    commandLine("git", "rev-parse", "--short=12", "HEAD")
}.standardOutput.asText.map { it.trim() }

fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
    .digest(bytes)
    .joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }

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
        applicationId = "com.shihab.diplay"
        minSdk = 25
        targetSdk = 37
        versionCode = 36
        versionName = "1.1.4"
        buildConfigField("String", "GIT_COMMIT", "\"${gitCommit.get()}\"")

    }


    localAuthenticationAssets?.let { sourceSets.getByName("main").assets.srcDir(it) }

    signingConfigs {
        create("release") {
            storeFile = file(
                providers.environmentVariable("ANDROID_KEYSTORE_PATH")
                    .getOrElse("missing-release-keystore.jks"),
            )
            storePassword = providers.environmentVariable("ANDROID_KEYSTORE_PASSWORD").getOrElse("")
            keyAlias = providers.environmentVariable("ANDROID_KEY_ALIAS").getOrElse("")
            keyPassword = providers.environmentVariable("ANDROID_KEY_PASSWORD").getOrElse("")
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
            applicationIdSuffix = ".hudtest"
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
    val allowed = localAuthenticationAssets?.let { dir ->
        listOf("identity.pk8", "certificate.p7b").map { dir.resolve("offline-mfi/$it").canonicalFile }.toSet()
    } ?: emptySet()
    inputs.files(filesToCheck)
    doLast {
        check(allowed.all { it.isFile }) { "Explicit local authentication assets are incomplete" }
        val unexpected = filesToCheck.files.filter { it.canonicalFile !in allowed }
        check(unexpected.isEmpty()) { "Unexpected credential files in APK assets" }
    }
}
tasks.named("preBuild") { dependsOn(rejectBundledCredentials) }

// Car-test packages must be standalone. Keep ordinary source/CI builds identity-free.
val verifyStandaloneAuthentication by tasks.registering {
    group = "verification"
    description = "Require the explicit runtime authentication input for a standalone car-test APK."
    val directory = localAuthenticationAssets
    doLast {
        check(directory != null) {
            "Standalone car builds require DIPLAY_AUTH_ASSETS_DIR; assembleDebug alone is source-only."
        }
        verifyMfiIdentity(directory)
        logger.lifecycle(
            "MFi identity validated as PKCS#8 + one P-256 X.509 certificate; 6 challenge signatures verified.",
        )
    }
}
tasks.named("preBuild") { mustRunAfter(verifyStandaloneAuthentication) }
tasks.register("assembleStandaloneDebug") {
    group = "build"
    description = "Build a standalone car-test APK with explicitly provisioned authentication."
    dependsOn(verifyStandaloneAuthentication, "assembleDebug")
}

tasks.register("verifyStandaloneDebugApk") {
    group = "verification"
    description = "Build a standalone authenticated debug APK and verify both embedded identity assets."
    dependsOn("assembleStandaloneDebug")
    doLast {
        val directory = checkNotNull(localAuthenticationAssets)
        val sourceHashes = verifyMfiIdentity(directory)
        val apk = layout.buildDirectory.file("outputs/apk/debug/mobile-debug.apk").get().asFile
        check(apk.isFile && apk.length() > 0) { "Standalone mobile APK was not produced" }

        ZipFile(apk).use { archive ->
            for ((name, expectedHash) in sourceHashes) {
                val entryName = "assets/offline-mfi/$name"
                val entry = archive.getEntry(entryName)
                    ?: error("Authenticated APK is missing $entryName")
                val actualHash = archive.getInputStream(entry).use { input ->
                    val digest = MessageDigest.getInstance("SHA-256")
                    val buffer = ByteArray(8192)
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        digest.update(buffer, 0, count)
                    }
                    digest.digest().joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
                }
                check(actualHash == expectedHash) { "Authenticated APK asset hash mismatch for $name" }
            }
        }

        val report = layout.buildDirectory.file("reports/standalone-authentication-verification.txt").get().asFile
        report.parentFile.mkdirs()
        report.writeText(
            buildString {
                appendLine("APK: ${apk.name}")
                appendLine("Bytes: ${apk.length()}")
                appendLine("Application ID: ${android.defaultConfig.applicationId}${android.buildTypes.getByName("debug").applicationIdSuffix}")
                appendLine("Version name: ${android.defaultConfig.versionName}")
                appendLine("Version code: ${android.defaultConfig.versionCode}")
                sourceHashes.toSortedMap().forEach { (name, hash) -> appendLine("$name SHA-256: $hash") }
                appendLine("APK SHA-256: ${sha256(apk.readBytes())}")
                appendLine("Signature: verify separately with apksigner")
                appendLine("Vehicle and iPhone CarPlay runtime: NOT_TESTED")
            },
        )
        logger.lifecycle("Authenticated APK asset hashes verified; report: ${report.absolutePath}")
    }
}
