"""Entry point for the Modbus IO (Eletechsup) add-on.

Reads the add-on options, opens the shared Modbus RTU serial connection,
connects to the configured MQTT broker, publishes MQTT discovery configs for
each board's inputs (binary_sensor) and outputs (switch) - or `button`/`light`
for points overridden via the `entities` option - and polls each board on its
own background thread in parallel.
"""
from __future__ import annotations

import json
import logging
import os
import re
import signal
import sys
import threading
from types import FrameType

import paho.mqtt.client as mqtt

from .button import ButtonDetector
from .const import ENTITY_TYPE_BUTTON, ENTITY_TYPE_LIGHT, OPTIONS_FILE
from .io_board import IoBoard
from .modbus_master import ModbusMaster, ModbusMasterError
from .mqtt_io import BoardEntities, dumps

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_LOGGER = logging.getLogger("modbusio")

_POINT_RE = re.compile(r"^(input|output)-(\d+)$")


def _load_options() -> dict:
    with open(OPTIONS_FILE, encoding="utf-8") as handle:
        return json.load(handle)


def _log_serial_devices() -> None:
    """Log available stable serial device paths to help diagnose port config."""
    by_path_dir = "/dev/serial/by-path"
    try:
        devices = sorted(os.listdir(by_path_dir))
    except OSError as err:
        _LOGGER.info("No serial devices found in %s (%s)", by_path_dir, err)
        return
    if devices:
        _LOGGER.info("Available serial devices in %s: %s", by_path_dir, ", ".join(devices))
    else:
        _LOGGER.info("No serial devices found in %s", by_path_dir)


def _mqtt_settings(options: dict) -> tuple[str, int, str | None, str | None]:
    """MQTT connection info: env vars set by run.sh (Supervisor service or
    manual fallback) take precedence over the raw add-on options."""
    host = os.environ.get("MQTT_HOST") or options.get("mqtt_host")
    port = int(os.environ.get("MQTT_PORT") or options.get("mqtt_port") or 1883)
    username = os.environ.get("MQTT_USERNAME") or options.get("mqtt_username") or None
    password = os.environ.get("MQTT_PASSWORD") or options.get("mqtt_password") or None
    if not host:
        raise ModbusMasterError("No MQTT broker configured (Supervisor service unavailable and mqtt_host is empty)")
    _LOGGER.info(
        "MQTT broker: %s:%d (username=%s, password=%s)",
        host,
        port,
        username or "<none>",
        "<set>" if password else "<none>",
    )
    return host, port, username, password


def _parse_entity_overrides(
    options: dict,
) -> tuple[dict[tuple[str, int], str | None], dict[tuple[str, int], str | None]]:
    """Parse the `entities` option into per-point button/light overrides.

    Keys are (board_name, 0-based index); values are the custom entity name
    (or None for the default generated name). Unlisted points keep the
    default binary_sensor (input) / switch (output) entity.
    """
    button_overrides: dict[tuple[str, int], str | None] = {}
    light_overrides: dict[tuple[str, int], str | None] = {}
    for entity_config in options.get("entities", []):
        match = _POINT_RE.match(entity_config["point"])
        if not match:
            _LOGGER.warning("Ignoring entity %r: invalid point %r", entity_config.get("name"), entity_config["point"])
            continue
        kind = match.group(1)
        key = (entity_config["board"], int(match.group(2)) - 1)
        name = entity_config.get("name") or None
        entity_type = entity_config["type"]
        if entity_type == ENTITY_TYPE_BUTTON and kind == "input":
            button_overrides[key] = name
        elif entity_type == ENTITY_TYPE_LIGHT and kind == "output":
            light_overrides[key] = name
        else:
            _LOGGER.warning(
                "Ignoring entity %r: type %r is not valid for point %r",
                name, entity_type, entity_config["point"],
            )
    return button_overrides, light_overrides


def _build_boards(options: dict) -> tuple[list[IoBoard], list[ModbusMaster]]:
    """Build boards, opening one shared ModbusMaster per unique port/baudrate/parity."""
    masters: dict[tuple[str, int, str], ModbusMaster] = {}
    boards: list[IoBoard] = []
    for board_config in options.get("boards", []):
        bus_key = (board_config["port"], board_config["baudrate"], board_config.get("parity", "N"))
        master = masters.get(bus_key)
        if master is None:
            master = ModbusMaster(port=bus_key[0], baudrate=bus_key[1], parity=bus_key[2])
            master.open()
            masters[bus_key] = master
        boards.append(
            IoBoard(
                board_config["name"],
                master,
                board_config["address"],
                board_config["type"],
                board_config["mode"],
                board_config["poll_interval_ms"],
            )
        )
    return boards, list(masters.values())


