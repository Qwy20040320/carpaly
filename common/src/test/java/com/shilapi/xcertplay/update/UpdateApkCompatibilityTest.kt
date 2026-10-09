package com.shilapi.xcertplay.update

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

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
}
