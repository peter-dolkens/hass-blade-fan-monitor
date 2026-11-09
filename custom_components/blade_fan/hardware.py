"""Blocking hardware access: GPIO tach counting and pwm-fan duty. Never call
these from the event loop; the coordinator runs them in the executor."""

from __future__ import annotations

from datetime import timedelta
import glob
import logging
import threading

import gpiod
from gpiod.line import Bias, Edge

_LOGGER = logging.getLogger(__name__)


class ChipNotFound(Exception):
    """No GPIO chip with the configured label."""


def find_chip(label: str) -> str:
    """Return the /dev/gpiochipN path whose label matches (numbering can change)."""
    for path in sorted(glob.glob("/dev/gpiochip*")):
        try:
            with gpiod.Chip(path) as chip:
                if chip.get_info().label == label:
                    return path
        except OSError as err:
            _LOGGER.debug("Skipping %s: %s", path, err)
    raise ChipNotFound(label)


def probe(label: str, gpio: int) -> str | None:
    """Check the tach line can be claimed. Returns a config-flow error key."""
    try:
        path = find_chip(label)
    except ChipNotFound:
        return "chip_not_found"
    try:
        gpiod.request_lines(
            path, consumer="blade-fan-probe", config={gpio: gpiod.LineSettings()}
        ).release()
    except OSError as err:
        _LOGGER.debug("Cannot claim %s line %d: %s", path, gpio, err)
        return "line_busy"
    except ValueError:
        return "invalid_gpio"
    return None


def find_hwmon(name: str) -> str | None:
    """Return the /sys/class/hwmon directory of the named device."""
    for path in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            with open(f"{path}/name", encoding="ascii") as file:
                if file.read().strip() == name:
                    return path
        except OSError:
            continue
    return None


def read_int(path: str) -> int | None:
    try:
        with open(path, encoding="ascii") as file:
            return int(file.read().strip())
    except (OSError, ValueError):
        return None


class TachCounter(threading.Thread):
    """Counts falling tach edges; the coordinator drains the count each update."""

    def __init__(self, chip_path: str, gpio: int) -> None:
        super().__init__(daemon=True, name=f"blade_fan_tach_{gpio}")
        self._request = gpiod.request_lines(
            chip_path,
            consumer="blade-fan-tach",
            config={
                gpio: gpiod.LineSettings(edge_detection=Edge.FALLING, bias=Bias.PULL_UP)
            },
        )
        self._count = 0
        self._lock = threading.Lock()
        self._stopping = threading.Event()

    def run(self) -> None:
        try:
            while not self._stopping.is_set():
                if self._request.wait_edge_events(timedelta(seconds=1)):
                    events = len(self._request.read_edge_events())
                    with self._lock:
                        self._count += events
        except Exception:
            # The coordinator sees the dead thread and restarts it.
            _LOGGER.exception("Tach counter stopped")
        finally:
            self._request.release()

    def drain(self) -> int:
        with self._lock:
            count, self._count = self._count, 0
        return count

    def stop(self) -> None:
        self._stopping.set()
        self.join(timeout=3)
