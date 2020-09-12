import adafruit_tsl2561 # type: ignore
import adafruit_tca9548a # type: ignore
import board
import busio
import logging

from datetime import datetime
from numpy import mean

from common import Input, LuxReading
from adafruit_tca9548a import TCA9548A


class LightSensor(Input):
    """Read lux data from an inner and outer sensor."""

    # This is the i2c multiplexer used for the light sensors (to deal with address conflict).
    _mux = None

    def __init__(self, outer_pin: int, inner_pin: int, name: str="<default>") -> None:
        self.name = name
        self.outer_pin = outer_pin
        self.inner_pin = inner_pin
        self._outer_tsl = None
        self._inner_tsl = None

    def setup(self) -> None:
        # For each sensor, create it using the TCA9548A channel acting as an I2C object.
        # May throw a ValueError if it's not connected.
        if self._outer_tsl is None:
            assert self._inner_tsl is None, "partially initialized state"
            logging.info("Initializing {} light sensors with mux pins Outer: {}, Inner: {}".format(
                self.name, self.outer_pin, self.inner_pin))
            self._outer_tsl = adafruit_tsl2561.TSL2561(LightSensor.get_mux()[self.outer_pin])
            self._inner_tsl = adafruit_tsl2561.TSL2561(LightSensor.get_mux()[self.inner_pin])

    def off(self) -> None:
        # TODO: de-init tsl2561 or just handled by main?
        pass

    @classmethod
    def get_mux(cls) -> TCA9548A:
        if cls._mux is None:
            logging.info("Initializing i2c mux TCA9548A on SCL and SDA pins")
            # Create I2C bus as normal.
            i2c = busio.I2C(board.SCL, board.SDA)
            # Create the TCA9548A object and give it the I2C bus.
            cls._mux = adafruit_tca9548a.TCA9548A(i2c)
        return cls._mux

    # Get a tuple of the current luminosity reading.
    def read(self) -> LuxReading:
        assert self._outer_tsl and self._inner_tsl, "Must call setup before reading"

        outer = self._outer_tsl.infrared
        inner = self._inner_tsl.infrared
        timestamp = datetime.now()
        avg = int(mean((outer, inner)))
        diff = inner - outer
        diff_percent = int(diff/avg * 100) if avg else 0
        return LuxReading(outer, inner, avg, diff, diff_percent, timestamp, self.name)