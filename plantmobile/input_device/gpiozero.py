import gpiozero

from plantmobile.common import Pin


class Button(gpiozero.Button):
    def __init__(self, pin: Pin):
        super(Button, self).__init__(pin.id)
