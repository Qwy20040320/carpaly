package com.shilapi.xcertplay.update

import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.os.Build
import java.io.File
import java.security.MessageDigest

/** Immutable package identity used to reject an APK that cannot update this installation. */
internal data class UpdateApkIdentity(
    val packageName: String,
    val versionCode: Long,
    val signerSha256: Set<String>,
)

internal object UpdateApkCompatibility {
    internal fun inspectInstalled(packageManager: PackageManager, packageName: String): UpdateApkIdentity? =
        runCatching { packageManager.getPackageInfo(packageName, signingFlags()) }
            .getOrNull()?.toIdentity()

    internal fun inspectArchive(packageManager: PackageManager, apk: File): UpdateApkIdentity? =
        runCatching { packageManager.getPackageArchiveInfo(apk.absolutePath, signingFlags()) }
            .getOrNull()?.toIdentity()

    /** Null means install-compatible; exact signer equality is intentionally conservative. */
    internal fun incompatibility(installed: UpdateApkIdentity, candidate: UpdateApkIdentity): String? = when {
        candidate.packageName != installed.packageName -> "APK package name does not match this installation"
        candidate.signerSha256.isEmpty() || installed.signerSha256.isEmpty() -> "APK signing certificate could not be verified"
        candidate.signerSha256 != installed.signerSha256 -> "APK signing certificate differs from this installation"
        candidate.versionCode <= installed.versionCode -> "APK version is not newer than this installation"
        else -> null
    }

    private fun signingFlags(): Int = if (Build.VERSION.SDK_INT >= 28) {
        PackageManager.GET_SIGNING_CERTIFICATES
    } else {
        @Suppress("DEPRECATION")
        PackageManager.GET_SIGNATURES
    }

    private fun PackageInfo.toIdentity(): UpdateApkIdentity {
        val signatures = if (Build.VERSION.SDK_INT >= 28) {
            signingInfo?.apkContentsSigners?.toList().orEmpty()
        } else {
            @Suppress("DEPRECATION")
            signatures?.toList().orEmpty()
        }
        val version = if (Build.VERSION.SDK_INT >= 28) longVersionCode else {
            @Suppress("DEPRECATION")
            versionCode.toLong()
        }
        return UpdateApkIdentity(
            packageName = packageName.orEmpty(),
            versionCode = version,
            signerSha256 = signatures.map { signature ->
                MessageDigest.getInstance("SHA-256").digest(signature.toByteArray())
                    .joinToString("") { byte -> "%02x".format(byte) }
            }.toSet(),
        )
    }
}
