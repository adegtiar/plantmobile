#!/usr/bin/python3

import logging
import RPi.GPIO as GPIO
import sys
import time

from enum import Enum
from gpiozero import Button

import motor

from common import ButtonStatus, Component, Direction, Region, Output, Status
from led_outputs import LedBarGraphs, LedDirectionIndicator, LuxDiffDisplay, PositionDisplay
from light_sensors import LightSensorReader
from logger import LightCsvLogger, StatusPrinter
from motor import StepperMotor
from ultrasonic_ranging import DistanceSensor

logging.basicConfig(level=logging.INFO)


MAIN_LOOP_SLEEP_SECS = 0.5


class PlatformDriver(Component):
    """The main driver for a single platform, wrapping up all sensors, actuators, and outputs."""

    def __init__(self, name, light_sensors, motor=None, distance_sensor=None,
            direction_leds=None, outer_button=None, inner_button=None, outputs=()):
        self.name = name
        self.light_sensors = light_sensors
        self.motor = motor
        self.distance_sensor = distance_sensor
        self.outer_button = outer_button
        self.inner_button = inner_button
        self.outputs = list(outputs)
        self._position_display = None
        self._direction_leds = direction_leds
        if direction_leds:
            self.outputs.append(direction_leds)

        for output in outputs:
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
        if self.motor:
            self.motor.setup()
        for output in self.outputs:
            output.setup()

    def off(self):
        """Cleans up and resets any local state and outputs."""
        for output in self.outputs:
            output.off()
        if self.motor:
            self.motor.off()

    def get_status(self, reset_position_on_edge=False):
        """Reads the current lux, button, position, and edge from sensors and state."""
        return Status(
                lux=self.light_sensors.read(),
                button=self.get_button_status(),
                position=self.position,
                region=self.get_region(reset_position_on_edge))

    def output_status(self, status):
        """Updates the indicators and logs with the given status."""
        for output in self.outputs:
            output.output_status(status)

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

    def get_region(self, reset_position_on_edge=False):
        if self.position == Region.INNER_EDGE.value:
            return Region.INNER_EDGE

        at_outer_edge = not self.distance_sensor.is_in_range()
        if at_outer_edge and (self.position is None or reset_position_on_edge):
            logging.info("At outer edge. Setting position to zero.")
            self._update_position(Region.OUTER_EDGE)
        return Region.OUTER_EDGE if at_outer_edge else Region.MID

    def _update_position(self, increment):
        if increment == Region.OUTER_EDGE:
            # Initialize the position to 0 at the edge.
            if self.position is None:
                logging.info("Initializing edge position to {}".format(Region.OUTER_EDGE))
            elif self.position != Region.OUTER_EDGE.value:
                log = logging.info if abs(self.position) < 10 else logging.warning
                log("Resetting outer edge position (drift: {})".format( self.position))
            self.position = Region.OUTER_EDGE.value
        else:
            # We've stepped in a direction, so increment.
            assert isinstance(increment, Direction), "Increment must be a Direction or Region"

            if self.position is not None:
                # Increment the position if it's been set.
                self.position += increment.value

        if self._position_display:
            self._position_display.update_position(self.position)

    def move_direction(self, direction, should_continue):
        logging.info("starting sequence move towards %s", direction)
        status = self.get_status()
        while should_continue(status):
            if status.region is direction.extreme_edge:
                logging.info("stopping sequence move towards %s: at edge", direction)
                return
            else:
                self.motor.move_step(direction.motor_rotation)
                self._update_position(direction)

            # When moving towards the edge, reset our position if we've drifted.
            status = self.get_status(reset_position_on_edge=direction is Direction.OUTER)
            self.output_status(status)

        logging.info("stopping sequence move towards %s: stopped", direction)

    def blink(self, times=2, pause_secs=0.2):
        for i in range(times):
            self._direction_leds.on()
            self.motor.all_on()
            time.sleep(pause_secs)
            self._direction_leds.off()
            self.motor.off()
            if i != times-1:
                time.sleep(pause_secs)


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
        platform.off()
    # GPIO cleanup not needed when also using gpiozero
    #GPIO.cleanup()


def keep_moving_checker(manual_mode, manual_hold_button):
    def keep_moving(status):
        if manual_mode:
            # Keep moving while the button is held down.
            return status.button is manual_hold_button
        else:
            # Keep moving unless any button is pressed to cancel it.
            return status.button is ButtonStatus.NONE_PRESSED
    return keep_moving


def control_loop(platform):
    manual_mode = True

    while True:
        status = platform.get_status()
        platform.output_status(status)

        # Enable manual button->motor control.
        if status.button is ButtonStatus.OUTER_PRESSED:
            if not manual_mode:
                platform.blink(times=2)
            keep_moving_outer = keep_moving_checker(manual_mode, ButtonStatus.OUTER_PRESSED)
            platform.move_direction(Direction.OUTER, should_continue=keep_moving_outer)
        if status.button is ButtonStatus.INNER_PRESSED:
            if not manual_mode:
                platform.blink(times=2)
            keep_moving_inner = keep_moving_checker(manual_mode, ButtonStatus.INNER_PRESSED)
            platform.move_direction(Direction.INNER, should_continue=keep_moving_inner)
        if status.button is ButtonStatus.BOTH_PRESSED:
            # Toggle between manual mode and auto mode.
            platform.blink(times=3)
            manual_mode = not manual_mode
            if not manual_mode:
                keep_moving_auto = keep_moving_checker(False, None)
                platform.move_direction(Direction.OUTER, should_continue=keep_moving_auto)
        elif status.button is ButtonStatus.NONE_PRESSED:
            platform.motor.off()

        # TODO: do something with the luxes.

        time.sleep(MAIN_LOOP_SLEEP_SECS)


if __name__ == '__main__':
    STEPPER_CAR = PlatformDriver(
            name="Stepper",
            light_sensors=LightSensorReader(outer_pin=2, inner_pin=3),
            motor=StepperMotor(27, 22, 10, 9),
            distance_sensor=DistanceSensor(trig_pin=4, echo_pin=17, threshold_cm=10, timeout=0.05),
            outer_button=Button(21),
            inner_button=Button(16),
            direction_leds=LedDirectionIndicator(outer_led_pin=20, inner_led_pin=12),
            outputs=[
                LightCsvLogger("data/car_sensor_log.csv"),
                LedBarGraphs(data_pin=25, latch_pin=8, clock_pin=7, min_level=500, max_level=30000),
                LuxDiffDisplay(clock_pin=6, data_pin=13),
                PositionDisplay(clock_pin=19, data_pin=26),
                StatusPrinter(print_interval=MAIN_LOOP_SLEEP_SECS),
            ])


    DC_CAR = PlatformDriver(
            name="DC",
            light_sensors=LightSensorReader(outer_pin=1, inner_pin=0),
            outputs=[
                LightCsvLogger("data/base_sensor_log.csv"),
            ])

    working_platforms = setup([STEPPER_CAR])
    if not working_platforms:
        print("No working platforms to run. Exiting.")
        sys.exit(1)
    try:
        control_loop(working_platforms[0])
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        cleanup(working_platforms)
