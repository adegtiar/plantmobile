#!/usr/bin/python3

import logging
import RPi.GPIO as GPIO
import sys
import time

from collections import namedtuple

from led_graphs import LedBarGraphs, DigitDisplay
from light_sensors import LightSensorReader
from logger import LightCsvLogger

logging.basicConfig(level=logging.INFO)



class PlatformDriver(object):
    """The main driver for a single platform, wrapping up all sensors, actuators, and outputs."""

    def __init__(self, name, light_sensors, logger, led_bar_graphs=None, digit_display=None):
        self.name = name
        self.light_sensors = light_sensors
        self.logger = logger
        self.led_bar_graphs = led_bar_graphs
        self.digit_display = digit_display

    def setup(self):
        """Initialize all components of the platform.

        This sets up connections and initializes default state. Any obvious failures in the hardware
        should trigger here.
        """
        # Set up the light sensors for reading.
        self.light_sensors.name = self.name
        self.light_sensors.setup()
        # Set up the logger for writing.
        self.logger.setup()
        if self.led_bar_graphs:
            self.led_bar_graphs.setup()
        if self.digit_display is not None:
            self.digit_display.setup()

    def cleanup(self):
        """Cleans up and resets any local state and outputs."""
        if self.led_bar_graphs:
            self.led_bar_graphs.reset()
        if self.digit_display:
            self.digit_display.reset()

    def update_lux(self):
        """Reads and processes the current lux from the sensors."""
        lux = self.light_sensors.read()
        self.logger.log(lux)
        if self.led_bar_graphs:
            self.led_bar_graphs.set_levels(lux.outer, lux.inner)
        if self.digit_display:
            self.digit_display.update_diff(lux)
        return lux


def setup(platforms):
    GPIO.setmode(GPIO.BCM)        # use BCM GPIO Numbering

    # Initialize all platforms and return the ones that are failure-free.
    working_platforms = []
    for platform in platforms:
        try:
            platform.setup()
        except ValueError: # This might happen if the car is disconnected
            logging.warning(
                    "Failed to setup {} platform: may be disconnected.".format(platform.name))
        else:
            working_platforms.append(platform)
    return working_platforms


def cleanup(platforms):
    for platform in platforms:
        platform.cleanup()
    GPIO.cleanup()


def print_status(luxes):
    def tabbed_join(accessor):
        return "\t".join(str(accessor(lux)) for lux in luxes)
    print("sensor:\t\t" + tabbed_join(lambda lux: lux.name))
    print("outer:\t\t" + tabbed_join(lambda lux: lux.outer))
    print("inner:\t\t" + tabbed_join(lambda lux: lux.inner))
    print("average:\t" + tabbed_join(lambda lux: lux.avg))
    print("diff:\t\t" + tabbed_join(lambda lux: lux.diff))
    print("diff percent:\t" + tabbed_join(lambda lux: "{}%".format(lux.diff_percent)))
    print()


def loop(platforms):
    while True:
        luxes = [platform.update_lux() for platform in platforms]

        print_status(luxes)

        # TODO: do something with the luxes.
        time.sleep(.5)


if __name__ == '__main__':
    STEPPER_CAR = PlatformDriver(
            name="Stepper",
            light_sensors=LightSensorReader(outer_pin=2, inner_pin=6),
            logger = LightCsvLogger("data/car_sensor_log.csv"),
            led_bar_graphs=LedBarGraphs(
                data_pin=26, latch_pin=19, clock_pin=13, min_level=500, max_level=30000),
            digit_display=DigitDisplay(clock_pin=20, data_pin=21, min_output_light=10))


    DC_CAR = PlatformDriver(
            name="DC",
            light_sensors=LightSensorReader(outer_pin=1, inner_pin=0),
            logger=LightCsvLogger("data/base_sensor_log.csv"))

    working_platforms = setup([STEPPER_CAR, DC_CAR])
    if not working_platforms:
        print("No working platforms to run. Exiting.")
        sys.exit(1)
    try:
        loop(working_platforms)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        cleanup(working_platforms)
