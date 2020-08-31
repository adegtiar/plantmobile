# This example shows using two TSL2491 light sensors attached to TCA9548A channels 0 and 1.
# Use with other I2C sensors would be similar.
import adafruit_tsl2561
import adafruit_tca9548a
import board
import busio
import logging

from collections import namedtuple
from datetime import datetime
from numpy import mean


# A reading of light sensor data.
SensorReading = namedtuple('SensorReading',
        ['outer', 'inner', 'avg', 'diff', 'diff_percent', 'timestamp', 'name'])


# Read lux data from a pair of sensors connected to multiplexer.
class LightSensorReader(object):
    # This is the i2c multiplexer used for the light sensors (to deal with address conflict).
    _mux = None

    def __init__(self, outer_pin, inner_pin, name="<default>"):
        self.name = name
        self.outer_pin = outer_pin
        self.inner_pin = inner_pin
        self._outer_tsl = None
        self._inner_tsl = None

    def initialize(self):
        # For each sensor, create it using the TCA9548A channel acting as an I2C object.
        # May throw a ValueError if it's not connected.
        if self._outer_tsl is None:
            assert self._inner_tsl is None, "partially initialized state"
            logging.info("Initializing {} light sensors with mux pins Outer: {}, Inner: {}".format(
                self.name, self.outer_pin, self.inner_pin))
            self._outer_tsl = adafruit_tsl2561.TSL2561(LightSensorReader.get_mux()[self.outer_pin])
            self._inner_tsl = adafruit_tsl2561.TSL2561(LightSensorReader.get_mux()[self.inner_pin])

    @classmethod
    def get_mux(cls):
        if cls._mux is None:
            logging.info("Initializing i2c mux TCA9548A on SCL and SDA pins")
            # Create I2C bus as normal.
            i2c = busio.I2C(board.SCL, board.SDA)
            # Create the TCA9548A object and give it the I2C bus.
            cls._mux = adafruit_tca9548a.TCA9548A(i2c)
        return cls._mux

    # Get a tuple of the current luminosity reading.
    def read(self):
        self.initialize()

        outer = self._outer_tsl.infrared
        inner = self._inner_tsl.infrared
        timestamp = datetime.now()
        avg = int(mean((outer, inner)))
        diff = outer - inner
        diff_percent = int(diff/avg * 100) if avg else 0
        return SensorReading(outer, inner, avg, diff, diff_percent, timestamp, self.name)
