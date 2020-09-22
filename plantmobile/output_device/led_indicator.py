from abc import abstractmethod
from typing import Optional
import logging

import gpiozero
import RPi.GPIO as GPIO
import tm1637   # type: ignore

from plantmobile.common import Output, Pin, Status
from plantmobile.input_device import ToggleButton


class LED(gpiozero.LED):
    def __init__(self, pin: Pin) -> None:
        super(LED, self).__init__(pin.id)


class LedIndicator(Output):
    # The minimum average lux at which it will output anything.
    # Used to keep the light off at night.
    MIN_OUTPUT_LUX = 10

    @abstractmethod
    def _output_status(self, status: Status) -> None:
        pass

    def output_status(self, status: Status) -> None:
        if status.lux.avg < LedIndicator.MIN_OUTPUT_LUX:
            self.off()
        else:
            self._output_status(status)


class ToggledLed(LedIndicator):

    def __init__(self, led: LED, button: ToggleButton):
        self._led = led
        button.add_press_handler(self.update)
        self._button = button

    def _output_status(self, status: Status) -> None:
        self.update()

    def off(self) -> None:
        self._led.off()

    def setup(self) -> None:
        pass

    def update(self) -> None:
        if self._button.enabled():
            self._led.on()
        else:
            self._led.off()


class DirectionalLeds(LedIndicator):

    def __init__(self, outer_led: LED, inner_led: LED, diff_percent_cutoff: int) -> None:
        self.outer_led = outer_led
        self.inner_led = inner_led
        self.diff_percent_cutoff = diff_percent_cutoff

    def setup(self) -> None:
        pass

    def on(self) -> None:
        self.outer_led.on()
        self.inner_led.on()

    def off(self) -> None:
        """Reset the LEDs to off."""
        self.outer_led.off()
        self.inner_led.off()

    def _output_status(self, status: Status) -> None:
        lux = status.lux
        # If one sensor is much brighter than the other, then light up the corresponding LED.
        if abs(lux.diff_percent) >= self.diff_percent_cutoff:
            if lux.outer > lux.inner:
                logging.debug("lighting outer led")
                self.outer_led.on()
                self.inner_led.off()
            else:
                assert lux.outer < lux.inner, "inconsistent lux reading"
                logging.debug("lighting inner led")
                self.inner_led.on()
                self.outer_led.off()
        else:
            self.inner_led.off()
            self.outer_led.off()


class DigitDisplay(LedIndicator):
    """A 7-digit display to show lux readings."""

    def __init__(self, clock_pin: Pin, data_pin: Pin, brightness: int = 4) -> None:
        self._display = tm1637.TM1637(clk=clock_pin.id, dio=data_pin.id)
        # The brightness of the display, from 0-7.
        self.brightness = brightness

    def setup(self) -> None:
        self._display.brightness(self.brightness)
        self.off()

    def _output_status(self, status: Status) -> None:
        """Displays the percent difference of the light reading."""
        self.output_number(self._get_number_output(status))

    @abstractmethod
    def _get_number_output(self, status: Status) -> Optional[int]:
        pass

    def off(self) -> None:
        """Reset the display to an empty state."""
        self._display.show("    ")

    def output_number(self, num: Optional[int]) -> None:
        if num is not None:
            self._display.number(num)
        else:
            self._display.show("    ")

    def show(self, output: str) -> None:
        assert len(output) == 4, "output must be 4 characters"
        self._display.show(output)


class LuxDiffDisplay(DigitDisplay):
    def _get_number_output(self, status: Status) -> int:
        return status.lux.diff_percent


class PositionDisplay(DigitDisplay):
    def _get_number_output(self, status: Status) -> Optional[int]:
        return status.position


class LedBarGraphs(LedIndicator):
    """
    Drives one or more Led Bar Graphs controller by shift register 74HC595.

    When configured with a min and max level different from the number of leds,
    scales the output between min and max accordingly.

    A level < min_level will light zero leds.
    A level >= min_level and < max_level will light between 1 and num_leds-1 leds.
    A level >= max_level will light all leds.
    """

    def __init__(self, data_pin: Pin, latch_pin: Pin, clock_pin: Pin, min_level: int = 0,
                 num_leds: int = 8, max_level: int = 8, num_graphs: int = 2) -> None:
        self.data_pin = data_pin.id
        self.latch_pin = latch_pin.id
        self.clock_pin = clock_pin.id
        # TODO: maybe get rid of min level?
        self.min_level = min_level
        self.num_leds = num_leds
        self.max_level = max_level
        self.num_graphs = num_graphs
        self.levels_per_led = (max_level - min_level) / (num_leds - 1)

    def setup(self) -> None:
        logging.info(
                "init {} graphs with {} leds, min {}, max {}, and {:.2f} levels per led".format(
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
    def _set_leds(self, led_level: int) -> None:
        assert led_level <= self.num_leds, \
                "led_level {} higher than num leds {}".format(led_level, self.num_leds)
        # Keep all leds on up to and not including the level.
        output_bits = [0]*(self.num_leds - led_level) + [1]*led_level
        for led_on in output_bits:
            # Prepare shift register for input.
            GPIO.output(self.clock_pin, GPIO.LOW)
            # Led bit sent on data wire.
            GPIO.output(self.data_pin, GPIO.HIGH if led_on else GPIO.LOW)
            # Set led bit and shift to next register.
            GPIO.output(self.clock_pin, GPIO.HIGH)
        # Keep clock pin low.
        GPIO.output(self.clock_pin, GPIO.LOW)

    def _get_leds_for_level(self, level: int) -> int:
        # Scale the level range to the led range.
        led_level = int((level - self.min_level) / self.levels_per_led + 1)
        # Clip the led_level between the min, max.
        return min(max(led_level, 0), self.num_leds)

    # Update the led graphs with a new set of levels.
    def set_levels(self, *levels: int) -> None:
        """Updates the bar graph with the levels specified, one per graph."""
        assert len(levels) == self.num_graphs, "call set_levels with one level per graph"
        GPIO.output(self.latch_pin, GPIO.LOW)   # Prepare the shift registers for input
        for i, level in enumerate(levels):
            led_level = self._get_leds_for_level(level)
            logging.debug("setting output of Graph{} to level {}/{} ({}/{} leds)".format(
                          i, level, self.max_level, led_level, self.num_leds))
            self._set_leds(led_level)
        GPIO.output(self.latch_pin, GPIO.HIGH)  # Latch the output to the latest register values.
        GPIO.output(self.latch_pin, GPIO.LOW)   # Keep latch pin low.

    def off(self) -> None:
        logging.debug("Resetting graphs to empty...")
        self.set_levels(*[0]*self.num_graphs)

    def _output_status(self, status: Status) -> None:
        self.set_levels(status.lux.inner, status.lux.outer)
