import logging
import time
from typing import Callable

from .controller import Controller
from plantmobile.common import Status
from plantmobile.platform_driver import MobilePlatform


class BatteryKeepAlive(Controller):
    # TODO: assert that voltage increased?

    def __init__(self,
                 platform: MobilePlatform,
                 ping_interval_secs: float,
                 ping_duration_secs: float,
                 enabled: Callable[[], bool] = lambda: True,
                 ) -> None:
        assert ping_interval_secs > 0, "Ping interval must be positive"
        self.platform = platform
        self.ping_interval_secs = ping_interval_secs
        self.ping_duration_secs = ping_duration_secs
        self.enabled = enabled
        self._last_ping = float("-inf")

    def perform_action(self, status: Status) -> bool:
        if not self.enabled():
            # Reset the counter so it will attempt to ping when enabled.
            self._last_ping = float("-inf")
            return False

        now = time.time()
        if now - self._last_ping > self.ping_interval_secs:
            logging.info("%d seconds elapsed: running keepalive ping for %.1f seconds",
                         self.ping_interval_secs, self.ping_duration_secs)
            self._last_ping = now
            self.platform.ping_motor(status, self.ping_duration_secs)
            return True
        return False
