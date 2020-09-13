import logging
import time
from abc import ABC, abstractmethod
from typing import Callable, List, NoReturn, Optional

from plantmobile.common import ButtonPress, Direction, Region, Status
from plantmobile.debug_panel import DebugPanel
from plantmobile.output_device import Tune
from plantmobile.platform_driver import BatteryError, PlatformDriver

CONTROL_LOOP_SLEEP_SECS = 0.5


class Controller(ABC):

    @abstractmethod
    def perform_action(self, status: Status) -> bool:
        pass


def control_loop(
        platform: PlatformDriver, debug_panel: DebugPanel, controllers: List[Controller]) -> NoReturn:
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
    # TODO: add button enable/disable
    # TODO: add battery keep-alive?

    def __init__(self, platform: PlatformDriver, debug_panel: DebugPanel, diff_percent_cutoff: int):
        assert platform.motor, "Must have motor configured"
        assert platform.light_sensors, "Must have light sensors configured"
        self.platform = platform
        self.debug_panel = debug_panel
        self.diff_percent_cutoff = diff_percent_cutoff
        self._enabled = True

    def toggle_enabled(self) -> None:
        self._enabled = not self._enabled

    def _notify(self) -> None:
        if self.debug_panel.buzzer:
            self.debug_panel.buzzer.play_tune(AUTO_MOVE_TUNE)
        else:
            self.debug_panel.blink(times=2)

    def _should_continue(self, status: Status) -> bool:
        # Output any status updates.
        self.debug_panel.output_status(status)
        return self._enabled

    def perform_action(self, status: Status) -> bool:
        lux = status.lux
        if not self._enabled:
            return False

        if self.platform.get_region() is Region.UNKNOWN:
            self._notify()
            self.platform.move_direction(Direction.OUTER, self._should_continue)
            return True
        elif abs(lux.diff_percent) >= self.diff_percent_cutoff:
            # TODO: stop on button press
            if lux.outer > lux.inner and status.region != Region.OUTER_EDGE:
                self._notify()
                self.platform.move_direction(Direction.OUTER, self._should_continue)
                return True
            elif lux.inner > lux.outer and status.region in (Region.MID, Region.OUTER_EDGE):
                self._notify()
                self.platform.move_direction(Direction.INNER, self._should_continue)
                return True
        return False


class ButtonController(Controller):

    def __init__(self, platform: PlatformDriver, debug_panel: DebugPanel):
        assert platform.motor, "Must have motor configured"
        assert debug_panel.outer_button and debug_panel.inner_button, "Must have buttons configured"
        self.platform = platform
        self.debug_panel = debug_panel
        # In hold mode, hold the button down for movement.
        self._hold_mode = True

    def _button_checker(
            self, manual_hold_button: Optional[ButtonPress]) -> Callable[[Status], bool]:
        def should_continue(status: Status) -> bool:
            # Output any status updates.
            self.debug_panel.output_status(status)
            button_press = self.debug_panel.get_directional_buttons()

            if self._hold_mode:
                # Keep moving while the button is held down.
                return button_press is manual_hold_button
            else:
                # Keep moving unless any button is pressed to cancel it.
                return button_press is ButtonPress.NONE
        return should_continue

    def perform_action(self, status: Status) -> bool:
        # TODO: move this into this class?
        button_press = self.debug_panel.get_directional_buttons()
        if button_press is ButtonPress.OUTER:
            if not self._hold_mode:
                self.debug_panel.blink(times=2)
            self.platform.move_direction(Direction.OUTER, self._button_checker(ButtonPress.OUTER))
            return True
        elif button_press is ButtonPress.INNER:
            if not self._hold_mode:
                self.debug_panel.blink(times=2)
            self.platform.move_direction(Direction.INNER, self._button_checker(ButtonPress.INNER))
            return True
        elif button_press is ButtonPress.BOTH:
            # Toggle between hold mode and auto mode.
            self.debug_panel.blink(times=3)
            self._hold_mode = not self._hold_mode
            # Only move if we're transitioning into auto mode.
            if not self._hold_mode:
                self.platform.move_direction(Direction.OUTER, self._button_checker(None))
            return True
        elif button_press is ButtonPress.NONE:
            return False
        else:
            assert False, "unknown button press {}".format(button_press)
