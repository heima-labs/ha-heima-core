"""Tests for CalendarDomain."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.heima.runtime.domains.calendar import (
    CalendarDomain,
    CalendarResult,
    _classify,
    _parse_dt_or_date,
    _resolve_classification_config,
)
from custom_components.heima.const import (
    DEFAULT_CALENDAR_CATEGORY_PRIORITY,
    DEFAULT_CALENDAR_KEYWORDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_state(state: str, attributes: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(state=state, attributes=dict(attributes or {}))


def _fake_hass(states: dict | None = None, service_response: dict | None = None) -> SimpleNamespace:
    state_map = {k: _fake_state(*v) if isinstance(v, tuple) else _fake_state(v) for k, v in (states or {}).items()}

    async def _async_call(domain, service, data, blocking=False, return_response=False):
        return service_response or {}

    return SimpleNamespace(
        states=SimpleNamespace(get=lambda eid: state_map.get(eid)),
        services=SimpleNamespace(async_call=_async_call),
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today_str() -> str:
    return _now().date().isoformat()


def _tomorrow_str() -> str:
    return (_now() + timedelta(days=1)).date().isoformat()


# ---------------------------------------------------------------------------
# _classify
# ---------------------------------------------------------------------------

def _kw_and_prio(cfg: dict | None = None):
    return _resolve_classification_config(cfg or {})


def test_classify_vacation_it():
    kw, prio = _kw_and_prio()
    assert _classify("Vacanza al mare", kw, prio) == "vacation"


def test_classify_vacation_en():
    kw, prio = _kw_and_prio()
    assert _classify("Summer Holiday", kw, prio) == "vacation"


def test_classify_wfh():
    kw, prio = _kw_and_prio()
    assert _classify("WFH today", kw, prio) == "wfh"


def test_classify_office():
    kw, prio = _kw_and_prio()
    assert _classify("In ufficio tutta la mattina", kw, prio) == "office"


def test_classify_visitor():
    kw, prio = _kw_and_prio()
    assert _classify("Ospiti a cena", kw, prio) == "visitor"


def test_classify_unknown():
    kw, prio = _kw_and_prio()
    assert _classify("Dentista", kw, prio) == "unknown"


def test_classify_office_beats_wfh_by_default_priority():
    """office has higher default priority than wfh."""
    kw, prio = _kw_and_prio()
    assert _classify("WFH in ufficio", kw, prio) == "office"


def test_classify_case_insensitive():
    kw, prio = _kw_and_prio()
    assert _classify("VACANZA MARE", kw, prio) == "vacation"


def test_classify_user_keywords_extended():
    cfg = {"calendar_keywords": {"vacation": ["cruise"]}}
    kw, prio = _kw_and_prio(cfg)
    assert _classify("Mediterranean Cruise", kw, prio) == "vacation"
    assert _classify("Holiday trip", kw, prio) == "vacation"


def test_classify_custom_category():
    """User-defined category is reachable via classification."""
    cfg = {"calendar_keywords": {"medical": ["dottore", "dentista"]}}
    kw, prio = _kw_and_prio(cfg)
    assert _classify("Dentista ore 10", kw, prio) == "medical"


def test_classify_custom_priority_overrides_builtin():
    """Custom category placed before vacation in priority beats vacation."""
    cfg = {
        "calendar_keywords": {"urgent": ["urgente"]},
        "category_priority": ["urgent", "vacation", "office", "wfh", "visitor"],
    }
    kw, prio = _kw_and_prio(cfg)
    assert prio[0] == "urgent"
    assert _classify("Evento urgente vacanza", kw, prio) == "urgent"


def test_resolve_config_extra_categories_appended_to_priority():
    """Categories defined in keywords but missing from priority get appended."""
    cfg = {
        "calendar_keywords": {"sport": ["palestra", "calcio"]},
        # no category_priority set
    }
    kw, prio = _kw_and_prio(cfg)
    assert "sport" in prio
    # sport is appended after built-ins
    assert prio.index("sport") > prio.index("visitor")


# ---------------------------------------------------------------------------
# _parse_dt_or_date
# ---------------------------------------------------------------------------

def test_parse_datetime_iso():
    dt = _parse_dt_or_date("2024-03-15T10:00:00+01:00")
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_date_only():
    dt = _parse_dt_or_date("2024-03-15")
    assert dt is not None
    assert dt.year == 2024
    assert dt.month == 3
    assert dt.day == 15


def test_parse_invalid_returns_none():
    assert _parse_dt_or_date("not-a-date") is None
    assert _parse_dt_or_date("") is None


# ---------------------------------------------------------------------------
# CalendarDomain.compute — no config
# ---------------------------------------------------------------------------

def test_compute_no_entities_returns_empty():
    domain = CalendarDomain(_fake_hass())
    result = domain.compute({})
    assert result.is_vacation_active is False
    assert result.is_wfh_today is False
    assert result.is_office_today is False
    assert result.next_vacation is None
    assert result.current_events == []


def test_compute_empty_entities_list():
    domain = CalendarDomain(_fake_hass())
    result = domain.compute({"calendar_entities": []})
    assert isinstance(result, CalendarResult)
    assert result.is_vacation_active is False


# ---------------------------------------------------------------------------
# CalendarDomain.compute — current events from entity state
# ---------------------------------------------------------------------------

def test_compute_vacation_active_from_entity_state():
    states = {
        "calendar.personal": ("on", {
            "message": "Vacanza settimana bianca",
            "start_time": _now().isoformat(),
            "end_time": (_now() + timedelta(hours=8)).isoformat(),
            "all_day": True,
        })
    }
    domain = CalendarDomain(_fake_hass(states=states))
    result = domain.compute({"calendar_entities": ["calendar.personal"]})
    assert result.is_vacation_active is True
    assert result.is_wfh_today is False
    assert len(result.current_events) == 1
    assert result.current_events[0].category == "vacation"


def test_compute_wfh_active_from_entity_state():
    states = {
        "calendar.work": ("on", {
            "message": "Smart working",
            "start_time": _now().isoformat(),
            "end_time": (_now() + timedelta(hours=8)).isoformat(),
            "all_day": False,
        })
    }
    domain = CalendarDomain(_fake_hass(states=states))
    result = domain.compute({"calendar_entities": ["calendar.work"]})
    assert result.is_wfh_today is True
    assert result.is_office_today is False


def test_compute_office_beats_wfh():
    """If office is active today, wfh is suppressed even if also present."""
    states = {
        "calendar.personal": ("on", {
            "message": "WFH",
            "start_time": _now().isoformat(),
            "end_time": (_now() + timedelta(hours=8)).isoformat(),
            "all_day": False,
        }),
        "calendar.work": ("on", {
            "message": "In ufficio",
            "start_time": _now().isoformat(),
            "end_time": (_now() + timedelta(hours=4)).isoformat(),
            "all_day": False,
        }),
    }
    domain = CalendarDomain(_fake_hass(states=states))
    result = domain.compute({"calendar_entities": ["calendar.personal", "calendar.work"]})
    assert result.is_office_today is True
    assert result.is_wfh_today is False


def test_compute_entity_off_ignored():
    states = {"calendar.personal": ("off", {})}
    domain = CalendarDomain(_fake_hass(states=states))
    result = domain.compute({"calendar_entities": ["calendar.personal"]})
    assert result.current_events == []
    assert result.is_vacation_active is False


def test_compute_unknown_entity_skipped():
    domain = CalendarDomain(_fake_hass(states={}))
    result = domain.compute({"calendar_entities": ["calendar.nonexistent"]})
    assert result.current_events == []


# ---------------------------------------------------------------------------
# CalendarDomain.compute — all-day events from cache
# ---------------------------------------------------------------------------

def test_compute_allday_vacation_from_cache():
    """All-day vacation event in cache covering today → is_vacation_active."""
    domain = CalendarDomain(_fake_hass())
    today = _now().date()
    tomorrow = today + timedelta(days=1)
    from custom_components.heima.runtime.domains.calendar import CalendarEvent
    domain._cached_events = [
        CalendarEvent(
            summary="Ferie",
            start=datetime(today.year, today.month, today.day, tzinfo=timezone.utc),
            end=datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=timezone.utc),
            all_day=True,
            category="vacation",
            calendar_entity="calendar.personal",
        )
    ]
    domain._cache_ts = _now()
    result = domain.compute({"calendar_entities": ["calendar.personal"]})
    assert result.is_vacation_active is True


def test_compute_next_vacation_from_cache():
    """next_vacation points to the soonest future vacation."""
    domain = CalendarDomain(_fake_hass())
    today = _now().date()
    future1 = today + timedelta(days=5)
    future2 = today + timedelta(days=10)
    from custom_components.heima.runtime.domains.calendar import CalendarEvent
    from datetime import date as date_type
    def _dt(d: date_type) -> datetime:
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)

    domain._cached_events = [
        CalendarEvent(
            summary="Vacanza lunga",
            start=_dt(future2),
            end=_dt(future2 + timedelta(days=7)),
            all_day=True,
            category="vacation",
            calendar_entity="calendar.personal",
        ),
        CalendarEvent(
            summary="Vacanza corta",
            start=_dt(future1),
            end=_dt(future1 + timedelta(days=2)),
            all_day=True,
            category="vacation",
            calendar_entity="calendar.personal",
        ),
    ]
    domain._cache_ts = _now()
    result = domain.compute({"calendar_entities": ["calendar.personal"]})
    assert result.next_vacation is not None
    assert result.next_vacation.summary == "Vacanza corta"


# ---------------------------------------------------------------------------
# CalendarDomain.reset
# ---------------------------------------------------------------------------

def test_reset_clears_cache():
    domain = CalendarDomain(_fake_hass())
    from custom_components.heima.runtime.domains.calendar import CalendarEvent
    today = _now().date()
    tomorrow = today + timedelta(days=1)
    domain._cached_events = [
        CalendarEvent(
            summary="Test",
            start=datetime(today.year, today.month, today.day, tzinfo=timezone.utc),
            end=datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=timezone.utc),
            all_day=True,
            category="vacation",
            calendar_entity="calendar.x",
        )
    ]
    domain._cache_ts = _now()
    domain.reset()
    assert domain._cached_events == []
    assert domain._cache_ts is None


# ---------------------------------------------------------------------------
# CalendarDomain.async_maybe_refresh
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_maybe_refresh_populates_cache():
    today = _now().date()
    tomorrow = today + timedelta(days=1)
    service_response = {
        "calendar.personal": {
            "events": [
                {
                    "summary": "Holiday",
                    "start": today.isoformat(),
                    "end": tomorrow.isoformat(),
                }
            ]
        }
    }
    domain = CalendarDomain(_fake_hass(service_response=service_response))
    cfg = {"calendar_entities": ["calendar.personal"], "lookahead_days": 7, "cache_ttl_hours": 2}
    await domain.async_maybe_refresh(cfg)
    assert domain._cache_ts is not None
    assert len(domain._cached_events) == 1
    assert domain._cached_events[0].category == "vacation"


@pytest.mark.asyncio
async def test_async_maybe_refresh_skips_if_fresh():
    """Second call within TTL does not re-fetch."""
    call_count = 0

    async def _counting_call(domain, service, data, blocking=False, return_response=False):
        nonlocal call_count
        call_count += 1
        return {}

    hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda _: None),
        services=SimpleNamespace(async_call=_counting_call),
    )
    domain = CalendarDomain(hass)
    cfg = {"calendar_entities": ["calendar.personal"], "cache_ttl_hours": 2}
    await domain.async_maybe_refresh(cfg)
    await domain.async_maybe_refresh(cfg)
    assert call_count == 1  # second call skipped


@pytest.mark.asyncio
async def test_async_maybe_refresh_no_entities_skips():
    call_count = 0

    async def _counting_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return {}

    hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda _: None),
        services=SimpleNamespace(async_call=_counting_call),
    )
    domain = CalendarDomain(hass)
    await domain.async_maybe_refresh({})
    assert call_count == 0


@pytest.mark.asyncio
async def test_async_maybe_refresh_handles_service_error_gracefully():
    async def _failing_call(domain, service, data, blocking=False, return_response=False):
        raise RuntimeError("service unavailable")

    hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda _: None),
        services=SimpleNamespace(async_call=_failing_call),
    )
    domain = CalendarDomain(hass)
    cfg = {"calendar_entities": ["calendar.personal"]}
    # Should not raise
    await domain.async_maybe_refresh(cfg)
    assert domain._cached_events == []
    # cache_ts IS set (refresh was attempted)
    assert domain._cache_ts is not None


# ---------------------------------------------------------------------------
# HouseStateDomain integration
# ---------------------------------------------------------------------------

def test_house_state_wfh_sets_working():
    from custom_components.heima.runtime.domains.house_state import HouseStateDomain
    from custom_components.heima.runtime.domains.calendar import CalendarResult
    from custom_components.heima.runtime.normalization.service import InputNormalizer

    hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda _: None),
        services=SimpleNamespace(async_call=None, async_services=lambda: {"notify": {}}),
        bus=SimpleNamespace(async_fire=lambda *a, **kw: None),
    )
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    cal = CalendarResult(is_wfh_today=True)

    from custom_components.heima.runtime.domains.events import EventsDomain
    events = EventsDomain(hass)
    result = domain.compute(
        options={},
        house_signal_entities={},
        anyone_home=True,
        events=events,
        state=SimpleNamespace(get_sensor=lambda _: None, get_binary=lambda _: None),
        calendar_result=cal,
    )
    assert result.house_state == "working"


def test_house_state_office_suppresses_working():
    from custom_components.heima.runtime.domains.house_state import HouseStateDomain
    from custom_components.heima.runtime.domains.calendar import CalendarResult
    from custom_components.heima.runtime.normalization.service import InputNormalizer

    hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda _: None),
        services=SimpleNamespace(async_call=None, async_services=lambda: {"notify": {}}),
        bus=SimpleNamespace(async_fire=lambda *a, **kw: None),
    )
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    cal = CalendarResult(is_office_today=True)

    from custom_components.heima.runtime.domains.events import EventsDomain
    events = EventsDomain(hass)
    result = domain.compute(
        options={},
        house_signal_entities={},
        anyone_home=True,
        events=events,
        state=SimpleNamespace(get_sensor=lambda _: None, get_binary=lambda _: None),
        calendar_result=cal,
    )
    # is_office_today → work_window forced False → home state (anyone home, no other signals)
    assert result.house_state == "home"


def test_house_state_vacation_from_calendar():
    from custom_components.heima.runtime.domains.house_state import HouseStateDomain
    from custom_components.heima.runtime.domains.calendar import CalendarResult
    from custom_components.heima.runtime.normalization.service import InputNormalizer

    hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda _: None),
        services=SimpleNamespace(async_call=None, async_services=lambda: {"notify": {}}),
        bus=SimpleNamespace(async_fire=lambda *a, **kw: None),
    )
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    cal = CalendarResult(is_vacation_active=True)

    from custom_components.heima.runtime.domains.events import EventsDomain
    events = EventsDomain(hass)
    result = domain.compute(
        options={},
        house_signal_entities={},
        anyone_home=False,
        events=events,
        state=SimpleNamespace(get_sensor=lambda _: None, get_binary=lambda _: None),
        calendar_result=cal,
    )
    assert result.house_state == "vacation"


def test_house_state_no_calendar_result_unchanged():
    """Without CalendarResult, behavior is identical to before."""
    from custom_components.heima.runtime.domains.house_state import HouseStateDomain
    from custom_components.heima.runtime.normalization.service import InputNormalizer

    hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda _: None),
        services=SimpleNamespace(async_call=None, async_services=lambda: {"notify": {}}),
        bus=SimpleNamespace(async_fire=lambda *a, **kw: None),
    )
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)

    from custom_components.heima.runtime.domains.events import EventsDomain
    events = EventsDomain(hass)
    result = domain.compute(
        options={},
        house_signal_entities={},
        anyone_home=True,
        events=events,
        state=SimpleNamespace(get_sensor=lambda _: None, get_binary=lambda _: None),
        calendar_result=None,
    )
    assert result.house_state == "home"


# ---------------------------------------------------------------------------
# Pipeline integration: CalendarDomain + HouseStateDomain end-to-end
# ---------------------------------------------------------------------------

def _make_hass_with_calendar_state(entity_id: str, summary: str) -> SimpleNamespace:
    """Helper: creates a fake hass with a calendar entity in state 'on'."""
    state = _fake_state("on", {
        "message": summary,
        "start_time": _now().isoformat(),
        "end_time": (_now() + timedelta(hours=8)).isoformat(),
        "all_day": True,
    })
    return SimpleNamespace(
        states=SimpleNamespace(get=lambda eid: state if eid == entity_id else None),
        services=SimpleNamespace(
            async_call=None,
            async_services=lambda: {"notify": {}},
        ),
        bus=SimpleNamespace(async_fire=lambda *a, **kw: None),
    )


def _run_pipeline(hass, entity_id: str, anyone_home: bool = False) -> "any":
    from custom_components.heima.runtime.domains.house_state import HouseStateDomain
    from custom_components.heima.runtime.normalization.service import InputNormalizer
    from custom_components.heima.runtime.domains.events import EventsDomain

    calendar = CalendarDomain(hass)
    cal_result = calendar.compute({"calendar_entities": [entity_id]})

    normalizer = InputNormalizer(hass)
    hs_domain = HouseStateDomain(hass, normalizer)
    events = EventsDomain(hass)
    return hs_domain.compute(
        options={},
        house_signal_entities={},
        anyone_home=anyone_home,
        events=events,
        state=SimpleNamespace(get_sensor=lambda _: None, get_binary=lambda _: None),
        calendar_result=cal_result,
    )


def test_pipeline_vacation_active_drives_vacation():
    """Entity 'on' with vacation summary → house_state = vacation."""
    hass = _make_hass_with_calendar_state("calendar.personal", "Vacanza settimana bianca")
    result = _run_pipeline(hass, "calendar.personal", anyone_home=False)
    assert result.house_state == "vacation"


def test_pipeline_wfh_drives_working():
    """Entity 'on' with WFH summary + anyone_home=True → house_state = working."""
    hass = _make_hass_with_calendar_state("calendar.work", "Smart working oggi")
    result = _run_pipeline(hass, "calendar.work", anyone_home=True)
    assert result.house_state == "working"


def test_pipeline_custom_sick_does_not_alter_house_state():
    """A 'sick' category event (custom) doesn't map to any house_state change."""
    hass = _make_hass_with_calendar_state("calendar.personal", "Influenza a casa")
    # Need sick in keywords to get classified
    calendar = CalendarDomain(hass)
    cal_result = calendar.compute({
        "calendar_entities": ["calendar.personal"],
        "calendar_keywords": {"sick": ["influenza", "malattia"]},
    })
    # sick category classified but doesn't affect vacation/wfh/office
    assert cal_result.is_vacation_active is False
    assert cal_result.is_wfh_today is False
    assert cal_result.is_office_today is False

    from custom_components.heima.runtime.domains.house_state import HouseStateDomain
    from custom_components.heima.runtime.normalization.service import InputNormalizer
    from custom_components.heima.runtime.domains.events import EventsDomain
    normalizer = InputNormalizer(hass)
    hs_domain = HouseStateDomain(hass, normalizer)
    events = EventsDomain(hass)
    result = hs_domain.compute(
        options={},
        house_signal_entities={},
        anyone_home=True,
        events=events,
        state=SimpleNamespace(get_sensor=lambda _: None, get_binary=lambda _: None),
        calendar_result=cal_result,
    )
    # stays "home" — sick doesn't change anything
    assert result.house_state == "home"


