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
