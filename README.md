# Compute Blade Fan for Home Assistant

A Home Assistant integration that monitors the fan unit of an
[Uptime Lab Compute Blade](https://computeblade.com) running Home Assistant on the
blade's own Raspberry Pi CM5. Raspberry Pi OS also works.

The Linux `pwm-fan` driver can run the fan from a CPU-temperature curve with no
software involved, but it never reads the fan's tach. This integration does. It
counts tach pulses on a GPIO, reads the duty the driver is applying, and gives you
a **Blade Fan** device with:

| Entity | |
|---|---|
| `sensor.blade_fan_speed` | Fan speed in rpm, from the tach |
| `sensor.blade_fan_duty` | Duty the kernel is applying, 0–100 % (raw 0–255 in the `pwm` attribute) |
| `binary_sensor.blade_fan_stall` | Problem sensor: on when the fan should be spinning but gives no tach pulses |

It only *observes*. It never drives the fan, so it can't affect cooling.

## Requirements

- Home Assistant running **on the blade itself**, e.g. Home Assistant OS on a CM5.
  The default GPIO chip label is `pinctrl-rp1` (Pi 5 / CM5). Earlier Pis use other
  labels.
- The fan unit plugged into header **J1**. Only J1 receives PWM, though both
  headers can read the tach. The blade↔fan-unit connector is **unkeyed**, so check
  that it's aligned.
- The `pwm-fan` overlay in `config.txt` (below). Without it, the fan isn't
  temperature-controlled, and the integration raises a Repairs issue.

## Fan control

Add the following to `config.txt` on the boot partition, then reboot. On Home
Assistant OS that's the `hassos-boot` partition, which you can reach from the
host or by mounting the drive on another machine.

```
dtoverlay=pwm-fan,fan_gpio_12
dtparam=fan_temp0=45000,fan_temp0_speed=77
dtparam=fan_temp1=52000,fan_temp1_speed=128
dtparam=fan_temp2=60000,fan_temp2_speed=192
dtparam=fan_temp3=68000,fan_temp3_speed=255
```

Temperatures are in millidegrees. With 5 °C hysteresis, the fan is off below 40 °C,
at 30 % from 45 °C, 50 % from 52 °C, 75 % from 60 °C and 100 % from 68 °C. PWM runs
at 25 kHz, as Noctua specifies.

> **`config.txt` silently truncates lines longer than 98 characters.** Put every
> parameter on its own `dtparam=` line. A single long `dtoverlay=` line will be cut
> mid-value. A cut `fan_temp1_speed=128` becomes `12`, and the fan slows down as the
> CPU heats up.

## Install

**Marketplace:** Settings → Marketplace → ⋮ → *Custom repositories* → add
`https://github.com/peter-dolkens/hass-blade-fan-monitor` as an *Integration*.
Install **Compute Blade Fan** and restart Home Assistant.

**Manual:** copy `custom_components/blade_fan` into `<config>/custom_components/`
and restart.

Then go to Settings → Devices & services → *Add integration* → **Compute Blade Fan**.
The defaults suit a Compute Blade: tach on GPIO13 of `pinctrl-rp1`, 2 pulses per
revolution (Noctua), stall alarm after 30 s, updates every 10 s. You can change
these later under *Configure*.

## Troubleshooting

- **Speed is 0 and the stall sensor turns on.** The fan isn't on J1, the connector
  is misaligned, or the fan is jammed.
- **"GPIO is in use" during setup.** Something else has claimed the tach line, such
  as another integration or an add-on.
- **Duty and Stall are unavailable, and there's a Repairs issue.** The `pwm-fan`
  overlay isn't loaded. See [Fan control](#fan-control).
