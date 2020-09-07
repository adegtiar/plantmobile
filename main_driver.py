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
        return motor.Direction.CW if self is Direction.OUTER else motor.Direction.CCW

    @property
    def extreme_edge(self):
        return Edge.OUTER if self is Direction.OUTER else Edge.INNER

    @property
    def extreme_edge(self):
        return Edge.OUTER if self is Direction.OUTER else Edge.INNER


class Edge(Enum):
    NONE = None
    OUTER = 0
    INNER = 640


class MotorCommand(Enum):
    STOP = 0
    OUTER_STEP = 1
    INNER_STEP = 2

    @property
    def direction(self):
        if self is MotorCommand.OUTER_STEP:
            return Direction.OUTER
        elif self is MotorCommand.INNER_STEP:
            return Direction.INNER
        else:
            return None


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
            output.off()
        if self.motor:
            self.motor.off()

    def get_status(self, reset_position_on_edge=False):
        """Reads the current lux, button, position, and edge from sensors and state."""
        return Status(
                lux=self.light_sensors.read(),
                button=self.get_button_status(),
                position=self.position,
                edge=self.get_edge_status(reset_position_on_edge))

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

    def get_edge_status(self, reset_position_on_edge=False):
        if self.position == Edge.INNER.value:
            return Edge.INNER

        at_outer_edge = not self.distance_sensor.is_in_range()
        if at_outer_edge and (self.position is None or reset_position_on_edge):
            logging.info("At outer edge. Setting position to zero.")
            self._update_position(Edge.OUTER)
        return Edge.OUTER if at_outer_edge else Edge.NONE

    def _update_position(self, increment):
        if increment == Edge.OUTER:
            # Initialize the position to 0 at the edge.
            if self.position is None:
                logging.info("Initializing edge position to {}".format(Edge.OUTER))
            elif self.position != Edge.OUTER.value:
                log = logging.info if abs(self.position) < 10 else logging.warning
                log("Resetting edge position to {} (drift: {})".format(Edge.OUTER, self.position))
            self.position = Edge.OUTER.value
        else:
            # We've stepped in a direction, so increment.
            assert isinstance(increment, Direction), "Increment must be a Direction or Edge"

            if self.position is not None:
                # Increment the position if it's been set.
                self.position += increment.value

        if self._position_display:
            self._position_display.update_position(self.position)

    def move_direction(self, printer, status, direction, continue_checker):
        logging.info("starting sequence move towards %s", direction)
        while continue_checker(status):
            if status.edge is direction.extreme_edge:
                logging.info("stopping sequence move towards %s: at edge", direction)
                return
            else:
                self.motor.move_step(direction.motor_direction)
                self._update_position(direction)

            # When moving towards the edge, reset our position if we've drifted.
            status = self.get_status(reset_position_on_edge=direction is Direction.OUTER)
            printer.print_status([status])
        logging.info("stopping sequence move towards %s: stopped", direction)


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


class StatusPrinter(object):

    def __init__(self, print_interval=MAIN_LOOP_SLEEP_SECS):
        self.print_interval = print_interval
        self._last_printed_time = float("-inf")

    def print_status(self, statuses):
        if time.time() - self._last_printed_time < self.print_interval:
            return

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
        self._last_printed_time = time.time()


def loop(platforms):
    printer = StatusPrinter()

    auto_mode = False
    while True:
        statuses = [platform.get_status() for platform in platforms]

        printer.print_status(statuses)

        for i, (status, platform) in enumerate(zip(statuses, platforms)):
            platform.output_status(status)

            # Enable manual button->motor control.
            if status.button is ButtonStatus.OUTER_PRESSED:
                continue_checker = lambda s: auto_mode or s.button is ButtonStatus.OUTER_PRESSED
                platform.move_direction(printer, status, Direction.OUTER, continue_checker)
            if status.button is ButtonStatus.INNER_PRESSED:
                continue_checker = lambda s: auto_mode or s.button is ButtonStatus.INNER_PRESSED
                platform.move_direction(printer, status, Direction.INNER, continue_checker)
            if status.button is ButtonStatus.BOTH_PRESSED:
                # Toggle between manual mode and auto mode.
                platform.move_direction(printer, status, Direction.OUTER, lambda _: not auto_mode)
            elif status.button is ButtonStatus.NONE_PRESSED:
                platform.motor.off()

        # TODO: do something with the luxes.

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
