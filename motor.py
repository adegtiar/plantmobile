#!/usr/bin/env python3

import RPi.GPIO as GPIO
import time

from enum import Enum
from gpiozero import LED, Button

from common import Component, Rotation


CCW_STEPS = (0, 1, 2, 3) # define power supply order for rotating anticlockwise
CW_STEPS = (3, 2, 1, 0)  # define power supply order for rotating clockwise
MIN_PAUSE_SECS = 0.003


class StepperMotor(Component):
    """The stepper motor moves in discrete steps and so can be used to track rotations."""

    def __init__(self, pin1, pin2, pin3, pin4, pause_secs=MIN_PAUSE_SECS):
        self.pins = (pin1, pin2, pin3, pin4)
        self.pause_secs = max(pause_secs, MIN_PAUSE_SECS)

    def setup(self):
        for pin in self.pins:
            GPIO.setup(pin, GPIO.OUT)

    def off(self):
        """Reset the motor to stopped."""
        for pin in self.pins:
            GPIO.output(pin, GPIO.LOW)

    def all_on(self):
        """Set all the outputs of the motor to high. Only useful for lights."""
        for pin in self.pins:
            GPIO.output(pin, GPIO.HIGH)

    def move_step(self, direction):
        """Rotate the motor one period.

        Note: this is technically 4 steps for convenience of implementation."""
        if direction == Rotation.CCW:
            steps = CCW_STEPS
        else:
            steps = CW_STEPS

        for step_idx in steps:
            for pin_idx, pin in enumerate(self.pins):
                # When the step index matches the pin index, make it high. Make all others low.
                GPIO.output(pin, GPIO.HIGH if step_idx == pin_idx else GPIO.LOW)
            # Pause just enough to max the rotation speed.
            time.sleep(self.pause_secs)

    # continuous rotation function, the parameter steps specifies the rotation cycles, every four steps is a cycle
    def move_steps(self, direction, steps):
        for i in range(steps):
            self.move_step(direction)


def loop(motor):
    while True:
        motor.move_steps(1,750)  # rotating 360 deg clockwise, a total of 2048 steps in a circle, 512 cycles (+1/4)
        time.sleep(0.5)
        motor.move_steps(0,750)  # rotating 360 deg anticlockwise (+1/4)
        time.sleep(0.5)


def control_loop(motor, blue_button, blue_led, red_button, red_led):
    while True:
        if blue_button.is_pressed:
            blue_led.on()
            red_led.off()
            motor.move_step(Rotation.CW)
        elif red_button.is_pressed:
            red_led.on()
            blue_led.off()
            motor.move_step(Rotation.CCW)
        else:
            red_led.off()
            blue_led.off()
            motor.off()


if __name__ == '__main__':     # Program entrance
    print('Program is starting...')
    print('BLUE button towards outer, RED towards inner')
    GPIO.setmode(GPIO.BCM)       # use BCM GPIO Numbering
    MOTOR = StepperMotor(27, 22, 10, 9)    # define pins connected to four phase ABCD of stepper motor
    MOTOR.setup()

    try:
       control_loop(
               motor=MOTOR, blue_button=Button(21), blue_led=LED(20),
               red_button=Button(16), red_led=LED(12))
    except KeyboardInterrupt:  # Press ctrl-c to end the program.
        pass
