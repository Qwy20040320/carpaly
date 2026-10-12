package com.shilapi.xcertplay.update

import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.concurrent.atomic.AtomicBoolean

/** Downloads only the versioned CarPaly asset selected by the signed manifest, then verifies its digest. */
internal object UpdateApkDownloader {
    internal const val MAX_APK_BYTES = 50L * 1024L * 1024L
    private const val MAX_REDIRECTS = 5
    private const val CONNECT_TIMEOUT_MILLIS = 15_000
    private const val READ_TIMEOUT_MILLIS = 45_000
    private const val REPOSITORY = "Qwy20040320/carpaly"
    private val sha256Pattern = Regex("^[0-9a-fA-F]{64}$")

    internal fun matchesVerifiedRelease(apk: File, release: UpdateRelease): Boolean = runCatching {
        release.tagName == "v${release.versionName}" &&
            release.apkName == UpdateCatalog.apkName(release.versionName) &&
            apk.isFile && apk.length() == release.sizeBytes && release.sizeBytes > 0L && release.sizeBytes <= MAX_APK_BYTES &&
            sha256Pattern.matches(release.sha256) && sha256(apk).equals(release.sha256, ignoreCase = true)
    }.getOrDefault(false)

    /**
     * Fetches to a private app directory. A partial or digest-mismatched file is never returned as an APK.
     * The injectable connection factory keeps the streaming and redirect policy deterministic in unit tests.
     */
    internal fun download(
        release: UpdateRelease,
        destinationDirectory: File,
        connectionFactory: (URL) -> HttpURLConnection = { it.openConnection() as HttpURLConnection },
        cancellation: UpdateDownloadCancellation = UpdateDownloadCancellation(),
        onProgress: (Long, Long) -> Unit = { _, _ -> },
    ): File {
        require(release.apkName == UpdateCatalog.apkName(release.versionName)) { "Unexpected APK filename" }
        require(release.tagName == "v${release.versionName}") { "Release tag and APK version differ" }
        require(UpdateVersion.releaseVersion(release.tagName) == release.versionName) { "Invalid semantic release tag" }
        require(release.sizeBytes > 0L && release.sizeBytes <= MAX_APK_BYTES) { "APK exceeds the supported download size" }
        require(release.checksumSizeBytes in 1L..256L) { "Invalid checksum sidecar size" }
        require(sha256Pattern.matches(release.sha256)) { "Invalid release SHA-256" }

        val initialUrl = URL(release.apkUrl)
        val expectedPath = "/$REPOSITORY/releases/download/${release.tagName}/${release.apkName}"
        require(release.apkUrl == "https://github.com$expectedPath" &&
            initialUrl.protocol.equals("https", ignoreCase = true) &&
            initialUrl.host.equals("github.com", ignoreCase = true) &&
            initialUrl.path == expectedPath && initialUrl.userInfo == null &&
            (initialUrl.port == -1 || initialUrl.port == 443) && initialUrl.query == null && initialUrl.ref == null) {
            "APK URL is not the expected GitHub release asset"
        }
        require(release.checksumUrl == "https://github.com$expectedPath.sha256") {
            "Checksum URL is not the expected GitHub release sidecar"
        }
        cancellation.check()
        fetchAndVerifyChecksumSidecar(release, connectionFactory, cancellation)

        if (!destinationDirectory.exists() && !destinationDirectory.mkdirs()) {
            throw IOException("Could not create the update cache directory")
        }
        val root = destinationDirectory.canonicalFile
        if (root.usableSpace < release.sizeBytes + MINIMUM_FREE_SPACE_BYTES) {
            throw IOException("Insufficient storage space for the verified update APK")
        }
        root.listFiles()?.filter { it.name.startsWith(".carpaly-update-") && it.name.endsWith(".part") }
            ?.forEach { it.delete() }
        val target = File(root, release.apkName).canonicalFile
        if (target.parentFile != root) throw IOException("Invalid update cache path")
        if (matchesVerifiedRelease(target, release)) return target
        if (target.exists() && !target.delete()) throw IOException("Could not replace a stale cached APK")

        val temporary = File.createTempFile(".carpaly-update-", ".part", root)
        var connection: HttpURLConnection? = null
        try {
            connection = openFollowingTrustedRedirects(initialUrl, connectionFactory, cancellation)
            val status = connection.responseCode
            cancellation.check()
            if (status != HttpURLConnection.HTTP_OK) throw IOException("APK download failed: HTTP $status")
            val encoding = connection.getHeaderField("Content-Encoding")
            if (!encoding.isNullOrBlank() && !encoding.equals("identity", ignoreCase = true)) {
                throw IOException("Unexpected encoded APK response")
            }
            val contentLength = connection.getHeaderFieldLong("Content-Length", -1L)
            if (contentLength >= 0 && contentLength != release.sizeBytes) {
                throw IOException("APK response length does not match release metadata")
            }

            val digest = MessageDigest.getInstance("SHA-256")
            var downloaded = 0L
            var lastProgressReported = 0L
            BufferedInputStream(connection.inputStream).use { input ->
                BufferedOutputStream(FileOutputStream(temporary)).use { output ->
                    val buffer = ByteArray(32 * 1024)
                    while (true) {
                        cancellation.check()
                        val count = input.read(buffer)
                        if (count < 0) break
                        downloaded += count
                        if (downloaded > release.sizeBytes || downloaded > MAX_APK_BYTES) {
                            throw IOException("APK response exceeds release metadata")
                        }
                        digest.update(buffer, 0, count)
                        output.write(buffer, 0, count)
                        if (downloaded - lastProgressReported >= PROGRESS_INTERVAL_BYTES ||
                            downloaded == release.sizeBytes) {
                            onProgress(downloaded, release.sizeBytes)
                            lastProgressReported = downloaded
                        }
                    }
                    output.flush()
                }
            }
            if (downloaded != release.sizeBytes) throw IOException("APK response is incomplete")
            cancellation.check()
            val actualSha256 = digest.digest().toHex()
            if (!actualSha256.equals(release.sha256, ignoreCase = true)) {
                throw IOException("APK SHA-256 does not match GitHub release metadata")
            }
            if (!temporary.renameTo(target)) throw IOException("Could not finalize the verified APK")
            return target
        } finally {
            connection?.disconnect()
            connection?.let(cancellation::clear)
            if (temporary.exists()) temporary.delete()
        }
    }

