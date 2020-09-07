from abc import ABC, abstractmethod
from collections import namedtuple
from enum import Enum

# A reading of light sensor data.
LuxReading = namedtuple('SensorReading',
        ['outer', 'inner', 'avg', 'diff', 'diff_percent', 'timestamp', 'name'])


class Edge(Enum):
    NONE = None
    OUTER = 0
    INNER = 100


class ButtonStatus(Enum):
    NONE_PRESSED = 0
    OUTER_PRESSED = 1
    INNER_PRESSED = 2
    BOTH_PRESSED = 3

    @property
    def corresponding_direction(self):
        if self is ButtonStatus.OUTER_PRESSED:
            return Direction.OUTER
        elif self is ButtonStatus.INNER_PRESSED:
            return Direction.INNER
        else:
            return None


class Direction(Enum):
    OUTER = -1
    INNER = +1

    @property
    def motor_direction(self):
        return Rotation.CCW if self is Direction.OUTER else Rotation.CW

    @property
    def extreme_edge(self):
        return Edge.OUTER if self is Direction.OUTER else Edge.INNER


class Rotation(Enum):
    CW = 0
    CCW = 1


class Status:
    def __init__(self, lux, button, position, edge):
        self.lux = lux
        self.button = button
        self.position = position
        self.edge = edge


class Component(ABC):
    @abstractmethod
    def setup(self):
        pass

    @abstractmethod
    def off(self):
        pass


class Output(Component):
    @abstractmethod
    def output_status(self, status):
        pass


class Input(Component):
    @abstractmethod
    def read(self):
        pass
