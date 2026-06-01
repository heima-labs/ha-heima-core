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
OPT_ACTIVITY_BINDINGS = "activity_bindings"
OPT_DISCOVERY = "discovery"

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
    "work_activity_entities": [],
    "workday_entity": "",
    "sleep_enter_min": 10,
    "sleep_exit_min": 2,
    "work_enter_min": 5,
    "work_activity_required": False,
    "work_activity_grace_min": 20,
    "relax_enter_min": 2,
    "relax_exit_min": 10,
    "sleep_requires_media_off": True,
    "sleep_charging_min_count": None,
}

DEFAULT_ACTIVITY_BINDINGS: dict[str, dict[str, object]] = {
    "stove_on": {
        "entity_key": "stove_power_entity",
        "threshold_w": 200.0,
        "candidate_period_s": 5.0,
        "grace_period_s": 30.0,
    },
    "oven_on": {
        "entity_key": "oven_power_entity",
        "threshold_w": 500.0,
        "candidate_period_s": 10.0,
        "grace_period_s": 120.0,
    },
    "tv_active": {
        "entity_key": "tv_entity",
        "threshold_w": 20.0,
        "candidate_period_s": 10.0,
        "grace_period_s": 120.0,
    },
    "pc_active": {
        "entity_key": "pc_power_entity",
        "threshold_w": 50.0,
        "candidate_period_s": 30.0,
        "grace_period_s": 60.0,
    },
    "shower_running": {
        "entity_key": "bathroom_humidity_entity",
        "humidity_threshold": 65.0,
        "min_rate_per_min": 0.1,
        "candidate_period_s": 60.0,
        "grace_period_s": 300.0,
    },
    "washing_machine_running": {
        "entity_key": "washing_machine_entity",
        "threshold_w": 200.0,
        "candidate_period_s": 60.0,
        "grace_period_s": 300.0,
    },
    "dishwasher_running": {
        "entity_key": "dishwasher_entity",
        "threshold_w": 200.0,
        "candidate_period_s": 60.0,
        "grace_period_s": 300.0,
    },
}

# Keys whose change requires a full HA entry reload (entity sets are rebuilt from them).
# All other keys are "runtime" — handled by coordinator.async_reload_options().
STRUCTURAL_OPTION_KEYS: frozenset[str] = frozenset(
    {
        OPT_PEOPLE_NAMED,
        OPT_PEOPLE_ANON,
        OPT_PEOPLE_DEBUG_ALIASES,
        OPT_ROOMS,
        OPT_LIGHTING_ROOMS,
        OPT_LIGHTING_ZONES,
        OPT_HEATING,
        OPT_SECURITY,
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
HOUSE_STATES_HARD = [
    "vacation",
    "guest",
    "away",
]
HOUSE_STATES_HOME_SUBSTATES = [
    "sleeping",
    "relax",
    "working",
    "home",
]
HOUSE_STATES_LEARNED_CONTEXT_ELIGIBLE = HOUSE_STATES_HOME_SUBSTATES

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

# Proposal types
SIGNAL_DISCOVERY_ANALYZER_ID = "signal_discovery"
SIGNAL_DISCOVERY_REACTION_TYPE = "signal_discovery"

# Services
SERVICE_COMMAND = "command"
SERVICE_APPROVE_PROPOSAL = "approve_proposal"
SERVICE_OVERRIDE_APPROVAL = "override_approval"
SERVICE_RUN_DIAGNOSTICS = "run_diagnostics"
SERVICE_SET_MODE = "set_mode"
SERVICE_SET_OVERRIDE = "set_override"
SERVICE_CONFIGURE_ANOMALY_RULE = "configure_anomaly_rule"

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
