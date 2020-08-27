#!/usr/bin/python3

import RPi.GPIO as GPIO
import time

from collections import namedtuple

from led_graphs import LedBarGraphs
from light_sensors import LightSensorReader
from logger import LightCsvLogger


LED_BAR_GRAPHS = LedBarGraphs(data_pin=26, latch_pin=19, clock_pin=13,
        min_level=100, max_level=20000)

CAR_SENSORS = LightSensorReader(outer_pin=2, inner_pin=6)
CAR_LOGGER = LightCsvLogger("data/car_sensor_log.csv")

BASE_SENSORS = LightSensorReader(outer_pin=1, inner_pin=7)
BASE_LOGGER = LightCsvLogger("data/base_sensor_log.csv")


def setup():
    GPIO.setmode(GPIO.BCM)        # use BCM GPIO Numbering


def destroy():
    LED_BAR_GRAPHS.reset()
    GPIO.cleanup()


def print_status(base_lux, car_lux):
    if car_lux:
        car_outer, car_inner, car_avg, car_diff, car_diff_percent, _ = car_lux
    else:
        car_outer, car_inner, car_avg, car_diff, car_diff_percent = ("N/A",) * 5
    print("sensor:\t\tCar\tBase")
    print("outer:\t\t{}\t{}".format(car_outer, base_lux.outer))
    print("inner:\t\t{}\t{}".format(car_inner, base_lux.inner))
    print("average:\t{}\t{}".format(car_avg, base_lux.avg))
    print("diff:\t\t{}\t{}".format(car_diff, base_lux.diff))
    print("diff percent:\t{}%\t{}%".format(car_diff_percent, base_lux.diff_percent))
    print()


def loop(base_sensors, car_sensors):
    base_sensors.initialize()
    try:
        car_sensors.initialize()
    except ValueError: # This might happen if the car is disconnected
        car_sensors = None

    while True:
        base_lux = base_sensors.read()
        car_lux = car_sensors.read() if car_sensors else None

        print_status(base_lux, car_lux)

        LED_BAR_GRAPHS.set_levels(base_lux.outer, base_lux.inner)
        BASE_LOGGER.log(base_lux)
        if car_sensors:
            CAR_LOGGER.log(car_lux)

        time.sleep(.5)


if __name__ == '__main__':
    try:
        loop(BASE_SENSORS, CAR_SENSORS)
    except KeyboardInterrupt:
        destroy()
        print("Stopped")
