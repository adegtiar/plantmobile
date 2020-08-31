import numpy as np

# Logs light data to csv. Writes in minutely intervals.
# Format of each line is "isotimestamp,outer_lux,inner_lux"
class LightCsvLogger(object):

    def __init__(self, filename):
        self.filename = filename
        self._file = None
        self._cur_timestamp = None
        self._cur_timestamp_luxes = []

    def setup(self):
        if self._file is None:
            self._file = open(self.filename, 'a')

    def log(self, lux):
        self.setup()

        # Timestamp truncated down to the minute
        timestamp = lux.timestamp.isoformat(timespec='minutes')

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
        self._cur_timestamp_luxes.append(lux)
        return
