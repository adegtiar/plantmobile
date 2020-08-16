#!/usr/bin/python3

import time

from light_sensors import read_light_data
from logger import LightCsvLogger

LOG_FILENAME = "data/sensor_log.csv"

logger = LightCsvLogger(LOG_FILENAME)

try:
    while True:
        lux = read_light_data()
        print("outer sensor:\t", lux.outer)
        print("inner sensor:\t", lux.inner)
        print("average     :\t", lux.avg)
        print("diff        :\t", lux.diff)
        print("diff percent:\t {}%".format(lux.diff_percent))
        print()
        logger.log(lux)
        time.sleep(.5)
except KeyboardInterrupt:
    print("Stopped")
