#!/usr/bin/python3

import logging
import RPi.GPIO as GPIO
import sys
import time

from collections import namedtuple
from enum import Enum
from gpiozero import Button

from led_outputs import DigitDisplay, LedBarGraphs, LedShadowIndicator
from light_sensors import LightSensorReader
from logger import LightCsvLogger
from motor import Direction, StepperMotor

logging.basicConfig(level=logging.INFO)


OUTER_DIRECTION = Direction.CW
INNER_DIRECTION = Direction.CCW


Status = namedtuple('Status', ['lux', 'button', 'position'])


class MotorCommand(Enum):
    STOP = 0
    OUTER_STEP = 1
    INNER_STEP = 2
    FIND_ORIGIN = 3


class ButtonStatus(Enum):
    NONE_PRESSED = 0
    OUTER_PRESSED = 1
    INNER_PRESSED = 2
    BOTH_PRESSED = 3


class PlatformDriver(object):
    """The main driver for a single platform, wrapping up all sensors, actuators, and outputs."""

    def __init__(self, name, light_sensors, logger,
            motor=None, outer_button=None, inner_button=None, output_indicators=None):
        self.name = name
        self.light_sensors = light_sensors
        self.logger = logger
        self.motor = motor
        self.outer_button = outer_button
        self.inner_button = inner_button
        self.output_indicators = output_indicators
        self.position = 0

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
        if self.motor:
            self.motor.setup()
        for output in self.output_indicators:
            output.setup()

    def cleanup(self):
        """Cleans up and resets any local state and outputs."""
        for output in self.output_indicators:
            output.reset()
        if self.motor:
            self.motor.reset()

    def update_status(self):
        """Reads and processes the current lux from the sensors."""
        lux = self.light_sensors.read()
        self.logger.log(lux)

        button_status = self.get_button_status()
        status = Status(lux, button=button_status, position=self.position)

        for output in self.output_indicators:
            output.update_status(status)

        return status

    def get_button_status(self):
        OUTER_PRESSED = self.outer_button.is_pressed if self.outer_button else False
        INNER_PRESSED = self.inner_button.is_pressed if self.inner_button else False

        if OUTER_PRESSED and INNER_PRESSED:
            return ButtonStatus.BOTH_PRESSED
        elif OUTER_PRESSED:
            return ButtonStatus.OUTER_PRESSED
        elif INNER_PRESSED:
            return ButtonStatus.INNER_PRESSED
        else:
            return ButtonStatus.NONE_PRESSED

    def motor_command(self, motor_command):
        if motor_command is MotorCommand.STOP:
            self.motor.reset()
        elif motor_command is MotorCommand.OUTER_STEP:
            self.motor.move_step(OUTER_DIRECTION)
            self.position -= 1
        elif motor_command is MotorCommand.INNER_STEP:
            self.motor.move_step(INNER_DIRECTION)
            self.position += 1
        elif motor_command is MotorCommand.FIND_ORIGIN:
            logging.warning("FIND_ORIGIN command not implemented")
        else:
            assert False, "motor command {} not supported".format(motor_command)


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


def print_status(statuses):
    luxes = [status.lux for status in statuses]
    def tabbed_join(accessor):
        return "\t".join(str(accessor(lux)) for lux in luxes)
    print("sensor:\t\t" + tabbed_join(lambda lux: lux.name))
    print("outer:\t\t" + tabbed_join(lambda lux: lux.outer))
    print("inner:\t\t" + tabbed_join(lambda lux: lux.inner))
    print("average:\t" + tabbed_join(lambda lux: lux.avg))
    print("diff:\t\t" + tabbed_join(lambda lux: lux.diff))
    print("diff percent:\t" + tabbed_join(lambda lux: "{}%".format(lux.diff_percent)))
    print("button_status:\t" + "\t".join([status.button.name for status in statuses]))
    print("position:\t" + "\t".join([str(status.position) for status in statuses]))
    print()


def loop(platforms):
    while True:
        statuses = [platform.update_status() for platform in platforms]

        print_status(statuses)

        for status, platform in zip(statuses, platforms):
            # Enable manual button->motor control.
            if status.button is ButtonStatus.OUTER_PRESSED:
                logging.info("starting command sequence OUTER_STEP")
                while platform.get_button_status() is ButtonStatus.OUTER_PRESSED:
                    platform.motor_command(MotorCommand.OUTER_STEP)
                logging.info("stopping command sequence OUTER_STEP")
            if status.button is ButtonStatus.INNER_PRESSED:
                logging.info("starting command sequence INNER_STEP")
                while platform.get_button_status() is ButtonStatus.INNER_PRESSED:
                    platform.motor_command(MotorCommand.INNER_STEP)
                logging.info("stopping command sequence INNER_STEP")
            elif status.button is ButtonStatus.BOTH_PRESSED:
                logging.info("sending command FIND_ORIGIN")
                platform.motor_command(MotorCommand.FIND_ORIGIN)
            elif status.button is ButtonStatus.NONE_PRESSED:
                logging.debug("sending command STOP")
                platform.motor_command(MotorCommand.STOP)
        # TODO: do something with the luxes.
        time.sleep(.5)


if __name__ == '__main__':
    STEPPER_CAR = PlatformDriver(
            name="Stepper",
            light_sensors=LightSensorReader(outer_pin=2, inner_pin=3),
            logger=LightCsvLogger("data/car_sensor_log.csv"),
            motor=StepperMotor(27, 22, 10, 9),
            outer_button=Button(21),
            inner_button=Button(16),
            output_indicators=[
                LedBarGraphs(data_pin=25, latch_pin=8, clock_pin=7, min_level=500, max_level=30000),
                DigitDisplay(clock_pin=6, data_pin=13, display_func=lambda s: s.lux.diff_percent),
                DigitDisplay(clock_pin=19, data_pin=26, display_func=lambda s: s.position),
                LedShadowIndicator(outer_led_pin=20, inner_led_pin=12),
            ])


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
