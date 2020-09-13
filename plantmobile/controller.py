from abc import ABC, abstractmethod
from typing import Callable, Optional

from plantmobile.common import ButtonPress, Direction, Status
from plantmobile.platform_driver import PlatformDriver


class MotorController(ABC):

    @abstractmethod
    def perform_action(self, status: Status) -> bool:
        pass


class ButtonController(MotorController):

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
