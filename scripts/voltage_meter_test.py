#!/usr/bin/env python3

from plantmobile.input_device import VoltageMeter

if __name__ == '__main__':
    voltage_reader = VoltageMeter(r1=100, r2=100)
    voltage_reader.setup()
    print(voltage_reader.read())
    # GPIO cleanup handled by gpiozero.
