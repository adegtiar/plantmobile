#!/usr/bin/python3

import time

from collections import namedtuple
from light_sensors import LightSensorReader
from logger import LightCsvLogger


CAR_SENSORS = LightSensorReader(outer_pin=2, inner_pin=6)
CAR_LOGGER = LightCsvLogger("data/car_sensor_log.csv")

BASE_SENSORS = LightSensorReader(outer_pin=1, inner_pin=7)
BASE_LOGGER = LightCsvLogger("data/base_sensor_log.csv")


try:
    while True:
        car_lux = CAR_SENSORS.read()
        base_lux = BASE_SENSORS.read()
        print("sensor:\t\tCar\tBase")
        print("outer:\t\t{}\t{}".format(car_lux.outer, base_lux.outer))
        print("inner:\t\t{}\t{}".format(car_lux.inner, base_lux.inner))
        print("average:\t{}\t{}".format(car_lux.avg, base_lux.avg))
        print("diff:\t\t{}\t{}".format(car_lux.diff, base_lux.diff))
        print("diff percent:\t{}%\t{}%".format(car_lux.diff_percent, base_lux.diff_percent))
        print()
        CAR_LOGGER.log(car_lux)
        BASE_LOGGER.log(base_lux)
        time.sleep(.5)
except KeyboardInterrupt:
    print("Stopped")
