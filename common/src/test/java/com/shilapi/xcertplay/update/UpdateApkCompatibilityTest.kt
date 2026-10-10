package com.shilapi.xcertplay.update

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class UpdateApkCompatibilityTest {
    private val installed = UpdateApkIdentity("com.example.carpaly", 10, setOf("cert-a"))

    @Test fun acceptsOnlySamePackageSignerAndANewerVersion() {
        val candidate = installed.copy(versionCode = 11)
        assertNull(UpdateApkCompatibility.incompatibility(installed, candidate))
    }

    @Test fun rejectsPackageSignerAndVersionMismatches() {
        assertEquals(
            "APK package name does not match this installation",
            UpdateApkCompatibility.incompatibility(installed, installed.copy(packageName = "com.example.other", versionCode = 11)),
        )
        assertEquals(
            "APK signing certificate differs from this installation",
            UpdateApkCompatibility.incompatibility(installed, installed.copy(versionCode = 11, signerSha256 = setOf("cert-b"))),
        )
        assertEquals(
            "APK version is not newer than this installation",
            UpdateApkCompatibility.incompatibility(installed, installed.copy(versionCode = 10)),
        )
    }

    @Test fun rejectsUnverifiableSigningIdentity() {
        assertEquals(
            "APK signing certificate could not be verified",
            UpdateApkCompatibility.incompatibility(installed, installed.copy(versionCode = 11, signerSha256 = emptySet())),
        )
    }

    @Test fun requiresBothNonEmptyOfflineAuthenticationAssetsInTheApk() {
        val apk = File.createTempFile("carpaly-auth-assets", ".apk")
        try {
            ZipOutputStream(apk.outputStream()).use { zip ->
                listOf("identity.pk8", "certificate.p7b").forEach { name ->
                    zip.putNextEntry(ZipEntry("assets/offline-mfi/$name"))
                    zip.write(byteArrayOf(1, 2, 3))
                    zip.closeEntry()
                }
            }
            assertTrue(UpdateApkCompatibility.hasAuthenticationAssets(apk))

            ZipOutputStream(apk.outputStream()).use { zip ->
                zip.putNextEntry(ZipEntry("assets/offline-mfi/identity.pk8"))
                zip.write(byteArrayOf(1))
                zip.closeEntry()
            }
            assertFalse(UpdateApkCompatibility.hasAuthenticationAssets(apk))
        } finally {
            apk.delete()
        }
    }
}
