package com.shilapi.xcertplay.update

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UpdateCheckPolicyTest {
    @Test fun firstEnabledLaunchIsDue() {
        assertTrue(UpdateCheckPolicy.isDue(enabled = true, lastCheckAtMillis = 0L, nowMillis = 100L))
    }

    @Test fun disabledAutomaticChecksNeverRun() {
        assertFalse(UpdateCheckPolicy.isDue(enabled = false, lastCheckAtMillis = 0L, nowMillis = Long.MAX_VALUE))
    }

    @Test fun automaticChecksWaitAFullDayAfterTheLastAttempt() {
        assertFalse(UpdateCheckPolicy.isDue(
            enabled = true,
            lastCheckAtMillis = 1_000L,
            nowMillis = 1_000L + UpdateCheckPolicy.INTERVAL_MILLIS - 1,
        ))
        assertTrue(UpdateCheckPolicy.isDue(
            enabled = true,
            lastCheckAtMillis = 1_000L,
            nowMillis = 1_000L + UpdateCheckPolicy.INTERVAL_MILLIS,
        ))
    }

    @Test fun clockMovingBackwardsDoesNotTriggerAnEarlyCheck() {
        assertFalse(UpdateCheckPolicy.isDue(enabled = true, lastCheckAtMillis = 5_000L, nowMillis = 4_000L))
    }
}
