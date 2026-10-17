"""Digital I/O polling logic for a single Eletechsup Modbus IO board.

Ported from the legacy C# `ModbusIoDevice`: inputs are read as holding
registers starting at 192 and unpacked into bits (little-endian per
register); outputs are packed into bits and written back one register at a
time starting at 112.
"""
from __future__ import annotations

import logging
import math
import time
from collections import deque

from .const import BOARD_IO_COUNT, INPUT_REGISTER_START, OUTPUT_REGISTER_START
from .modbus_master import ModbusMaster

_LOGGER = logging.getLogger(__name__)

# Special `port` value that runs a board in simulation instead of over a real bus.
DUMMY_PORT = "dummy"

# Width of the sliding window used to average Modbus read/write call durations.
POLL_TIME_WINDOW_S = 1.0

# Floor for the dynamic master timeout, matching ModbusMaster's initial default.
MIN_MASTER_TIMEOUT_S = 0.2

# Safety margin applied to the measured call duration when sizing the master timeout.
TIMEOUT_MULTIPLIER = 2


class _DurationTracker:
    """Averages durations recorded within the trailing POLL_TIME_WINDOW_S."""

    def __init__(self) -> None:
        self._samples: deque[tuple[float, float]] = deque()

    def record(self, duration: float) -> None:
        now = time.monotonic()
        self._samples.append((now, duration))
        cutoff = now - POLL_TIME_WINDOW_S
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()

    @property
    def average_ms(self) -> float:
        if not self._samples:
            return 0.0
        durations = [duration for _, duration in self._samples]
        return sum(durations) / len(durations) * 1000

    @property
    def average_s(self) -> float:
        return self.average_ms / 1000


class IoBoard:
    """Owns the input/output bit state for one Modbus IO board.

    `master=None` (the `dummy` port) runs the board in simulation: outputs are
    looped back onto its own inputs instead of being sent to a bus.
    """

    def __init__(
        self,
        name: str,
        master: ModbusMaster | None,
        address: int,
        board_type: str,
        mode: str,
        poll_interval_ms: int,
    ) -> None:
        self.name = name
        self.address = address
        self.board_type = board_type
        self.mode = mode
        self.poll_interval = poll_interval_ms / 1000
        self._master = master
        self.io_count = BOARD_IO_COUNT[board_type]
        self._register_count = math.ceil(self.io_count / 16)

        self.inputs: list[bool] = [False] * self.io_count
        self.outputs: list[bool] = [False] * self.io_count

        self._read_durations = _DurationTracker()
        self._write_durations = _DurationTracker()

    def poll(self) -> bool:
        """Read inputs and write pending outputs. Returns True if inputs changed."""
        changed = False
        if self.mode in ("input", "input_output"):
            changed = self._read_inputs()
        if self.mode in ("output", "input_output"):
            self._write_outputs()
        return changed

    @property
    def average_read_time_ms(self) -> float:
        """Average read_holding_registers() call duration in ms, over the last POLL_TIME_WINDOW_S."""
        return self._read_durations.average_ms

    @property
    def average_write_time_ms(self) -> float:
        """Average write_registers() call duration in ms, over the last POLL_TIME_WINDOW_S."""
        return self._write_durations.average_ms

    def set_output(self, index: int, value: bool) -> None:
        """Set a single 0-based output bit; written to the bus on the next poll."""
        self.outputs[index] = value

    def _read_inputs(self) -> bool:
        if self._master is None:
            bits = list(self.outputs)
        else:
            start = time.monotonic()
            registers = self._master.read_holding_registers(
                self.address, INPUT_REGISTER_START, self._register_count
            )
            self._read_durations.record(time.monotonic() - start)
            self._update_timeout(self._read_durations)
            bits = _registers_to_bits(registers, self.io_count)
        changed = bits != self.inputs
        self.inputs = bits
        return changed

    def _write_outputs(self) -> None:
        if self._master is None:
            return
        registers = _bits_to_registers(self.outputs)
        for offset, register in enumerate(registers):
            start = time.monotonic()
            self._master.write_registers(self.address, OUTPUT_REGISTER_START + offset, [register])
            self._write_durations.record(time.monotonic() - start)
            self._update_timeout(self._write_durations)

    def _update_timeout(self, tracker: _DurationTracker) -> None:
        """Keep the master's serial timeout ahead of the call latency that was just observed."""
        self._master.set_timeout(max(MIN_MASTER_TIMEOUT_S, tracker.average_s * TIMEOUT_MULTIPLIER))


def _registers_to_bits(registers: list[int], count: int) -> list[bool]:
    bits: list[bool] = []
    for register in registers:
        bits.extend(bool((register >> bit_index) & 1) for bit_index in range(16))
    return bits[:count]


def _bits_to_registers(bits: list[bool]) -> list[int]:
    register_count = math.ceil(len(bits) / 16)
    registers = [0] * register_count
    for index, bit in enumerate(bits):
        if bit:
            registers[index // 16] |= 1 << (index % 16)
    return registers