def main() -> None:
    options = _load_options()
    _log_serial_devices()

    try:
        boards, masters = _build_boards(options)
    except ModbusMasterError as err:
        _LOGGER.error("%s", err)
        sys.exit(1)

    entities = {board.name: BoardEntities(board) for board in boards}
    discovery_prefix = options.get("discovery_prefix", "homeassistant")
    button_overrides, light_overrides = _parse_entity_overrides(options)

    try:
        mqtt_host, mqtt_port, mqtt_username, mqtt_password = _mqtt_settings(options)
    except ModbusMasterError as err:
        _LOGGER.error("%s", err)
        sys.exit(1)

    client = mqtt.Client()
    if mqtt_username:
        client.username_pw_set(mqtt_username, mqtt_password)

    output_topics: dict[str, tuple[IoBoard, int]] = {}

    long_press_s = options.get("long_press_time_ms", 1000) / 1000
    double_click_s = options.get("double_click_time_ms", 300) / 1000
    button_detectors: dict[tuple[str, int], ButtonDetector] = {}
    for board_name, index in button_overrides:
        board_entities = entities[board_name]

        def _on_state(state: str, board_entities: BoardEntities = board_entities, index: int = index) -> None:
            client.publish(board_entities.input_button_topic(index), state, retain=False)

        button_detectors[(board_name, index)] = ButtonDetector(long_press_s, double_click_s, _on_state)

    def on_connect(client: mqtt.Client, _userdata, _flags, _rc) -> None:
        _LOGGER.info("Connected to MQTT broker, publishing %d board(s)", len(boards))
        for board in boards:
            board_entities = entities[board.name]
            client.publish(board_entities.availability_topic, "online", retain=True)

            if board.mode in ("input", "input_output"):
                for index in range(board.io_count):
                    button_name = button_overrides.get((board.name, index))
                    if (board.name, index) in button_overrides:
                        topic, payload = board_entities.input_button_discovery(discovery_prefix, index, button_name)
                        client.publish(topic, dumps(payload), retain=True)
                        client.publish(board_entities.input_button_topic(index), "none", retain=True)
                    else:
                        topic, payload = board_entities.input_discovery(discovery_prefix, index)
                        client.publish(topic, dumps(payload), retain=True)
                        client.publish(board_entities.input_topic(index), "OFF", retain=True)

            if board.mode in ("output", "input_output"):
                for index in range(board.io_count):
                    light_name = light_overrides.get((board.name, index))
                    if (board.name, index) in light_overrides:
                        topic, payload = board_entities.output_light_discovery(discovery_prefix, index, light_name)
                    else:
                        topic, payload = board_entities.output_discovery(discovery_prefix, index)
                    client.publish(topic, dumps(payload), retain=True)
                    client.publish(board_entities.output_state_topic(index), "OFF", retain=True)
                    command_topic = board_entities.output_command_topic(index)
                    output_topics[command_topic] = (board, index)
                    client.subscribe(command_topic)

    def on_message(client: mqtt.Client, _userdata, message: mqtt.MQTTMessage) -> None:
        target = output_topics.get(message.topic)
        if target is None:
            return
        board, index = target
        value = message.payload.decode("utf-8").strip().upper() == "ON"
        board.set_output(index, value)
        client.publish(entities[board.name].output_state_topic(index), "ON" if value else "OFF", retain=True)

    client.on_connect = on_connect
    client.on_message = on_message

    stop_event = threading.Event()

    def poll_loop(board: IoBoard) -> None:
        board_entities = entities[board.name]
        while not stop_event.is_set():
            previous_inputs = list(board.inputs)
            try:
                changed = board.poll()
            except ModbusMasterError as err:
                _LOGGER.warning("Board %s poll failed: %s", board.name, err)
            else:
                if changed:
                    for index, value in enumerate(board.inputs):
                        detector = button_detectors.get((board.name, index))
                        if detector is not None:
                            if value != previous_inputs[index]:
                                detector.handle_edge(value)
                        else:
                            client.publish(board_entities.input_topic(index), "ON" if value else "OFF", retain=True)
            stop_event.wait(board.poll_interval)

    def handle_shutdown(_signum: int, _frame: FrameType | None) -> None:
        _LOGGER.info("Shutting down")
        stop_event.set()
        for board_entities in entities.values():
            client.publish(board_entities.availability_topic, "offline", retain=True)
        client.disconnect()
        for master in masters:
            master.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    client.connect(mqtt_host, mqtt_port)

    # One thread per board so a slow/unresponsive board can't delay the others;
    # actual bus access is still serialized by the ModbusMaster's lock.
    for board in boards:
        threading.Thread(target=poll_loop, name=f"modbusio_poll_{board.name}", args=(board,), daemon=True).start()

    client.loop_forever()


if __name__ == "__main__":
    main()
