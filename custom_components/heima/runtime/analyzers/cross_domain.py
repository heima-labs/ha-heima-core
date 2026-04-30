"""Cross-domain pattern analyzers for room-scoped composite assist proposals."""

# mypy: disable-error-code=index

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..event_store import EventStore, HeimaEvent
from ..plugin_contracts import BehaviorFinding, pattern_finding
from .base import ReactionProposal, compute_house_state_filter
from .composite import (
    CompositePatternSpec,
    CompositeSignalSpec,
    RoomScopedCompositeMatcher,
)
from .learning_diagnostics import build_learning_diagnostics
from .lighting_vacancy import median_vacancy_delay_s
from .pattern_library import CompositeLearningPatternDefinition

_MIN_OCCURRENCES = 5
_MIN_WEEKS = 2
_HUMIDITY_RISE_THRESHOLD = 8.0
_TEMPERATURE_RISE_THRESHOLD = 0.8
_CO2_RISE_THRESHOLD = 200.0
_ROOM_LUX_LOW_THRESHOLD = 120.0
_CORRELATION_WINDOW_S = 10 * 60
_FOLLOWUP_WINDOW_S = 15 * 60


@dataclass(frozen=True)
class CompositeProposalQualityPolicy:
    """Quality policy for composite proposal payload stabilization."""

    followup_entity_min_ratio: float = 0.5
    followup_entity_min_episodes: int = 3
    corroboration_promote_min_ratio: float = 0.6
    corroboration_promote_min_episodes: int = 3
    minimal_evidence_confidence_cap: float = 0.86
    near_minimal_evidence_confidence_cap: float = 0.90
    minimal_evidence_max_confirmed: int = 6
    minimal_evidence_max_weeks: int = 2
    near_minimal_evidence_max_confirmed: int = 7
    near_minimal_evidence_max_weeks: int = 3
    corroboration_cap_bonus: float = 0.02


DEFAULT_COMPOSITE_PROPOSAL_QUALITY_POLICY = CompositeProposalQualityPolicy()


def composite_quality_policy_from_learning_config(
    learning_config: dict[str, Any] | None,
) -> CompositeProposalQualityPolicy:
    """Build a composite proposal quality policy from learning config overrides."""
    raw = dict(learning_config or {})
    policy_raw = raw.get("composite_quality_policy")
    if not isinstance(policy_raw, dict):
        return DEFAULT_COMPOSITE_PROPOSAL_QUALITY_POLICY

    default = DEFAULT_COMPOSITE_PROPOSAL_QUALITY_POLICY
    return CompositeProposalQualityPolicy(
        followup_entity_min_ratio=_coerce_ratio(
            policy_raw.get("followup_entity_min_ratio"),
            default.followup_entity_min_ratio,
        ),
        followup_entity_min_episodes=_coerce_positive_int(
            policy_raw.get("followup_entity_min_episodes"),
            default.followup_entity_min_episodes,
        ),
        corroboration_promote_min_ratio=_coerce_ratio(
            policy_raw.get("corroboration_promote_min_ratio"),
            default.corroboration_promote_min_ratio,
        ),
        corroboration_promote_min_episodes=_coerce_positive_int(
            policy_raw.get("corroboration_promote_min_episodes"),
            default.corroboration_promote_min_episodes,
        ),
        minimal_evidence_confidence_cap=_coerce_ratio(
            policy_raw.get("minimal_evidence_confidence_cap"),
            default.minimal_evidence_confidence_cap,
        ),
        near_minimal_evidence_confidence_cap=_coerce_ratio(
            policy_raw.get("near_minimal_evidence_confidence_cap"),
            default.near_minimal_evidence_confidence_cap,
        ),
        minimal_evidence_max_confirmed=_coerce_positive_int(
            policy_raw.get("minimal_evidence_max_confirmed"),
            default.minimal_evidence_max_confirmed,
        ),
        minimal_evidence_max_weeks=_coerce_positive_int(
            policy_raw.get("minimal_evidence_max_weeks"),
            default.minimal_evidence_max_weeks,
        ),
        near_minimal_evidence_max_confirmed=_coerce_positive_int(
            policy_raw.get("near_minimal_evidence_max_confirmed"),
            default.near_minimal_evidence_max_confirmed,
        ),
        near_minimal_evidence_max_weeks=_coerce_positive_int(
            policy_raw.get("near_minimal_evidence_max_weeks"),
            default.near_minimal_evidence_max_weeks,
        ),
        corroboration_cap_bonus=_coerce_ratio(
            policy_raw.get("corroboration_cap_bonus"),
            default.corroboration_cap_bonus,
        ),
    )


class CrossDomainPatternAnalyzer:
    """Detect room-scoped humidity burst + occupancy + ventilation follow-up patterns."""

    def __init__(
        self,
        *,
        quality_policy: CompositeProposalQualityPolicy | None = None,
    ) -> None:
        self._matcher = RoomScopedCompositeMatcher()
        self._definition = _definition_by_pattern_id("room_signal_assist")
        self._quality_policy = quality_policy or DEFAULT_COMPOSITE_PROPOSAL_QUALITY_POLICY

    @property
    def analyzer_id(self) -> str:
        return self._definition.analyzer_id

    async def analyze(
        self,
        event_store: EventStore,
        snapshot_store: Any | None = None,
    ) -> list[BehaviorFinding]:
        del snapshot_store
        proposals = await _analyze_definition(
            event_store=event_store,
            matcher=self._matcher,
            definition=self._definition,
            quality_policy=self._quality_policy,
        )
        return _proposal_findings(self.analyzer_id, proposals)


class RoomCoolingPatternAnalyzer:
    """Detect room-scoped temperature rise + cooling follow-up patterns."""

    def __init__(
        self,
        *,
        quality_policy: CompositeProposalQualityPolicy | None = None,
    ) -> None:
        self._matcher = RoomScopedCompositeMatcher()
        self._definition = _definition_by_pattern_id("room_cooling_assist")
        self._quality_policy = quality_policy or DEFAULT_COMPOSITE_PROPOSAL_QUALITY_POLICY

    @property
    def analyzer_id(self) -> str:
        return self._definition.analyzer_id

    async def analyze(
        self,
        event_store: EventStore,
        snapshot_store: Any | None = None,
    ) -> list[BehaviorFinding]:
        del snapshot_store
        proposals = await _analyze_definition(
            event_store=event_store,
            matcher=self._matcher,
            definition=self._definition,
            quality_policy=self._quality_policy,
        )
        return _proposal_findings(self.analyzer_id, proposals)


