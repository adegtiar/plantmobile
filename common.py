from abc import ABC, abstractmethod
from collections import namedtuple
from enum import Enum
from typing import Any, Optional, Union

# A reading of light sensor data.
LuxReading = namedtuple('LuxReading',
        ['outer', 'inner', 'avg', 'diff', 'diff_percent', 'timestamp', 'name'])


class Region(Enum):
    """Indicates the region of the table corresponding to the position."""
    OUTER_EDGE = 0
    MID = None
    INNER_EDGE = 100


class Rotation(Enum):
    CW = 0
    CCW = 1


class Direction(Enum):
    OUTER = -1
    INNER = +1

    @property
    def motor_rotation(self) -> Rotation:
        return Rotation.CCW if self is Direction.OUTER else Rotation.CW

    @property
    def extreme_edge(self) -> Region:
        return Region.OUTER_EDGE if self is Direction.OUTER else Region.INNER_EDGE


class ButtonStatus(Enum):
    NONE_PRESSED = 0
    OUTER_PRESSED = 1
    INNER_PRESSED = 2
    BOTH_PRESSED = 3

    @property
    def corresponding_direction(self) -> Union[Direction, None]:
        if self is ButtonStatus.OUTER_PRESSED:
            return Direction.OUTER
        elif self is ButtonStatus.INNER_PRESSED:
            return Direction.INNER
        else:
            return None


class Status:
    def __init__(self,
            lux: Optional[LuxReading],
            button: Optional[ButtonStatus],
            position: Optional[int],
            region: Optional[Region]) -> None:
        self.lux = lux
        self.button = button
        self.position = position
        self.region = region


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