def test_pipeline_allday_vacation_from_cache_entity_off():
    """All-day vacation event in cache, entity currently 'off' → still is_vacation_active."""
    from custom_components.heima.runtime.domains.calendar import CalendarEvent

    hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda _: _fake_state("off")),  # entity is off
        services=SimpleNamespace(async_call=None, async_services=lambda: {"notify": {}}),
        bus=SimpleNamespace(async_fire=lambda *a, **kw: None),
    )
    calendar = CalendarDomain(hass)
    today = _now().date()
    tomorrow = today + timedelta(days=1)
    calendar._cached_events = [
        CalendarEvent(
            summary="Ferie",
            start=datetime(today.year, today.month, today.day, tzinfo=timezone.utc),
            end=datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=timezone.utc),
            all_day=True,
            category="vacation",
            calendar_entity="calendar.personal",
        )
    ]
    calendar._cache_ts = _now()

    cal_result = calendar.compute({"calendar_entities": ["calendar.personal"]})
    assert cal_result.is_vacation_active is True

    from custom_components.heima.runtime.domains.house_state import HouseStateDomain
    from custom_components.heima.runtime.normalization.service import InputNormalizer
    from custom_components.heima.runtime.domains.events import EventsDomain
    normalizer = InputNormalizer(hass)
    hs_domain = HouseStateDomain(hass, normalizer)
    events = EventsDomain(hass)
    result = hs_domain.compute(
        options={},
        house_signal_entities={},
        anyone_home=False,
        events=events,
        state=SimpleNamespace(get_sensor=lambda _: None, get_binary=lambda _: None),
        calendar_result=cal_result,
    )
    assert result.house_state == "vacation"