class CompositePatternCatalogAnalyzer:
    """Run the declared composite pattern catalog through one shared analyzer path."""

    def __init__(
        self,
        *,
        catalog: tuple[CompositeLearningPatternDefinition, ...] | None = None,
        quality_policy: CompositeProposalQualityPolicy | None = None,
    ) -> None:
        self._matcher = RoomScopedCompositeMatcher()
        self._catalog = tuple(catalog or DEFAULT_COMPOSITE_PATTERN_CATALOG)
        self._quality_policy = quality_policy or DEFAULT_COMPOSITE_PROPOSAL_QUALITY_POLICY

    @property
    def analyzer_id(self) -> str:
        return "CompositePatternCatalogAnalyzer"

    async def analyze(
        self,
        event_store: EventStore,
        snapshot_store: Any | None = None,
    ) -> list[BehaviorFinding]:
        del snapshot_store
        proposals: list[ReactionProposal] = []
        for definition in self._catalog:
            proposals.extend(
                await _analyze_definition(
                    event_store=event_store,
                    matcher=self._matcher,
                    definition=definition,
                    quality_policy=self._quality_policy,
                )
            )
        return _proposal_findings(self.analyzer_id, _dominant_composite_candidates(proposals))


async def rooms_with_confirmed_pattern_evidence(
    event_store: EventStore,
    *,
    pattern_id: str,
) -> set[str]:
    """Return rooms whose event history already satisfies a catalog pattern."""

    matcher = RoomScopedCompositeMatcher()
    definition = _definition_by_pattern_id(pattern_id)
    events = await _events_for_definition(event_store, definition)
    if not events:
        return set()

    by_room: dict[str, list[HeimaEvent]] = {}
    for event in events:
        by_room.setdefault(str(event.room_id), []).append(event)

    confirmed_rooms: set[str] = set()
    for room_id, room_events in by_room.items():
        room_events.sort(key=lambda event: event.ts)
        episodes = matcher.detect(room_id=room_id, events=room_events, spec=definition.matcher_spec)
        if len(episodes) < definition.min_occurrences or not _spans_min_weeks(
            episodes, min_weeks=definition.min_weeks
        ):
            continue
        confirmed = [episode for episode in episodes if episode.followup_entities]
        if len(confirmed) < definition.min_occurrences:
            continue
        confirmed_rooms.add(room_id)
    return confirmed_rooms


def _proposal_findings(
    analyzer_id: str,
    proposals: list[ReactionProposal],
) -> list[BehaviorFinding]:
    return [
        pattern_finding(
            analyzer_id=analyzer_id,
            description=proposal.description,
            confidence=proposal.confidence,
            payload=proposal,
        )
        for proposal in proposals
    ]


async def _analyze_definition(
    *,
    event_store: EventStore,
    matcher: RoomScopedCompositeMatcher,
    definition: CompositeLearningPatternDefinition,
    quality_policy: CompositeProposalQualityPolicy,
) -> list[ReactionProposal]:
    events = await _events_for_definition(event_store, definition)
    if not events:
        return []

    by_room: dict[str, list[HeimaEvent]] = {}
    for event in events:
        by_room.setdefault(str(event.room_id), []).append(event)

    proposals: list[ReactionProposal] = []
    for room_id, room_events in by_room.items():
        room_events.sort(key=lambda e: e.ts)
        episodes = matcher.detect(room_id=room_id, events=room_events, spec=definition.matcher_spec)
        if len(episodes) < definition.min_occurrences or not _spans_min_weeks(
            episodes, min_weeks=definition.min_weeks
        ):
            continue

        confirmed = [ep for ep in episodes if ep.followup_entities]
        if len(confirmed) < definition.min_occurrences:
            continue

        house_state_filter = compute_house_state_filter(room_events)
        suggested = definition.suggested_config_builder(room_id, confirmed, quality_policy)
        suggested["house_state_filter"] = house_state_filter  # computed via §3.0.2
        diagnostics = _build_default_diagnostics(
            room_id=room_id,
            definition=definition,
            episodes=episodes,
            confirmed=confirmed,
            quality_policy=quality_policy,
        )
        if definition.diagnostics_builder is not None:
            diagnostics.update(
                definition.diagnostics_builder(
                    room_id,
                    episodes,
                    confirmed,
                    definition.matcher_spec,
                )
            )
        suggested["learning_diagnostics"] = diagnostics
        corroborated = int(suggested.get("corroborated_episodes", 0))
        proposals.append(
            ReactionProposal(
                analyzer_id=definition.analyzer_id,
                reaction_type=definition.reaction_type,
                description=definition.description_builder(room_id, len(confirmed), corroborated),
                confidence=round(
                    _call_composite_confidence_builder(
                        definition.confidence_builder,
                        confirmed,
                        quality_policy,
                    ),
                    3,
                ),
                suggested_reaction_config=suggested,
                fingerprint=(
                    f"{definition.analyzer_id}|{definition.reaction_type}|{room_id}|"
                    f"{definition.fingerprint_key}"
                ),
            )
        )
        if definition.reaction_type == "room_darkness_lighting_assist":
            contextual_candidate = _build_contextual_lighting_candidate(
                room_id=room_id,
                confirmed=confirmed,
                quality_policy=quality_policy,
            )
            if contextual_candidate is not None:
                proposals.append(contextual_candidate)
    return proposals


async def _events_for_definition(
    event_store: EventStore,
    definition: CompositeLearningPatternDefinition,
) -> list[HeimaEvent]:
    events: list[HeimaEvent] = []
    for event_type in _event_types_for_definition(definition):
        events.extend(await event_store.async_query(event_type=event_type))
    return [event for event in events if isinstance(event, HeimaEvent) and event.room_id]


