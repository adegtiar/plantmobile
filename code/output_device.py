import gpiozero

from common import Pin
from led_outputs import DirectionalLeds, LedBarGraphs, LuxDiffDisplay, PositionDisplay  # noqa
from motor import StepperMotor # noqa


class TonalBuzzer(gpiozero.TonalBuzzer):
    def __init__(self, pin: Pin) -> None:
        super(TonalBuzzer, self).__init__(pin.id)
