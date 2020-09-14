from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Optional, NamedTuple

from adafruit_blinka.microcontroller.bcm283x.pin import Pin  # type: ignore # noqa

# A reading of light sensor data.
LuxReading = NamedTuple('LuxReading', [
    ('outer', int), ('inner', int), ('avg', int), ('diff', int),
    ('diff_percent', int), ('timestamp', datetime),
])


class Region(Enum):
    """Indicates the region of the table corresponding to the position."""
    UNKNOWN = None
    OUTER_EDGE = 0
    MID = 50
    INNER_EDGE = 100

    @classmethod
    def size(cls) -> int:
        return abs(Region.INNER_EDGE.value - Region.OUTER_EDGE.value)


class Rotation(Enum):
    """The spin direction of the motor."""
    CW = 0
    CCW = 1


class Direction(Enum):
    """The relative direction of travel."""
    OUTER = -1
    INNER = +1

    @property
    def motor_rotation(self) -> Rotation:
        return Rotation.CCW if self is Direction.OUTER else Rotation.CW

    @property
    def extreme_edge(self) -> Region:
        return Region.OUTER_EDGE if self is Direction.OUTER else Region.INNER_EDGE


class ButtonPress(Enum):
    NONE = 0
    OUTER = 1
    INNER = 2
    BOTH = 3

    @classmethod
    def from_buttons(cls, outer_pressed: bool, inner_pressed: bool) -> 'ButtonPress':
        if outer_pressed and inner_pressed:
            return ButtonPress.BOTH
        elif outer_pressed:
            return ButtonPress.OUTER
        elif inner_pressed:
            return ButtonPress.INNER
        else:
            return ButtonPress.NONE


Status = NamedTuple('Status', [
    ('name', str), ('lux', LuxReading), ('motor_voltage', Optional[float]),
    ('position', Optional[int]), ('region', Region)])


class Component(ABC):
    @abstractmethod
    def setup(self) -> None:
        pass

    @abstractmethod
    def off(self) -> None:
        pass


class Output(Component):
    @abstractmethod
    def output_status(self, status: Status) -> None:
        pass


class Input(Component):
    @abstractmethod
    def read(self) -> Any:
        pass
