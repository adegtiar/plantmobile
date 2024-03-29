import time
from typing import Callable, Optional, no_type_check

from plantmobile.common import Output, Status
from plantmobile.logger import StatusPrinter
from plantmobile.output_device import TonalBuzzer, DirectionalLeds, PositionDisplay

# The tone to buzz on motor error.
ERROR_TONE_HZ = 220


class DebugPanel(Output):
    def __init__(self, *outputs: Output, buzzer: Optional[TonalBuzzer] = None) -> None:
        self.outputs = outputs
        self.buzzer = buzzer

        self.direction_leds = None
        self.position_display = None
        self.status_printer = None
        for output in outputs:
            if isinstance(output, PositionDisplay):
                self.position_display = output
            elif isinstance(output, DirectionalLeds):
                self.direction_leds = output
            elif isinstance(output, StatusPrinter):
                self.status_printer = output

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
        assert self.position_display or self.buzzer, \
                "position display or buzzer must be configured"

        def on():
            if self.position_display:
                self.position_display.show(output)
            if self.buzzer:
                self.buzzer.play(ERROR_TONE_HZ)

        def off():
            if self.position_display:
                self.position_display.off()
            if self.buzzer:
                self.buzzer.stop()
        self._blink(on, off, times=1, on_secs=1, off_secs=0.5)

    @no_type_check
    def blink(self, times: int = 2, pause_secs: float = 0.2) -> None:
        assert self.direction_leds, "LEDs must be configured"

        def on() -> None:
            self.direction_leds.on()

        def off() -> None:
            self.direction_leds.off()
        self._blink(on, off, times=2, on_secs=0.2, off_secs=0.2)
