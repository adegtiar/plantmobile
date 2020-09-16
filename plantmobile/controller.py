import logging
import time
from abc import ABC, abstractmethod
from typing import Callable, List, NoReturn, Optional

from plantmobile.common import Direction, Region, Status
from plantmobile.debug_panel import DebugPanel
from plantmobile.input_device import Button
from plantmobile.output_device import LED, Tune
from plantmobile.platform_driver import BatteryError, MobilePlatform

CONTROL_LOOP_SLEEP_SECS = 0.5


class Controller(ABC):

    @abstractmethod
    def perform_action(self, status: Status) -> bool:
        """Perform an action if one is appropriate for the current state.

        Returns whether an action was performed.
        """
        pass


def control_loop(
        platform: MobilePlatform,
        debug_panel: DebugPanel,
        controllers: List[Controller]) -> NoReturn:
    """Runs the control loop for a platform.

    In each loop, the controllers will be run in order until one performs an action.

    param platform:
        The platform to drive.
    param controllers:
        The prioritized list of controllers.
    """
    while True:
        status = platform.get_status()
        debug_panel.output_status(status)

        # TODO: refactor in terms of steps/changes?
        try:
            for controller in controllers:
                if controller.perform_action(status):
                    logging.debug("Performed action from %s", controller)
                    break
        except BatteryError:
            debug_panel.output_error("BATT")

        time.sleep(CONTROL_LOOP_SLEEP_SECS)


# Tune for "Here Comes the Sun" by The Beatles.
AUTO_MOVE_TUNE = Tune(["F#5", "D5", "E5", "F#5", "D5"], [1, 1, 1, 2, 2])


class AvoidShadowController(Controller):
    # TODO: bias towards outer
    # TODO: add smoothing
    # TODO: add rate-limiting

    def __init__(
            self,
            platform: MobilePlatform,
            debug_panel: DebugPanel,
            enable_button: Button,
            enabled_led: LED,
            diff_percent_cutoff: int,
            min_light_level: int = 20):
        assert platform.motor, "Must have motor configured"
        assert platform.light_sensors, "Must have light sensors configured"
        self.platform = platform
        self.debug_panel = debug_panel
        self.diff_percent_cutoff = diff_percent_cutoff
        self.enabled_led = enabled_led
        self.enable_button = enable_button,
        self.min_light_level = 20

        enable_button.when_pressed = self.toggle_enabled

    def toggle_enabled(self, enabled: Optional[bool] = None) -> None:
        enable = enabled if enabled is not None else not self.enabled()
        if enable:
            self.enabled_led.on()
        else:
            self.enabled_led.off()
        # TODO: stop buzzer?

    def enabled(self) -> bool:
        return self.enabled_led.is_active

    def _notify(self) -> None:
        if self.debug_panel.buzzer:
            self.debug_panel.buzzer.play_tune(AUTO_MOVE_TUNE)
        else:
            self.debug_panel.blink(times=2)

    def _should_continue(self, status: Status) -> bool:
        # Output any status updates.
        self.debug_panel.output_status(status)
        return self.enabled()

    def _move(self, direction: Direction) -> None:
        self._notify()
        self.platform.move_direction(direction, self._should_continue)

    def perform_action(self, status: Status) -> bool:
        lux = status.lux
        if not self.enabled():
            return False
        if max(lux.outer, lux.inner) < self.min_light_level:
            logging.debug("Skipped shadow avoid logic: too little light (%s lux)", lux.avg)
            return False

        if self.platform.get_region() is Region.UNKNOWN:
            # Initialize the position.
            self._move(Direction.OUTER)
            return True

        elif abs(lux.diff_percent) >= self.diff_percent_cutoff:
            # TODO: stop on button press
            if lux.outer > lux.inner and status.region != Region.OUTER_EDGE:
                self._move(Direction.OUTER)
                return True
            elif lux.inner > lux.outer and status.region in (Region.MID, Region.OUTER_EDGE):
                self._move(Direction.INNER)
                return True
        return False