# ---------------------------------------------------------------------------
# async_maybe_refresh — TTL expiry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_maybe_refresh_triggers_after_ttl_expired():
    """Second call after TTL window does trigger a re-fetch."""
    call_count = 0

    async def _counting_call(domain, service, data, blocking=False, return_response=False):
        nonlocal call_count
        call_count += 1
        return {}

    hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda _: None),
        services=SimpleNamespace(async_call=_counting_call),
    )
    domain = CalendarDomain(hass)
    cfg = {"calendar_entities": ["calendar.personal"], "cache_ttl_hours": 1}

    await domain.async_maybe_refresh(cfg)
    assert call_count == 1

    # Simulate cache older than TTL
    domain._cache_ts = _now() - timedelta(hours=2)
    await domain.async_maybe_refresh(cfg)
    assert call_count == 2


# ---------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------

def test_diagnostics_empty():
    domain = CalendarDomain(_fake_hass())
    d = domain.diagnostics()
    assert d["cache_ts"] is None
    assert d["cached_events_count"] == 0
    assert d["cached_events"] == []


def test_diagnostics_with_events():
    from custom_components.heima.runtime.domains.calendar import CalendarEvent
    domain = CalendarDomain(_fake_hass())
    today = _now().date()
    domain._cached_events = [
        CalendarEvent(
            summary="Ferie",
            start=datetime(today.year, today.month, today.day, tzinfo=timezone.utc),
            end=datetime(today.year, today.month, today.day + 1, tzinfo=timezone.utc),
            all_day=True,
            category="vacation",
            calendar_entity="calendar.test",
        )
    ]
    domain._cache_ts = _now()
    d = domain.diagnostics()
    assert d["cached_events_count"] == 1
    assert d["cache_ts"] is not None
    ev = d["cached_events"][0]
    assert ev["summary"] == "Ferie"
    assert ev["category"] == "vacation"
    assert ev["all_day"] is True
