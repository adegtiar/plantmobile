import logging
import time
from enum import Enum
from typing import Optional


from .controller import Controller
from plantmobile.common import (
        Direction, get_diff_percent, LuxAggregator, LuxReading, Region, Status,
)
from plantmobile.debug_panel import DebugPanel
from plantmobile.input_device import ToggleButton
from plantmobile.logger import StatusPrinter
from plantmobile.output_device import Tune
from plantmobile.platform_driver import MobilePlatform


# Tune for "Here Comes the Sun" by The Beatles.
AUTO_MOVE_TUNE = Tune(["F#5", "D5", "E5", "F#5"], [1, 1, 1, 2])


class LightLevel(Enum):
    DARK = 0
    DIM = 1
    BRIGHT = 2
    OUTER_BRIGHTER = 3
    INNER_BRIGHTER = 4


class ShadowAvoider(Controller):

    def __init__(
            self,
            platform: MobilePlatform,
            debug_panel: DebugPanel,
            status_printer: StatusPrinter,
            enable_button: ToggleButton,
            diff_percent_cutoff: int,
            dim_lux_threshold: int = 300,
            bright_lux_threshold: int = 500,
            run_interval_secs: float = 10,
            ):
        assert platform.motor, "Must have motor configured"
        assert platform.light_sensors, "Must have light sensors configured"
        self.platform = platform
        self.debug_panel = debug_panel
        self.status_printer = status_printer
        self._enable_button = enable_button
        self.diff_percent_cutoff = diff_percent_cutoff
        self.dim_lux_threshold = dim_lux_threshold
        self.bright_lux_threshold = bright_lux_threshold
        self._prev_level: Optional[LightLevel] = None
        self._run_interval_secs = run_interval_secs
        self._last_run_time = float("-inf")
        self._lux_agg = LuxAggregator()
        self._i = 0

    def _lux_compare(self, lux: LuxReading) -> LightLevel:
        intensity = max(lux.outer, lux.inner)
        if intensity < self.dim_lux_threshold:
            return LightLevel.DARK
        elif abs(lux.diff_percent) >= self.diff_percent_cutoff:
            if lux.outer > lux.inner:
                return LightLevel.OUTER_BRIGHTER
            elif lux.inner > lux.outer:
                return LightLevel.INNER_BRIGHTER
            else:
                assert False, "Inconsistent lux reading"
        elif intensity < self.bright_lux_threshold:
            return LightLevel.DIM
        else:
            return LightLevel.BRIGHT

    def enabled(self) -> bool:
        return self._enable_button.enabled()

    def _notify(self) -> None:
        if self.debug_panel.buzzer:
            self.debug_panel.buzzer.play_tune(AUTO_MOVE_TUNE)
        else:
            self.debug_panel.blink(times=2)

    def _should_continue(self, status: Status) -> bool:
        # Output any status updates.
        self.debug_panel.output_status(status)
        if self._i % 10 == 0:
            self.status_printer.output_status(status, force=True)
        self._i += 1
        return self.enabled()

    def _move(
            self,
            direction: Direction,
            region: Region,
            lux: LuxReading,
            reason: str,
            steps: Optional[int] = None) -> int:

        if ((direction is Direction.OUTER and region == Region.OUTER_EDGE)
                or (direction is Direction.INNER and region == Region.INNER_EDGE)):
            # Don't try to move if we're already at the corresponding edge.
            logging.info("Not moving to %s: already at edge", direction)
            return 0

        logging.info("Ran analysis on lux %s", lux)
        logging.info("%s: moving to %s edge", reason, direction)

        if direction is Direction.INNER:
            assert region, "Region must be initialized to automatically move towards inner"

        self._notify()
        self._i = 0
        steps = self.platform.move_direction(direction, self._should_continue, steps)

        # If we moved, reset the prev light level since the reading is for the old position.
        self._prev_level = None
        return steps

    def perform_action(self, status: Status) -> bool:
        # Add the current lux to the running average.
        self._lux_agg.add(status.lux)

        # TODO: consider doing a running aggregation for a consistent time response time.
        # NOTE: this would also fix the issue with ignoring time spent on button handler.
        if time.time() - self._last_run_time < self._run_interval_secs:
            return False

        # Get the average lux over the configured aggregation interval.
        agg_lux = self._lux_agg.average()
        self._lux_agg.clear()
        try:
            return self._perform_action(agg_lux, status.region)
        finally:
            self._last_run_time = time.time()

    def _perform_action(self, lux: LuxReading, cur_region: Region) -> bool:
        if not self.enabled():
            return False

        if self.platform.get_region() is Region.UNKNOWN:
            # When the position is unknown, we move to the outer edge where the sensor can find it.
            steps = self._move(Direction.OUTER, cur_region, lux, "Initializing position")

            old_avg = lux.avg
            new_status = self.platform.get_status()
            new_avg = new_status.lux.avg
            # Reuse the same logic as difference between outer and inner sensors.
            if get_diff_percent(new_avg, old_avg) >= self.diff_percent_cutoff:
                # Undo our initialization move if average brightness got worse.
                # TODO: this is finicky... can we fix it? Maybe move into main loop.
                reason = "Old lux {} was higher than lux {} at outer edge".format(old_avg, new_avg)
                self.status_printer.reset()
                self._move(Direction.INNER, new_status.region, lux, reason, steps)
            return True

        logging.debug("Running light analysis with averaged lux: %s", lux)
        prev_level = self._prev_level
        light_level = self._prev_level = self._lux_compare(lux)
        logging.info("Prev light level: %s, New light level: %s", prev_level, light_level)
        if light_level is LightLevel.DARK:
            # When dark, keep at inner edge to avoid the blinds.
            self._move(Direction.INNER, cur_region, lux, "Light dimming below active threshold")
        elif light_level is LightLevel.OUTER_BRIGHTER:
            # Move in the direction of the the brither light.
            self._move(Direction.OUTER, cur_region, lux, "Light difference found")
        elif light_level is LightLevel.INNER_BRIGHTER:
            # Move in the direction of the the brighter light.
            self._move(Direction.INNER, cur_region, lux, "Light difference found")
        elif light_level is LightLevel.BRIGHT:
            if prev_level is LightLevel.INNER_BRIGHTER:
                # When inner is no longer brighter, the shadow is likely passing the outer edge.
                self._move(Direction.OUTER, cur_region, lux, "Inner light no longer brighter")
            elif prev_level in (LightLevel.DARK, LightLevel.DIM):
                # When no longer dim (blinds are opened), move to outer edge for more sunlight.
                self._move(Direction.OUTER, cur_region, lux, "Light rising to active threshold")
        else:
            assert light_level is LightLevel.DIM
            # Do nothing, to allow a buffer for light fluctuating back down without thrashing.
        return True