def _event_types_for_definition(
    definition: CompositeLearningPatternDefinition,
) -> tuple[str, ...]:
    reaction_type = str(definition.reaction_type or "").strip()
    if reaction_type == "room_darkness_lighting_assist":
        return ("room_signal_threshold", "lighting", "room_occupancy")
    if reaction_type == "room_vacancy_lighting_off":
        return ("room_occupancy", "lighting")
    if reaction_type == "room_air_quality_assist":
        return ("room_signal_threshold", "actuation", "room_occupancy")
    if reaction_type == "room_signal_assist":
        return ("room_signal_threshold", "actuation", "room_occupancy")
    if reaction_type == "room_cooling_assist":
        return ("room_signal_burst", "actuation", "room_occupancy")
    return ("room_signal_threshold", "actuation", "lighting", "room_occupancy")


def _is_user_lighting_on_event(event: HeimaEvent) -> bool:
    if event.event_type != "lighting":
        return False
    if event.source != "user":
        return False
    return str(event.data.get("action") or "") == "on"


def _is_user_lighting_off_event(event: HeimaEvent) -> bool:
    if event.event_type != "lighting":
        return False
    if event.source != "user":
        return False
    return str(event.data.get("action") or "") == "off"


def _is_room_vacancy_event(event: HeimaEvent) -> bool:
    if event.event_type != "room_occupancy":
        return False
    return str(event.data.get("transition") or "").strip() == "vacant"


def _is_cooling_followup_event(event: HeimaEvent) -> bool:
    if event.event_type != "actuation":
        return False
    entity_id = str(event.subject_id or event.data.get("entity_id") or "")
    domain = str(event.domain or "")
    action = str(event.data.get("action") or "").lower()
    if domain in {"fan", "switch"} or entity_id.startswith(("fan.", "switch.")):
        return action == "on"
    if domain == "climate" or entity_id.startswith("climate."):
        return action in {"cool", "cooling", "dry", "fan_only", "on"}
    return False


def _is_ventilation_followup_event(event: HeimaEvent) -> bool:
    if event.event_type != "actuation":
        return False
    entity_id = str(event.subject_id or event.data.get("entity_id") or "")
    domain = str(event.domain or "")
    action = str(event.data.get("action") or "").lower()
    if domain in {"fan", "switch"} or entity_id.startswith(("fan.", "switch.")):
        return action == "on"
    if domain == "climate" or entity_id.startswith("climate."):
        return action in {"fan_only", "on"}
    return False


def _spans_min_weeks(episodes: list, *, min_weeks: int) -> bool:
    weeks: set[tuple[int, int]] = set()
    for episode in episodes:
        iso = episode.ts.isocalendar()
        weeks.add((iso.year, iso.week))
    return len(weeks) >= min_weeks


def _corroborated_ratio(episodes: list, key: str) -> float:
    if not episodes:
        return 0.0
    return sum(1 for ep in episodes if ep.corroboration_matches.get(key)) / len(episodes)


def _composite_confidence(
    confirmed: list,
    *,
    base: float,
    cap: float,
    quality_policy: CompositeProposalQualityPolicy,
    corroboration_key: str | None = None,
) -> float:
    count = len(confirmed)
    weeks = _episode_week_count(confirmed)
    corroboration_ratio = (
        _corroborated_ratio(confirmed, corroboration_key) if corroboration_key else 0.0
    )

    confidence = base
    confidence += min(0.24, 0.045 * count)
    confidence += min(0.12, 0.05 * max(0, weeks - 1))
    if corroboration_key:
        confidence += min(0.08, 0.08 * corroboration_ratio)

    # Keep barely-above-gate patterns below the maximum until they gather
    # more observations across weeks.
    if (
        count <= quality_policy.minimal_evidence_max_confirmed
        and weeks <= quality_policy.minimal_evidence_max_weeks
    ):
        cap = min(
            cap,
            quality_policy.minimal_evidence_confidence_cap
            + (quality_policy.corroboration_cap_bonus * corroboration_ratio),
        )
    elif (
        count <= quality_policy.near_minimal_evidence_max_confirmed
        and weeks <= quality_policy.near_minimal_evidence_max_weeks
    ):
        cap = min(
            cap,
            quality_policy.near_minimal_evidence_confidence_cap
            + (quality_policy.corroboration_cap_bonus * corroboration_ratio),
        )

    return min(cap, round(confidence, 3))


def _call_composite_confidence_builder(
    builder: Any,
    confirmed: list,
    quality_policy: CompositeProposalQualityPolicy,
) -> float:
    try:
        return float(builder(confirmed, quality_policy))
    except TypeError:
        return float(builder(confirmed))


def _stable_entities_from_corroboration(
    confirmed: list,
    key: str,
    *,
    quality_policy: CompositeProposalQualityPolicy,
) -> list[str]:
    counts: dict[str, int] = {}
    total = len(confirmed)
    if total <= 0:
        return []
    for episode in confirmed:
        matched = {
            entity_id for entity_id in episode.corroboration_matches.get(key, ()) if entity_id
        }
        for entity_id in matched:
            counts[entity_id] = counts.get(entity_id, 0) + 1
    return _stable_entities_from_counts(
        counts,
        total=total,
        min_ratio=quality_policy.corroboration_promote_min_ratio,
        min_episodes=quality_policy.corroboration_promote_min_episodes,
    )


def _stable_followup_entities(
    confirmed: list,
    *,
    quality_policy: CompositeProposalQualityPolicy,
) -> list[str]:
    counts: dict[str, int] = {}
    total = len(confirmed)
    if total <= 0:
        return []
    for episode in confirmed:
        matched = {entity_id for entity_id in episode.followup_entities if entity_id}
        for entity_id in matched:
            counts[entity_id] = counts.get(entity_id, 0) + 1
    return _stable_entities_from_counts(
        counts,
        total=total,
        min_ratio=quality_policy.followup_entity_min_ratio,
        min_episodes=quality_policy.followup_entity_min_episodes,
    )


