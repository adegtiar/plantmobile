# Logs light data to csv. Writes in minutely intervals.
# Format of each line is "isotimestamp,outer_lux,inner_lux"
class LightCsvLogger(object):

    def __init__(self, filename):
        self.filename = filename
        self._file = None
        self._last_written_timestamp = None

    def _init_file(self):
        # Terribly inefficient yet simple way to get the last line.
        # Replace this with seeking if it ever becomes a problem.
        self._file = open(self.filename, 'a')
        line = None
        for line in open(self.filename, 'r'):
            pass
        self._last_written_timestamp = line.split(',')[0] if line else None

    def log(self, lux):
        if self._file is None:
            self._init_file()

        timestamp = lux.timestamp.isoformat(timespec='minutes')
        if timestamp == self._last_written_timestamp:
            # Write at most one line per minute.
            return
        log_line = "{},{},{}\n".format(timestamp, lux.outer, lux.inner)
        self._file.write(log_line)
        self._file.flush()
        self._last_written_timestamp = timestamp
