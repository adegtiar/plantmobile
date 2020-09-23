import logging
import time
from abc import ABC, abstractmethod
from typing import List, NoReturn

from plantmobile.common import Status
from plantmobile.debug_panel import DebugPanel
from plantmobile.logger import StatusPrinter
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
        status_printer: StatusPrinter,
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
        status_printer.output_status(status)

        # TODO: refactor in terms of steps/changes?
        try:
            for controller in controllers:
                if controller.perform_action(status):
                    logging.debug("Performed action from %s", controller)
                    break
        except BatteryError:
            logging.warning("insufficient battery voltage: is the power bank enabled?")
            debug_panel.output_error("BATT")

        time.sleep(CONTROL_LOOP_SLEEP_SECS)
