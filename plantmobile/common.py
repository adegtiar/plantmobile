from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, List, Optional, NamedTuple

import numpy as np
from adafruit_blinka.microcontroller.bcm283x.pin import Pin  # type: ignore # noqa

# TODO: make into a package

# A reading of light sensor data.
LuxReading = NamedTuple('LuxReading', [
    ('outer', int), ('inner', int), ('avg', int), ('diff', int),
    ('diff_percent', int), ('timestamp', datetime),
])


class LuxAggregator(object):

    def __init__(self) -> None:
        self._luxes: List[LuxReading] = []

    def add(self, lux: LuxReading) -> None:
        self._luxes.append(lux)

    def average(self) -> LuxReading:
        return LuxReading(
            self._int_avg('outer'),
            self._int_avg('inner'),
            self._int_avg('avg'),
            self._int_avg('diff'),
            self._int_avg('diff_percent'),
            self._timestamp_avg())

    def clear(self) -> None:
        self._luxes.clear()

    def _int_avg(self, field: str) -> int:
        field_values = [getattr(lux, field) for lux in self._luxes]
        assert all(type(val) is int for val in field_values)
        return int(np.mean(field_values))

    def _timestamp_avg(self) -> datetime:
        dates = [lux.timestamp for lux in self._luxes]
        ref_date = datetime(1900, 1, 1)
        return ref_date + sum([date - ref_date for date in dates], timedelta()) / len(dates)

    def __len__(self) -> int:
        return len(self._luxes)


def get_diff_percent(outer: int, inner: int) -> int:
    avg = int(np.mean((outer, inner)))
    diff = inner - outer
    return int(diff/avg * 100) if avg else 0


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
