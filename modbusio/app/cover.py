"""Position-simulated `cover` entity, driven by a pair of relay outputs.

Ported from the legacy C# `CoverEntity`: the boards report no real position
feedback, so a cover's position is estimated from how long its drive relays
have been energized versus the configured `open_time_ms`, interpolating and
publishing it every `COVER_POSITION_PUBLISH_INTERVAL_S` while moving.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from .const import (
    COVER_CONTROL_UP_DOWN,
    COVER_POSITION_CLOSED,
    COVER_POSITION_OPEN,
    COVER_POSITION_PUBLISH_INTERVAL_S,
    COVER_STATE_CLOSED,
    COVER_STATE_CLOSING,
    COVER_STATE_OPEN,
    COVER_STATE_OPENING,
    COVER_STATE_STOPPED,
)
from .io_board import IoBoard

PAYLOAD_OPEN = "OPEN"
PAYLOAD_CLOSE = "CLOSE"
PAYLOAD_STOP = "STOP"


class CoverController:
    """Drives a cover's two output relays and simulates its position/state."""

    def __init__(
        self,
        name: str,
        board: IoBoard,
        output_first: int,
        output_second: int,
        control_mode: str,
        open_time_ms: int,
        on_state: Callable[[str], None],
        on_position: Callable[[int], None],
    ) -> None:
        self.name = name
        self._board = board
        self._output_first = output_first
        self._output_second = output_second
        self._control_mode = control_mode
        self._open_time_ms = open_time_ms
        self._on_state = on_state
        self._on_position = on_position

        self._lock = threading.Lock()
        self._position: int | None = None
        self._cancel_event: threading.Event | None = None

    def handle_command(self, payload: str) -> None:
        payload = payload.strip().upper()
        if payload == PAYLOAD_STOP:
            self._stop()
        elif payload == PAYLOAD_OPEN:
            self.move_to(COVER_POSITION_OPEN)
        elif payload == PAYLOAD_CLOSE:
            self.move_to(COVER_POSITION_CLOSED)

    def handle_set_position(self, payload: str) -> None:
        try:
            position = int(payload)
        except ValueError:
            return
        self.move_to(position)

    def _stop(self) -> None:
        with self._lock:
            self._cancel_movement()
            self._set_outputs(False, False)
            self._on_state(COVER_STATE_STOPPED)
            if self._position is not None:
                self._on_position(self._position)

    def move_to(self, desired_position: int) -> None:
        desired_position = max(COVER_POSITION_CLOSED, min(COVER_POSITION_OPEN, desired_position))
        with self._lock:
            self._cancel_movement()

            current_position = self._position
            # Already there: nudge off an extreme so a re-open/re-close still
            # moves; otherwise there's nothing to do.
            if current_position == desired_position:
                if current_position == COVER_POSITION_OPEN:
                    current_position = COVER_POSITION_OPEN - 10
                elif desired_position == COVER_POSITION_CLOSED:
                    current_position = COVER_POSITION_CLOSED + 10
                else:
                    return

            start_position = (
                current_position
                if current_position is not None
                else (COVER_POSITION_CLOSED if desired_position > 50 else COVER_POSITION_OPEN)
            )
            distance = abs(desired_position - start_position)
            total_move_time_s = 0.0 if distance == 0 else distance * self._open_time_ms / COVER_POSITION_OPEN / 1000
            move_up = desired_position > start_position

            self._position = start_position
            cancel_event = threading.Event()
            self._cancel_event = cancel_event

            self._on_state(COVER_STATE_OPENING if move_up else COVER_STATE_CLOSING)
            self._on_position(start_position)
            self._drive(move_up)

            threading.Thread(
                target=self._run_movement,
                args=(start_position, desired_position, total_move_time_s, cancel_event),
                daemon=True,
                name=f"cover_{self.name}",
            ).start()

    def _run_movement(
        self, start_position: int, desired_position: int, total_move_time_s: float, cancel_event: threading.Event
    ) -> None:
        start_time = time.monotonic()
        while True:
            if cancel_event.is_set():
                return
            elapsed_s = min(time.monotonic() - start_time, total_move_time_s)
            progress = 1.0 if total_move_time_s == 0 else elapsed_s / total_move_time_s
            position = start_position + round((desired_position - start_position) * progress)
            position = max(min(start_position, desired_position), min(max(start_position, desired_position), position))

            with self._lock:
                if cancel_event.is_set():
                    return
                self._position = position
            self._on_position(position)

            if elapsed_s >= total_move_time_s:
                break
            if cancel_event.wait(COVER_POSITION_PUBLISH_INTERVAL_S):
                return

        with self._lock:
            if cancel_event.is_set():
                return
            self._set_outputs(False, False)
            self._position = desired_position

        if desired_position == COVER_POSITION_OPEN:
            self._on_state(COVER_STATE_OPEN)
        elif desired_position == COVER_POSITION_CLOSED:
            self._on_state(COVER_STATE_CLOSED)
        else:
            self._on_state(COVER_STATE_STOPPED)
        self._on_position(desired_position)

    def _cancel_movement(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()
            self._cancel_event = None

    def _drive(self, move_up: bool) -> None:
        if self._control_mode == COVER_CONTROL_UP_DOWN:
            self._set_outputs(move_up, not move_up)
        else:
            self._set_outputs(True, move_up)

    def _set_outputs(self, first_value: bool, second_value: bool) -> None:
        self._board.set_output(self._output_first, first_value)
        self._board.set_output(self._output_second, second_value)
