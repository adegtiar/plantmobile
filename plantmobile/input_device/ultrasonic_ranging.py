import logging

from adafruit_hcsr04 import HCSR04  # type: ignore

from plantmobile.common import Component, Pin


class DistanceSensor(Component):

    def __init__(self, trig_pin: Pin, echo_pin: Pin,
                 threshold_cm: int = 10, timeout: float = 0.05) -> None:
        self.trig_pin = trig_pin
        self.echo_pin = echo_pin
        self.threshold_cm = threshold_cm
        self.timeout = timeout
        self._sensor = None
        self._prev_distance = None

    def setup(self) -> None:
        if self._sensor is None:
            self._sensor = HCSR04(
                    trigger_pin=self.trig_pin, echo_pin=self.echo_pin, timeout=self.timeout)

    def off(self) -> None:
        if self._sensor:
            self._sensor.deinit()

    def read(self) -> float:
        """Gets the distance in cm via the sensor.

        Returns inf when no response is heard within timeout."""
        assert self._sensor, "Must call setup before reading"

        try:
            self._prev_distance = self._sensor.distance
        except RuntimeError:
            logging.warn("Failed to read distance. Defaulting to previously read value")

        if self._prev_distance is None:
            logging.warn("Initializing first value to inf and retrying")
            self._prev_distance = float("inf")
            return self.read()
        else:
            return self._prev_distance

    def is_in_range(self) -> bool:
        return self.read() < self.threshold_cm