def _stable_entities_from_counts(
    counts: dict[str, int],
    *,
    total: int,
    min_ratio: float,
    min_episodes: int,
) -> list[str]:
    stable: list[str] = []
    for entity_id, count in counts.items():
        ratio = _ratio(count, total)
        if count < min_episodes:
            continue
        if ratio < min_ratio:
            continue
        stable.append(entity_id)
    return sorted(stable)


def _dominant_composite_candidates(
    proposals: list[ReactionProposal],
) -> list[ReactionProposal]:
    by_slot: dict[str, ReactionProposal] = {}
    for proposal in proposals:
        slot_key = _composite_slot_key(proposal)
        current = by_slot.get(slot_key)
        if current is None or _composite_candidate_rank(proposal) > _composite_candidate_rank(
            current
        ):
            by_slot[slot_key] = proposal
    return sorted(
        by_slot.values(),
        key=lambda proposal: (
            str(proposal.reaction_type),
            str(_safe_dict(proposal.suggested_reaction_config).get("room_id") or ""),
            str(proposal.description),
        ),
    )


def _composite_slot_key(proposal: ReactionProposal) -> str:
    cfg = _safe_dict(proposal.suggested_reaction_config)
    primary_signal = str(cfg.get("primary_signal_name") or "").strip().lower()
    return f"{proposal.reaction_type}|room={cfg.get('room_id')}|primary={primary_signal}"


def _composite_candidate_rank(proposal: ReactionProposal) -> tuple[float, int, int, str]:
    cfg = _safe_dict(proposal.suggested_reaction_config)
    return (
        float(proposal.confidence),
        int(cfg.get("episodes_observed") or 0),
        int(cfg.get("corroborated_episodes") or 0),
        str(proposal.description),
    )


def _build_signal_assist_config(
    room_id: str,
    confirmed: list,
    quality_policy: CompositeProposalQualityPolicy,
) -> dict[str, Any]:
    humidity_entities = sorted({ep.primary_entity for ep in confirmed if ep.primary_entity})
    temperature_entities = _stable_entities_from_corroboration(
        confirmed,
        "temperature",
        quality_policy=quality_policy,
    )
    followup_entities = _stable_followup_entities(confirmed, quality_policy=quality_policy)
    return {
        "reaction_type": "room_signal_assist",
        "room_id": room_id,
        "trigger_signal_entities": humidity_entities,
        "primary_signal_entities": humidity_entities,
        "primary_signal_name": "room_humidity",
        "primary_bucket": "high",
        "temperature_signal_entities": temperature_entities,
        "corroboration_signal_entities": temperature_entities,
        "corroboration_signal_name": "room_temperature",
        "corroboration_bucket": "warm",
        "humidity_rise_threshold": _HUMIDITY_RISE_THRESHOLD,
        "temperature_rise_threshold": _TEMPERATURE_RISE_THRESHOLD,
        "correlation_window_s": _CORRELATION_WINDOW_S,
        "followup_window_s": _FOLLOWUP_WINDOW_S,
        "steps": [],
        "episodes_observed": len(confirmed),
        "corroborated_episodes": sum(
            1 for ep in confirmed if ep.corroboration_matches.get("temperature")
        ),
        "observed_followup_entities": followup_entities,
    }


def _build_cooling_assist_config(
    room_id: str,
    confirmed: list,
    quality_policy: CompositeProposalQualityPolicy,
) -> dict[str, Any]:
    temperature_entities = sorted({ep.primary_entity for ep in confirmed if ep.primary_entity})
    humidity_entities = _stable_entities_from_corroboration(
        confirmed,
        "humidity",
        quality_policy=quality_policy,
    )
    followup_entities = _stable_followup_entities(confirmed, quality_policy=quality_policy)
    corroborated_count = sum(1 for ep in confirmed if ep.corroboration_matches.get("humidity"))
    return {
        "reaction_type": "room_cooling_assist",
        "room_id": room_id,
        "primary_signal_entities": temperature_entities,
        "primary_signal_name": "room_temperature",
        "corroboration_signal_entities": humidity_entities,
        "corroboration_signal_name": "room_humidity",
        "followup_window_s": _FOLLOWUP_WINDOW_S,
        "steps": [],
        "episodes_observed": len(confirmed),
        "corroborated_episodes": corroborated_count,
        "observed_followup_entities": followup_entities,
    }


def _build_air_quality_assist_config(
    room_id: str,
    confirmed: list,
    quality_policy: CompositeProposalQualityPolicy,
) -> dict[str, Any]:
    co2_entities = sorted({ep.primary_entity for ep in confirmed if ep.primary_entity})
    followup_entities = _stable_followup_entities(confirmed, quality_policy=quality_policy)
    return {
        "reaction_type": "room_air_quality_assist",
        "room_id": room_id,
        "trigger_signal_entities": co2_entities,
        "primary_signal_entities": co2_entities,
        "primary_signal_name": "room_co2",
        "primary_bucket": "elevated",
        "temperature_signal_entities": [],
        "corroboration_signal_entities": [],
        "corroboration_signal_name": "corroboration",
        "correlation_window_s": _CORRELATION_WINDOW_S,
        "followup_window_s": _FOLLOWUP_WINDOW_S,
        "steps": [],
        "episodes_observed": len(confirmed),
        "corroborated_episodes": 0,
        "observed_followup_entities": followup_entities,
    }


def _build_darkness_lighting_assist_config(
    room_id: str,
    confirmed: list,
    quality_policy: CompositeProposalQualityPolicy,
) -> dict[str, Any]:
    lux_entities = sorted({ep.primary_entity for ep in confirmed if ep.primary_entity})
    entity_steps = _aggregate_lighting_followup_steps(confirmed, quality_policy=quality_policy)
    followup_entities = sorted(
        {step["entity_id"] for step in entity_steps if step.get("entity_id")}
    )
    return {
        "reaction_type": "room_darkness_lighting_assist",
        "room_id": room_id,
        "primary_signal_entities": lux_entities,
        "primary_bucket": "dim",
        "primary_signal_name": "room_lux",
        "corroboration_signal_entities": [],
        "corroboration_signal_name": "corroboration",
        "correlation_window_s": _CORRELATION_WINDOW_S,
        "followup_window_s": _FOLLOWUP_WINDOW_S,
        "entity_steps": entity_steps,
        "episodes_observed": len(confirmed),
        "observed_followup_entities": followup_entities,
    }


