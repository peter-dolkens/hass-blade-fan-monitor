"""Constants for the Compute Blade Fan integration."""

DOMAIN = "blade_fan"

CONF_CHIP_LABEL = "gpio_chip_label"
CONF_TACH_GPIO = "tach_gpio"
CONF_PULSES_PER_REV = "pulses_per_rev"
CONF_STALL_SECONDS = "stall_seconds"
CONF_INTERVAL_SECONDS = "interval_seconds"

# Raspberry Pi 5 / CM5 GPIO controller; the Compute Blade fan tach is on GPIO13.
DEFAULT_CHIP_LABEL = "pinctrl-rp1"
DEFAULT_TACH_GPIO = 13
# Noctua fans (the fan unit ships an NF-A4x20): 2 tach pulses per revolution.
DEFAULT_PULSES_PER_REV = 2
DEFAULT_STALL_SECONDS = 30
DEFAULT_INTERVAL_SECONDS = 10

# hwmon device the kernel pwm-fan driver registers (dtoverlay=pwm-fan).
PWM_FAN_HWMON = "pwmfan"
ISSUE_PWM_FAN_MISSING = "pwm_fan_missing"
