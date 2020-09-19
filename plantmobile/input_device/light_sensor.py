import logging
from datetime import datetime
from typing import Optional

import adafruit_tsl2561  # type: ignore
import board
import busio
import numpy as np
from adafruit_tca9548a import TCA9548A  # type: ignore

from plantmobile.common import get_diff_percent, Input, LuxReading


DIFF_PERCENT_CUTOFF = 30


class TSL2561(adafruit_tsl2561.TSL2561):

    @property
    def chip_id(self):  # type: ignore
        partno, revno = super(TSL2561, self).chip_id
        if partno == 0x4:
            # This needs to be overridden for off-brand TSL2561 sensors like HiLetgo.
            logging.warning("Invalid partno 0x4 for TSL2561 chip. Passing fake partno into lib.")
            partno = 0x5
        return partno, revno


class LightSensor(Input):
    """Read lux data from an inner and outer sensor."""

    # This is the i2c multiplexer used for the light sensors (to deal with address conflict).
    _mux = None

    def __init__(self, outer_pin: int, inner_pin: int) -> None:
        """
        param outer_pin:
            The outer sensor pin on the i2c mux
        param inner_pin:
            The inner sense pin on the i2c mux
        """
        assert all(0 <= pin <= 7 for pin in (outer_pin, inner_pin)), "mux pin must be 0-7."
        self.outer_pin = outer_pin
        self.inner_pin = inner_pin
        self._outer_tsl: Optional[TSL2561] = None
        self._inner_tsl: Optional[TSL2561] = None

    def setup(self) -> None:
        # For each sensor, create it using the TCA9548A channel acting as an I2C object.
        # May throw a ValueError if it's not connected.
        if self._outer_tsl is None:
            assert self._inner_tsl is None, "partially initialized state"
            logging.info("Initializing light sensors with mux pins Outer: {}, Inner: {}".format(
                self.outer_pin, self.inner_pin))
            self._outer_tsl = TSL2561(LightSensor.get_mux()[self.outer_pin])
            self._inner_tsl = TSL2561(LightSensor.get_mux()[self.inner_pin])

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
            cls._mux = TCA9548A(i2c)
        return cls._mux

    # Get a tuple of the current luminosity reading.
    def read(self) -> LuxReading:
        assert self._outer_tsl and self._inner_tsl, "Must call setup before reading"

        outer = self._outer_tsl.infrared
        inner = self._inner_tsl.infrared
        timestamp = datetime.now()
        avg = int(np.mean((outer, inner)))
        diff = inner - outer
        diff_percent = get_diff_percent(outer, inner)
        return LuxReading(outer, inner, avg, diff, diff_percent, timestamp)
