#!/usr/bin/env python3

import time
from typing import NoReturn

import RPi.GPIO as GPIO
import board
from RpiMotorLib import RpiMotorLib  # type: ignore

from plantmobile.common import Component, Pin, Rotation
from plantmobile.input_device import Button
from plantmobile.output_device import LED

PAUSE_SECS = 0.001
STEP_TYPE = "half"


class StepperMotor(Component):
    """The stepper motor moves in discrete steps and so can be used to track rotations."""

    def __init__(self, pin1: Pin, pin2: Pin, pin3: Pin, pin4: Pin) -> None:
        self.pins = [pin.id for pin in (pin1, pin2, pin3, pin4)]
        self._motor = RpiMotorLib.BYJMotor("Stepper", "28BYJ")

    def setup(self) -> None:
        for pin in self.pins:
            GPIO.setup(pin, GPIO.OUT)

    def off(self) -> None:
        """Reset the motor to stopped."""
        for pin in self.pins:
            GPIO.output(pin, GPIO.LOW)

    def all_on(self) -> None:
        """Set all the outputs of the motor to high. Only useful for lights.

        Warning: this drains a fair bit of current so use sparingly.
        """
        for pin in self.pins:
            GPIO.output(pin, GPIO.HIGH)

    def move_steps(self, rotation: Rotation, steps: int = 1) -> None:
        """Rotate the motor one period.

        Note: this is technically 4 steps for convenience of implementation."""
        self._motor.motor_run(
                self.pins, wait=PAUSE_SECS, steps=steps,
                ccwise=rotation is Rotation.CCW, steptype=STEP_TYPE)


def loop(motor: StepperMotor) -> NoReturn:
    while True:
        # rotating 360 deg clockwise, a total of 2048 steps in a circle, 512 cycles
        motor.move_steps(Rotation.CW, 512)
        time.sleep(0.5)
        motor.move_steps(Rotation.CCW, 512)  # rotating 360 deg anticlockwise
        time.sleep(0.5)


STEPS_PER_MOVE = 7


def control_loop(
        motor: StepperMotor, blue_button: Button, blue_led: LED,
        red_button: Button, red_led: LED) -> NoReturn:
    position = 0
    while True:
        if red_button.is_pressed and blue_button.is_pressed:
            print("position is", position)
            time.sleep(1)
            position = 0
        elif blue_button.is_pressed:
            blue_led.on()
            red_led.off()
            motor.move_steps(Rotation.CCW, STEPS_PER_MOVE)
            position -= 1
        elif red_button.is_pressed:
            red_led.on()
            blue_led.off()
            motor.move_steps(Rotation.CW, STEPS_PER_MOVE)
            position += 1
        else:
            red_led.off()
            blue_led.off()
            motor.off()


if __name__ == '__main__':
    print('Program is starting...')
    print('BLUE button towards outer, RED towards inner')
    GPIO.setmode(GPIO.BCM)
    MOTOR = StepperMotor(board.D27, board.D22, board.MOSI, board.MISO)
    MOTOR.setup()

    try:
        control_loop(
               motor=MOTOR, blue_button=Button(board.D21), blue_led=LED(board.D20),
               red_button=Button(board.D16), red_led=LED(board.D12))
    except KeyboardInterrupt:  # Press ctrl-c to end the program.
        pass
