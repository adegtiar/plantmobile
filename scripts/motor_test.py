#!/usr/bin/env python3
import time
from typing import NoReturn

import board
import RPi.GPIO as GPIO

from plantmobile.output_device import LED, StepperMotor
from plantmobile.common import Rotation
from plantmobile.input_device import Button

STEPS_PER_MOVE = 7


def stepper_loop(motor: StepperMotor) -> NoReturn:
    while True:
        # rotating 360 deg clockwise, a total of 2048 steps in a circle, 512 cycles
        motor.move_steps(Rotation.CW, 512)
        time.sleep(0.5)
        motor.move_steps(Rotation.CCW, 512)  # rotating 360 deg anticlockwise
        time.sleep(0.5)


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
        MOTOR.off()
        # GPIO cleanup handled by gpiozero.
