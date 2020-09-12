#!/usr/bin/env python3

import board
import busio
import sys

from adafruit_ads1x15.ads1115 import ADS1115, Mode  # type: ignore
from adafruit_ads1x15.analog_in import AnalogIn  # type: ignore

from common import Input


class VoltageReader(Input):
    """A voltage reader which uses the ADS1115 ADC.

    Resistor values can be specified to calculate the source voltage
    assuming you have a voltage divider set up of Vs~r1~ADC~r2~GND.
    """

    def __init__(self, analog_pin: int = 0, r1: float = 0, r2: float = sys.maxsize):
        """Constructs the voltage reader with the given pin and resistances.

        analog_pin: [0, 4] corresponding to A0 through A4 on the ADC.
        r1: the resistance in kOhms of the first resistor in series.
        r2: the resistance in kOhms of the second resistor in series.
        """
        assert 0 <= analog_pin <= 4, "analog reader pin must be 0-4"
        self.analog_pin = analog_pin
        self._voltage_multipler = (r1 + r2) / r2
        self._chan = None

    def setup(self) -> None:
        if self._chan is None:
            i2c = busio.I2C(board.SCL, board.SDA)
            ads = ADS1115(i2c)
            ads.mode = Mode.CONTINUOUS
            self._chan = AnalogIn(ads, self.analog_pin)

    def off(self) -> None:
        pass

    def read(self) -> float:
        assert self._chan, "Must call setup before reading"
        return self._chan.voltage * self._voltage_multipler


if __name__ == '__main__':
    voltage_reader = VoltageReader(r1=100, r2=100)
    voltage_reader.setup()
    print(voltage_reader.read())
