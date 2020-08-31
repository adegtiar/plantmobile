#!/usr/bin/env python3

import logging
import RPi.GPIO as GPIO
import time

import tm1637

def setup():
    GPIO.setmode(GPIO.BCM)        # use BCM GPIO Numbering


class DigitDisplay(object):
    """A 7-digit display to show lux readings."""

    def __init__(self, clock_pin, data_pin, min_output_light=-1, brightness=2):
        self._display=tm1637.TM1637(clk=clock_pin, dio=data_pin)
        # The minumum light intensity at which the graphs will update.
        # Used to keep the light off at night.
        self.min_output_light = min_output_light
        # The brightness of the display, from 0-7
        self.brightness=brightness

    def setup(self):
        self._display.brightness(self.brightness)
        self.reset()

    def update_diff(self, lux):
        """Displays the percent difference of the light reading."""
        if lux.avg >= self.min_output_light:
            self._display.number(lux.diff_percent)
        else:
            self.reset()

    def reset(self):
        """Reset the display to an empty state."""
        self._display.show("    ")


class LedBarGraphs(object):
    """
    Drives one or more Led Bar Graphs controller by shift register 74HC595.

    When configured with a min and max level different from the number of leds,
    scales the output between min and max accordingly.

    A level < min_level will light zero leds.
    A level >= min_level and < max_level will light between 1 and num_leds-1 leds.
    A level >= max_level will light all leds.
    """

    def __init__(self, data_pin, latch_pin, clock_pin,
            min_level=0, num_leds=8, max_level=8, num_graphs=2):
        self.data_pin = data_pin
        self.latch_pin = latch_pin
        self.clock_pin = clock_pin
        self.min_level = min_level
        self.num_leds = num_leds
        self.max_level = max_level
        self.num_graphs = num_graphs
        self.levels_per_led = (max_level - min_level) / (num_leds - 1)

    def setup(self):
        logging.info(
                "initializing {} graphs with {} leds, min {}, max {}, and {} levels per led".format(
                    self.num_graphs, self.num_leds, self.min_level,
                    self.max_level, self.levels_per_led))

        # Prepare the pin channels for output.
        GPIO.setup(self.data_pin, GPIO.OUT)
        GPIO.setup(self.latch_pin, GPIO.OUT)
        GPIO.setup(self.clock_pin, GPIO.OUT)
        # Initialize output to nothing. This resets the graph in case it was
        # partially set and validates that the basic IO is working.
        self.set_levels(*[0]*self.num_graphs)

    # Set led values for one graph.
    def _set_leds(self, led_level):
        assert led_level <= self.num_leds, \
                "led_level {} higher than num leds {}".format(led_level, self.num_leds)
        # Keep all leds on up to and not including the level.
        output_bits = [0]*(self.num_leds - led_level) + [1]*led_level
        for led_on in output_bits:
            GPIO.output(self.clock_pin, GPIO.LOW)   # Prepare shift register for input.
            GPIO.output(self.data_pin, GPIO.HIGH if led_on else GPIO.LOW) # Led bit sent on data wire.
            GPIO.output(self.clock_pin, GPIO.HIGH)  # Set led bit and shift to next register.
        GPIO.output(self.clock_pin, GPIO.LOW)       # Keep clock pin low.

    def _get_leds_for_level(self, level):
        # Scale the level range to the led range.
        led_level = int((level - self.min_level) / self.levels_per_led + 1)
        # Clip the led_level between the min, max.
        return min(max(led_level, 0), self.num_leds)

    # Update the led graphs with a new set of levels.
    def set_levels(self, *levels):
        """Updates the bar graph with the levels specified, one per graph."""
        assert len(levels) == self.num_graphs, "call set_levels with one level per graph"
        GPIO.output(self.latch_pin, GPIO.LOW)   # Prepare the shift registers for input
        for i, level in enumerate(levels):
            led_level = self._get_leds_for_level(level)
            logging.debug("setting output of Graph {} to level {} ({} leds)".format(i, level, led_level))
            self._set_leds(led_level)
        logging.debug("latching output to update graphs")
        GPIO.output(self.latch_pin, GPIO.HIGH)  # Latch the output to the latest register values.
        GPIO.output(self.latch_pin, GPIO.LOW)   # Keep latch pin low.

    def reset(self):
        logging.info("Resetting graphs to empty...")
        self.set_levels(*[0]*self.num_graphs)


if __name__ == '__main__': # Program entrance
    logging.basicConfig(level=logging.DEBUG)
    logging.info('Running test program for led graphs...')
    setup()
    try:
        max_level=16
        graphs = LedBarGraphs(
                data_pin=26, latch_pin=19, clock_pin=13, min_level=8, max_level=max_level)
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
        graphs.reset()
        GPIO.cleanup()
