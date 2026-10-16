package com.shilapi.xcertplay.geely

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class GeelyReadonlyAdaptersTest {
    @Test fun productionVehicleAdapterReturnsUnknownRatherThanSyntheticZeros() {
        val snapshot = UnavailableGeelyVehicleReadOnlyAdapter.snapshot()

        assertNull(snapshot.speedKmh.value)
        assertNull(snapshot.fuelPercent.value)
        assertNull(snapshot.engineRpm.value)
        assertNull(snapshot.gear.value)
        assertNull(snapshot.cabinTemperatureCelsius.value)
    }

    @Test fun simulatedReadingsAreExplicitlyMarkedAndValidated() {
        val snapshot = SimulatedGeelyVehicleReadOnlyAdapter(
            speedKmh = 42.0,
            fuelPercent = 61.0,
            engineRpm = 1_500.0,
            gear = GearPosition.PARK,
            cabinTemperatureCelsius = 20.5,
            timestampEpochMillis = 100,
        ).snapshot()

        assertEquals(42.0, snapshot.speedKmh.value!!, 0.0)
        assertEquals(VehicleDataSource.SIMULATED, snapshot.speedKmh.source)
        assertEquals(VehicleDataValidity.VALID, snapshot.speedKmh.validity)
        assertEquals(VehicleDataUnit.CABIN_TEMPERATURE_CELSIUS, snapshot.cabinTemperatureCelsius.unit)
    }

    @Test fun invalidSimulatedReadingRemainsUnavailable() {
        val snapshot = SimulatedGeelyVehicleReadOnlyAdapter(fuelPercent = 150.0).snapshot()

        assertNull(snapshot.fuelPercent.value)
        assertEquals(VehicleDataValidity.INVALID, snapshot.fuelPercent.validity)
    }

    @Test fun steeringCallbacksKeepUnmappedArgumentsAndSimulationOrigin() {
        val adapter = SimulatedGeelySteeringWheelInputAdapter()
        var observed: GeelyRawSteeringEvent? = null
        assertEquals(GeelyAdapterStartResult.SIMULATION_STARTED, adapter.start { observed = it })

        assertTrue(adapter.emit(GeelyOneOsCallback.KEY_EVENT, 31, 2, 4))
        assertEquals(GeelyOneOsCallback.KEY_EVENT, observed?.callback)
        assertEquals(listOf(31, 2, 4), observed?.integerArguments)
        assertEquals(GeelySteeringEventOrigin.SIMULATED, observed?.origin)
        assertFalse(adapter.emit(GeelyOneOsCallback.KEY_EVENT, 31, 2))
    }

    @Test fun unavailableOemAdapterFailsClosedAndClosedSimulatorDoesNotEmit() {
        assertEquals(GeelyAdapterStartResult.BLOCKED_UNVERIFIED_OEM,
            UnavailableGeelySteeringWheelInputAdapter.start {})

        val adapter = SimulatedGeelySteeringWheelInputAdapter()
        adapter.start {}
        adapter.close()
        assertFalse(adapter.emit(GeelyOneOsCallback.SHORT_CLICK, 1, 2))
    }
}
