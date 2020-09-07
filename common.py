from abc import ABC, abstractmethod
from collections import namedtuple
from enum import Enum

# A reading of light sensor data.
LuxReading = namedtuple('SensorReading',
        ['outer', 'inner', 'avg', 'diff', 'diff_percent', 'timestamp', 'name'])


class ButtonStatus(Enum):
    NONE_PRESSED = 0
    OUTER_PRESSED = 1
    INNER_PRESSED = 2
    BOTH_PRESSED = 3


#Status = namedtuple('Status', ['lux', 'button', 'position', 'edge'])
class Status:
    def __init__(self, lux, button, position, edge):
        self.lux = lux
        self.button = button
        self.position = position
        self.edge = edge


class Output(ABC):
    @abstractmethod
    def setup(self):
        pass

    @abstractmethod
    def off(self):
        pass

    @abstractmethod
    def update_status(self, status):
        pass
