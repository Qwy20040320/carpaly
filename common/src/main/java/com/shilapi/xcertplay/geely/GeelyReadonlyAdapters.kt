package com.shilapi.xcertplay.geely

/** Exact callback names recovered from an APK; integer payload semantics are deliberately unmapped. */
enum class GeelyOneOsCallback(val methodName: String, val argumentCount: Int) {
    KEY_EVENT("onKeyEvent", 3),
    SHORT_CLICK("onShortClick", 2),
    LONG_PRESS("onLongPressTriggered", 2),
    HOLD_STARTED("onHoldingPressStarted", 2),
    HOLD_STOPPED("onHoldingPressStopped", 2),
    DOUBLE_CLICK("onDoubleClick", 2),
}

enum class GeelySteeringEventOrigin { OEM_UNVERIFIED, SIMULATED }

data class GeelyRawSteeringEvent(
    val callback: GeelyOneOsCallback,
    val integerArguments: List<Int>,
    val origin: GeelySteeringEventOrigin,
)

enum class GeelyAdapterStartResult { BLOCKED_UNVERIFIED_OEM, SIMULATION_STARTED }

/** App-owned boundary for a future authorized OneOS listener; no Binder implementation is supplied. */
interface GeelySteeringWheelInputAdapter : AutoCloseable {
    fun start(listener: (GeelyRawSteeringEvent) -> Unit): GeelyAdapterStartResult
    override fun close()
}

/** Production default fails closed until the OEM grant and callable service are verified. */
object UnavailableGeelySteeringWheelInputAdapter : GeelySteeringWheelInputAdapter {
    override fun start(listener: (GeelyRawSteeringEvent) -> Unit) = GeelyAdapterStartResult.BLOCKED_UNVERIFIED_OEM
    override fun close() = Unit
}

/** Test-only simulation. It forwards exact callback-shaped integer tuples and never assigns key meanings. */
class SimulatedGeelySteeringWheelInputAdapter : GeelySteeringWheelInputAdapter {
    private var listener: ((GeelyRawSteeringEvent) -> Unit)? = null

    override fun start(listener: (GeelyRawSteeringEvent) -> Unit): GeelyAdapterStartResult {
        this.listener = listener
        return GeelyAdapterStartResult.SIMULATION_STARTED
    }

    fun emit(callback: GeelyOneOsCallback, vararg arguments: Int): Boolean {
        if (arguments.size != callback.argumentCount) return false
        val target = listener ?: return false
        target(GeelyRawSteeringEvent(callback, arguments.toList(), GeelySteeringEventOrigin.SIMULATED))
        return true
    }

    override fun close() {
        listener = null
    }
}

data class GeelyVehicleReadings(
    val speedKmh: VehicleDataSample<Double>,
    val fuelPercent: VehicleDataSample<Double>,
    val engineRpm: VehicleDataSample<Double>,
    val gear: VehicleDataSample<GearPosition>,
    val cabinTemperatureCelsius: VehicleDataSample<Double>,
)

/** Read-only provider contract. A snapshot contains no vehicle-control methods. */
interface GeelyVehicleReadOnlyAdapter {
    fun snapshot(): GeelyVehicleReadings
}

/** Default provider: absence of OEM authority or a verified client is represented as UNKNOWN. */
object UnavailableGeelyVehicleReadOnlyAdapter : GeelyVehicleReadOnlyAdapter {
    override fun snapshot() = GeelyVehicleReadings(
        speedKmh = VehicleDataSample.unavailable(unit = VehicleDataUnit.SPEED_KMH),
        fuelPercent = VehicleDataSample.unavailable(unit = VehicleDataUnit.FUEL_PERCENT),
        engineRpm = VehicleDataSample.unavailable(unit = VehicleDataUnit.ENGINE_RPM),
        gear = VehicleDataSample.unavailable(unit = VehicleDataUnit.GEAR_POSITION),
        cabinTemperatureCelsius = VehicleDataSample.unavailable(unit = VehicleDataUnit.CABIN_TEMPERATURE_CELSIUS),
    )
}

/** Explicit test fixture; it is never selected by the production capability registry. */
class SimulatedGeelyVehicleReadOnlyAdapter(
    private val speedKmh: Double? = 0.0,
    private val fuelPercent: Double? = 50.0,
    private val engineRpm: Double? = 0.0,
    private val gear: GearPosition? = GearPosition.PARK,
    private val cabinTemperatureCelsius: Double? = 21.0,
    private val timestampEpochMillis: Long = 1L,
    private val staleAfterMillis: Long = 5_000L,
) : GeelyVehicleReadOnlyAdapter {
    override fun snapshot() = GeelyVehicleReadings(
        speedKmh = speedKmh.sample(VehicleDataUnit.SPEED_KMH),
        fuelPercent = fuelPercent.sample(VehicleDataUnit.FUEL_PERCENT),
        engineRpm = engineRpm.sample(VehicleDataUnit.ENGINE_RPM),
        gear = gear?.let {
            VehicleDataSample.reading(it, VehicleDataSource.SIMULATED, VehicleDataUnit.GEAR_POSITION,
                timestampEpochMillis, staleAfterMillis)
        } ?: VehicleDataSample.unavailable(unit = VehicleDataUnit.GEAR_POSITION),
        cabinTemperatureCelsius = cabinTemperatureCelsius.sample(VehicleDataUnit.CABIN_TEMPERATURE_CELSIUS),
    )

    private fun Double?.sample(unit: VehicleDataUnit): VehicleDataSample<Double> = this?.let {
        VehicleDataSample.reading(it, VehicleDataSource.SIMULATED, unit, timestampEpochMillis, staleAfterMillis)
    } ?: VehicleDataSample.unavailable(unit = unit)
}
