"""MQTT discovery entities for a Modbus IO board.

Exposes inputs as `binary_sensor` entities and outputs as `switch` entities
using the built-in MQTT integration (no custom Home Assistant component
required - same approach as the uDMX add-on's `light.mqtt` entities).
"""
from __future__ import annotations

import json
import re
from typing import Any

from .io_board import IoBoard

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    return _SLUG_RE.sub("_", name.lower()).strip("_")


def dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload)


class BoardEntities:
    """Builds MQTT discovery configs and topics for one board's I/O points."""

    def __init__(self, board: IoBoard) -> None:
        self.board = board
        self.slug = _slugify(board.name)
        self.availability_topic = f"modbusio/{self.slug}/status"

    def input_topic(self, index: int) -> str:
        return f"modbusio/{self.slug}/input/{index + 1}/state"

    def output_command_topic(self, index: int) -> str:
        return f"modbusio/{self.slug}/output/{index + 1}/set"

    def output_state_topic(self, index: int) -> str:
        return f"modbusio/{self.slug}/output/{index + 1}/state"

    def input_discovery(self, discovery_prefix: str, index: int) -> tuple[str, dict[str, Any]]:
        object_id = f"{self.slug}_input_{index + 1}"
        topic = f"{discovery_prefix}/binary_sensor/modbusio/{object_id}/config"
        payload = {
            "name": f"{self.board.name} Input {index + 1}",
            "unique_id": f"modbusio_{object_id}",
            "state_topic": self.input_topic(index),
            "payload_on": "ON",
            "payload_off": "OFF",
            "availability_topic": self.availability_topic,
            "device": self._device_info(),
        }
        return topic, payload

    def output_discovery(self, discovery_prefix: str, index: int) -> tuple[str, dict[str, Any]]:
        object_id = f"{self.slug}_output_{index + 1}"
        topic = f"{discovery_prefix}/switch/modbusio/{object_id}/config"
        payload = {
            "name": f"{self.board.name} Output {index + 1}",
            "unique_id": f"modbusio_{object_id}",
            "command_topic": self.output_command_topic(index),
            "state_topic": self.output_state_topic(index),
            "payload_on": "ON",
            "payload_off": "OFF",
            "availability_topic": self.availability_topic,
            "device": self._device_info(),
        }
        return topic, payload

    def _device_info(self) -> dict[str, Any]:
        return {
            "identifiers": [f"modbusio_{self.slug}"],
            "name": self.board.name,
            "manufacturer": "Eletechsup",
            "model": self.board.board_type,
        }
