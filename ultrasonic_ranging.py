#!/usr/bin/env python3

import RPi.GPIO as GPIO
import time

from adafruit_hcsr04 import HCSR04
import board


class DistanceSensor(object):

    def __init__(self, trig_pin, echo_pin, threshold_cm=10, timeout=0.05):
        self.trig_pin = board.pin.Pin(trig_pin)
        self.echo_pin = board.pin.Pin(echo_pin)
        self.threshold_cm = threshold_cm
        self.timeout = timeout
        self._sensor = None

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
            return self._sensor.distance
        except RuntimeError:
            return float("inf")

    def is_in_range(self):
        return self.get_distance() < self.threshold_cm


def loop(sensor):
    while(True):
        #print ("The distance is : %.2f cm" % (sensor.get_distance()))
        in_range = sensor.is_in_range()
        print("sensor is {} range".format("in" if in_range else "out of"))
        time.sleep(.1)



if __name__ == '__main__':     # Program entrance
    print ('Program is starting...')
    sensor = DistanceSensor(trig_pin=4, echo_pin=17, threshold_cm=10)
    try:
        loop(sensor)
    except KeyboardInterrupt:  # Press ctrl-c to end the program.
        #GPIO.cleanup()         # release GPIO resource
        sensor.off()
