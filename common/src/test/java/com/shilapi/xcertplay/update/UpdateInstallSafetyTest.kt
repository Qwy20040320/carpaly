package com.shilapi.xcertplay.update

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UpdateInstallSafetyTest {
    @Test fun unknownVehicleStateBlocksInstallerByDefault() {
        assertFalse(UpdateInstallSafety.mayLaunchInstaller(TrustedVehicleMotion.UNKNOWN, false))
    }

    @Test fun explicitParkedConfirmationAllowsUnknownStateOnlyWhenCarPlayIsStopped() {
        assertTrue(UpdateInstallSafety.mayLaunchInstaller(TrustedVehicleMotion.UNKNOWN, false, true))
        assertFalse(UpdateInstallSafety.mayLaunchInstaller(TrustedVehicleMotion.UNKNOWN, true, true))
    }

    @Test fun movingStateAlwaysBlocksAndValidatedParkedStateAllows() {
        assertFalse(UpdateInstallSafety.mayLaunchInstaller(TrustedVehicleMotion.MOVING, false, true))
        assertTrue(UpdateInstallSafety.mayLaunchInstaller(TrustedVehicleMotion.PARKED, false))
        assertFalse(UpdateInstallSafety.mayLaunchInstaller(TrustedVehicleMotion.PARKED, true))
    }
}
