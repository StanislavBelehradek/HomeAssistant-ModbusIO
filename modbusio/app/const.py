"""Constants for the Modbus IO (Eletechsup) add-on."""
from __future__ import annotations

# Eletechsup M23IOxx RTU register map: outputs (relays) and inputs (opto
# isolated) are each packed 16 bits/register, LSB-first within a register.
OUTPUT_REGISTER_START = 112
INPUT_REGISTER_START = 192

# Number of digital I/O points per supported board type.
BOARD_IO_COUNT = {
    "M23IOA08": 8,
    "M23IOB16": 16,
    "M23IOC24": 24,
    "M23IOD32": 32,
    "M23IOE48": 48,
    "M23IOF64": 64,
}

OPTIONS_FILE = "/data/options.json"

# Entity type overrides selectable per I/O point via the `entities` option,
# replacing the default binary_sensor (input) / switch (output) entity.
ENTITY_TYPE_BUTTON = "button"
ENTITY_TYPE_LIGHT = "light"

# States reported by a `button` entity: "none" is the idle/reset state
# between presses, the others are the detected press pattern.
BUTTON_STATE_NONE = "none"
BUTTON_STATE_SINGLE = "single"
BUTTON_STATE_DOUBLE = "double"
BUTTON_STATE_LONG = "long"
BUTTON_STATES = [BUTTON_STATE_NONE, BUTTON_STATE_SINGLE, BUTTON_STATE_DOUBLE, BUTTON_STATE_LONG]

# How long a "single"/"double"/"long" pulse stays reported before the button
# entity resets to "none", so repeated identical presses re-trigger a state change.
BUTTON_RESET_DELAY_S = 0.3

# Control modes for a `cover` entity's pair of drive relays: `up_down` uses
# two exclusive relays (one per direction); `move_direction` uses one
# enable/move relay plus one direction relay.
COVER_CONTROL_UP_DOWN = "up_down"
COVER_CONTROL_MOVE_DIRECTION = "move_direction"

COVER_POSITION_CLOSED = 0
COVER_POSITION_OPEN = 100

# States reported by a `cover` entity while its position is simulated from
# the configured `open_time_s` (no real position feedback from the board).
COVER_STATE_OPEN = "open"
COVER_STATE_OPENING = "opening"
COVER_STATE_CLOSED = "closed"
COVER_STATE_CLOSING = "closing"
COVER_STATE_STOPPED = "stopped"

# How often a moving cover's interpolated position is published.
COVER_POSITION_PUBLISH_INTERVAL_S = 0.2
