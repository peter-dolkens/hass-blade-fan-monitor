# Blade Fan Monitor

Read-only companion to the kernel `pwm-fan` overlay on the Compute Blade (CM5,
HAOS). The kernel drives the fan from GPIO12 on a CPU-temperature curve set in
`config.txt`; it does not read the tach. This add-on fills that gap.

| Entity | Meaning |
|---|---|
| `sensor.blade_fan_speed` | RPM from tach pulses on GPIO13 (falling edges ÷ pulses/rev) |
| `sensor.blade_fan_duty` | Duty the kernel is applying, 0–100 % (raw 0–255 in the `pwm` attribute) |
| `binary_sensor.blade_fan_stall` | `on` when duty > 0 but no tach pulses for `stall_seconds` |

It never writes to the fan, so stopping or crashing it can't affect cooling.

With an MQTT broker (the Mosquitto add-on plus the MQTT integration), the entities
are created by MQTT discovery. They have unique_ids, so you can rename them in the
UI, and they're grouped under a **Blade Fan** device. They show as unavailable when
the add-on stops.

Without a broker, it falls back to pushing plain states through the core REST API.
The entity_ids are the same, but the entities have no unique_id or device. They
reappear within one `interval_seconds` after a Home Assistant restart. If you add a
broker later, restart Home Assistant once after the switch. Otherwise the leftover
REST states will push the new entities to `_2` IDs.

Hardware notes: only the blade on fan-unit header **J1** gets PWM; both blades
can read the tach. The blade↔fan-unit connector is unkeyed — a misaligned plug
shows up here as 0 rpm with duty > 0 (stall).
