"""Digital I/O polling logic for a single Eletechsup Modbus IO board.

Ported from the legacy C# `ModbusIoDevice`: inputs are read as holding
registers starting at 192 and unpacked into bits (little-endian per
register); outputs are packed into bits and written back one register at a
time starting at 112.
"""
from __future__ import annotations

import logging
import math

from .const import BOARD_IO_COUNT, INPUT_REGISTER_START, OUTPUT_REGISTER_START
from .modbus_master import ModbusMaster, ModbusMasterError

_LOGGER = logging.getLogger(__name__)


class IoBoard:
    """Owns the input/output bit state for one Modbus IO board."""

    def __init__(self, name: str, master: ModbusMaster, address: int, board_type: str, mode: str) -> None:
        self.name = name
        self.address = address
        self.board_type = board_type
        self.mode = mode
        self._master = master
        self.io_count = BOARD_IO_COUNT[board_type]
        self._register_count = math.ceil(self.io_count / 16)

        self.inputs: list[bool] = [False] * self.io_count
        self.outputs: list[bool] = [False] * self.io_count

    def poll(self) -> bool:
        """Read inputs and write pending outputs. Returns True if inputs changed."""
        changed = False
        if self.mode in ("input", "input_output"):
            changed = self._read_inputs()
        if self.mode in ("output", "input_output"):
            self._write_outputs()
        return changed

    def set_output(self, index: int, value: bool) -> None:
        """Set a single 0-based output bit; written to the bus on the next poll."""
        self.outputs[index] = value

    def _read_inputs(self) -> bool:
        registers = self._master.read_holding_registers(
            self.address, INPUT_REGISTER_START, self._register_count
        )
        bits = _registers_to_bits(registers, self.io_count)
        changed = bits != self.inputs
        self.inputs = bits
        return changed

    def _write_outputs(self) -> None:
        registers = _bits_to_registers(self.outputs)
        for offset, register in enumerate(registers):
            self._master.write_registers(self.address, OUTPUT_REGISTER_START + offset, [register])


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