    private fun openFollowingTrustedRedirects(
        initialUrl: URL,
        connectionFactory: (URL) -> HttpURLConnection,
        cancellation: UpdateDownloadCancellation,
    ): HttpURLConnection {
        var currentUrl = initialUrl
        for (redirectCount in 0..MAX_REDIRECTS) {
            val connection = connectionFactory(currentUrl)
            cancellation.track(connection)
            connection.instanceFollowRedirects = false
            connection.requestMethod = "GET"
            connection.connectTimeout = CONNECT_TIMEOUT_MILLIS
            connection.readTimeout = READ_TIMEOUT_MILLIS
            connection.useCaches = false
            connection.setRequestProperty("Accept", "application/octet-stream")
            connection.setRequestProperty("Accept-Encoding", "identity")
            connection.setRequestProperty("User-Agent", "CarPaly-update")
            val status = connection.responseCode
            if (status !in 300..399) return connection

            val location = connection.getHeaderField("Location")
            connection.disconnect()
            cancellation.clear(connection)
            if (redirectCount == MAX_REDIRECTS || location.isNullOrBlank()) {
                throw IOException("APK download redirect limit exceeded")
            }
            val redirected = URL(currentUrl, location)
            if (!isTrustedHttpsUrl(redirected)) throw IOException("APK download redirected to an untrusted host")
            currentUrl = redirected
        }
        throw IOException("APK download redirect limit exceeded")
    }

