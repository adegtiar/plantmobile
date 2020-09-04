#!/usr/bin/env python3
########################################################################
# Filename    : SteppingMotor.py
# Description : Drive SteppingMotor
# Author      : www.freenove.com
# modification: 2019/12/27
########################################################################
import RPi.GPIO as GPIO
import time

from gpiozero import LED, Button

motorPins = (25, 24, 8, 7)    # define pins connected to four phase ABCD of stepper motor
CCWStep = (0x01,0x02,0x04,0x08) # define power supply order for rotating anticlockwise
CWStep = (0x08,0x04,0x02,0x01)  # define power supply order for rotating clockwise

def setup():
    GPIO.setmode(GPIO.BCM)       # use BCM GPIO Numbering
    for pin in motorPins:
        GPIO.setup(pin,GPIO.OUT)

# as for four phase stepping motor, four steps is a cycle. the function is used to drive the stepping motor clockwise or anticlockwise to take four steps
def moveOnePeriod(direction,ms):
    for j in range(0,4,1):      # cycle for power supply order
        for i in range(0,4,1):  # assign to each pin
            if (direction == 1):# power supply order clockwise
                GPIO.output(motorPins[i],((CCWStep[j] == 1<<i) and GPIO.HIGH or GPIO.LOW))
            else :              # power supply order anticlockwise
                GPIO.output(motorPins[i],((CWStep[j] == 1<<i) and GPIO.HIGH or GPIO.LOW))
        if(ms<3):       # the delay can not be less than 3ms, otherwise it will exceed speed limit of the motor
            ms = 3
        time.sleep(ms*0.001)

# continuous rotation function, the parameter steps specifies the rotation cycles, every four steps is a cycle
def moveSteps(direction, ms, steps):
    for i in range(steps):
        moveOnePeriod(direction, ms)

# function used to stop motor
def motorStop():
    for i in range(0,4,1):
        GPIO.output(motorPins[i],GPIO.LOW)

def loop():
    while True:
        moveSteps(1,3,750)  # rotating 360 deg clockwise, a total of 2048 steps in a circle, 512 cycles (+1/4)
        time.sleep(0.5)
        moveSteps(0,3,750)  # rotating 360 deg anticlockwise (+1/4)
        time.sleep(0.5)

blue_led = LED(20)
blue_button = Button(21)

yellow_led = LED(12)
yellow_button = Button(16)

def control_loop():
    while True:
        if blue_button.is_pressed:
            blue_led.on()
            moveOnePeriod(1, 3)
        else:
            blue_led.off()
        if yellow_button.is_pressed:
            yellow_led.on()
            moveOnePeriod(0, 3)
        else:
            yellow_led.off()

def destroy():
    GPIO.cleanup()             # Release resource

if __name__ == '__main__':     # Program entrance
    print('Program is starting...')
    print('BLUE button towards inner, YELLOW towards outer')
    setup()
    try:
       control_loop()
    except KeyboardInterrupt:  # Press ctrl-c to end the program.
        pass
    finally:
        destroy()



