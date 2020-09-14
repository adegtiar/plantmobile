import time
from typing import Iterator, Sequence, Tuple

import gpiozero

from plantmobile.common import Pin

BEAT_DURATION = 0.3


class Tune(object):
    def __init__(self, notes: Sequence[str], beats: Sequence[int]) -> None:
        assert len(notes) == len(beats), "beats and notes must be same length"
        self.notes = notes
        self.beats = beats

    def __iter__(self) -> Iterator[Tuple[str, float]]:
        """Returns an iterator over (note, beat_duration)"""
        for note, beat in zip(self.notes, self.beats):
            yield note, beat*BEAT_DURATION


class TonalBuzzer(gpiozero.TonalBuzzer):
    def __init__(self, pin: Pin) -> None:
        super(TonalBuzzer, self).__init__(pin.id)

    def play_tune(self, tune: Tune) -> None:
        for note, duration in tune:
            self.play(note)
            time.sleep(duration)
        self.stop()