    private fun fetchAndVerifyChecksumSidecar(
        release: UpdateRelease,
        connectionFactory: (URL) -> HttpURLConnection,
        cancellation: UpdateDownloadCancellation,
    ) {
        var connection: HttpURLConnection? = null
        try {
            connection = openFollowingTrustedRedirects(URL(release.checksumUrl), connectionFactory, cancellation)
            val status = connection.responseCode
            cancellation.check()
            if (status != HttpURLConnection.HTTP_OK) throw IOException("Checksum download failed: HTTP $status")
            val encoding = connection.getHeaderField("Content-Encoding")
            if (!encoding.isNullOrBlank() && !encoding.equals("identity", ignoreCase = true)) {
                throw IOException("Unexpected encoded checksum response")
            }
            val contentLength = connection.getHeaderFieldLong("Content-Length", -1L)
            if (contentLength >= 0 && contentLength != release.checksumSizeBytes) {
                throw IOException("Checksum sidecar length does not match release metadata")
            }

            val output = ByteArrayOutputStream(release.checksumSizeBytes.toInt())
            connection.inputStream.use { input ->
                val buffer = ByteArray(256)
                var total = 0
                while (true) {
                    cancellation.check()
                    val count = input.read(buffer)
                    if (count < 0) break
                    total += count
                    if (total > 256 || total.toLong() > release.checksumSizeBytes) {
                        throw IOException("Checksum sidecar exceeds its allowed size")
                    }
                    output.write(buffer, 0, count)
                }
            }
            if (output.size().toLong() != release.checksumSizeBytes) {
                throw IOException("Checksum sidecar is incomplete")
            }
            val checksumText = output.toString(Charsets.US_ASCII.name())
            val expectedLine = Regex("^([0-9a-fA-F]{64})  ${Regex.escape(release.apkName)}\\r?\\n$")
                .matchEntire(checksumText)?.groupValues?.get(1)
                ?: throw IOException("Checksum sidecar format is invalid")
            if (!expectedLine.equals(release.sha256, ignoreCase = true)) {
                throw IOException("Checksum sidecar disagrees with GitHub release metadata")
            }
        } finally {
            connection?.disconnect()
            connection?.let(cancellation::clear)
        }
    }

    private fun isTrustedHttpsUrl(url: URL): Boolean {
        val host = url.host.lowercase()
        val trustedHost = host == "github.com" || host == "release-assets.githubusercontent.com" ||
            host == "objects.githubusercontent.com"
        return url.protocol.equals("https", ignoreCase = true) && trustedHost && url.userInfo == null &&
            (url.port == -1 || url.port == 443)
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().buffered().use { input ->
            val buffer = ByteArray(32 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().toHex()
    }

    private fun ByteArray.toHex(): String = joinToString("") { byte -> "%02x".format(byte) }

    private const val MINIMUM_FREE_SPACE_BYTES = 5L * 1024L * 1024L
    private const val PROGRESS_INTERVAL_BYTES = 256L * 1024L
}

internal class UpdateDownloadCancelledException : IOException("Update download was cancelled")

/** Disconnects an in-flight request and removes any partial file before returning control to the UI. */
internal class UpdateDownloadCancellation {
    private val cancelled = AtomicBoolean(false)
    @Volatile private var activeConnection: HttpURLConnection? = null

    internal fun cancel() {
        cancelled.set(true)
        activeConnection?.disconnect()
    }

    internal fun check() {
        if (cancelled.get() || Thread.currentThread().isInterrupted) throw UpdateDownloadCancelledException()
    }

    internal fun isCancelled(): Boolean = cancelled.get()

    internal fun track(connection: HttpURLConnection) {
        if (cancelled.get()) {
            connection.disconnect()
            throw UpdateDownloadCancelledException()
        }
        activeConnection = connection
    }

    internal fun clear(connection: HttpURLConnection) {
        if (activeConnection === connection) activeConnection = null
    }
}
