package com.shilapi.xcertplay.geely

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class GeelyVehicleDataTest {
    @Test fun unavailableVehicleValuesStayUnknownInsteadOfBecomingZero() {
        val speed = VehicleDataSample.unavailable<Double>(unit = VehicleDataUnit.SPEED_KMH)

        assertNull(speed.value)
        assertNull(speed.timestampEpochMillis)
        assertEquals(VehicleDataValidity.UNKNOWN, speed.validity)
        assertFalse(speed.isUsableAt(1_000L))
    }

    @Test fun validTimestampedReadingsAreUsableOnlyWithinTheirFreshnessWindow() {
        val speed = VehicleDataSample.reading(
            value = 72.5,
            source = VehicleDataSource.ECARX,
            unit = VehicleDataUnit.SPEED_KMH,
            timestampEpochMillis = 1_000L,
            staleAfterMillis = 2_000L,
        )

        assertEquals(VehicleDataValidity.VALID, speed.validityAt(3_000L))
        assertTrue(speed.isUsableAt(3_000L))
        assertEquals(VehicleDataValidity.STALE, speed.validityAt(3_001L))
        assertFalse(speed.isUsableAt(3_001L))
    }

    @Test fun invalidOrOutOfRangeNumbersAreRemovedFromTheSample() {
        listOf(Double.NaN, Double.POSITIVE_INFINITY, -1.0, 351.0).forEach { value ->
            val speed = VehicleDataSample.reading(
                value,
                VehicleDataSource.ECARX,
                VehicleDataUnit.SPEED_KMH,
                timestampEpochMillis = 1L,
                staleAfterMillis = 1_000L,
            )
            assertEquals(VehicleDataValidity.INVALID, speed.validity)
            assertNull(speed.value)
        }
    }

    @Test fun fuelAndRpmUseTheirOwnUnitsAndRanges() {
        val fuel = VehicleDataSample.reading(101.0, VehicleDataSource.ECARX,
            VehicleDataUnit.FUEL_PERCENT, 1L, 1_000L)
        val rpm = VehicleDataSample.reading(9_000.0, VehicleDataSource.ECARX,
            VehicleDataUnit.ENGINE_RPM, 1L, 1_000L)

        assertEquals(VehicleDataValidity.INVALID, fuel.validity)
        assertNull(fuel.value)
        assertEquals(VehicleDataValidity.VALID, rpm.validity)
    }

    @Test fun deniedAndDisconnectedProvidersCarryNoVehicleData() {
        val denied = VehicleDataSample.unavailable<Double>(
            source = VehicleDataSource.ONEOS,
            unit = VehicleDataUnit.ENGINE_RPM,
            validity = VehicleDataValidity.PERMISSION_DENIED,
        )
        val disconnected = VehicleDataSample.unavailable<GearPosition>(
            source = VehicleDataSource.ECARX,
            unit = VehicleDataUnit.GEAR_POSITION,
            validity = VehicleDataValidity.DISCONNECTED,
        )

        assertNull(denied.value)
        assertEquals(VehicleDataValidity.PERMISSION_DENIED, denied.validity)
        assertNull(disconnected.value)
        assertEquals(VehicleDataValidity.DISCONNECTED, disconnected.validity)
    }

    @Test fun unknownGearAndFutureTimestampAreNotRenderable() {
        val gear = VehicleDataSample.reading(GearPosition.UNKNOWN, VehicleDataSource.ECARX,
            VehicleDataUnit.GEAR_POSITION, 1L, 1_000L)
        val future = VehicleDataSample.reading(30.0, VehicleDataSource.ONEOS,
            VehicleDataUnit.SPEED_KMH, 2_000L, 1_000L)

        assertEquals(VehicleDataValidity.INVALID, gear.validity)
        assertNull(gear.value)
        assertEquals(VehicleDataValidity.INVALID, future.validityAt(1_999L))
        assertFalse(future.isUsableAt(1_999L))
    }
}
