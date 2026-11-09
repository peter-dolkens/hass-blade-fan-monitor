"""Blade Fan Monitor: tach RPM + kernel pwm-fan duty -> Home Assistant sensors.

The kernel pwm-fan driver owns GPIO12 (PWM) and the thermal curve; it does not
read the tach. This add-on only observes: it counts falling edges on the tach
line and reads the duty the driver last applied. It never drives the fan, so a
crash here can't affect cooling.

Sensors are published by MQTT discovery when the Supervisor offers an MQTT
service (unique_ids, one "Blade Fan" device, renamable in the UI). Without a
broker it falls back to pushing plain states through the core REST API.
"""
import glob
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import timedelta

import gpiod
from gpiod.line import Bias, Edge

OPTIONS_PATH = "/data/options.json"
SUPERVISOR = "http://supervisor"
# Supervisor passes the add-on version as a build arg; the Dockerfile keeps it.
VERSION = os.environ.get("BUILD_VERSION") or None

log = logging.getLogger("blade_fan")


def load_options():
    with open(OPTIONS_PATH) as f:
        return json.load(f)


def supervisor_request(path, body=None):
    req = urllib.request.Request(
        f"{SUPERVISOR}{path}",
        data=None if body is None else json.dumps(body).encode(),
        method="GET" if body is None else "POST",
        headers={
            "Authorization": f"Bearer {os.environ.get('SUPERVISOR_TOKEN', '')}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.load(resp) if body is None else None


def find_chip(label):
    for path in sorted(glob.glob("/dev/gpiochip*")):
        try:
            with gpiod.Chip(path) as chip:
                if chip.get_info().label == label:
                    return path
        except OSError as exc:
            log.debug("skip %s: %s", path, exc)
    raise SystemExit(f"no GPIO chip labelled {label!r} (is 'gpio: true' / the device mapped?)")


def find_hwmon(name):
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            with open(f"{d}/name") as f:
                if f.read().strip() == name:
                    return d
        except OSError:
            pass
    return None


def read_int(path):
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


class TachCounter(threading.Thread):
    """Counts falling tach edges; the main loop drains the count each interval."""

    def __init__(self, chip_path, gpio):
        super().__init__(daemon=True, name="tach")
        self.request = gpiod.request_lines(
            chip_path,
            consumer="blade-fan-tach",
            config={gpio: gpiod.LineSettings(edge_detection=Edge.FALLING, bias=Bias.PULL_UP)},
        )
        self._count = 0
        self._lock = threading.Lock()

    def run(self):
        while True:
            if self.request.wait_edge_events(timedelta(seconds=1)):
                n = len(self.request.read_edge_events())
                with self._lock:
                    self._count += n

    def drain(self):
        with self._lock:
            n, self._count = self._count, 0
        return n


# key -> (component, discovery fields). Shared by both sinks.
ENTITIES = {
    "speed": ("sensor", {
        "name": "Speed", "unit_of_measurement": "rpm", "state_class": "measurement",
        "icon": "mdi:fan",
    }),
    "duty": ("sensor", {
        "name": "Duty", "unit_of_measurement": "%", "state_class": "measurement",
        "icon": "mdi:speedometer",
    }),
    "stall": ("binary_sensor", {
        "name": "Stall", "device_class": "problem",
    }),
}


class MqttSink:
    """MQTT discovery: one "Blade Fan" device, entities with unique_ids."""

    def __init__(self, svc, prefix, discovery_prefix):
        import paho.mqtt.client as mqtt

        self.prefix = prefix
        self.discovery_prefix = discovery_prefix
        self.state_topic = f"{prefix}/state"
        self.avail_topic = f"{prefix}/availability"
        # paho 2.x requires a callback API version; 1.x (Alpine's) has no such arg.
        if hasattr(mqtt, "CallbackAPIVersion"):
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=f"{prefix}-monitor")
        else:
            self.client = mqtt.Client(client_id=f"{prefix}-monitor")
        if svc.get("username"):
            self.client.username_pw_set(svc["username"], svc.get("password"))
        if svc.get("ssl"):
            self.client.tls_set()
        self.client.will_set(self.avail_topic, "offline", retain=True)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(1, 60)
        self.client.connect_async(svc["host"], int(svc["port"]))
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            log.warning("MQTT connect refused (rc=%s)", rc)
            return
        log.info("MQTT connected; publishing discovery")
        self._announce()
        # Re-announce when Home Assistant restarts (its birth message).
        client.subscribe(f"{self.discovery_prefix}/status")

    def _on_message(self, client, userdata, msg):
        if msg.payload == b"online":
            self._announce()

    def _announce(self):
        device = {
            "identifiers": [self.prefix],
            "name": "Blade Fan",
            "manufacturer": "Uptime Lab",
            "model": "Compute Blade Fan Unit",
            "sw_version": VERSION,
        }
        for key, (component, fields) in ENTITIES.items():
            cfg = dict(fields, **{
                "unique_id": f"{self.prefix}_{key}",
                # Keeps the entity_ids the REST fallback used.
                "default_entity_id": f"{component}.{self.prefix}_{key}",
                "has_entity_name": True,
                "device": device,
                "state_topic": self.state_topic,
                "value_template": f"{{{{ value_json.{key} }}}}",
                "availability_topic": self.avail_topic,
            })
            if component == "binary_sensor":
                cfg.update({"payload_on": "ON", "payload_off": "OFF"})
            if key == "duty":
                cfg["json_attributes_topic"] = f"{self.prefix}/duty_attributes"
            self.client.publish(
                f"{self.discovery_prefix}/{component}/{self.prefix}/{key}/config",
                json.dumps(cfg), retain=True,
            )
        self.client.publish(self.avail_topic, "online", retain=True)

    def publish(self, rpm, duty, pwm, stalled):
        state = {"speed": rpm}
        if duty is not None:
            state.update({"duty": duty, "stall": "ON" if stalled else "OFF"})
            self.client.publish(f"{self.prefix}/duty_attributes", json.dumps({"pwm": pwm}))
        self.client.publish(self.state_topic, json.dumps(state))


class RestSink:
    """Fallback without a broker: plain states via core's REST API (no unique_id)."""

    NAMES = {"speed": "Blade fan speed", "duty": "Blade fan duty", "stall": "Blade fan stall"}

    def __init__(self, prefix):
        self.prefix = prefix
        self.failing = False

    def _set(self, entity_id, state, attributes):
        try:
            supervisor_request(f"/core/api/states/{entity_id}", {"state": state, "attributes": attributes})
        except (urllib.error.URLError, OSError) as exc:
            # Core restarting or still booting: warn once per outage, not every tick.
            if not self.failing:
                log.warning("cannot reach Home Assistant (%s); will keep retrying", exc)
            self.failing = True
            return
        if self.failing:
            log.info("Home Assistant reachable again")
        self.failing = False

    def _attrs(self, key, **extra):
        attrs = {k: v for k, v in ENTITIES[key][1].items() if k != "name"}
        attrs["friendly_name"] = self.NAMES[key]
        attrs.update(extra)
        return attrs

    def publish(self, rpm, duty, pwm, stalled):
        self._set(f"sensor.{self.prefix}_speed", rpm, self._attrs("speed"))
        if duty is not None:
            self._set(f"sensor.{self.prefix}_duty", duty, self._attrs("duty", pwm=pwm))
            self._set(f"binary_sensor.{self.prefix}_stall", "on" if stalled else "off", self._attrs("stall"))


def make_sink(opts):
    prefix = opts["entity_prefix"]
    try:
        svc = supervisor_request("/services/mqtt")["data"]
        svc["host"], svc["port"]
    except (urllib.error.URLError, OSError, KeyError, ValueError, TypeError) as exc:
        log.warning("no MQTT service (%s); using REST states (entities have no unique_id)", exc)
        return RestSink(prefix)
    log.info("using MQTT broker %s:%s", svc["host"], svc["port"])
    return MqttSink(svc, prefix, opts["discovery_prefix"])


def main():
    opts = load_options()
    logging.basicConfig(
        level=getattr(logging, opts["log_level"].upper().replace("WARN", "WARNING"), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    chip_path = find_chip(opts["gpio_chip_label"])
    tach = TachCounter(chip_path, opts["tach_gpio"])
    tach.start()
    log.info("counting tach on %s line %d, %d pulses/rev", chip_path, opts["tach_gpio"], opts["pulses_per_rev"])

    fan_hwmon = find_hwmon("pwmfan")
    if fan_hwmon is None:
        log.warning("no pwmfan hwmon device; duty and stall detection disabled (is the pwm-fan overlay loaded?)")

    sink = make_sink(opts)
    interval = opts["interval_seconds"]
    last_ok = time.monotonic()
    stalled = False
    last = time.monotonic()
    tach.drain()

    while True:
        time.sleep(interval)
        # A dead counter would report a silent 0 rpm forever; exit so the
        # Supervisor watchdog restarts the add-on instead.
        if not tach.is_alive():
            raise SystemExit("tach counter thread died")
        now = time.monotonic()
        pulses = tach.drain()
        rpm = round(pulses / opts["pulses_per_rev"] / (now - last) * 60)
        last = now

        pwm = read_int(f"{fan_hwmon}/pwm1") if fan_hwmon else None
        duty = None if pwm is None else round(pwm * 100 / 255)

        # A stall is commanded duty with no tach for stall_seconds. Duty 0 (fan
        # deliberately stopped) or unknown duty never counts against it.
        if pulses > 0 or not duty:
            last_ok = now
        now_stalled = duty is not None and now - last_ok >= opts["stall_seconds"]
        if now_stalled != stalled:
            (log.error if now_stalled else log.info)(
                "fan %s (duty %s%%, %d rpm)", "STALLED" if now_stalled else "recovered", duty, rpm
            )
            stalled = now_stalled

        log.debug("pulses=%d rpm=%d pwm=%s duty=%s%% stalled=%s", pulses, rpm, pwm, duty, stalled)
        sink.publish(rpm, duty, pwm, stalled)


if __name__ == "__main__":
    main()
