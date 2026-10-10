package com.shilapi.xcertplay.update

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UpdateVersionTest {
    @Test
    fun newerTagIsAnUpdate() {
        assertTrue(UpdateVersion.isNewer("v0.2.15", "0.2.14"))
    }

    @Test
    fun sameVersionIsNotAnUpdate() {
        assertFalse(UpdateVersion.isNewer("0.2.14", "0.2.14"))
    }

    @Test
    fun olderTagIsIgnored() {
        assertFalse(UpdateVersion.isNewer("v0.2.13", "0.2.14"))
    }

    @Test
    fun numericFieldsCompareLeftToRight() {
        assertTrue(UpdateVersion.isNewer("0.3.0", "0.2.14"))
        assertFalse(UpdateVersion.isNewer("0.2.9", "0.2.14"))
    }

    @Test
    fun preReleaseSuffixStillComparesByNumbers() {
        assertTrue(UpdateVersion.isNewer("0.2.15-beta.1", "0.2.14"))
        assertFalse(UpdateVersion.isNewer("0.2.14-rc.1", "0.2.14"))
    }

    @Test
    fun nextCarPalyReleaseTagIsNewerThanTheCurrentHudTestBuild() {
        assertTrue(UpdateVersion.isNewer("v0.2.16", "0.2.15-hud-test"))
        assertFalse(UpdateVersion.isNewer("v0.1.1", "0.2.15-hud-test"))
    }

    @Test
    fun comparesMultiDigitPatchNumbersNumerically() {
        assertTrue(UpdateVersion.isNewer("1.1.10", "1.1.9"))
        assertTrue(UpdateVersion.isNewer("1.1.11", "1.1.10"))
        assertFalse(UpdateVersion.isNewer("1.1.9", "1.1.10"))
    }

    @Test
    fun independentCarPalyVersionIsNewerThanLegacyHudTestVersions() {
        assertTrue(UpdateVersion.isNewer("1.1.4", "0.2.16-hud-test"))
        assertTrue(UpdateVersion.isNewer("1.1.4", "0.2.15-hud-test"))
    }

    @Test
    fun onlyPlainVersionTagsAreReleaseIdentifiers() {
        assertTrue(UpdateVersion.releaseVersion("v1.1.4") == "1.1.4")
        assertTrue(UpdateVersion.releaseVersion("v1.1.4-beta.1") == null)
        assertTrue(UpdateVersion.releaseVersion("1.1.4") == null)
    }

    @Test
    fun unparseableRemoteVersionIsNeverAnUpdate() {
        assertFalse(UpdateVersion.isNewer("public-preview", "0.2.14"))
    }

    @Test
    fun unparseableInstalledVersionAcceptsAnyParseableRemote() {
        assertTrue(UpdateVersion.isNewer("0.2.15", "psa.2"))
        assertFalse(UpdateVersion.isNewer("public-preview", "psa.2"))
    }
}
