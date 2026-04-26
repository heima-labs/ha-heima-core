"""Semantic view-model builder for non-admin Heima surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_LANGUAGE, OPT_LIGHTING_ROOMS, OPT_LIGHTING_ZONES, OPT_ROOMS
from .runtime.state_store import CanonicalState


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _format_temp(value: float | None, language: str) -> str:
    if value is None:
        return "—"
    if language.startswith("it"):
        return f"{value:.1f}".replace(".", ",") + " °C"
    return f"{value:.1f} °C"


def _duration_since(value: datetime | None, *, now: datetime, language: str) -> str | None:
    if value is None:
        return None
    delta = now - value
    total_s = max(int(delta.total_seconds()), 0)
    hours, rem = divmod(total_s, 3600)
    minutes = rem // 60
    if hours <= 0 and minutes <= 0:
        return "0m"
    if language.startswith("it"):
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


@dataclass(frozen=True)
class _Strings:
    home_title: str
    relax_title: str
    away_title: str
    sleeping_title: str
    working_title: str
    vacation_title: str
    guest_title: str
    no_people: str
    people_one: str
    people_many_fmt: str
    security_ok: str
    security_warning: str
    security_alert: str
    no_insights: str
    proposals_pending_fmt: str
    reactions_active_fmt: str
    nobody_home_for_fmt: str
    room_active: str
    room_idle: str
    room_off: str
    lighting_hold: str
    lighting_auto: str
    climate_comfort: str
    climate_heating: str
    climate_cooling: str
    climate_idle: str
    unavailable: str


def _strings(language: str) -> _Strings:
    if language.startswith("it"):
        return _Strings(
            home_title="Casa attiva",
            relax_title="Casa in relax",
            away_title="Nessuno in casa",
            sleeping_title="Casa in riposo",
            working_title="Modalità lavoro",
            vacation_title="Vacanza",
            guest_title="Ospiti",
            no_people="Nessuno in casa",
            people_one="1 persona in casa",
            people_many_fmt="{count} persone in casa",
            security_ok="Sicurezza ok",
            security_warning="Allarme inserito",
            security_alert="Attenzione sicurezza",
            no_insights="Nessun insight rilevante",
            proposals_pending_fmt="{count} proposte in attesa",
            reactions_active_fmt="{count} reazioni attive",
            nobody_home_for_fmt="Nessuno in casa da {duration}",
            room_active="Attiva",
            room_idle="Appena usata",
            room_off="Inattiva",
            lighting_hold="Controllo manuale attivo",
            lighting_auto="Luci in automatico",
            climate_comfort="Comfort stabile",
            climate_heating="Riscaldamento attivo",
            climate_cooling="Raffrescamento attivo",
            climate_idle="Clima in attesa",
            unavailable="Non disponibile",
        )
    return _Strings(
        home_title="Home active",
        relax_title="Home in relax mode",
        away_title="Nobody home",
        sleeping_title="Sleeping mode",
        working_title="Working mode",
        vacation_title="Vacation mode",
        guest_title="Guests home",
        no_people="Nobody home",
        people_one="1 person home",
        people_many_fmt="{count} people home",
        security_ok="Security ok",
        security_warning="Alarm armed away",
        security_alert="Security attention",
        no_insights="No relevant insights",
        proposals_pending_fmt="{count} pending proposals",
        reactions_active_fmt="{count} active reactions",
        nobody_home_for_fmt="Nobody home for {duration}",
        room_active="Active",
        room_idle="Recently used",
        room_off="Inactive",
        lighting_hold="Manual control active",
        lighting_auto="Lighting in auto",
        climate_comfort="Comfort stable",
        climate_heating="Heating active",
        climate_cooling="Cooling active",
        climate_idle="Climate idle",
        unavailable="Unavailable",
    )


class HeimaViewModelBuilder:
    """Builds semantic non-admin view entities into the canonical state store."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry

    def update_entry(self, entry: ConfigEntry) -> None:
        self._entry = entry

    def publish(self, state: CanonicalState) -> None:
        language = self._language()
        texts = _strings(language)
        now = datetime.now(UTC)

        self._publish_home_view(state, texts=texts, language=language, now=now)
        self._publish_insights_view(state, texts=texts, language=language, now=now)
        self._publish_security_view(state, texts=texts)
        self._publish_climate_view(state, texts=texts, language=language)
        self._publish_room_views(state, texts=texts, language=language, now=now)

    def _publish_home_view(
        self, state: CanonicalState, *, texts: _Strings, language: str, now: datetime
    ) -> None:
        house_state = str(state.get_sensor("heima_house_state") or "unknown")
        title = {
            "home": texts.home_title,
            "relax": texts.relax_title,
            "away": texts.away_title,
            "sleeping": texts.sleeping_title,
            "working": texts.working_title,
            "vacation": texts.vacation_title,
            "guest": texts.guest_title,
        }.get(house_state, texts.unavailable)
        reason = str(state.get_sensor("heima_house_state_reason") or texts.unavailable)
        people_count = int(state.get_sensor("heima_people_count") or 0)
        anyone_home = bool(state.get_binary("heima_anyone_home"))
        security_state = str(state.get_sensor("heima_security_state") or "")
        target_temp = _as_float(state.get_sensor("heima_heating_target_temp"))
        heating_phase = str(state.get_sensor("heima_heating_phase") or "")

        security_summary = self._security_summary(security_state, anyone_home, texts)
        presence_summary = self._presence_summary(anyone_home, people_count, texts)
        pills = [
            _format_temp(target_temp, language),
            security_summary,
            presence_summary,
        ]
        if heating_phase:
            pills.append(self._climate_summary(heating_phase, texts))
        pills = [item for item in pills if item and item != "—"][:4]

        priority = "normal"
        if security_state == "armed_away" and anyone_home:
            priority = "critical"
        elif security_state == "armed_away":
            priority = "attention"

        state.set_sensor("heima_home_view", house_state)
        state.set_sensor_attributes(
            "heima_home_view",
            {
                "title": title[:30],
                "subtitle": reason[:60],
                "pills": pills,
                "status": {
                    "temperature": _format_temp(target_temp, language),
                    "security": security_summary,
                    "presence": presence_summary,
                },
                "priority": priority,
                "last_update": now.isoformat(),
            },
        )

    def _publish_insights_view(
        self, state: CanonicalState, *, texts: _Strings, language: str, now: datetime
    ) -> None:
        items: list[dict[str, str]] = []
        reason = str(state.get_sensor("heima_house_state_reason") or "").strip()
        if reason:
            items.append({"text": reason[:40], "severity": "info"})

        proposal_total = int(state.get_sensor("heima_reaction_proposals") or 0)
        if proposal_total > 0:
            items.append(
                {
                    "text": texts.proposals_pending_fmt.format(count=proposal_total)[:40],
                    "severity": "warning",
                }
            )

        reactions_total = int(state.get_sensor("heima_reactions_active") or 0)
        if reactions_total > 0:
            items.append(
                {
                    "text": texts.reactions_active_fmt.format(count=reactions_total)[:40],
                    "severity": "info",
                }
            )

        if not bool(state.get_binary("heima_anyone_home")):
            last_change = self._latest_room_change(state)
            duration = _duration_since(last_change, now=now, language=language)
            if duration:
                items.append(
                    {
                        "text": texts.nobody_home_for_fmt.format(duration=duration)[:40],
                        "severity": "info",
                    }
                )

        if not items:
            items.append({"text": texts.no_insights[:40], "severity": "info"})

        severity_rank = {"critical": 0, "warning": 1, "info": 2}
        items = sorted(items, key=lambda item: severity_rank.get(item["severity"], 9))[:3]
        if any(item["severity"] == "critical" for item in items):
            view_state = "critical"
        elif any(item["severity"] == "warning" for item in items):
            view_state = "attention"
        else:
            view_state = "normal"

        state.set_sensor("heima_insights_view", view_state)
        state.set_sensor_attributes("heima_insights_view", {"items": items})

    def _publish_security_view(self, state: CanonicalState, *, texts: _Strings) -> None:
        security_state = str(state.get_sensor("heima_security_state") or "")
        security_reason = str(state.get_sensor("heima_security_reason") or "").strip()
        anyone_home = bool(state.get_binary("heima_anyone_home"))

        alerts: list[str] = []
        if security_reason and security_reason not in {"ok", "default"}:
            alerts.append(security_reason)

        if alerts or (security_state == "armed_away" and anyone_home):
            view_state = "alert"
        elif security_state == "armed_away":
            view_state = "warning"
        else:
            view_state = "ok"

        summary = {
            "ok": texts.security_ok,
            "warning": texts.security_warning,
            "alert": texts.security_alert,
        }[view_state]

        items = [summary]
        if security_reason:
            items.append(security_reason)

        state.set_sensor("heima_security_view", view_state)
        state.set_sensor_attributes(
            "heima_security_view",
            {"summary": summary, "items": items[:4], "alerts": alerts[:3]},
        )

    def _publish_climate_view(
        self, state: CanonicalState, *, texts: _Strings, language: str
    ) -> None:
        phase = str(state.get_sensor("heima_heating_phase") or "")
        target_temp = _as_float(state.get_sensor("heima_heating_target_temp"))
        current_temp = _as_float(state.get_sensor("heima_heating_current_setpoint"))
        display_temp = current_temp if current_temp is not None else target_temp

        if phase == "heating":
            view_state = "heating"
        elif phase == "cooling":
            view_state = "cooling"
        elif phase == "maintaining":
            view_state = "comfort"
        else:
            view_state = "idle"

        summary = {
            "comfort": texts.climate_comfort,
            "heating": texts.climate_heating,
            "cooling": texts.climate_cooling,
            "idle": texts.climate_idle,
        }[view_state]
        detail = str(state.get_sensor("heima_heating_branch") or texts.unavailable)

        state.set_sensor("heima_climate_view", view_state)
        state.set_sensor_attributes(
            "heima_climate_view",
            {
                "temperature": _format_temp(display_temp, language),
                "summary": summary,
                "detail": detail,
                "trend": "stable",
            },
        )

    def _publish_room_views(
        self, state: CanonicalState, *, texts: _Strings, language: str, now: datetime
    ) -> None:
        options = dict(self._entry.options)
        room_configs = [cfg for cfg in list(options.get(OPT_ROOMS, [])) if isinstance(cfg, dict)]
        zone_map = self._room_zone_map()
        for room in room_configs:
            room_id = str(room.get("room_id") or "").strip()
            if not room_id:
                continue
            display_name = str(room.get("display_name") or room_id).strip()
            occupied = bool(state.get_binary(f"heima_occupancy_{room_id}"))
            last_change = _parse_dt(state.get_sensor(f"heima_occupancy_{room_id}_last_change"))
            age_minutes = None
            if last_change is not None:
                age_minutes = max(int((now - last_change).total_seconds() // 60), 0)

            if occupied:
                view_state = "active"
            elif age_minutes is not None and age_minutes < 30:
                view_state = "idle"
            else:
                view_state = "off"

            zone_id = zone_map.get(room_id)
            intent = (
                str(state.get_select(f"heima_lighting_intent_{zone_id}") or "").strip()
                if zone_id
                else ""
            )
            hold = bool(state.get_binary(f"heima_lighting_hold_{room_id}"))
            line1 = self._room_primary_line(view_state, intent, texts, language)
            line2 = (
                texts.lighting_hold if hold else (texts.lighting_auto if zone_id and intent else "")
            )
            features = [
                {"type": "occupancy", "state": view_state},
            ]
            if zone_id:
                features.append({"type": "lighting", "state": intent or "auto"})

            state.set_sensor(f"heima_room_{room_id}_view", view_state)
            state.set_sensor_attributes(
                f"heima_room_{room_id}_view",
                {
                    "title": display_name,
                    "line1": line1,
                    "line2": line2,
                    "features": features,
                    "actions": [],
                },
            )

    def _latest_room_change(self, state: CanonicalState) -> datetime | None:
        latest: datetime | None = None
        for room in self._room_ids():
            candidate = _parse_dt(state.get_sensor(f"heima_occupancy_{room}_last_change"))
            if candidate is None:
                continue
            if latest is None or candidate > latest:
                latest = candidate
        return latest

    def _room_ids(self) -> list[str]:
        options = dict(self._entry.options)
        room_configs = [cfg for cfg in list(options.get(OPT_ROOMS, [])) if isinstance(cfg, dict)]
        return [str(cfg.get("room_id") or "").strip() for cfg in room_configs if cfg.get("room_id")]

    def _room_zone_map(self) -> dict[str, str]:
        options = dict(self._entry.options)
        mapping: dict[str, str] = {}
        zone_configs = [
            cfg for cfg in list(options.get(OPT_LIGHTING_ZONES, [])) if isinstance(cfg, dict)
        ]
        room_cfgs = {
            str(cfg.get("room_id") or "").strip(): dict(cfg)
            for cfg in list(options.get(OPT_LIGHTING_ROOMS, []))
            if isinstance(cfg, dict) and str(cfg.get("room_id") or "").strip()
        }
        for room_id in room_cfgs:
            for zone in zone_configs:
                zone_id = str(zone.get("zone_id") or "").strip()
                zone_rooms = [str(item).strip() for item in list(zone.get("rooms", []))]
                if zone_id and room_id in zone_rooms:
                    mapping[room_id] = zone_id
                    break
        return mapping

    def _language(self) -> str:
        lang_state = self._hass.states.get("input_select.heima_language")
        if lang_state is not None:
            value = str(lang_state.state or "").strip().lower()
            if value in {"it", "en"}:
                return value
        return str(dict(self._entry.options).get(CONF_LANGUAGE, "it") or "it").lower()

    @staticmethod
    def _security_summary(security_state: str, anyone_home: bool, texts: _Strings) -> str:
        if security_state == "armed_away" and anyone_home:
            return texts.security_alert
        if security_state == "armed_away":
            return texts.security_warning
        return texts.security_ok

    @staticmethod
    def _presence_summary(anyone_home: bool, people_count: int, texts: _Strings) -> str:
        if not anyone_home or people_count <= 0:
            return texts.no_people
        if people_count == 1:
            return texts.people_one
        return texts.people_many_fmt.format(count=people_count)

    @staticmethod
    def _climate_summary(phase: str, texts: _Strings) -> str:
        if phase == "heating":
            return texts.climate_heating
        if phase == "cooling":
            return texts.climate_cooling
        if phase == "maintaining":
            return texts.climate_comfort
        return texts.climate_idle

    @staticmethod
    def _room_primary_line(view_state: str, intent: str, texts: _Strings, language: str) -> str:
        if view_state == "active" and intent:
            if language.startswith("it"):
                return f"Luci: {intent}"
            return f"Lighting: {intent}"
        if view_state == "active":
            return texts.room_active
        if view_state == "idle":
            return texts.room_idle
        return texts.room_off
