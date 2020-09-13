#!/usr/bin/env python3

import itertools
import logging
import time
from typing import NoReturn

import board
import RPi.GPIO as GPIO
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


def loop(sensor: DistanceSensor) -> NoReturn:
    out_of_range = False
    for i in itertools.count():
        distance = sensor.read()
        if out_of_range or i % 1 == 0:
            print("The distance is : %.2f cm" % (distance))
        out_of_range = distance == float("inf")
        if out_of_range:
            out_of_range = True
            print("sensor is out of range")
        time.sleep(.1)
    assert False, "Not reached"


if __name__ == '__main__':
    # TODO: move this to a separate script
    print('Program is starting...')
    sensor = DistanceSensor(trig_pin=board.D4, echo_pin=board.D17, threshold_cm=10)
    sensor.setup()

    try:
        loop(sensor)
    except KeyboardInterrupt:
        sensor.off()
        GPIO.cleanup()