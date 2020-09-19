#!/usr/bin/env python3
import itertools
import time
from typing import NoReturn

import board
import RPi.GPIO as GPIO

from plantmobile.input_device import DistanceSensor


def loop(sensor: DistanceSensor) -> NoReturn:
    out_of_range = False
    for i in itertools.count():
        distance = sensor.read()
        if out_of_range or i % 1 == 0:
            print("The distance is : %.2f cm" % (distance))
        out_of_range = distance == float("inf")
        if out_of_range:
            out_of_range = True
            print("sensor is out of range")
        time.sleep(.1)
    assert False, "Not reached"


if __name__ == '__main__':
    # TODO: move this to a separate script
    print('Program is starting...')
    sensor = DistanceSensor(trig_pin=board.D4, echo_pin=board.D17, threshold_cm=10)
    sensor.setup()

    try:
        loop(sensor)
    except KeyboardInterrupt:
        sensor.off()
        GPIO.cleanup()
