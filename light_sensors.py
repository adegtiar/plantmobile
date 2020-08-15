#!/usr/bin/python3

# This example shows using two TSL2491 light sensors attached to TCA9548A channels 0 and 1.
# Use with other I2C sensors would be similar.
import adafruit_tsl2561
import adafruit_tca9548a
import board
import busio
import time

from collections import namedtuple
from numpy import mean

CLOSER_SENSOR = 7
FURTHER_SENSOR = 2

# Create I2C bus as normal
i2c = busio.I2C(board.SCL, board.SDA)

# Create the TCA9548A object and give it the I2C bus
# This is the i2c multiplexer used for the light sensors with duplicate addresses.
tca = adafruit_tca9548a.TCA9548A(i2c)

# For each sensor, create it using the TCA9548A channel instead of the I2C object.
outer_tsl = adafruit_tsl2561.TSL2561(tca[FURTHER_SENSOR])
inner_tsl = adafruit_tsl2561.TSL2561(tca[CLOSER_SENSOR])

LightData = namedtuple('LuxData', ['outer', 'inner', 'avg', 'diff', 'diff_percent'])


# Get a tuple of the current luminosity reading.
def read_light_data():
    outer, inner = outer_tsl.infrared, inner_tsl.infrared
    avg = int(mean((outer, inner)))
    diff = outer - inner
    diff_percent = int(diff/avg * 100) if avg else 0
    return LightData(outer, inner, avg, diff, diff_percent)


try:
    while True:
        lux = read_light_data()
        print("outer sensor:\t", lux.outer)
        print("inner sensor:\t", lux.inner)
        print("average     :\t", lux.avg)
        print("diff        :\t", lux.diff)
        print("diff percent:\t {}%".format(lux.diff_percent))
        print()
        time.sleep(.5)
except KeyboardInterrupt:
    print("Stopped")
