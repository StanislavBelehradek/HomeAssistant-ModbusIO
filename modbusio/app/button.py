"""Press-pattern detection for inputs configured as a `button` entity.

Turns raw press/release edges into single/double/long press pulses, reported
through a callback as one of the `BUTTON_STATES` (with "none" as the idle
state in between). "single" is reported immediately on press, then upgraded
to "double" or "long" if a second press or a long hold follows.
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
        self._reset_timer: threading.Timer | None = None
        self._long_press_fired = False

    def handle_edge(self, pressed: bool) -> None:
        """Feed a raw press (True) or release (False) edge into the detector."""
        if pressed:
            self._on_press()
        else:
            self._on_release()

    def _on_press(self) -> None:
        self._long_press_fired = False
        self._long_press_timer = self._start_timer(self._long_press_s, self._fire_long_press)
        if self._double_click_timer is not None:
            # Second press within the window: upgrade the already-emitted single to a double.
            self._cancel(self._double_click_timer)
            self._double_click_timer = None
            self._emit(BUTTON_STATE_DOUBLE)
        else:
            # Report a press immediately; it may still be upgraded to double/long later.
            self._emit(BUTTON_STATE_SINGLE)

    def _fire_long_press(self) -> None:
        self._long_press_timer = None
        self._long_press_fired = True
        self._emit(BUTTON_STATE_LONG)

    def _on_release(self) -> None:
        self._cancel(self._long_press_timer)
        self._long_press_timer = None
        if self._long_press_fired:
            return
        self._double_click_timer = self._start_timer(self._double_click_s, self._clear_double_click_window)

    def _clear_double_click_window(self) -> None:
        self._double_click_timer = None

    def _emit(self, state: str) -> None:
        self._cancel(self._reset_timer)
        self._on_state(state)
        self._reset_timer = self._start_timer(BUTTON_RESET_DELAY_S, self._fire_reset)

    def _fire_reset(self) -> None:
        self._reset_timer = None
        self._on_state(BUTTON_STATE_NONE)

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
