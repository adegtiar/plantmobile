#!/usr/bin/python3

import logging
import RPi.GPIO as GPIO
import sys
import time

from collections import namedtuple

from led_outputs import DigitDisplay, LedBarGraphs, LedShadowIndicator
from light_sensors import LightSensorReader
from logger import LightCsvLogger

logging.basicConfig(level=logging.INFO)


class PlatformDriver(object):
    """The main driver for a single platform, wrapping up all sensors, actuators, and outputs."""

    def __init__(self, name, light_sensors, logger,
            led_bar_graphs=None, digit_display=None, led_shadow_indicator=None):
        self.name = name
        self.light_sensors = light_sensors
        self.logger = logger

        output_indicators = []
        if led_bar_graphs:
            output_indicators.append(led_bar_graphs)
        if digit_display:
            output_indicators.append(digit_display)
        if led_shadow_indicator:
            output_indicators.append(led_shadow_indicator)
        self.output_indicators = output_indicators

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
        for output in self.output_indicators:
            output.setup()

    def cleanup(self):
        """Cleans up and resets any local state and outputs."""
        for output in self.output_indicators:
            output.reset()

    def update_lux(self):
        """Reads and processes the current lux from the sensors."""
        lux = self.light_sensors.read()
        self.logger.log(lux)

        for output in self.output_indicators:
            output.update_lux(lux)
        return lux


def setup(platforms):
    GPIO.setmode(GPIO.BCM)        # use BCM GPIO Numbering

    # Initialize all platforms and return the ones that are failure-free.
    working_platforms = []
    for platform in platforms:
        try:
            platform.setup()
        except ValueError as e: # This might happen if the car is disconnected
            logging.error(e)
            logging.warning(
                    "Failed to setup {} platform: may be disconnected.".format(platform.name))
        else:
            working_platforms.append(platform)
    return working_platforms


def cleanup(platforms):
    for platform in platforms:
        platform.cleanup()
    # GPIO cleanup not needed when also using gpiozero
    #GPIO.cleanup()


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
            light_sensors=LightSensorReader(outer_pin=2, inner_pin=7),
            logger = LightCsvLogger("data/car_sensor_log.csv"),
            led_bar_graphs=LedBarGraphs(
                data_pin=26, latch_pin=19, clock_pin=13, min_level=500, max_level=30000),
            digit_display=DigitDisplay(clock_pin=5, data_pin=6),
            led_shadow_indicator=LedShadowIndicator(outer_led_pin=12, inner_led_pin=20))


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
