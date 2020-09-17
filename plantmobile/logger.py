import numpy as np
import time
from typing import Any, Callable, IO, List, Optional, Tuple

from texttable import Texttable  # type: ignore

from plantmobile.common import LuxReading, Output, Status


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
    FIELDS: List[Tuple[str, Callable[[Status], Any]]] = [
            ("name", lambda s: s.name),
            ("outer_lux", lambda s: s.lux.outer),
            ("inner_lux", lambda s: s.lux.inner),
            ("average_lux", lambda s: s.lux.avg),
            ("diff", lambda s: s.lux.diff),
            ("diff_percent", lambda s: str(s.lux.diff_percent) + '%'),
            ("position", lambda s: s.position),
            ("region", lambda s: s.region.name),
            ("motor voltage", lambda s: s.motor_voltage),
    ]

    def __init__(self, print_interval: float = 0) -> None:
        self.print_interval = print_interval
        self._last_printed_time = float("-inf")
        self._header = [field[0] for field in StatusPrinter.FIELDS]
        self._i = 0

    def setup(self) -> None:
        pass

    def off(self) -> None:
        pass

    def output_status(self, status: Status) -> None:
        if time.time() - self._last_printed_time < self.print_interval:
            return

        table = Texttable()
        table.set_deco(Texttable.HEADER)
        if self._i % 20 == 0:
            table.header(self._header)

        row = [field[1](status) for field in StatusPrinter.FIELDS]
        table.add_row(row)
        col_widths = [len(elm) if type(elm) is str else 0 for elm in row]
        table.set_cols_width([max(len(h), w) for h, w in zip(self._header, col_widths)])

        print(table.draw())
        self._last_printed_time = time.time()
        self._i += 1