class ButtonController(Controller):
    """Controller for the mobile platform via two buttons.

    In hold mode, hold one of the buttons for movement and let go to stop.
    In press mode, press one of the buttons and it will move until it reaches an edge.
    """

    def __init__(self,
                 platform: MobilePlatform,
                 debug_panel: DebugPanel,
                 outer_button: Button,
                 inner_button: Button,
                 hold_button_threshold_secs: float = 0.1) -> None:
        self.platform = platform
        self.debug_panel = debug_panel
        for button in (outer_button, inner_button):
            button.when_pressed = self._on_press
            button.when_held = self._on_hold
            button.when_released = self._on_release
            button.hold_time = hold_button_threshold_secs
        self.outer_button = outer_button
        self.inner_button = inner_button
        # In hold mode, hold the button down for movement.
        self._hold_mode = True
        self._direction_commanded: Optional[Direction] = None

    def _on_press(self, button: Button) -> None:
        # This logic controller the non-hold mode.
        logging.debug("Button press: %s", button)

        if self.outer_button.is_pressed and self.inner_button.is_pressed:
            # Both are pressed.
            self._direction_commanded = None
            self.toggle_hold_mode()
            logging.debug("Both buttons pressed: toggling hold mode to %s", self._hold_mode)
            return
        if self._hold_mode:
            # Hold mode commands are handled by _on_hold.
            return

        if self._direction_commanded:
            # Any button press cancels an in-progress move.
            logging.debug("Cancelling in-progress command %s (press)", self._direction_commanded)
            self._direction_commanded = None
        else:
            self._direction_commanded = self._corresponding_direction(button)
            logging.debug("Commanding move in direction %s (press)", self._direction_commanded)

    def _on_hold(self, button: Button) -> None:
        logging.debug("Button hold: %s", button)
        if not self._hold_mode:
            # Press mode commands are handled by _on_press.
            return

        if self.outer_button.is_pressed and self.inner_button.is_pressed:
            logging.debug("Both buttons held: doing nothing")
            return

        self._direction_commanded = self._corresponding_direction(button)
        logging.debug("Commanding move in direction %s (hold)", self._direction_commanded)

    def _on_release(self, button: Button) -> None:
        if self._hold_mode:
            logging.debug("Button %s no longer held down. Cancelling movement", button)
            self._direction_commanded = None

    def _corresponding_direction(self, button: Button) -> Direction:
        return Direction.INNER if button is self.inner_button else Direction.OUTER

    def toggle_hold_mode(self) -> None:
        """Toggle between hold mode and press mode."""
        self.debug_panel.blink(times=3)
        self._hold_mode = not self._hold_mode

    def _should_continue(self, direction_commanded: Direction) -> Callable[[Status], bool]:
        def should_continue(status: Status) -> bool:
            self.debug_panel.output_status(status)
            return self._direction_commanded is direction_commanded
        return should_continue

    def perform_action(self, status: Status) -> bool:
        direction = self._direction_commanded
        if direction:
            try:
                self.platform.move_direction(direction, self._should_continue(direction))
                return True
            finally:
                # Clear the command if move_direction finished without cancellation.
                self._direction_commanded = None
        else:
            return False


class BatteryKeepAlive(Controller):

    def __init__(self,
                 platform: MobilePlatform,
                 ping_interval_secs: float,
                 ping_duration_secs: float,
                 enabled: Callable[[], bool] = lambda: True,
                 ) -> None:
        assert ping_interval_secs > 0, "Ping interval must be positive"
        self.platform = platform
        self.ping_interval_secs = ping_interval_secs
        self.ping_duration_secs = ping_duration_secs
        self.enabled = enabled
        self._last_ping = float("-inf")

    def perform_action(self, status: Status) -> bool:
        if not self.enabled():
            # Reset the counter so it will attempt to ping when enabled.
            self._last_ping = float("-inf")
            return False

        now = time.time()
        if now - self._last_ping > self.ping_interval_secs:
            logging.info("%d seconds elapsed: running keepalive ping for %.1f seconds",
                         self.ping_interval_secs, self.ping_duration_secs)
            self._last_ping = now
            self.platform.ping_motor(status, self.ping_duration_secs)
            return True
        return False
