package com.shilapi.xcertplay.update

import com.shilapi.xcertplay.DiPlayActivity
import org.junit.Assert.assertFalse
import org.junit.Test

class UpdateInstallCompatibilityTest {
    @Test fun updaterDoesNotDownloadOrInstallApksInTheBackground() {
        val methods = DiPlayActivity::class.java.declaredMethods.map { it.name }.toSet()
        val fields = DiPlayActivity::class.java.declaredFields.map { it.name }.toSet()
        assertFalse("Activity must not expose an in-app APK download path", "downloadUpdate" in methods)
        assertFalse("Activity must not invoke the APK installer", "installUpdate" in methods)
        assertFalse("Activity must not persist a downloaded installer APK", "updateFile" in fields)
    }
}
