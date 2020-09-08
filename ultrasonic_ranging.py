#!/usr/bin/env python3

import itertools
import logging
import RPi.GPIO as GPIO
import time

from adafruit_hcsr04 import HCSR04  # type: ignore
import board

from common import Component


class DistanceSensor(Component):

    def __init__(self, trig_pin, echo_pin, threshold_cm=10, timeout=0.05):
        self.trig_pin = board.pin.Pin(trig_pin)
        self.echo_pin = board.pin.Pin(echo_pin)
        self.threshold_cm = threshold_cm
        self.timeout = timeout
        self._sensor = None
        self._prev_distance = None

    def setup(self):
        if self._sensor is None:
            self._sensor = HCSR04(
                    trigger_pin=self.trig_pin, echo_pin=self.echo_pin, timeout=self.timeout)

    def off(self):
        if self._sensor:
            self._sensor.deinit()

    def get_distance(self):
        """Gets the distance in cm via the sensor.

        Returns inf when no response is heard within timeout."""
        self.setup()
        try:
            self._prev_distance = self._sensor.distance
        except RuntimeError:
            logging.warn("Failed to read distance. Defaulting to previously read value")

        if self._prev_distance is None:
            logging.warn("Initializing first value to inf and retrying")
            self._prev_distance = float("inf")
            return self.get_distance()
        else:
            return self._prev_distance

    def is_in_range(self):
        return self.get_distance() < self.threshold_cm


def loop(sensor):
    out_of_range = False
    for i in itertools.count():
        distance = sensor.get_distance()
        if out_of_range or i % 1 == 0:
            print("The distance is : %.2f cm" % (distance))
        out_of_range = distance == float("inf")
        if out_of_range:
            out_of_range = True
            print("sensor is out of range")
        time.sleep(.1)


if __name__ == '__main__':     # Program entrance
    print ('Program is starting...')
    sensor = DistanceSensor(trig_pin=4, echo_pin=17, threshold_cm=10)

    try:
        loop(sensor)
    except KeyboardInterrupt:  # Press ctrl-c to end the program.
        #GPIO.cleanup()         # release GPIO resource
        sensor.off()
