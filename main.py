#!/usr/bin/python3

import logging
import RPi.GPIO as GPIO
import sys
import time
from typing import Callable, Iterable, List, NoReturn

from gpiozero import Button

from common import ButtonPress, Direction, Status
from led_outputs import LedBarGraphs, LedDirectionIndicator, LuxDiffDisplay, PositionDisplay
from light_sensors import LightSensorReader
from logger import LightCsvLogger, StatusPrinter
from motor import StepperMotor
from platform_driver import PlatformDriver
from ultrasonic_ranging import DistanceSensor

logging.basicConfig(level=logging.INFO)


MAIN_LOOP_SLEEP_SECS = 0.5

def setup(platforms: Iterable[PlatformDriver]) -> List[PlatformDriver]:
    # Use BCM GPIO numbering.
    GPIO.setmode(GPIO.BCM)

    # Initialize all platforms and return the ones that are failure-free.
    working_platforms = []
    for platform in platforms:
        try:
            platform.setup()
        except ValueError as e:
            # This might happen if the car is disconnected.
            logging.error(e)
            logging.warning(
                    "Failed to setup {} platform: may be disconnected.".format(platform.name))
        else:
            working_platforms.append(platform)
    return working_platforms


def cleanup(platforms: Iterable[PlatformDriver]) -> None:
    for platform in platforms:
        platform.off()
    # GPIO cleanup not needed when also using gpiozero
    #GPIO.cleanup()


def stop_requester(manual_mode: bool, manual_hold_button: ButtonPress) -> Callable[[Status], bool]:
    def stop_requested(status: Status) -> bool:
        if manual_mode:
            # Keep moving while the button is held down.
            return not (status.button is manual_hold_button)
        else:
            # Keep moving unless any button is pressed to cancel it.
            return not (status.button is ButtonPress.NONE)
    return stop_requested


def control_loop(platform: PlatformDriver) -> NoReturn:
    manual_mode = True

    while True:
        status = platform.get_status()
        platform.output_status(status)

        # Enable manual button->motor control.
        if platform.motor:
            if status.button is ButtonPress.OUTER:
                if not manual_mode:
                    platform.blink(times=2)
                platform.move_direction(
                        Direction.OUTER,
                        stop_requester(manual_mode, ButtonPress.OUTER))
            elif status.button is ButtonPress.INNER:
                if not manual_mode:
                    platform.blink(times=2)
                platform.move_direction(
                        Direction.INNER,
                        stop_requester(manual_mode, ButtonPress.INNER))
            elif status.button is ButtonPress.BOTH:
                # Toggle between manual mode and auto mode.
                platform.blink(times=3)
                manual_mode = not manual_mode
                if not manual_mode:
                    platform.move_direction(
                            Direction.OUTER,
                            stop_requested=lambda s: not (s.button is ButtonPress.NONE))
            elif status.button is ButtonPress.NONE:
                platform.motor.off()
            else:
                assert False, "unknown button press {}".format(status.button)

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
