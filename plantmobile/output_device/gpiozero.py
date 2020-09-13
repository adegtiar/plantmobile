import gpiozero

from plantmobile.common import Pin


class LED(gpiozero.LED):
    def __init__(self, pin: Pin) -> None:
        super(LED, self).__init__(pin.id)


class TonalBuzzer(gpiozero.TonalBuzzer):
    def __init__(self, pin: Pin) -> None:
        super(TonalBuzzer, self).__init__(pin.id)
