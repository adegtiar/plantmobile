#!/usr/bin/python3

import logging
import RPi.GPIO as GPIO
import sys
import time

from enum import Enum
from gpiozero import Button

import motor

from common import ButtonPress, Component, Direction, Region, Output, Status
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
                button=self.get_button_pressed(),
                position=self.position,
                region=self.get_region(reset_position_on_edge))

    def output_status(self, status):
        """Updates the indicators and logs with the given status."""
        for output in self.outputs:
            output.output_status(status)

        return status

    def get_button_pressed(self):
        """Gets the current button press status."""
        return ButtonPress.from_buttons(
                outer_pressed=self.outer_button and self.outer_button.is_pressed,
                inner_pressed=self.inner_button and self.inner_button.is_pressed)

    def get_region(self, reset_position_on_edge=False):
        """Get the region of the table in which the platform is located.

        Note: upon intialization when the position is unknown, we might report
        being in MID while we're actually at the inner edge."""
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

    def move_direction(self, direction, stop_requested):
        logging.info("starting sequence move towards %s", direction)
        stop_fmt = "stopping sequence move towards {}: %s (%d steps)".format(direction)

        # Move at most the region size, with a small error buffer to bias towards the outer edge.
        max_distance = int(Region.size() * 1.1)

        for steps_travelled in range(max_distance+1):
            # When moving towards the edge, reset our position if we've drifted.
            status = self.get_status(reset_position_on_edge=direction is Direction.OUTER)
            self.output_status(status)

            if stop_requested(status):
                logging.info(stop_fmt, "stopped", steps_travelled)
                return
            elif status.region is direction.extreme_edge:
                logging.info(stop_fmt, "at edge", steps_travelled)
                return
            elif steps_travelled == max_distance:
                # Terminate with an explicit check to run edge check first.
                logging.warning(stop_fmt, "went {} steps without reaching edge".format(steps))
                return
            else:
                self.motor.move_step(direction.motor_rotation)
                self._update_position(direction)
        assert False, "should terminate within the loop"

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


def stop_requester(manual_mode, manual_hold_button):
    def stop_requested(status):
        if manual_mode:
            # Keep moving while the button is held down.
            return not (status.button is manual_hold_button)
        else:
            # Keep moving unless any button is pressed to cancel it.
            return not (status.button is ButtonPress.NONE)
    return stop_requested


def control_loop(platform):
    manual_mode = True

    while True:
        status = platform.get_status()
        platform.output_status(status)

        # Enable manual button->motor control.
        if status.button is ButtonPress.OUTER:
            if not manual_mode:
                platform.blink(times=2)
            platform.move_direction(Direction.OUTER, stop_requester(manual_mode, ButtonPress.OUTER))
        if status.button is ButtonPress.INNER:
            if not manual_mode:
                platform.blink(times=2)
            platform.move_direction(Direction.INNER, stop_requester(manual_mode, ButtonPress.INNER))
        if status.button is ButtonPress.BOTH:
            # Toggle between manual mode and auto mode.
            platform.blink(times=3)
            manual_mode = not manual_mode
            if not manual_mode:
                platform.move_direction(Direction.OUTER, stop_requester(False, None))
        elif status.button is ButtonPress.NONE:
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