def _build_contextual_lighting_candidate(
    *,
    room_id: str,
    confirmed: list,
    quality_policy: CompositeProposalQualityPolicy,
) -> ReactionProposal | None:
    grouped = _contextual_episode_groups(confirmed)
    stable_groups: dict[str, list] = {}
    profiles: dict[str, dict[str, Any]] = {}
    for profile_name, episodes in grouped.items():
        if len(episodes) < 2:
            continue
        entity_steps = _aggregate_lighting_followup_steps(episodes, quality_policy=quality_policy)
        if not entity_steps:
            continue
        stable_groups[profile_name] = episodes
        profiles[profile_name] = {"entity_steps": entity_steps}
    if len(stable_groups) < 2:
        return None

    step_signatures = {
        _lighting_steps_signature(payload.get("entity_steps") or [])
        for payload in profiles.values()
        if payload.get("entity_steps")
    }
    if len(step_signatures) < 2:
        return None

    lux_entities = sorted({ep.primary_entity for ep in confirmed if ep.primary_entity})
    observed_followup_entities = sorted(
        {
            step["entity_id"]
            for payload in profiles.values()
            for step in list(payload.get("entity_steps") or [])
            if isinstance(step, dict) and step.get("entity_id")
        }
    )
    diagnostics = build_learning_diagnostics(
        pattern_id="room_contextual_lighting_assist",
        analyzer_id="CompositePatternCatalogAnalyzer",
        reaction_type="room_contextual_lighting_assist",
        plugin_family="composite_room_assist",
        room_id=room_id,
        primary_signal="room_lux",
        corroboration_signals=[],
        followup_signal="lighting_replay",
        require_room_occupancy=True,
        correlation_window_s=_CORRELATION_WINDOW_S,
        followup_window_s=_FOLLOWUP_WINDOW_S,
        episodes_detected=len(confirmed),
        episodes_confirmed=len(confirmed),
        weeks_observed=_episode_week_count(confirmed),
        corroborated_episodes=0,
        followup_entity_min_ratio=quality_policy.followup_entity_min_ratio,
        followup_entity_min_episodes=quality_policy.followup_entity_min_episodes,
        corroboration_promote_min_ratio=quality_policy.corroboration_promote_min_ratio,
        corroboration_promote_min_episodes=quality_policy.corroboration_promote_min_episodes,
        matched_primary_entities=lux_entities,
        matched_corroboration_entities=[],
        observed_followup_entities=observed_followup_entities,
    )
    diagnostics["contextual_profiles"] = sorted(profiles)
    diagnostics["contextual_variation_dimensions"] = _contextual_variation_dimensions(stable_groups)

    suggested = {
        "reaction_type": "room_contextual_lighting_assist",
        "room_id": room_id,
        "primary_signal_entities": lux_entities,
        "primary_signal_name": "room_lux",
        "primary_bucket": "dim",
        "primary_bucket_match_mode": "lte",
        "followup_window_s": _FOLLOWUP_WINDOW_S,
        "profiles": profiles,
        "rules": _contextual_rules_for_profiles(sorted(profiles)),
        "default_profile": _contextual_default_profile(profiles),
        "episodes_observed": len(confirmed),
        "observed_followup_entities": observed_followup_entities,
        "improvement_reason": "contextual_variation",
        "learning_diagnostics": diagnostics,
    }
    return ReactionProposal(
        analyzer_id="CompositePatternCatalogAnalyzer",
        reaction_type="room_contextual_lighting_assist",
        description=(
            f"{room_id}: contextual lighting upgrade — darkness-triggered lighting varies "
            f"by time/context ({len(confirmed)} observed episodes)."
        ),
        confidence=round(min(0.91, 0.50 + (0.04 * len(confirmed))), 3),
        followup_kind="discovery",
        suggested_reaction_config=suggested,
        fingerprint=(
            "CompositePatternCatalogAnalyzer|room_contextual_lighting_assist|"
            f"{room_id}|darkness_context_variation"
        ),
    )


def _build_vacancy_lighting_off_config(
    room_id: str,
    confirmed: list,
    quality_policy: CompositeProposalQualityPolicy,
) -> dict[str, Any]:
    entity_steps = [
        step
        for step in _aggregate_lighting_followup_steps(confirmed, quality_policy=quality_policy)
        if str(step.get("action") or "").strip() == "off"
    ]
    followup_entities = sorted(
        {step["entity_id"] for step in entity_steps if step.get("entity_id")}
    )
    return {
        "reaction_type": "room_vacancy_lighting_off",
        "room_id": room_id,
        "vacancy_delay_s": median_vacancy_delay_s(confirmed),
        "followup_window_s": _FOLLOWUP_WINDOW_S,
        "entity_steps": entity_steps,
        "episodes_observed": len(confirmed),
        "observed_followup_entities": followup_entities,
    }


