#!/usr/bin/env python3

import logging
import sys
import time
from typing import Callable, Iterable, List, NoReturn

import board
import RPi.GPIO as GPIO

from plantmobile.common import ButtonPress, Direction, Status
from plantmobile.logger import LightCsvLogger, StatusPrinter
from plantmobile.input_device import Button, DistanceSensor, LightSensor, VoltageReader
from plantmobile.output_device import (
        TonalBuzzer, DirectionalLeds, PositionDisplay, StepperMotor, LedBarGraphs, LuxDiffDisplay
)
from plantmobile.platform_driver import PlatformDriver

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
            logging.exception(e)
            logging.warning(
                    "Failed to setup {} platform: may be disconnected.".format(platform.name))
        else:
            working_platforms.append(platform)
    return working_platforms


def cleanup(platforms: Iterable[PlatformDriver]) -> None:
    for platform in platforms:
        platform.off()
    # GPIO cleanup handled by gpiozero.
    # GPIO.cleanup()


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
            light_sensors=LightSensor(outer_pin=2, inner_pin=3),
            motor=StepperMotor(board.D27, board.D22, board.MOSI, board.MISO),
            distance_sensor=DistanceSensor(
                trig_pin=board.D4, echo_pin=board.D17, threshold_cm=10, timeout=0.05),
            outer_button=Button(board.D21),
            inner_button=Button(board.D16),
            direction_leds=DirectionalLeds(outer_led_pin=board.D20, inner_led_pin=board.D12),
            voltage_reader=VoltageReader(analog_pin=0, r1=100, r2=100),
            buzzer=TonalBuzzer(board.D18),
            outputs=[
                LightCsvLogger("data/car_sensor_log.csv"),
                LedBarGraphs(
                    data_pin=board.D23, latch_pin=board.D24, clock_pin=board.D25,
                    min_level=500, max_level=30000),
                LuxDiffDisplay(clock_pin=board.D6, data_pin=board.D13),
                PositionDisplay(clock_pin=board.D19, data_pin=board.D26),
                StatusPrinter(print_interval=MAIN_LOOP_SLEEP_SECS),
            ])

    DC_CAR = PlatformDriver(
            name="DC",
            light_sensors=LightSensor(outer_pin=1, inner_pin=0),
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
