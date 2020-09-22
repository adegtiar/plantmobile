import gpiozero
from typing import Callable, List, Optional

from plantmobile.common import Pin


class Button(gpiozero.Button):
    def __init__(self, pin: Pin):
        super(Button, self).__init__(pin.id)


class ToggleButton(Button):
    def __init__(self, pin: Pin):
        super(Button, self).__init__(pin.id)
        self._enabled = False
        self.when_pressed = self._toggle
        self._handlers: List[Callable] = []

    def add_press_handler(self, handler: Callable) -> None:
        self._handlers.append(handler)

    def enabled(self) -> bool:
        return self._enabled

    def toggle(self, enabled: Optional[bool] = None) -> None:
        if enabled is not None:
            # Toggle it to the opposite of the requested value, so the toggle callback will undo it.
            self._enabled = not enabled
        self._toggle()

    def _toggle(self, button: Optional[gpiozero.Button] = None) -> None:
        self._enabled = not self._enabled
        for handler in self._handlers:
            handler()
