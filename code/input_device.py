import gpiozero

from common import Pin
# These imports are moved here for convenience of importing.
# TODO: is there a better way to do this, e.g. in __init__.py?
from light_sensors import LightSensor  # noqa
from power_monitor import VoltageReader  # noqa
from ultrasonic_ranging import DistanceSensor  # noqa


class Button(gpiozero.Button):
    def __init__(self, pin: Pin):
        super(Button, self).__init__(pin.id)
