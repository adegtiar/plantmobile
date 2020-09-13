import logging
import time
from abc import ABC, abstractmethod
from typing import Callable, List, NoReturn, Optional

from plantmobile.common import ButtonPress, Direction, Region, Status
from plantmobile.output_device import Tune
from plantmobile.platform_driver import PlatformDriver

CONTROL_LOOP_SLEEP_SECS = 0.5


class Controller(ABC):

    @abstractmethod
    def perform_action(self, status: Status) -> bool:
        pass


def control_loop(platform: PlatformDriver, controllers: List[Controller]) -> NoReturn:
    """Runs the control loop for a platform.

    In each loop, the controllers will be run in order until one performs an action.

    param platform:
        The platform to drive.
    param controllers:
        The prioritized list of controllers.
    """
    while True:
        status = platform.get_status()
        platform.output_status(status)
        # TODO: refactor in terms of steps/changes?

        for controller in controllers:
            if controller.perform_action(status):
                logging.debug("Performed action from %s", controller)
                break

        time.sleep(CONTROL_LOOP_SLEEP_SECS)


# Tune for "Here Comes the Sun" by The Beatles.
AUTO_MOVE_TUNE = Tune(["F#5", "D5", "E5", "F#5", "D5"], [1, 1, 1, 2, 2])


class AvoidShadowController(Controller):
    # TODO: bias towards outer
    # TODO: add smoothing
    # TODO: add rate-limiting
    # TODO: add button enable/disable
    # TODO: add battery keep-alive?

    def __init__(self, platform: PlatformDriver, diff_percent_cutoff: int):
        assert platform.motor, "Must have motor configured"
        assert platform.light_sensors, "Must have light sensors configured"
        self.platform = platform
        self.diff_percent_cutoff = diff_percent_cutoff
        self._enabled = True

    def _notify(self) -> None:
        if self.platform.buzzer:
            self.platform.buzzer.play_tune(AUTO_MOVE_TUNE)
        else:
            self.platform.blink(times=2)

    def perform_action(self, status: Status) -> bool:
        lux = status.lux
        if abs(lux.diff_percent) >= self.diff_percent_cutoff:
            # TODO: stop on button press
            if lux.outer > lux.inner and status.region != Region.OUTER_EDGE:
                self._notify()
                self.platform.move_direction(Direction.OUTER, lambda _: False)
                return True
            elif lux.inner > lux.outer and status.region != Region.INNER_EDGE:
                self._notify()
                self.platform.move_direction(Direction.INNER, lambda _: False)
                return True
        return False


class ButtonController(Controller):

    def __init__(self, platform: PlatformDriver):
        assert platform.motor, "Must have motor configured"
        assert platform.outer_button and platform.inner_button, "Must have buttons configured"
        self.platform = platform
        # In hold mode, hold the button down for movement.
        self._hold_mode = True

    def _stop_requester(
            self, manual_hold_button: Optional[ButtonPress]) -> Callable[[Status], bool]:
        def stop_requested(status: Status) -> bool:
            if self._hold_mode:
                # Keep moving while the button is held down.
                return not (status.button is manual_hold_button)
            else:
                # Keep moving unless any button is pressed to cancel it.
                return not (status.button is ButtonPress.NONE)
        return stop_requested

    def perform_action(self, status: Status) -> bool:
        if status.button is ButtonPress.OUTER:
            if not self._hold_mode:
                self.platform.blink(times=2)
            self.platform.move_direction(Direction.OUTER, self._stop_requester(ButtonPress.OUTER))
            return True
        elif status.button is ButtonPress.INNER:
            if not self._hold_mode:
                self.platform.blink(times=2)
            self.platform.move_direction(Direction.INNER, self._stop_requester(ButtonPress.INNER))
            return True
        elif status.button is ButtonPress.BOTH:
            # Toggle between hold mode and auto mode.
            self.platform.blink(times=3)
            self._hold_mode = not self._hold_mode
            # Only move if we're transitioning into auto mode.
            if not self._hold_mode:
                self.platform.move_direction(Direction.OUTER, self._stop_requester(None))
            return True
        elif status.button is ButtonPress.NONE:
            return False
        else:
            assert False, "unknown button press {}".format(status.button)
