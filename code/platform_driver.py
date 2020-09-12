import logging
import time

from enum import Enum
from typing import Any, Callable, Iterable, Optional, Union

from gpiozero import Button, TonalBuzzer

from common import ButtonPress, Component, Direction, Region, Output, Status
from led_outputs import DirectionalLeds, PositionDisplay
from light_sensors import LightSensor
from motor import StepperMotor
from ultrasonic_ranging import DistanceSensor
from power_monitor import VoltageReader

STEPS_PER_MOVE = 7
MOTOR_VOLTAGE_CUTOFF = 4.0
ERROR_TONE_HZ = 220


class PlatformDriver(Component):
    """The main driver for a single platform, wrapping up all sensors, actuators, and outputs."""

    def __init__(self,
            name: str,
            light_sensors: LightSensor,
            motor: Optional[StepperMotor] = None,
            distance_sensor: Optional[DistanceSensor] = None,
            direction_leds: Optional[DirectionalLeds] = None,
            outer_button: Optional[Button] = None,
            inner_button: Optional[Button] = None,
            outputs: Iterable[Output] = (),
            voltage_reader: Optional[VoltageReader] = None,
            buzzer: Optional[TonalBuzzer] = None,
        ) -> None:
        self.name = name
        self.light_sensors = light_sensors
        self.motor = motor
        self.voltage_reader = voltage_reader
        self.distance_sensor = distance_sensor
        self.outer_button = outer_button
        self.inner_button = inner_button
        self.outputs = list(outputs)
        self.buzzer = buzzer
        self._position_display = None

        self._direction_leds = direction_leds
        if direction_leds:
            self.outputs.append(direction_leds)

        for output in outputs:
            if isinstance(output, PositionDisplay):
                self._position_display = output
                break
        self.position: Optional[int] = None

    def setup(self) -> None:
        """Initialize all components of the platform.

        This sets up connections and initializes default state. Any obvious failures in the hardware
        should trigger here.
        """
        # Set up the light sensors for reading.
        self.light_sensors.name = self.name
        self.light_sensors.setup()
        if self.voltage_reader:
            self.voltage_reader.setup()
        if self.distance_sensor:
            self.distance_sensor.setup()
        if self.motor:
            self.motor.setup()
        for output in self.outputs:
            output.setup()

    def off(self) -> None:
        """Cleans up and resets any local state and outputs."""
        for output in self.outputs:
            output.off()
        if self.motor:
            self.motor.off()

    def get_status(self, force_edge_check: bool = False) -> Status:
        """Reads the current lux, button, position, and edge from sensors and state.

        force_edge_check: whether to check the distance sensor to verify the edge position.
        """
        return Status(
                lux=self.light_sensors.read(),
                motor_voltage=self.voltage_reader.read() if self.voltage_reader else None,
                button=self.get_button_pressed(),
                position=self.position,
                region=self.get_region(force_edge_check))

    def output_status(self, status: Status) -> None:
        """Updates the indicators and logs with the given status."""
        for output in self.outputs:
            output.output_status(status)

    def get_button_pressed(self) -> ButtonPress:
        """Gets the current button press status."""
        return ButtonPress.from_buttons(
                outer_pressed=bool(self.outer_button and self.outer_button.is_pressed),
                inner_pressed=bool(self.inner_button and self.inner_button.is_pressed))

    def get_region(self, force_edge_check: bool = False) -> Region:
        """Get the region of the table in which the platform is located.

        Note: upon intialization when the position is unknown, we might report
        being in MID while we're actually at the inner edge.
        """
        assert self.distance_sensor, "distance sensor must be configured"

        if self.position == Region.INNER_EDGE.value:
            return Region.INNER_EDGE

        at_outer_edge = self.position is Region.OUTER_EDGE.value
        if self.position is None or force_edge_check:
            at_outer_edge = not self.distance_sensor.is_in_range()
            if at_outer_edge:
                logging.info("At outer edge. Setting position to zero.")
                self._reset_pos_to_outer_edge()
        return Region.OUTER_EDGE if at_outer_edge else Region.MID

    def _reset_pos_to_outer_edge(self) -> None:
        """Reset the current internal position to be 0, i.e. the OUTER_EDGE."""
        if self.position is None:
            logging.info("Initializing edge position to {}".format(Region.OUTER_EDGE))
        elif self.position != Region.OUTER_EDGE.value:
            log = logging.info if abs(self.position) < 10 else logging.warning
            log("Resetting outer edge position (drift: {})".format( self.position))
        self.position = Region.OUTER_EDGE.value

        if self._position_display:
            self._position_display.output_number(self.position)

    def _voltage_low(self, status):
        """Returns whether the motor voltage is too low to actuate."""
        return status.motor_voltage is not None and status.motor_voltage < MOTOR_VOLTAGE_CUTOFF

    def move_direction(self,
            direction: Direction, stop_requested: Callable[[Status], bool]) -> None:
        assert self.motor, "motor must be configured"

        logging.info("starting sequence move towards %s", direction)
        stop_fmt = "stopping sequence move towards {}: %s (%d steps)".format(direction)

        # Move at most the region size, with a small error buffer to bias towards the outer edge.
        max_distance = int(Region.size() * 1.1)

        for steps in range(max_distance+1):
            # When moving towards the outer edge, cross-check with the sensor in case we've drifted.
            status = self.get_status(force_edge_check=direction is Direction.OUTER)
            self.output_status(status)

            if self._voltage_low(status):
                logging.error(stop_fmt, "insufficient voltage", steps)
                self.output_error("baTT")
                return
            elif stop_requested(status):
                logging.info(stop_fmt, "stopped", steps)
                return
            elif status.region is direction.extreme_edge:
                logging.info(stop_fmt, "at edge", steps)
                return
            elif steps == max_distance:
                # Terminate with an explicit check to run edge check first.
                logging.warning(stop_fmt, "travelled max distance without reaching edge", steps)
                return
            else:
                self.motor.move_steps(direction.motor_rotation, STEPS_PER_MOVE)
                # Update the internal position, if it's already been intialized.
                if self.position is not None:
                    self.position += direction.value
                if self._position_display:
                    self._position_display.output_number(self.position)
        assert False, "should terminate within the loop"

    def _blink(self, on: Callable, off: Callable,
            times: int, on_secs: float, off_secs: float) -> None:
        for i in range(times):
            on()
            time.sleep(on_secs)
            off()
            if i != times-1:
                time.sleep(off_secs)

    def output_error(self, output: str, times: int = 1,
            on_secs: float = 1, off_secs: float = 0.5) -> None:
        assert self._position_display and self.buzzer, \
                "position display and buzzer must be configured"
        def on():
            self._position_display.show(output)
            self.buzzer.play(ERROR_TONE_HZ)
        def off():
            self._position_display.off()
            self.buzzer.stop()
        self._blink(on, off, times=1, on_secs=1, off_secs=0.5)

    def blink(self, times: int = 2, pause_secs: float = 0.2) -> None:
        assert self._direction_leds, "LEDs must be configured"
        def on():
            self._direction_leds.on()
            if self.motor:
                self.motor.all_on()
        def off():
            self._direction_leds.off()
            if self.motor:
                self.motor.off()
        self._blink(on, off, times=2, on_secs=0.2, off_secs=0.2)
