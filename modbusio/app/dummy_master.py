"""In-memory stand-in for `ModbusMaster`, selected via the `dummy` port value.

Used instead of opening a real serial connection, so a board can be tested
without any hardware attached. Writes to the output register range are
looped back onto the matching input register range, so the simulated board
mirrors whatever it's told to output.
"""
from __future__ import annotations

import logging
import threading

from .const import INPUT_REGISTER_START, OUTPUT_REGISTER_START

_LOGGER = logging.getLogger(__name__)

# Special `port` value that simulates a board instead of opening a real bus.
DUMMY_PORT = "dummy"


class DummyModbusMaster:
    """Simulates a bus in memory, with the same interface as `ModbusMaster`."""

    def __init__(self, port: str) -> None:
        self._port = port
        self._lock = threading.Lock()
        self._registers: dict[int, dict[int, int]] = {}

    def open(self) -> None:
        _LOGGER.info("Port 'dummy' configured: simulating bus, no serial connection opened")

    def close(self) -> None:
        return

    def read_holding_registers(self, slave_address: int, start_address: int, count: int) -> list[int]:
        with self._lock:
            registers = self._registers.setdefault(slave_address, {})
            return [registers.get(start_address + offset, 0) for offset in range(count)]

    def write_registers(self, slave_address: int, start_address: int, values: list[int]) -> None:
        with self._lock:
            registers = self._registers.setdefault(slave_address, {})
            for offset, value in enumerate(values):
                address = start_address + offset
                registers[address] = value
                # Loop outputs back to the matching input bit so the
                # simulated board mirrors what was just written.
                if start_address >= OUTPUT_REGISTER_START:
                    registers[INPUT_REGISTER_START + (address - OUTPUT_REGISTER_START)] = value