def _build_default_diagnostics(
    *,
    room_id: str,
    definition: CompositeLearningPatternDefinition,
    episodes: list,
    confirmed: list,
    quality_policy: CompositeProposalQualityPolicy,
) -> dict[str, Any]:
    corroboration_signal_names = [signal.name for signal in definition.matcher_spec.corroborations]
    primary_entities = sorted({ep.primary_entity for ep in confirmed if ep.primary_entity})
    corroboration_entities = sorted(
        {
            entity_id
            for ep in confirmed
            for matches in ep.corroboration_matches.values()
            for entity_id in matches
            if entity_id
        }
    )
    followup_entities = sorted(
        {entity_id for ep in confirmed for entity_id in ep.followup_entities if entity_id}
    )
    return build_learning_diagnostics(
        pattern_id=definition.pattern_id,
        analyzer_id=definition.analyzer_id,
        reaction_type=definition.reaction_type,
        plugin_family="composite_room_assist",
        room_id=room_id,
        primary_signal=definition.matcher_spec.primary.name,
        corroboration_signals=corroboration_signal_names,
        followup_signal=(
            definition.matcher_spec.followup.name
            if definition.matcher_spec.followup is not None
            else None
        ),
        require_room_occupancy=definition.matcher_spec.require_room_occupancy,
        correlation_window_s=definition.matcher_spec.correlation_window_s,
        followup_window_s=definition.matcher_spec.followup_window_s,
        episodes_detected=len(episodes),
        episodes_confirmed=len(confirmed),
        weeks_observed=_episode_week_count(episodes),
        corroborated_episodes=sum(1 for ep in confirmed if any(ep.corroboration_matches.values())),
        followup_entity_min_ratio=quality_policy.followup_entity_min_ratio,
        followup_entity_min_episodes=quality_policy.followup_entity_min_episodes,
        corroboration_promote_min_ratio=quality_policy.corroboration_promote_min_ratio,
        corroboration_promote_min_episodes=quality_policy.corroboration_promote_min_episodes,
        matched_primary_entities=primary_entities,
        matched_corroboration_entities=corroboration_entities,
        observed_followup_entities=followup_entities,
    )


def _describe(room_id: str, observed: int, corroborated: int) -> str:
    if corroborated:
        return (
            f"{room_id}: humidity assist — when occupancy is present and humidity rises rapidly, "
            f"you usually start ventilation within a few minutes "
            f"({observed} episodes, {corroborated} temperature-correlated)."
        )
    return (
        f"{room_id}: humidity assist — when occupancy is present and humidity rises rapidly, "
        f"you usually start ventilation within a few minutes "
        f"({observed} observed episodes)."
    )


def _describe_cooling(room_id: str, observed: int, corroborated: int) -> str:
    if corroborated:
        return (
            f"{room_id}: cooling assist — when occupancy is present and temperature rises quickly, "
            f"you usually start cooling within a few minutes "
            f"({observed} episodes, {corroborated} humidity-correlated)."
        )
    return (
        f"{room_id}: cooling assist — when occupancy is present and temperature rises quickly, "
        f"you usually start cooling within a few minutes "
        f"({observed} observed episodes)."
    )


def _describe_air_quality(room_id: str, observed: int, corroborated: int) -> str:
    del corroborated
    return (
        f"{room_id}: air quality assist — when occupancy is present and CO2 rises quickly, "
        f"you usually start ventilation within a few minutes "
        f"({observed} observed episodes)."
    )


def _describe_darkness_lighting(room_id: str, observed: int, corroborated: int) -> str:
    del corroborated
    return (
        f"{room_id}: darkness lighting assist — when the room becomes too dark while occupied, "
        f"you usually turn on lights with a similar brightness "
        f"({observed} observed episodes)."
    )


def _describe_vacancy_lighting_off(room_id: str, observed: int, corroborated: int) -> str:
    del corroborated
    return (
        f"{room_id}: vacancy lights-off assist — when the room stays vacant, "
        f"you usually turn lights off after a short delay "
        f"({observed} observed episodes)."
    )


_ROOM_SIGNAL_ASSIST_PATTERN = CompositeLearningPatternDefinition(
    pattern_id="room_signal_assist",
    analyzer_id="CrossDomainPatternAnalyzer",
    reaction_type="room_signal_assist",
    fingerprint_key="humidity_burst",
    matcher_spec=CompositePatternSpec(
        primary=CompositeSignalSpec(
            name="humidity",
            predicate=lambda event: (
                event.event_type == "room_signal_threshold"
                and str(event.subject_id or "").strip() == "room_humidity"
                and str(event.data.get("to_bucket") or "").strip() == "high"
            ),
            min_delta=None,
        ),
        corroborations=(
            CompositeSignalSpec(
                name="temperature",
                predicate=lambda event: (
                    event.event_type == "room_signal_threshold"
                    and str(event.subject_id or "").strip() == "room_temperature"
                    and str(event.data.get("to_bucket") or "").strip() in {"warm", "hot"}
                ),
                min_delta=None,
                required=False,
            ),
        ),
        followup=CompositeSignalSpec(
            name="ventilation",
            predicate=_is_ventilation_followup_event,
        ),
        require_room_occupancy=True,
        correlation_window_s=_CORRELATION_WINDOW_S,
        followup_window_s=_FOLLOWUP_WINDOW_S,
    ),
    min_occurrences=_MIN_OCCURRENCES,
    min_weeks=_MIN_WEEKS,
    description_builder=_describe,
    suggested_config_builder=lambda room_id, confirmed, quality_policy: _build_signal_assist_config(
        room_id, confirmed, quality_policy
    ),
    confidence_builder=lambda confirmed, quality_policy: _composite_confidence(
        confirmed,
        base=0.46,
        cap=0.95,
        quality_policy=quality_policy,
        corroboration_key="temperature",
    ),
)


_ROOM_COOLING_PATTERN = CompositeLearningPatternDefinition(
    pattern_id="room_cooling_assist",
    analyzer_id="RoomCoolingPatternAnalyzer",
    reaction_type="room_cooling_assist",
    fingerprint_key="temperature_rise",
    matcher_spec=CompositePatternSpec(
        primary=CompositeSignalSpec(
            name="room_temperature",
            predicate=lambda event: (
                event.event_type == "room_signal_burst"
                and str(event.subject_id or "").strip() == "room_temperature"
            ),
            min_delta=None,
        ),
        corroborations=(
            CompositeSignalSpec(
                name="humidity",
                predicate=lambda event: (
                    event.event_type == "room_signal_burst"
                    and str(event.subject_id or "").strip() == "room_humidity"
                ),
                min_delta=None,
                required=False,
            ),
        ),
        followup=CompositeSignalSpec(
            name="cooling",
            predicate=_is_cooling_followup_event,
        ),
        require_room_occupancy=True,
        correlation_window_s=_CORRELATION_WINDOW_S,
        followup_window_s=_FOLLOWUP_WINDOW_S,
    ),
    min_occurrences=_MIN_OCCURRENCES,
    min_weeks=_MIN_WEEKS,
    description_builder=_describe_cooling,
    suggested_config_builder=lambda room_id, confirmed, quality_policy: (
        _build_cooling_assist_config(room_id, confirmed, quality_policy)
    ),
    confidence_builder=lambda confirmed, quality_policy: _composite_confidence(
        confirmed,
        base=0.43,
        cap=0.95,
        quality_policy=quality_policy,
        corroboration_key="humidity",
    ),
)


