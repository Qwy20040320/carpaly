package com.shilapi.xcertplay.update

import android.content.Intent
import android.net.Uri
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [29])
class UpdateApkInstallIntentTest {
    @Test
    fun installerUsesAndroidConfirmationAndOnlyReceivesReadAccessToVerifiedApkUri() {
        val apkUri = Uri.parse("content://com.shihab.diplay.update-apks/update/CarPaly-XingyueL1.1.5.apk")
        val intent = UpdateApkInstallIntent.create(apkUri)

        assertEquals(Intent.ACTION_INSTALL_PACKAGE, intent.action)
        assertEquals(apkUri, intent.data)
        assertEquals(UpdateApkInstallIntent.APK_MIME_TYPE, intent.type)
        assertTrue(intent.flags and Intent.FLAG_GRANT_READ_URI_PERMISSION != 0)
        assertTrue(intent.getBooleanExtra(Intent.EXTRA_RETURN_RESULT, false))
    }
}
