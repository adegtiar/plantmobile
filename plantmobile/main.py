#!/usr/bin/env python3

import logging
import sys
from typing import Iterable, List

import board
import RPi.GPIO as GPIO

from plantmobile.controller import (
        BatteryKeepAlive, ButtonHandler, control_loop, ShadowAvoider,
)
from plantmobile.debug_panel import DebugPanel
from plantmobile.logger import LightCsvLogger, StatusPrinter
from plantmobile.input_device import Button, DistanceSensor, LightSensor, ToggleButton
from plantmobile.motor import StepperMotor
from plantmobile.output_device import (
        DirectionalLeds,
        LED,
        LedBarGraphs,
        LuxDiffDisplay,
        PositionDisplay,
        ToggledLed,
        TonalBuzzer,
)
from plantmobile.platform_driver import MobilePlatform

# How different one sensor has to be from the average to trigger a move.
DIFF_PERCENT_CUTOFF = 30
# How often the status is printer to stdout.
PRINT_INTERVAL_SECS = 2.5
# How often to ping the battery with some current to keep it alive.
PING_INTERVAL_SECS = 85
# How long to trigger the battery with current during a keepalive ping.
PING_DURATION_SECS = 0.5
# Whether to ping the battery periodically to keep it active.
ENABLE_BATTERY_KEEP_ALIVE = False


def setup(debug_panel: DebugPanel, platforms: Iterable[MobilePlatform]) -> List[MobilePlatform]:
    # Use BCM GPIO numbering.
    GPIO.setmode(GPIO.BCM)
    debug_panel.setup()

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


def cleanup(platforms: Iterable[MobilePlatform]) -> None:
    for platform in platforms:
        platform.off()
    # GPIO cleanup handled by gpiozero.
    # GPIO.cleanup()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    STATUS_PRINTER = StatusPrinter(print_interval=PRINT_INTERVAL_SECS)

    STEPPER_CAR = MobilePlatform(
            name="StepperMobile",
            light_sensors=LightSensor(outer_pin=2, inner_pin=3),
            motor=StepperMotor(board.D27, board.D22, board.MOSI, board.MISO),
            distance_sensor=DistanceSensor(
                trig_pin=board.D4, echo_pin=board.D17, threshold_cm=10, timeout=0.05),
    )

    ENABLE_AUTO_BUTTON = ToggleButton(board.CE1)
    ENABLE_AUTO_LED = ToggledLed(LED(board.CE0), ENABLE_AUTO_BUTTON)
    ENABLE_AUTO_BUTTON.toggle(enabled=True)

    DEBUG_PANEL = DebugPanel(
            DirectionalLeds(LED(board.D20), LED(board.D12), DIFF_PERCENT_CUTOFF),
            LightCsvLogger("data/car_sensor_log.csv"),
            LedBarGraphs(
                data_pin=board.D23, latch_pin=board.D24, clock_pin=board.D25,
                min_level=500, max_level=30000),
            LuxDiffDisplay(clock_pin=board.D6, data_pin=board.D13),
            PositionDisplay(clock_pin=board.D19, data_pin=board.D26),
            ENABLE_AUTO_LED,
            buzzer=TonalBuzzer(board.D18),
    )

    button_handler = ButtonHandler(
        STEPPER_CAR, DEBUG_PANEL, STATUS_PRINTER,
        outer_button=Button(board.D21), inner_button=Button(board.D16))
    shadow_avoider = ShadowAvoider(
        STEPPER_CAR, DEBUG_PANEL, STATUS_PRINTER, ENABLE_AUTO_BUTTON, DIFF_PERCENT_CUTOFF)
    CONTROLLERS = [button_handler, shadow_avoider]
    if ENABLE_BATTERY_KEEP_ALIVE:
        keep_alive = BatteryKeepAlive(
                STEPPER_CAR, PING_INTERVAL_SECS, PING_DURATION_SECS, ENABLE_AUTO_BUTTON.enabled)
        CONTROLLERS.insert(0, keep_alive)

    # DC_CAR = MobilePlatform(
    #         name="DC",
    #         light_sensors=LightSensor(outer_pin=1, inner_pin=0),
    #         outputs=[
    #             LightCsvLogger("data/base_sensor_log.csv"),
    #         ])

    working_platforms = setup(DEBUG_PANEL, [STEPPER_CAR])
    if not working_platforms:
        print("No working platforms to run. Exiting.")
        sys.exit(1)
    try:
        control_loop(working_platforms[0], DEBUG_PANEL, STATUS_PRINTER, CONTROLLERS)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        cleanup(working_platforms)
