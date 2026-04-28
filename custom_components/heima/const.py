"""Constants for the Heima integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "heima"
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
]

# Options keys (v1)
CONF_ENGINE_ENABLED = "engine_enabled"
CONF_TIMEZONE = "timezone"
CONF_LANGUAGE = "language"

OPT_PEOPLE_NAMED = "people_named"
OPT_PEOPLE_ANON = "people_anonymous"
OPT_PEOPLE_DEBUG_ALIASES = "people_debug_aliases"
OPT_ROOMS = "rooms"
OPT_LIGHTING_ROOMS = "lighting_rooms"
OPT_LIGHTING_ZONES = "lighting_zones"
OPT_LIGHTING_APPLY_MODE = "lighting_apply_mode"
OPT_HOUSE_SIGNALS = "house_signals"
OPT_HOUSE_STATE_CONFIG = "house_state_config"
OPT_HEATING = "heating"
OPT_SECURITY = "security"
OPT_NOTIFICATIONS = "notifications"
OPT_REACTIONS = "reactions"
OPT_CALENDAR = "calendar"
OPT_LEARNING = "learning"
OPT_EXTERNAL_CONTEXT = "external_context"

DEFAULT_CALENDAR_LOOKAHEAD_DAYS = 7
DEFAULT_CALENDAR_CACHE_TTL_HOURS = 2
DEFAULT_CALENDAR_KEYWORDS: dict[str, list[str]] = {
    "vacation": ["vacanza", "holiday", "ferie", "viaggio", "vacation"],
    "wfh": ["wfh", "smart working", "lavoro da casa", "remote"],
    "office": ["ufficio", "office", "in sede"],
    "visitor": ["ospiti", "visitor", "amici", "guests"],
}
DEFAULT_CALENDAR_CATEGORY_PRIORITY: list[str] = ["vacation", "office", "wfh", "visitor"]

HOUSE_SIGNAL_NAMES = [
    "vacation_mode",
    "guest_mode",
    "sleep_window",
    "relax_mode",
    "work_window",
]

DEFAULT_HOUSE_STATE_CONFIG: dict[str, object] = {
    "media_active_entities": [],
    "sleep_charging_entities": [],
    "workday_entity": "",
    "sleep_enter_min": 10,
    "sleep_exit_min": 2,
    "work_enter_min": 5,
    "relax_enter_min": 2,
    "relax_exit_min": 10,
    "sleep_requires_media_off": True,
    "sleep_charging_min_count": None,
}

# Keys whose change requires a full HA entry reload (entity sets are rebuilt from them).
# All other keys are "runtime" — handled by coordinator.async_reload_options().
STRUCTURAL_OPTION_KEYS: frozenset[str] = frozenset(
    {
        OPT_PEOPLE_NAMED,
        OPT_PEOPLE_ANON,
        OPT_PEOPLE_DEBUG_ALIASES,
        OPT_ROOMS,
        OPT_LIGHTING_ZONES,
    }
)

DEFAULT_ENGINE_ENABLED = True
DEFAULT_LIGHTING_APPLY_MODE = "scene"

HOUSE_STATES_CANONICAL = [
    "away",
    "home",
    "guest",
    "vacation",
    "sleeping",
    "relax",
    "working",
]

EVENT_CATEGORIES_ALL = [
    "people",
    "occupancy",
    "house_state",
    "lighting",
    "heating",
    "security",
    "system",
]
EVENT_CATEGORIES_TOGGLEABLE = [
    "people",
    "occupancy",
    "house_state",
    "lighting",
    "heating",
    "security",
]
DEFAULT_ENABLED_EVENT_CATEGORIES = [
    "people",
    "occupancy",
    "lighting",
    "heating",
    "security",
]

OCCUPANCY_MISMATCH_POLICIES = ["off", "smart", "strict"]
DEFAULT_OCCUPANCY_MISMATCH_POLICY = "smart"
DEFAULT_OCCUPANCY_MISMATCH_MIN_DERIVED_ROOMS = 2
DEFAULT_OCCUPANCY_MISMATCH_PERSIST_S = 600

SECURITY_MISMATCH_POLICIES = ["off", "smart", "strict"]
DEFAULT_SECURITY_MISMATCH_POLICY = "smart"
DEFAULT_SECURITY_MISMATCH_PERSIST_S = 300
SECURITY_MISMATCH_EVENT_MODES = ["explicit_only", "generic_only", "dual_emit"]
DEFAULT_SECURITY_MISMATCH_EVENT_MODE = "explicit_only"

# Services
SERVICE_COMMAND = "command"
SERVICE_SET_MODE = "set_mode"
SERVICE_SET_OVERRIDE = "set_override"

# Events
EVENT_HEIMA_EVENT = "heima_event"
EVENT_HEIMA_SNAPSHOT = "heima_snapshot"
EVENT_HEIMA_HEALTH = "heima_health"

DIAGNOSTICS_REDACT_KEYS = {
    "latitude",
    "longitude",
    "gps",
    "device_id",
    "entity_id",
}
