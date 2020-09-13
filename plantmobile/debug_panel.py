import time
from typing import Callable, Iterable, no_type_check, Optional

from plantmobile.common import ButtonPress, Output, Status
from plantmobile.input_device import Button
from plantmobile.output_device import TonalBuzzer, DirectionalLeds, PositionDisplay

# The tone to buzz on motor error.
ERROR_TONE_HZ = 220


class DebugPanel(Output):
    def __init__(self,
                 outer_button: Optional[Button] = None,
                 inner_button: Optional[Button] = None,
                 outputs: Iterable[Output] = (),
                 buzzer: Optional[TonalBuzzer] = None) -> None:
        self.outer_button = outer_button
        self.inner_button = inner_button
        self.buzzer = buzzer
        self.outputs = list(outputs)

        self._direction_leds = None
        self._position_display = None
        for output in outputs:
            if isinstance(output, PositionDisplay):
                self._position_display = output
            elif isinstance(output, DirectionalLeds):
                self._direction_leds = output

    def setup(self) -> None:
        """Initialize all components of the debug panel.

        This sets up connections and initializes default state. Any obvious failures in the hardware
        should trigger here.
        """
        for output in self.outputs:
            output.setup()

    def off(self) -> None:
        """Cleans up and resets any local state and outputs."""
        for output in self.outputs:
            output.off()

    def output_status(self, status: Status) -> None:
        """Updates the indicators and logs with the given status."""
        for output in self.outputs:
            output.output_status(status)

    def _blink(self, on: Callable, off: Callable,
               times: int, on_secs: float, off_secs: float) -> None:
        for i in range(times):
            on()
            time.sleep(on_secs)
            off()
            if i != times-1:
                time.sleep(off_secs)

    @no_type_check
    def output_error(self, output: str) -> None:
        assert self._position_display and self.buzzer, \
                "position display and buzzer must be configured"

        def on():
            self._position_display.show(output)
            self.buzzer.play(ERROR_TONE_HZ)

        def off():
            self._position_display.off()
            self.buzzer.stop()
        self._blink(on, off, times=1, on_secs=1, off_secs=0.5)

    @no_type_check
    def blink(self, times: int = 2, pause_secs: float = 0.2) -> None:
        assert self._direction_leds, "LEDs must be configured"

        def on() -> None:
            self._direction_leds.on()

        def off() -> None:
            self._direction_leds.off()
        self._blink(on, off, times=2, on_secs=0.2, off_secs=0.2)

    def get_directional_buttons(self) -> ButtonPress:
        """Gets the current button press status."""
        return ButtonPress.from_buttons(
                outer_pressed=bool(self.outer_button and self.outer_button.is_pressed),
                inner_pressed=bool(self.inner_button and self.inner_button.is_pressed))
