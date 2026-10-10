package com.shilapi.xcertplay

import android.app.AlertDialog
import android.widget.Button
import com.shilapi.xcertplay.host.R
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowAlertDialog
import org.robolectric.util.ReflectionHelpers

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [29], qualifiers = "en")
class ConnectionAuthenticationFeedbackTest {
    @Test fun connectButtonRemainsActionableAndRoutesAuthenticationFailureToDiagnostics() {
        val controller = Robolectric.buildActivity(DiPlayActivity::class.java).setup()
        val activity = controller.get()
        try {
            ReflectionHelpers.setField(activity, "setupError", "MFi assets unavailable")
            ReflectionHelpers.setField(activity, "page", "home")
            ReflectionHelpers.callInstanceMethod<Unit>(activity, "render")

            val button = ReflectionHelpers.getField<Button>(activity, "connectButton")
            assertNotNull(button)
            assertTrue("The button must stay actionable to explain the blocker", button.isEnabled)
            assertEquals(activity.getString(R.string.setup_needs_attention), button.text.toString())
            button.performClick()

            val dialog = ShadowAlertDialog.getLatestAlertDialog() as? AlertDialog
            assertNotNull("Tapping connect should show the authentication blocker", dialog)
            assertEquals(activity.getString(R.string.diagnostics),
                dialog!!.getButton(AlertDialog.BUTTON_POSITIVE).text.toString())
        } finally {
            controller.pause().stop().destroy()
        }
    }
}
