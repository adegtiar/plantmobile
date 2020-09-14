import logging
from typing import Callable, Optional

from plantmobile.common import Component, Direction, Region, Status
from plantmobile.input_device import DistanceSensor, LightSensor, VoltageReader
from plantmobile.output_device import StepperMotor

# Number of steps in a single movement unit between sensor checks.
STEPS_PER_MOVE = 7
# A voltage reading below this will abort motor movement and display an error.
MOTOR_VOLTAGE_CUTOFF = 4.0


class BatteryError(Exception):
    """Indicates the platform is unable to move due to a battery voltage issue."""


class MobilePlatform(Component):
    """The main driver for a single platform, wrapping up all sensors, actuators, and outputs."""

    def __init__(self,
                 name: str,
                 light_sensors: LightSensor,
                 motor: Optional[StepperMotor] = None,
                 distance_sensor: Optional[DistanceSensor] = None,
                 voltage_reader: Optional[VoltageReader] = None) -> None:
        self.name = name
        self.light_sensors = light_sensors
        self.motor = motor
        self.voltage_reader = voltage_reader
        self.distance_sensor = distance_sensor
        self.position: Optional[int] = None

    def setup(self) -> None:
        """Initialize all components of the platform.

        This sets up connections and initializes default state. Any obvious failures in the hardware
        should trigger here.
        """
        # Set up the light sensors for reading.
        self.light_sensors.setup()
        if self.motor:
            self.motor.setup()
        if self.distance_sensor:
            self.distance_sensor.setup()
        if self.voltage_reader:
            self.voltage_reader.setup()

    def off(self) -> None:
        """Cleans up and resets any local state and outputs."""
        if self.motor:
            self.motor.off()

    def get_status(self, force_edge_check: bool = False) -> Status:
        """Reads the current status from sensors and internal state.

        force_edge_check: whether to check the distance sensor to verify the edge position.
        """
        return Status(
                name=self.name,
                lux=self.light_sensors.read(),
                motor_voltage=self.voltage_reader.read() if self.voltage_reader else None,
                position=self.position,
                region=self.get_region(force_edge_check))

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
        if at_outer_edge:
            return Region.OUTER_EDGE
        elif self.position is not None:
            return Region.MID
        else:
            return Region.UNKNOWN

    def _reset_pos_to_outer_edge(self) -> None:
        """Reset the current internal position to be 0, i.e. the OUTER_EDGE."""
        if self.position is None:
            logging.info("Initializing edge position to {}".format(Region.OUTER_EDGE))
        elif self.position != Region.OUTER_EDGE.value:
            log = logging.info if abs(self.position) < 10 else logging.warning
            log("Resetting outer edge position (drift: {})".format(self.position))
        self.position = Region.OUTER_EDGE.value

    def _voltage_low(self, status: Status) -> bool:
        """Returns whether the motor voltage is too low to actuate."""
        return status.motor_voltage is not None and status.motor_voltage < MOTOR_VOLTAGE_CUTOFF

    def move_direction(self,
                       direction: Direction, should_continue: Callable[[Status], bool]) -> None:
        assert self.motor, "motor must be configured"

        logging.info("starting sequence move towards %s", direction)
        stop_fmt = "stopping sequence move towards {}: %s (%d steps)".format(direction)

        # Move at most the region size, with a small error buffer to bias towards the outer edge.
        max_distance = int(Region.size() * 1.1)

        for steps in range(max_distance+1):
            # When moving towards the outer edge, cross-check with the sensor in case we've drifted.
            status = self.get_status(force_edge_check=direction is Direction.OUTER)

            if self._voltage_low(status):
                logging.error(stop_fmt, "insufficient voltage", steps)
                raise BatteryError()
            elif not should_continue(status):
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
        assert False, "should terminate within the loop"
