"""Modbus RTU serial master shared by all configured IO boards.

Wraps pymodbus's serial client with a lock, since a single RS485 bus can only
handle one in-flight request at a time no matter how many boards share it.
"""
from __future__ import annotations

import logging
import threading

from pymodbus.client import ModbusSerialClient

from .const import INPUT_REGISTER_START, OUTPUT_REGISTER_START

_LOGGER = logging.getLogger(__name__)

# Special `port` value that simulates a board instead of opening a real bus.
DUMMY_PORT = "dummy"


class ModbusMasterError(Exception):
    """Raised when the Modbus serial connection cannot be opened or used."""


class ModbusMaster:
    """Owns the serial connection; all boards on the bus reuse this instance."""

    def __init__(self, port: str, baudrate: int, parity: str = "N") -> None:
        self._port = port
        self._lock = threading.Lock()
        self._dummy = port == DUMMY_PORT
        self._dummy_registers: dict[int, dict[int, int]] = {}
        self._client = None if self._dummy else ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            parity=parity,
            bytesize=8,
            stopbits=1,
            timeout=1,
        )

    def open(self) -> None:
        if self._dummy:
            _LOGGER.info("Port 'dummy' configured: simulating bus, no serial connection opened")
            return
        if not self._client.connect():
            raise ModbusMasterError(f"Failed to open Modbus serial port {self._port}")

    def close(self) -> None:
        if self._dummy:
            return
        self._client.close()

    def read_holding_registers(self, slave_address: int, start_address: int, count: int) -> list[int]:
        if self._dummy:
            with self._lock:
                registers = self._dummy_registers.setdefault(slave_address, {})
                return [registers.get(start_address + offset, 0) for offset in range(count)]
        with self._lock:
            result = self._client.read_holding_registers(start_address, count=count, slave=slave_address)
        if result.isError():
            raise ModbusMasterError(f"Read holding registers failed: {result}")
        return result.registers

    def write_registers(self, slave_address: int, start_address: int, values: list[int]) -> None:
        if self._dummy:
            with self._lock:
                registers = self._dummy_registers.setdefault(slave_address, {})
                for offset, value in enumerate(values):
                    address = start_address + offset
                    registers[address] = value
                    # Loop outputs back to the matching input bit so the
                    # simulated board mirrors what was just written.
                    if start_address >= OUTPUT_REGISTER_START:
                        registers[INPUT_REGISTER_START + (address - OUTPUT_REGISTER_START)] = value
            return
        with self._lock:
            result = self._client.write_registers(start_address, values, slave=slave_address)
        if result.isError():
            raise ModbusMasterError(f"Write holding registers failed: {result}")
