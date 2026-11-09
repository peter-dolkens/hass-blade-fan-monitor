# Blade Fan Monitor

Home Assistant add-on repository for the [Uptime Lab Compute Blade](https://computeblade.com)
fan unit, running Home Assistant OS on a Raspberry Pi CM5.

On HAOS the kernel `pwm-fan` driver can run the fan from a CPU-temperature curve, but
it doesn't read the fan's tach. This add-on counts the tach pulses on GPIO13 and
reports Home Assistant sensors for speed, duty, and stalls. See
[`blade_fan/README.md`](blade_fan/README.md).

## Install

1. Settings → Add-ons → Add-on Store → ⋮ → **Repositories** → add
   `https://github.com/peter-dolkens/blade-fan-monitor`
2. Install **Blade Fan Monitor**. Turn on **Watchdog** and **Auto update**, then start it.

## Fan control (prerequisite)

The add-on only *observes*. Fan control comes from the `pwm-fan` overlay in HAOS's
`config.txt`, on the boot partition. For example:

```
dtoverlay=pwm-fan,fan_gpio_12
dtparam=fan_temp0=45000,fan_temp0_speed=77
dtparam=fan_temp1=52000,fan_temp1_speed=128
dtparam=fan_temp2=60000,fan_temp2_speed=192
dtparam=fan_temp3=68000,fan_temp3_speed=255
```

`config.txt` silently truncates lines over 98 characters. Put each parameter pair on
its own `dtparam=` line, never in one long `dtoverlay=` line.

Only the blade on fan-unit header **J1** can drive PWM. Both blades can read the tach.
