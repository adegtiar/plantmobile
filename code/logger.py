import numpy as np
import time
from typing import IO, List, Optional

from common import LuxReading, Output, Status


class LightCsvLogger(Output):
    """Logs light data to csv in minutely intervals.
    Format of each line is "isotimestamp,outer_lux,inner_lux".
    """

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self._file: Optional[IO] = None
        self._cur_timestamp: Optional[str] = None
        self._cur_timestamp_luxes: List[LuxReading] = []

    def setup(self) -> None:
        if self._file is None:
            self._file = open(self.filename, 'a')

    def off(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    def output_status(self, status: Status) -> None:
        assert self._file is not None, "must call setup() to initialize"

        # Timestamp truncated down to the minute
        timestamp = status.lux.timestamp.isoformat(timespec='minutes')

        if self._cur_timestamp is None:
            # Initialize current timestamp
            self._cur_timestamp = timestamp
        elif self._cur_timestamp != timestamp:
            # We've moved past a minute boundary.
            assert self._cur_timestamp_luxes, "Timestamp with no lux data?"
            # We've buffered readings. Output them now.
            outer_avg = int(np.mean([lux.outer for lux in self._cur_timestamp_luxes]))
            inner_avg = int(np.mean([lux.inner for lux in self._cur_timestamp_luxes]))
            log_line = "{},{},{}\n".format(self._cur_timestamp, outer_avg, inner_avg)
            self._file.write(log_line)
            self._file.flush()

            # Reset data for the new timestamp.
            self._cur_timestamp = timestamp
            self._cur_timestamp_luxes = []

        # Add another reading to aggregate within the same minute.
        self._cur_timestamp_luxes.append(status.lux)
        return


class StatusPrinter(Output):
    """Prints statuses to stdout at a configurable interval."""

    def __init__(self, print_interval: float = 0) -> None:
        self.print_interval = print_interval
        self._last_printed_time = float("-inf")

    def setup(self) -> None:
        pass

    def off(self) -> None:
        pass

    def output_status(self, status: Status) -> None:
        if time.time() - self._last_printed_time < self.print_interval:
            return

        print("sensor:\t\t", status.lux.name)
        print("outer:\t\t", status.lux.outer)
        print("inner:\t\t", status.lux.inner)
        print("average:\t", status.lux.avg)
        print("diff:\t\t", status.lux.diff)
        print("diff percent:\t {}%".format(status.lux.diff_percent))
        print("button_status:\t", status.button.name)
        print("position:\t", status.position)
        print("region:\t\t", status.region)
        print("motor voltage:\t {:.3f}".format(status.motor_voltage))
        print()
        self._last_printed_time = time.time()
