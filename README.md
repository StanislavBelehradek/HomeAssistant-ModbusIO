# HomeAssistant-ModbusIO

A Home Assistant **add-on** that talks Modbus RTU (RS485, e.g. via a
USB-to-RS485 adapter) to **Eletechsup M23IOxx** relay/opto-input boards
(M23IOA08, M23IOB16, M23IOC24, M23IOD32, M23IOE48, M23IOF64 - 8 to 64 digital
I/O points). Inputs and outputs are exposed to Home Assistant as regular
`binary_sensor`/`switch` entities through **MQTT discovery** (no custom
component required - just the built-in MQTT integration).

It runs as a standalone add-on (rather than a custom integration) so it can
own the serial port and poll the bus continuously without depending on Home
Assistant Core's Python environment.

## Features

- Talks Modbus RTU over a serial port (`pyserial`/`pymodbus`) to Eletechsup
  M23IOxx boards, one or more per bus (each board has its own slave address).
  Boards on the same `port`/`baudrate`/`parity` share a single serial
  connection; boards with different serial settings get their own.
- Publishes each board's digital inputs as `binary_sensor` entities and
  outputs as `switch` entities via MQTT discovery.
- Configurable per-board mode: `input`, `output`, or `input_output`.
- Configurable per-board poll interval and serial parameters (port/baudrate/parity).

## Installation

1. In Home Assistant, go to **Settings → Add-ons → Add-on Store → ⋮ →
   Repositories**, and add this repository's URL.
2. Install the **Modbus IO (Eletechsup)** add-on that appears in the store.
3. Configure the add-on: serial port/baudrate, MQTT broker connection, and
   the list of boards (name, slave address, board type, mode).
4. Start the add-on. The configured inputs/outputs will appear in Home
   Assistant once MQTT discovery messages are published.

## Configuration

| Option | Description |
| --- | --- |
| `mqtt_host` / `mqtt_port` / `mqtt_username` / `mqtt_password` | Fallback MQTT broker connection details, only used if the Supervisor-managed broker (see below) isn't available. |
| `discovery_prefix` | MQTT discovery prefix configured in the Home Assistant MQTT integration (default `homeassistant`). |
| `boards` | List of boards, each with its own serial connection: `name`, `address` (Modbus slave address, 1-247), `type` (`M23IOA08`, `M23IOB16`, `M23IOC24`, `M23IOD32`, `M23IOE48`, `M23IOF64`), `mode` (`input`, `output`, `input_output`), `port` (serial device, e.g. `/dev/ttyUSB0`), `baudrate`, `parity` (`N`/`E`/`O`), `poll_interval_ms` (milliseconds between input polls of this board's bus). Boards sharing the same `port`/`baudrate`/`parity` reuse the same serial connection. |

### MQTT broker discovery

This add-on requests the `mqtt` Supervisor service (`services: ["mqtt:want"]`),
so if you have the official Mosquitto broker add-on (or another add-on
providing the MQTT service) installed, the broker host/port/credentials are
picked up automatically - no manual configuration needed. The `mqtt_host` /
`mqtt_port` / `mqtt_username` / `mqtt_password` options are only used as a
fallback when no such service is available (e.g. an external broker).

## Requirements

- The Home Assistant **MQTT integration**, backed by a broker (e.g. the
  official Mosquitto add-on), must already be set up.
- A USB-to-RS485 adapter (or other serial interface) wired to the Modbus IO
  board(s); the add-on requests serial/UART access (`uart: true`)
  automatically.


