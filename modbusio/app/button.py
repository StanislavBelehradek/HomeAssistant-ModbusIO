"""Press-pattern detection for inputs configured as a `button` entity.

Turns raw press/release edges into single/double/long press pulses, reported
through a callback as one of the `BUTTON_STATES` (with "none" as the idle
state in between). Timing mirrors the long-press/double-click detection used
by the HomeAssistant-VirtualDevices custom component's `event.py`.
"""
from __future__ import annotations

import threading
from typing import Callable

from .const import (
    BUTTON_RESET_DELAY_S,
    BUTTON_STATE_DOUBLE,
    BUTTON_STATE_LONG,
    BUTTON_STATE_NONE,
    BUTTON_STATE_SINGLE,
)


class ButtonDetector:
    """Detects single/double/long press patterns from raw press/release edges."""

    def __init__(
        self,
        long_press_s: float,
        double_click_s: float,
        on_state: Callable[[str], None],
    ) -> None:
        self._long_press_s = long_press_s
        self._double_click_s = double_click_s
        self._on_state = on_state
        self._long_press_timer: threading.Timer | None = None
        self._double_click_timer: threading.Timer | None = None
        self._long_press_fired = False

    def handle_edge(self, pressed: bool) -> None:
        """Feed a raw press (True) or release (False) edge into the detector."""
        if pressed:
            self._on_press()
        else:
            self._on_release()

    def _on_press(self) -> None:
        self._long_press_fired = False
        self._cancel(self._long_press_timer)
        self._long_press_timer = self._start_timer(self._long_press_s, self._fire_long_press)

    def _fire_long_press(self) -> None:
        self._long_press_timer = None
        self._long_press_fired = True
        self._emit(BUTTON_STATE_LONG)

    def _on_release(self) -> None:
        self._cancel(self._long_press_timer)
        self._long_press_timer = None
        if self._long_press_fired:
            return
        if self._double_click_timer is not None:
            self._cancel(self._double_click_timer)
            self._double_click_timer = None
            self._emit(BUTTON_STATE_DOUBLE)
            return
        self._double_click_timer = self._start_timer(self._double_click_s, self._fire_single_press)

    def _fire_single_press(self) -> None:
        self._double_click_timer = None
        self._emit(BUTTON_STATE_SINGLE)

    def _emit(self, state: str) -> None:
        self._on_state(state)
        self._start_timer(BUTTON_RESET_DELAY_S, lambda: self._on_state(BUTTON_STATE_NONE))

    @staticmethod
    def _start_timer(delay_s: float, callback: Callable[[], None]) -> threading.Timer:
        timer = threading.Timer(delay_s, callback)
        timer.daemon = True
        timer.start()
        return timer

    @staticmethod
    def _cancel(timer: threading.Timer | None) -> None:
        if timer is not None:
            timer.cancel()
