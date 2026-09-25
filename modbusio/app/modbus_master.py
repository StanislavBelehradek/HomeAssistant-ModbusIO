"""Modbus RTU serial master shared by all configured IO boards.

Wraps pymodbus's serial client with a lock, since a single RS485 bus can only
handle one in-flight request at a time no matter how many boards share it.
"""
from __future__ import annotations

import logging
import threading

from pymodbus.client import ModbusSerialClient

_LOGGER = logging.getLogger(__name__)


class ModbusMasterError(Exception):
    """Raised when the Modbus serial connection cannot be opened or used."""


class ModbusMaster:
    """Owns the serial connection; all boards on the bus reuse this instance."""

    def __init__(self, port: str, baudrate: int, parity: str = "N") -> None:
        self._port = port
        self._lock = threading.Lock()
        self._client = ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            parity=parity,
            bytesize=8,
            stopbits=1,
            timeout=1,
        )

    def open(self) -> None:
        if not self._client.connect():
            raise ModbusMasterError(f"Failed to open Modbus serial port {self._port}")

    def close(self) -> None:
        self._client.close()

    def read_holding_registers(self, slave_address: int, start_address: int, count: int) -> list[int]:
        with self._lock:
            result = self._client.read_holding_registers(start_address, count=count, slave=slave_address)
        if result.isError():
            raise ModbusMasterError(f"Read holding registers failed: {result}")
        return result.registers

    def write_registers(self, slave_address: int, start_address: int, values: list[int]) -> None:
        with self._lock:
            result = self._client.write_registers(start_address, values, slave=slave_address)
        if result.isError():
            raise ModbusMasterError(f"Write holding registers failed: {result}")
