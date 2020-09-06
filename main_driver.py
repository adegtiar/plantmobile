#!/usr/bin/python3

import logging
import RPi.GPIO as GPIO
import sys
import time

from enum import Enum
from gpiozero import Button

import motor

from common import ButtonStatus, Status
from led_outputs import LedBarGraphs, LedShadowIndicator, LuxDiffDisplay, PositionDisplay
from light_sensors import LightSensorReader
from logger import LightCsvLogger
from ultrasonic_ranging import DistanceSensor

logging.basicConfig(level=logging.INFO)


MAIN_LOOP_SLEEP_SECS = 0.5


class Direction(Enum):
    OUTER = -1
    INNER = +1

    @property
    def motor_direction(self):
        if self is Direction.OUTER:
            return motor.Direction.CW
        elif self is Direction.INNER:
            return motor.Direction.CCW


class Edge(Enum):
    NONE = float("inf")
    OUTER = 0
    INNER = 620


class MotorCommand(Enum):
    STOP = 0
    OUTER_STEP = 1
    INNER_STEP = 2
    FIND_ORIGIN = 3


class PlatformDriver(object):
    """The main driver for a single platform, wrapping up all sensors, actuators, and outputs."""

    def __init__(self, name, light_sensors, logger, motor=None, distance_sensor=None,
            outer_button=None, inner_button=None, output_indicators=()):
        self.name = name
        self.light_sensors = light_sensors
        self.logger = logger
        self.motor = motor
        self.distance_sensor = distance_sensor
        self.outer_button = outer_button
        self.inner_button = inner_button
        self.output_indicators = output_indicators
        self._position_display = None
        for output in output_indicators:
            if isinstance(output, PositionDisplay):
                self._position_display = output
                break
        self.position = None
        self._at_outer_edge_cached = None

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

    def get_status(self):
        """Reads the current lux, button, position, and edge from sensors and state."""
        return Status(
                lux=self.light_sensors.read(), button=self.get_button_status(),
                position=self.position, edge=self.get_edge_status())

    def output_status(self, status):
        """Updates the indicators and logs with the given status."""
        self.logger.log(status.lux)
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

    def get_edge_status(self, skip_cache=False):
        if self.position == Edge.INNER.value:
            return Edge.INNER

        # Cache this value if we're not moving.
        if self._at_outer_edge_cached is None or skip_cache:
            self._at_outer_edge_cached = not self.distance_sensor.is_in_range()
            if self._at_outer_edge_cached:
                logging.info("At outer edge. Setting position to zero.")
                self._update_position(Edge.OUTER)
        return Edge.OUTER if self._at_outer_edge_cached else Edge.NONE

    def _update_position(self, increment):
        if increment == Edge.OUTER:
            # Initialize the position to 0 at the edge.
            if self.position is None:
                logging.info("Initializing edge position to {}".format(Edge.OUTER))
            elif self.position != 0:
                log = logging.info if abs(self.position) < 10 else logging.warning
                log("Resetting edge position to {} (drift: {})".format(Edge.OUTER, self.position))
            self.position = Edge.OUTER.value
        else:
            assert isinstance(increment, Direction), "Increment must be a Direction or Edge"
            # Clear the cached edge value, since we moved and it might have changed.
            self._at_outer_edge_cached = None

            if self.position is not None:
                # Increment the position if it's been set.
                self.position += increment.value

        if self._position_display:
            self._position_display.update_position(self.position)

    def motor_command(self, command):
        """Returns if the command was able to be run."""
        if command is MotorCommand.STOP:
            self.motor.reset()
        elif command is MotorCommand.OUTER_STEP:
            if self.get_edge_status(skip_cache=True) is Edge.OUTER:
                logging.info("skipping command OUTER_STEP: at edge")
                return False
            direction = Direction.OUTER
            self.motor.move_step(direction.motor_direction)
            self._update_position(direction)
        elif command is MotorCommand.INNER_STEP:
            if self.get_edge_status() is Edge.INNER:
                logging.info("skipping command INNER_STEP: at edge")
                return False
            direction = Direction.INNER
            self.motor.move_step(direction.motor_direction)
            self._update_position(direction)
        elif command is MotorCommand.FIND_ORIGIN:
            logging.warning("FIND_ORIGIN command not implemented")
            return False
        else:
            assert False, "motor command {} not supported".format(command)
        return True


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
    print("at edge:\t" + "\t".join([str(status.edge) for status in statuses]))
    print()


def loop(platforms):
    partial_run = False
    while True:
        statuses = [platform.get_status() for platform in platforms]

        if not partial_run:
            print_status(statuses)

        for status, platform in zip(statuses, platforms):
            platform.output_status(status)

            # Enable manual button->motor control.
            if status.button is ButtonStatus.OUTER_PRESSED:
                if not partial_run:
                    logging.info("starting command sequence OUTER_STEP")
                partial_run = platform.motor_command(MotorCommand.OUTER_STEP)
                if not partial_run:
                    logging.info("stopping command sequence OUTER_STEP")
            if status.button is ButtonStatus.INNER_PRESSED:
                if not partial_run:
                    logging.info("starting command sequence INNER_STEP")
                partial_run = platform.motor_command(MotorCommand.INNER_STEP)
                if not partial_run:
                    logging.info("stopping command sequence INNER_STEP")
            elif status.button is ButtonStatus.BOTH_PRESSED:
                logging.info("sending command FIND_ORIGIN")
                platform.motor_command(MotorCommand.FIND_ORIGIN)
            elif status.button is ButtonStatus.NONE_PRESSED:
                if partial_run:
                    logging.info("sending command STOP")
                    partial_run = False
                else:
                    logging.debug("sending command STOP")
                platform.motor_command(MotorCommand.STOP)

        # TODO: do something with the luxes.

        if not partial_run:
            # Sleep if not in the middle of doing something, else immediately continue the loop.
            time.sleep(MAIN_LOOP_SLEEP_SECS)


if __name__ == '__main__':
    STEPPER_CAR = PlatformDriver(
            name="Stepper",
            light_sensors=LightSensorReader(outer_pin=2, inner_pin=3),
            logger=LightCsvLogger("data/car_sensor_log.csv"),
            motor=motor.StepperMotor(27, 22, 10, 9),
            distance_sensor=DistanceSensor(trig_pin=4, echo_pin=17, threshold_cm=10, timeout=0.05),
            outer_button=Button(21),
            inner_button=Button(16),
            output_indicators=[
                LedBarGraphs(data_pin=25, latch_pin=8, clock_pin=7, min_level=500, max_level=30000),
                LuxDiffDisplay(clock_pin=6, data_pin=13),
                PositionDisplay(clock_pin=19, data_pin=26),
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
