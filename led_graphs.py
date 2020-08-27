#!/usr/bin/env python3

import RPi.GPIO as GPIO
import time


def setup():
    GPIO.setmode(GPIO.BCM)        # use BCM GPIO Numbering


class LedBarGraphs(object):

    def __init__(self, data_pin, latch_pin, clock_pin,
            min_level=0, num_leds=8, max_level=8, num_graphs=2):
        self.data_pin = data_pin
        self.latch_pin = latch_pin
        self.clock_pin = clock_pin
        self.min_level = min_level
        self.num_leds = num_leds
        self.max_level = max_level
        self.num_graphs = num_graphs
        self.high_bit = 0x1 << (num_leds + 1)

        # Prepare the pin channels for output.
        GPIO.setup(data_pin, GPIO.OUT)
        GPIO.setup(latch_pin, GPIO.OUT)
        GPIO.setup(clock_pin, GPIO.OUT)

    # Set led values for one graph.
    def _set_graph_output(self, level):
        if level > self.max_level:
            level = self.max_level
        assert level <= self.num_leds, "TODO: implement scaling"
        if level < self.min_level:
            level = 0
        # Keep all leds on up to and not including the level.
        output_bits = [0]*(self.num_leds - level) + [1]*level
        for led_on in output_bits:
            GPIO.output(self.clock_pin, GPIO.LOW)   # Prepare shift register for input.
            GPIO.output(self.data_pin, GPIO.HIGH if led_on else GPIO.LOW) # Led bit sent on data wire.
            GPIO.output(self.clock_pin, GPIO.HIGH)  # Set led bit and shift to next register.
        GPIO.output(self.clock_pin, GPIO.LOW)       # Keep clock pin low.

    # Update the led graphs with a new set of levels.
    def set_levels(self, *levels):
        assert len(levels) == self.num_graphs, "call set_levels with one level per graph"
        GPIO.output(self.latch_pin, GPIO.LOW)   # Prepare the shift registers for input
        for level in levels:
            self._set_graph_output(level)
        GPIO.output(self.latch_pin, GPIO.HIGH)  # Latch the output to the latest register values.
        GPIO.output(self.latch_pin, GPIO.LOW)   # Keep latch pin low.


if __name__ == '__main__': # Program entrance
    print ('Running test program for led graphs...' )
    setup()
    try:
        graphs = LedBarGraphs(data_pin=26, latch_pin=19, clock_pin=13)
        graphs.set_levels(0, 8)
        time.sleep(.5)
        while True:
            for i in range(1, 9):
                graphs.set_levels(i, 8-i)
                time.sleep(.5)
            for i in range(1, 9):
                graphs.set_levels(8-i, i)
                time.sleep(.5)
    except KeyboardInterrupt:  # Press ctrl-c to end the program.
        graphs.set_levels(0, 0)
        GPIO.cleanup()
