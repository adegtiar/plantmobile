import RPi.GPIO as GPIO
from RpiMotorLib import RpiMotorLib  # type: ignore

from plantmobile.common import Component, Pin, Rotation

# Suggested pause secs for a half step of the 28BYJ motor.
PAUSE_SECS = 0.001
# This type is a bit smoother, and supports a lower PAUSE_SECS than "full".
STEP_TYPE = "half"


class StepperMotor(Component):
    """The stepper motor moves in discrete steps and so can be used to track rotations."""

    def __init__(self, pin1: Pin, pin2: Pin, pin3: Pin, pin4: Pin) -> None:
        self.pins = [pin.id for pin in (pin1, pin2, pin3, pin4)]
        self._motor = RpiMotorLib.BYJMotor("Stepper", "28BYJ")

    def setup(self) -> None:
        for pin in self.pins:
            GPIO.setup(pin, GPIO.OUT)

    def off(self) -> None:
        """Reset the motor to stopped."""
        for pin in self.pins:
            GPIO.output(pin, GPIO.LOW)

    def all_on(self) -> None:
        """Set all the outputs of the motor to high. Only useful for lights.

        Warning: this drains a fair bit of current so use sparingly.
        """
        for pin in self.pins:
            GPIO.output(pin, GPIO.HIGH)

    def move_steps(self, rotation: Rotation, steps: int = 1) -> None:
        """Rotate the motor one period.

        Note: this is technically 4 steps for convenience of implementation."""
        self._motor.motor_run(
                self.pins, wait=PAUSE_SECS, steps=steps,
                ccwise=rotation is Rotation.CCW, steptype=STEP_TYPE)