_ROOM_AIR_QUALITY_PATTERN = CompositeLearningPatternDefinition(
    pattern_id="room_air_quality_assist",
    analyzer_id="CompositePatternCatalogAnalyzer",
    reaction_type="room_air_quality_assist",
    fingerprint_key="co2_rise",
    matcher_spec=CompositePatternSpec(
        primary=CompositeSignalSpec(
            name="co2",
            predicate=lambda event: (
                event.event_type == "room_signal_threshold"
                and str(event.subject_id or "").strip() == "room_co2"
                and str(event.data.get("to_bucket") or "").strip() in {"elevated", "high"}
            ),
            min_delta=None,
        ),
        followup=CompositeSignalSpec(
            name="ventilation",
            predicate=_is_ventilation_followup_event,
        ),
        require_room_occupancy=True,
        correlation_window_s=_CORRELATION_WINDOW_S,
        followup_window_s=_FOLLOWUP_WINDOW_S,
    ),
    min_occurrences=_MIN_OCCURRENCES,
    min_weeks=_MIN_WEEKS,
    description_builder=_describe_air_quality,
    suggested_config_builder=lambda room_id, confirmed, quality_policy: (
        _build_air_quality_assist_config(room_id, confirmed, quality_policy)
    ),
    confidence_builder=lambda confirmed, quality_policy: _composite_confidence(
        confirmed,
        base=0.41,
        cap=0.93,
        quality_policy=quality_policy,
    ),
)


_ROOM_DARKNESS_LIGHTING_PATTERN = CompositeLearningPatternDefinition(
    pattern_id="room_darkness_lighting_assist",
    analyzer_id="CompositePatternCatalogAnalyzer",
    reaction_type="room_darkness_lighting_assist",
    fingerprint_key="room_lux_low",
    matcher_spec=CompositePatternSpec(
        primary=CompositeSignalSpec(
            name="room_lux",
            predicate=lambda event: (
                event.event_type == "room_signal_threshold"
                and str(event.subject_id or "").strip() == "room_lux"
                and str(event.data.get("to_bucket") or "").strip() in {"dim", "dark"}
            ),
            min_delta=None,
        ),
        followup=CompositeSignalSpec(
            name="lighting_replay",
            predicate=_is_user_lighting_on_event,
        ),
        require_room_occupancy=True,
        correlation_window_s=_CORRELATION_WINDOW_S,
        followup_window_s=_FOLLOWUP_WINDOW_S,
    ),
    min_occurrences=_MIN_OCCURRENCES,
    min_weeks=_MIN_WEEKS,
    description_builder=_describe_darkness_lighting,
    suggested_config_builder=lambda room_id, confirmed, quality_policy: (
        _build_darkness_lighting_assist_config(room_id, confirmed, quality_policy)
    ),
    confidence_builder=lambda confirmed, quality_policy: _composite_confidence(
        confirmed,
        base=0.43,
        cap=0.94,
        quality_policy=quality_policy,
    ),
)


_ROOM_VACANCY_LIGHTING_OFF_PATTERN = CompositeLearningPatternDefinition(
    pattern_id="room_vacancy_lighting_off",
    analyzer_id="CompositePatternCatalogAnalyzer",
    reaction_type="room_vacancy_lighting_off",
    fingerprint_key="room_vacancy",
    matcher_spec=CompositePatternSpec(
        primary=CompositeSignalSpec(
            name="room_vacancy",
            predicate=_is_room_vacancy_event,
            min_delta=None,
        ),
        followup=CompositeSignalSpec(
            name="lighting_replay_off",
            predicate=_is_user_lighting_off_event,
        ),
        require_room_occupancy=False,
        correlation_window_s=_CORRELATION_WINDOW_S,
        followup_window_s=_FOLLOWUP_WINDOW_S,
    ),
    min_occurrences=_MIN_OCCURRENCES,
    min_weeks=_MIN_WEEKS,
    description_builder=_describe_vacancy_lighting_off,
    suggested_config_builder=lambda room_id, confirmed, quality_policy: (
        _build_vacancy_lighting_off_config(room_id, confirmed, quality_policy)
    ),
    confidence_builder=lambda confirmed, quality_policy: _composite_confidence(
        confirmed,
        base=0.42,
        cap=0.92,
        quality_policy=quality_policy,
    ),
)


DEFAULT_COMPOSITE_PATTERN_CATALOG: tuple[CompositeLearningPatternDefinition, ...] = (
    _ROOM_SIGNAL_ASSIST_PATTERN,
    _ROOM_COOLING_PATTERN,
    _ROOM_AIR_QUALITY_PATTERN,
    _ROOM_DARKNESS_LIGHTING_PATTERN,
    _ROOM_VACANCY_LIGHTING_OFF_PATTERN,
)


def _definition_by_pattern_id(pattern_id: str) -> CompositeLearningPatternDefinition:
    for definition in DEFAULT_COMPOSITE_PATTERN_CATALOG:
        if definition.pattern_id == pattern_id:
            return definition
    raise KeyError(pattern_id)


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return part / total


def _safe_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _coerce_ratio(value: Any, default: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if numeric < 0.0:
        return 0.0
    if numeric > 1.0:
        return 1.0
    return numeric


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, numeric)


def _episode_week_count(episodes: list) -> int:
    weeks: set[tuple[int, int]] = set()
    for episode in episodes:
        iso = episode.ts.isocalendar()
        weeks.add((iso.year, iso.week))
    return len(weeks)


