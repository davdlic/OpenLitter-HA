"""Constants for the OpenLitter integration."""
from __future__ import annotations

DOMAIN = "openlitter"

# Config entry keys
CONF_HOST = "host"
CONF_PORT = "port"
CONF_OTA_PASSWORD = "ota_password"
CONF_USE_MQTT = "use_mqtt"
CONF_MQTT_TOPIC_BASE = "mqtt_topic_base"

DEFAULT_PORT = 80
DEFAULT_MQTT_TOPIC_BASE = "openlitter"
DEFAULT_POLL_INTERVAL_SECONDS = 5

# Hostname / model strings used in the device registry
MANUFACTURER = "OpenLitter"
MODEL = "Litter Robot 1/2/3 ESP32"

# GitHub firmware releases (for the Update entity)
GITHUB_RELEASES_URL = (
    "https://api.github.com/repos/davdlic/OpenLitter/releases/latest"
)
FIRMWARE_ASSET_PREFIX = "openlitter-"
FIRMWARE_ASSET_SUFFIX = "-firmware.bin"
LITTLEFS_ASSET_SUFFIX = "-littlefs.bin"

# /api/status fields we surface as state attributes / entity values
ATTR_STATE = "state"
ATTR_HOME_POSITION = "home_position"
ATTR_DUMP_POSITION = "dump_position"
ATTR_CAT_PRESENT = "cat_present"
ATTR_WEIGHT_KG = "weight_kg"
ATTR_WEIGHT_ENABLED = "weight_enabled"
ATTR_PRESENCE_ENABLED = "presence_enabled"
ATTR_CYCLE_COUNT = "cycle_count"
ATTR_LAST_CYCLE = "last_cycle"
ATTR_UPTIME_SEC = "uptime_sec"
ATTR_ERROR = "error"
ATTR_RESET_IN_PROGRESS = "reset_in_progress"
ATTR_VERSION = "version"
ATTR_HISTORY = "history"
ATTR_NETWORK = "network"
ATTR_MQTT_CONNECTED = "mqtt_connected"

# Friendly state labels — mirror the firmware Web UI.
STATE_LABELS: dict[str, str] = {
    "IDLE": "Ready",
    "CAT_INSIDE": "Cat inside",
    "WAITING": "Waiting",
    "CYCLING_CCW": "Cleaning",
    "CYCLING_DUMP_PAUSE": "Dumping",
    "CYCLING_CW": "Returning",
    "CYCLING_LEVEL_OVERSHOOT": "Leveling",
    "CYCLING_LEVEL_RETURN": "Leveling",
    "CYCLING_LEVEL_BACK_OVERSHOOT": "Leveling",
    "CYCLING_LEVEL_BACK_RETURN": "Leveling",
    "EMPTYING": "Emptying",
    "EMPTYING_DUMP_PAUSE": "Dumping",
    "RESETTING": "Returning",
    "PAUSED": "Paused",
    "ERROR": "Error",
}

# Events fired on the HA bus for automations + the Logbook integration.
# Naming: `{domain}_*` so they appear under "OpenLitter" in the logbook.
EVENT_CYCLE_STARTED = f"{DOMAIN}_cycle_started"
EVENT_CYCLE_COMPLETED = f"{DOMAIN}_cycle_completed"
EVENT_CAT_DETECTED = f"{DOMAIN}_cat_detected"
EVENT_CAT_LEFT = f"{DOMAIN}_cat_left"
EVENT_ERROR = f"{DOMAIN}_error"

# Set of CYCLING_* states used to detect "cycle started" transitions.
CYCLING_STATES: frozenset[str] = frozenset({
    "CYCLING_CCW",
    "CYCLING_DUMP_PAUSE",
    "CYCLING_CW",
    "CYCLING_LEVEL_OVERSHOOT",
    "CYCLING_LEVEL_RETURN",
    "CYCLING_LEVEL_BACK_OVERSHOOT",
    "CYCLING_LEVEL_BACK_RETURN",
})

# Command name -> POST endpoint
COMMAND_PATHS: dict[str, str] = {
    "cycle": "/api/cycle",
    "empty": "/api/empty",
    "reset": "/api/reset",
    "home":  "/api/home",
    "pause": "/api/pause",
    "resume": "/api/resume",
    "tare": "/api/tare",
}
