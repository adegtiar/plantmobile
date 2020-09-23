import logging
from typing import Callable, Optional

from .controller import Controller
from plantmobile.common import Direction, Status
from plantmobile.debug_panel import DebugPanel
from plantmobile.input_device import Button
from plantmobile.logger import StatusPrinter
from plantmobile.platform_driver import MobilePlatform


class ButtonHandler(Controller):
    """Controller for the mobile platform via two buttons.

    In hold mode, hold one of the buttons for movement and let go to stop.
    In press mode, press one of the buttons and it will move until it reaches an edge.
    """

    def __init__(self,
                 platform: MobilePlatform,
                 debug_panel: DebugPanel,
                 status_printer: StatusPrinter,
                 outer_button: Button,
                 inner_button: Button,
                 hold_button_threshold_secs: float = 0.1) -> None:
        self.platform = platform
        self.debug_panel = debug_panel
        self.status_printer = status_printer
        for button in (outer_button, inner_button):
            button.when_pressed = self._on_press
            button.when_held = self._on_hold
            button.when_released = self._on_release
            button.hold_time = hold_button_threshold_secs
        self.outer_button = outer_button
        self.inner_button = inner_button
        # In hold mode, hold the button down for movement.
        self._hold_mode = False
        self._direction_commanded: Optional[Direction] = None
        self._i = 0

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
            if self._i % 10 == 0:
                self.status_printer.output_status(status, force=True)
            self._i += 1
            return self._direction_commanded is direction_commanded
        return should_continue

    def perform_action(self, status: Status) -> bool:
        direction = self._direction_commanded
        if direction:
            try:
                self._i = 0
                self.platform.move_direction(direction, self._should_continue(direction))
                return True
            finally:
                # Clear the command if move_direction finished without cancellation.
                self._direction_commanded = None
        else:
            return False
