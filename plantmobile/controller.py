import logging
import time
from abc import ABC, abstractmethod
from typing import Callable, List, NoReturn, Optional

from plantmobile.common import ButtonPress, Direction, Region, Status
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
    # TODO: add battery keep-alive?

    def __init__(
            self,
            platform: MobilePlatform,
            debug_panel: DebugPanel,
            enable_button: Button,
            led: LED,
            diff_percent_cutoff: int):
        assert platform.motor, "Must have motor configured"
        assert platform.light_sensors, "Must have light sensors configured"
        self.platform = platform
        self.debug_panel = debug_panel
        self.diff_percent_cutoff = diff_percent_cutoff
        self.led = led
        self.enable_button = enable_button,
        self._enabled = False

        enable_button.when_pressed = self.toggle_enabled

    def toggle_enabled(self) -> None:
        self._enabled = not self._enabled
        self.led.toggle()
        # TODO: stop buzzer?
        # TODO: stop motor

    def _notify(self) -> None:
        if self.debug_panel.buzzer:
            self.debug_panel.buzzer.play_tune(AUTO_MOVE_TUNE)
        else:
            self.debug_panel.blink(times=2)

    def _should_continue(self, status: Status) -> bool:
        # Output any status updates.
        self.debug_panel.output_status(status)
        return self._enabled

    def _move(self, direction: Direction) -> None:
        self._notify()
        self.platform.move_direction(direction, self._should_continue)

    def perform_action(self, status: Status) -> bool:
        lux = status.lux
        if not self._enabled:
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
                self._move(Direction.OUTER)
                return True
        return False


class ButtonController(Controller):

    def __init__(self,
                 platform: MobilePlatform,
                 debug_panel: DebugPanel,
                 outer_button: Button,
                 inner_button: Button) -> None:
        self.platform = platform
        self.debug_panel = debug_panel
        self.outer_button = outer_button
        self.inner_button = inner_button
        # In hold mode, hold the button down for movement.
        self._hold_mode = True

    def get_button_press(self) -> ButtonPress:
        """Gets the current button press status."""
        return ButtonPress.from_buttons(
                outer_pressed=bool(self.outer_button.is_pressed),
                inner_pressed=bool(self.inner_button.is_pressed))

    def _button_checker(
            self, manual_hold_button: Optional[ButtonPress]) -> Callable[[Status], bool]:
        # TODO: make this on press/release or hold.
        def should_continue(status: Status) -> bool:
            # Output any status updates.
            self.debug_panel.output_status(status)
            button_press = self.get_button_press()

            if self._hold_mode:
                # Keep moving while the button is held down.
                return button_press is manual_hold_button
            else:
                # Keep moving unless any button is pressed to cancel it.
                return button_press is ButtonPress.NONE
        return should_continue

    def perform_action(self, status: Status) -> bool:
        # TODO: move this into this class?
        button_press = self.get_button_press()
        logging.info("Button press: %s", button_press)
        if button_press in (ButtonPress.OUTER, ButtonPress.INNER):
            direction = Direction.OUTER if button_press is ButtonPress.OUTER else Direction.INNER

            if not self._hold_mode:
                self.debug_panel.blink(times=2)
            self.platform.move_direction(direction, self._button_checker(button_press))
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
