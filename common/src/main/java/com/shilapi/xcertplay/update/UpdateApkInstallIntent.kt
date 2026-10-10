package com.shilapi.xcertplay.update

import android.content.Intent
import android.net.Uri

/** Builds the standard Android package-installer request; Android still requires user confirmation. */
internal object UpdateApkInstallIntent {
    internal const val APK_MIME_TYPE = "application/vnd.android.package-archive"

    internal fun create(apkUri: Uri): Intent = Intent(Intent.ACTION_INSTALL_PACKAGE).apply {
        setDataAndType(apkUri, APK_MIME_TYPE)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        putExtra(Intent.EXTRA_RETURN_RESULT, true)
    }
}
