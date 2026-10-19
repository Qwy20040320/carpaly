package com.shilapi.xcertplay.geely

/** Origin asserted by the provider which produced a read-only vehicle sample. */
enum class VehicleDataSource {
    UNKNOWN,
    ECARX,
    ONEOS,
    ANDROID_AUTOMOTIVE,
    SIMULATED,
}

enum class VehicleDataUnit {
    SPEED_KMH,
    FUEL_PERCENT,
    ENGINE_RPM,
    GEAR_POSITION,
    CABIN_TEMPERATURE_CELSIUS,
}

enum class VehicleDataValidity {
    VALID,
    UNKNOWN,
    STALE,
    DISCONNECTED,
    PERMISSION_DENIED,
    UNSUPPORTED,
    INVALID,
}

enum class GearPosition {
    PARK,
    REVERSE,
    NEUTRAL,
    DRIVE,
    SPORT,
    LOW,
    UNKNOWN,
}

/**
 * A timestamped, typed, read-only value. This model does not connect to an OEM service and does
 * not provide a way to issue vehicle commands. Absent or invalid readings never become zero.
 */
class VehicleDataSample<T> private constructor(
    val value: T?,
    val source: VehicleDataSource,
    val unit: VehicleDataUnit,
    val timestampEpochMillis: Long?,
    val validity: VehicleDataValidity,
    val staleAfterMillis: Long,
) {
    /** Return the current effective validity without mutating the stored sample. */
    fun validityAt(nowEpochMillis: Long): VehicleDataValidity {
        if (validity != VehicleDataValidity.VALID) return validity
        val timestamp = timestampEpochMillis ?: return VehicleDataValidity.INVALID
        if (nowEpochMillis < 0L || nowEpochMillis < timestamp) return VehicleDataValidity.INVALID
        if (staleAfterMillis <= 0L || nowEpochMillis - timestamp > staleAfterMillis) {
            return VehicleDataValidity.STALE
        }
        return VehicleDataValidity.VALID
    }

    fun isUsableAt(nowEpochMillis: Long): Boolean =
        value != null && validityAt(nowEpochMillis) == VehicleDataValidity.VALID

    companion object {
        /** Validate a provider reading and keep invalid input unavailable to renderers. */
        fun <T> reading(
            value: T?,
            source: VehicleDataSource,
            unit: VehicleDataUnit,
            timestampEpochMillis: Long?,
            staleAfterMillis: Long,
        ): VehicleDataSample<T> {
            val valid = value != null && source != VehicleDataSource.UNKNOWN &&
                timestampEpochMillis != null && timestampEpochMillis >= 0L &&
                staleAfterMillis > 0L && valueMatchesUnit(value, unit)
            return VehicleDataSample(
                value = if (valid) value else null,
                source = source,
                unit = unit,
                timestampEpochMillis = timestampEpochMillis?.takeIf { it >= 0L },
                validity = if (valid) VehicleDataValidity.VALID else VehicleDataValidity.INVALID,
                staleAfterMillis = staleAfterMillis.coerceAtLeast(0L),
            )
        }

        /** A safe default: unavailable vehicle signals carry no fabricated value or timestamp. */
        fun <T> unavailable(
            source: VehicleDataSource = VehicleDataSource.UNKNOWN,
            unit: VehicleDataUnit,
            validity: VehicleDataValidity = VehicleDataValidity.UNKNOWN,
        ): VehicleDataSample<T> {
            require(validity in setOf(
                VehicleDataValidity.UNKNOWN,
                VehicleDataValidity.DISCONNECTED,
                VehicleDataValidity.PERMISSION_DENIED,
                VehicleDataValidity.UNSUPPORTED,
            )) { "Unavailable samples require an unavailable validity state" }
            return VehicleDataSample(
                value = null,
                source = source,
                unit = unit,
                timestampEpochMillis = null,
                validity = validity,
                staleAfterMillis = 0L,
            )
        }

        private fun valueMatchesUnit(value: Any, unit: VehicleDataUnit): Boolean = when (unit) {
            // Broad defensive bounds for rejecting corrupted samples only; these are not Geely/ECARX specs.
            VehicleDataUnit.SPEED_KMH -> (value as? Number)?.toDouble()?.let {
                it.isFinite() && it in 0.0..350.0
            } == true
            VehicleDataUnit.FUEL_PERCENT -> (value as? Number)?.toDouble()?.let {
                it.isFinite() && it in 0.0..100.0
            } == true
            VehicleDataUnit.ENGINE_RPM -> (value as? Number)?.toDouble()?.let {
                it.isFinite() && it in 0.0..20_000.0
            } == true
            VehicleDataUnit.GEAR_POSITION -> value is GearPosition && value != GearPosition.UNKNOWN
            VehicleDataUnit.CABIN_TEMPERATURE_CELSIUS -> (value as? Number)?.toDouble()?.let {
                it.isFinite() && it in -50.0..100.0
            } == true
        }
    }
}
