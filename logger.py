import numpy as np
import time

from common import Output


class LightCsvLogger(Output):
    """Logs light data to csv in minutely intervals.
    Format of each line is "isotimestamp,outer_lux,inner_lux".
    """

    def __init__(self, filename):
        self.filename = filename
        self._file = None
        self._cur_timestamp = None
        self._cur_timestamp_luxes = []

    def setup(self):
        if self._file is None:
            self._file = open(self.filename, 'a')

    def off(self):
        if self._file is None:
            self._file.close()
            self._file = None

    def output_status(self, status):
        self.setup()

        # Timestamp truncated down to the minute
        timestamp = status.lux.timestamp.isoformat(timespec='minutes')

        if self._cur_timestamp is None:
            # Initialize current timestamp
            self._cur_timestamp = timestamp
        elif self._cur_timestamp != timestamp:
            # We've moved past a minute boundary.
            assert self._cur_timestamp_luxes, "Timestamp with no lux data?"
            # We've buffered readings. Output them now.
            outer_avg = int(np.mean([l.outer for l in self._cur_timestamp_luxes]))
            inner_avg = int(np.mean([l.inner for l in self._cur_timestamp_luxes]))
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

    def __init__(self, print_interval=0):
        self.print_interval = print_interval
        self._last_printed_time = float("-inf")

    def setup(self):
        pass

    def off(self):
        pass

    def output_status(self, status):
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
        print()
        self._last_printed_time = time.time()
