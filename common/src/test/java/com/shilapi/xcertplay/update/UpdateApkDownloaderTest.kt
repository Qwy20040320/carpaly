package com.shilapi.xcertplay.update

import java.io.ByteArrayInputStream
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UpdateApkDownloaderTest {
    private val bytes = "verified test APK bytes".toByteArray()
    private val sha256 = MessageDigest.getInstance("SHA-256").digest(bytes).toHex()
    private val release = UpdateRelease(
        tagName = "v1.1.5",
        versionName = "1.1.5",
        apkName = "CarPaly-XingyueL1.1.5.apk",
        apkUrl = "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.5/CarPaly-XingyueL1.1.5.apk",
        checksumUrl = "https://github.com/Qwy20040320/carpaly/releases/download/v1.1.5/CarPaly-XingyueL1.1.5.apk.sha256",
        checksumSizeBytes = "$sha256  CarPaly-XingyueL1.1.5.apk\n".toByteArray().size.toLong(),
        releasePageUrl = "https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.5",
        releaseNotes = "test",
        sizeBytes = bytes.size.toLong(),
        isPrerelease = true,
        sha256 = sha256,
    )

    @Test
    fun downloadsOnlyTheExpectedBytesAndReturnsAfterSha256Verification() {
        val directory = createTempDirectory()
        try {
            val openedUrls = mutableListOf<URL>()
            val apk = UpdateApkDownloader.download(release, directory) { url ->
                openedUrls += url
                fakeFor(url)
            }
            assertEquals(listOf(URL(release.checksumUrl), URL(release.apkUrl)), openedUrls)
            assertEquals(release.apkName, apk.name)
            assertArrayEquals(bytes, apk.readBytes())
            assertEquals(sha256, MessageDigest.getInstance("SHA-256").digest(apk.readBytes()).toHex())
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun rejectsWrongDigestAndRemovesPartialFiles() {
        val directory = createTempDirectory()
        try {
            val badRelease = release.copy(sha256 = "0".repeat(64))
            try {
                UpdateApkDownloader.download(badRelease, directory) { url ->
                    fakeFor(url, badRelease)
                }
                throw AssertionError("expected digest mismatch")
            } catch (expected: IOException) {
                assertTrue(expected.message!!.contains("SHA-256"))
            }
            assertFalse(File(directory, release.apkName).exists())
            assertEquals(0, directory.listFiles().orEmpty().size)
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun rejectsOversizedMetadataBeforeOpeningNetwork() {
        val directory = createTempDirectory()
        try {
            var opened = false
            try {
                UpdateApkDownloader.download(release.copy(sizeBytes = UpdateApkDownloader.MAX_APK_BYTES + 1), directory) {
                    opened = true
                    FakeConnection(it, 200, bytes)
                }
                throw AssertionError("expected size rejection")
            } catch (expected: IllegalArgumentException) {
                assertTrue(expected.message!!.contains("size"))
            }
            assertFalse(opened)
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun rejectsRedirectsToNonHttpsOrUntrustedHosts() {
        val directory = createTempDirectory()
        try {
            try {
                UpdateApkDownloader.download(release, directory) { url ->
                    FakeConnection(url, 302, byteArrayOf(), mapOf("Location" to "http://example.com/CarPaly.apk"))
                }
                throw AssertionError("expected redirect rejection")
            } catch (expected: IOException) {
                assertTrue(expected.message!!.contains("untrusted"))
            }
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun rejectsChecksumSidecarThatDisagreesWithReleaseMetadata() {
        val directory = createTempDirectory()
        try {
            try {
                UpdateApkDownloader.download(release, directory) { url ->
                    val body = if (url.path.endsWith(".sha256")) {
                        "${"0".repeat(64)}  ${release.apkName}\n".toByteArray()
                    } else {
                        bytes
                    }
                    FakeConnection(url, 200, body, mapOf("Content-Length" to body.size.toString()))
                }
                throw AssertionError("expected checksum metadata mismatch")
            } catch (expected: IOException) {
                assertTrue(expected.message!!.contains("disagrees"))
            }
            assertEquals(0, directory.listFiles().orEmpty().size)
        } finally {
            directory.deleteRecursively()
        }
    }

    private fun createTempDirectory(): File = File(System.getProperty("java.io.tmpdir"), "carpaly-update-test-${System.nanoTime()}")
        .apply { assertTrue(mkdirs()) }

    private fun fakeFor(url: URL, requestedRelease: UpdateRelease = release): FakeConnection {
        val body = if (url.path.endsWith(".sha256")) {
            "${requestedRelease.sha256}  ${requestedRelease.apkName}\n".toByteArray()
        } else {
            bytes
        }
        return FakeConnection(url, 200, body, mapOf("Content-Length" to body.size.toString()))
    }

    private class FakeConnection(
        url: URL,
        private val status: Int,
        private val body: ByteArray,
        private val headers: Map<String, String> = emptyMap(),
    ) : HttpURLConnection(url) {
        override fun connect() = Unit
        override fun disconnect() = Unit
        override fun usingProxy(): Boolean = false
        override fun getResponseCode(): Int = status
        override fun getHeaderField(name: String?): String? = headers.entries
            .firstOrNull { it.key.equals(name, ignoreCase = true) }?.value
        override fun getInputStream() = ByteArrayInputStream(body)
    }

    private fun ByteArray.toHex(): String = joinToString("") { byte -> "%02x".format(byte) }
}
