#!/usr/bin/env python3
import logging
import time

import board
import RPi.GPIO as GPIO

from plantmobile.output_device import LedBarGraphs


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logging.info('Running test program for led graphs...')
    try:
        max_level = 16
        graphs = LedBarGraphs(
                data_pin=board.D23, latch_pin=board.D24, clock_pin=board.D25,
                min_level=8, max_level=max_level)
        graphs.setup()
        while True:
            for i in range(0, max_level+2):
                logging.info("setting level to ({}, {})".format(i, max_level-i))
                graphs.set_levels(i, max_level-i)
                time.sleep(.5)
            for i in range(0, max_level+2):
                logging.info("Setting level to ({}, {})".format(max_level-i, i))
                graphs.set_levels(max_level-i, i)
                time.sleep(.5)
    except KeyboardInterrupt:  # Press ctrl-c to end the program.
        graphs.off()
        GPIO.cleanup()