def _aggregate_lighting_followup_steps(
    episodes: list,
    *,
    quality_policy: CompositeProposalQualityPolicy,
) -> list[dict[str, Any]]:
    by_entity: dict[str, list[HeimaEvent]] = {}
    episode_counts: dict[str, int] = {}
    total = len(episodes)
    for episode in episodes:
        seen_in_episode: set[str] = set()
        for event in getattr(episode, "followup_events", ()):
            if not isinstance(event, HeimaEvent) or event.event_type != "lighting":
                continue
            entity_id = str(event.data.get("entity_id") or event.subject_id or "").strip()
            if not entity_id:
                continue
            by_entity.setdefault(entity_id, []).append(event)
            seen_in_episode.add(entity_id)
        for entity_id in seen_in_episode:
            episode_counts[entity_id] = episode_counts.get(entity_id, 0) + 1

    steps: list[dict[str, Any]] = []
    stable_entities = set(
        _stable_entities_from_counts(
            episode_counts,
            total=total,
            min_ratio=quality_policy.followup_entity_min_ratio,
            min_episodes=quality_policy.followup_entity_min_episodes,
        )
    )
    for entity_id, group in sorted(by_entity.items()):
        if entity_id not in stable_entities:
            continue
        action_counts: dict[str, int] = {}
        for event in group:
            action_name = str(event.data.get("action") or "on").strip() or "on"
            action_counts[action_name] = action_counts.get(action_name, 0) + 1
        action = max(
            action_counts.items(),
            key=lambda item: (item[1], item[0] == "on", item[0]),
        )[0]
        matching_events = [
            event for event in group if str(event.data.get("action") or "on").strip() == action
        ]
        selected_events = matching_events or group
        brightness = (
            _median_int([e.data.get("brightness") for e in selected_events])
            if action == "on"
            else None
        )
        color_temp = (
            _median_int([e.data.get("color_temp_kelvin") for e in selected_events])
            if action == "on"
            else None
        )
        rgb = (
            _mode_rgb([e.data.get("rgb_color") for e in selected_events])
            if action == "on"
            else None
        )
        steps.append(
            {
                "entity_id": entity_id,
                "action": action,
                "brightness": brightness if action == "on" else None,
                "color_temp_kelvin": color_temp if action == "on" else None,
                "rgb_color": rgb if action == "on" else None,
            }
        )
    return steps


def _lighting_steps_signature(entity_steps: list[dict[str, Any]]) -> tuple[tuple[Any, ...], ...]:
    signature: list[tuple[Any, ...]] = []
    for step in entity_steps:
        signature.append(
            (
                str(step.get("entity_id") or ""),
                str(step.get("action") or ""),
                step.get("brightness"),
                step.get("color_temp_kelvin"),
                tuple(step.get("rgb_color") or []) or None,
            )
        )
    return tuple(sorted(signature))


def _contextual_episode_groups(confirmed: list) -> dict[str, list]:
    grouped: dict[str, list] = {}
    for episode in confirmed:
        profile_name = _contextual_profile_name_for_episode(episode)
        grouped.setdefault(profile_name, []).append(episode)
    return grouped


def _contextual_profile_name_for_episode(episode: Any) -> str:
    context = getattr(next(iter(getattr(episode, "followup_events", ())), None), "context", None)
    house_state = str(getattr(context, "house_state", "") or "").strip()
    minute = getattr(context, "minute_of_day", None)
    if minute is None:
        ts = getattr(episode, "ts", None)
        if ts is not None:
            minute = int(ts.hour) * 60 + int(ts.minute)
        else:
            minute = 0
    minute = int(minute or 0)
    if 8 * 60 <= minute < 18 * 60 + 30 and house_state == "working":
        return "workday_focus"
    if 18 * 60 + 30 <= minute < 23 * 60 + 30:
        return "evening_relax"
    if minute >= 23 * 60 + 30 or minute < 6 * 60 + 30:
        return "night_navigation"
    return "day_generic"


def _contextual_rules_for_profiles(profile_names: list[str]) -> list[dict[str, Any]]:
    ordered_rules: list[dict[str, Any]] = []
    if "workday_focus" in profile_names:
        ordered_rules.append(
            {
                "profile": "workday_focus",
                "house_state_in": ["working"],
                "time_window": {"start": "08:00", "end": "18:30"},
            }
        )
    if "day_generic" in profile_names:
        ordered_rules.append(
            {
                "profile": "day_generic",
                "time_window": {"start": "08:00", "end": "18:30"},
            }
        )
    if "evening_relax" in profile_names:
        ordered_rules.append(
            {
                "profile": "evening_relax",
                "time_window": {"start": "18:30", "end": "23:30"},
            }
        )
    if "night_navigation" in profile_names:
        ordered_rules.append(
            {
                "profile": "night_navigation",
                "time_window": {"start": "23:30", "end": "06:30"},
            }
        )
    return ordered_rules


def _contextual_default_profile(profiles: dict[str, dict[str, Any]]) -> str:
    for profile_name in ("day_generic", "evening_relax", "workday_focus", "night_navigation"):
        if profile_name in profiles:
            return profile_name
    return next(iter(profiles), "day_generic")


def _contextual_variation_dimensions(grouped: dict[str, list]) -> list[str]:
    dimensions: list[str] = []
    if any(name == "workday_focus" for name in grouped) and any(
        name in grouped for name in ("day_generic", "evening_relax", "night_navigation")
    ):
        dimensions.append("house_state")
    if any(name in grouped for name in ("evening_relax", "night_navigation", "day_generic")):
        dimensions.append("time_window")
    return dimensions


def _median_int(values: list[Any]) -> int | None:
    nums = [int(v) for v in values if v is not None]
    if not nums:
        return None
    nums.sort()
    return nums[len(nums) // 2]


def _mode_rgb(values: list[Any]) -> list[int] | None:
    candidates = [tuple(v) for v in values if isinstance(v, (list, tuple)) and len(v) == 3]
    if not candidates:
        return None
    counts: dict[tuple[int, int, int], int] = {}
    for candidate in candidates:
        counts[candidate] = counts.get(candidate, 0) + 1
    return list(max(counts, key=lambda key: counts[key]))
