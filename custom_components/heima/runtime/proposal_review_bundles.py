"""Read models for proposal review bundles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .analyzers.base import ReactionProposal
from .inference.approval_store import HOUSE_STATE_PROPOSAL_TYPE


@dataclass(frozen=True)
class HouseStateTemporalContext:
    """Normalized context used to group house-state proposal review bundles."""

    weekday: int
    hour_bucket: int
    anyone_home: bool
    predicted_state: str
    support: int
    total: int

    @property
    def key(self) -> str:
        return (
            f"weekday:{self.weekday}:"
            f"anyone_home:{1 if self.anyone_home else 0}:"
            f"state:{self.predicted_state}"
        )


@dataclass(frozen=True)
class ProposalReviewBundleMember:
    """One visible proposal represented inside a review bundle."""

    proposal_id: str
    identity_key: str
    hour_bucket: int
    confidence: float
    support: int
    total: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "identity_key": self.identity_key,
            "hour_bucket": self.hour_bucket,
            "confidence": self.confidence,
            "support": self.support,
            "total": self.total,
        }


@dataclass(frozen=True)
class ProposalReviewBundle:
    """Derived bundle of visible proposals for review UX."""

    bundle_id: str
    bundle_type: str
    grouping_key: str
    weekday: int
    start_hour_bucket: int
    end_hour_bucket: int
    anyone_home: bool
    predicted_state: str
    proposal_ids: tuple[str, ...]
    identity_keys: tuple[str, ...]
    member_count: int
    confidence_min: float
    confidence_max: float
    confidence_avg: float
    support_total: int
    total_observations: int
    members: tuple[ProposalReviewBundleMember, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "bundle_type": self.bundle_type,
            "grouping_key": self.grouping_key,
            "weekday": self.weekday,
            "start_hour_bucket": self.start_hour_bucket,
            "end_hour_bucket": self.end_hour_bucket,
            "anyone_home": self.anyone_home,
            "predicted_state": self.predicted_state,
            "proposal_ids": list(self.proposal_ids),
            "identity_keys": list(self.identity_keys),
            "member_count": self.member_count,
            "confidence_min": self.confidence_min,
            "confidence_max": self.confidence_max,
            "confidence_avg": self.confidence_avg,
            "support_total": self.support_total,
            "total_observations": self.total_observations,
            "members": [member.as_dict() for member in self.members],
        }


@dataclass(frozen=True)
class ProposalReviewBundleView:
    """Complete derived view for proposal review bundles."""

    bundles: tuple[ProposalReviewBundle, ...]
    bundled_proposal_ids: tuple[str, ...]
    unbundled_proposal_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "bundles": [bundle.as_dict() for bundle in self.bundles],
            "bundled_proposal_ids": list(self.bundled_proposal_ids),
            "unbundled_proposal_ids": list(self.unbundled_proposal_ids),
        }


def build_temporal_review_bundles(
    proposals: Iterable[Any],
) -> ProposalReviewBundleView:
    """Build temporal review bundles from the already-visible proposal queue.

    The caller owns lifecycle visibility. This helper only groups the proposals it
    receives, so hidden review-group siblings cannot be accidentally included in
    bundle accept/reject actions.
    """

    proposal_list = list(proposals)
    candidates: list[tuple[HouseStateTemporalContext, ReactionProposal]] = []
    for proposal in proposal_list:
        context = _house_state_temporal_context(proposal)
        if context is None:
            continue
        candidates.append((context, proposal))

    by_key: dict[str, list[tuple[HouseStateTemporalContext, ReactionProposal]]] = {}
    for context, proposal in candidates:
        by_key.setdefault(context.key, []).append((context, proposal))

    bundles: list[ProposalReviewBundle] = []
    bundled_ids: set[str] = set()

    for grouping_key, items in by_key.items():
        items.sort(
            key=lambda item: (
                item[0].weekday,
                item[0].hour_bucket,
                -float(item[1].confidence or 0.0),
                _proposal_identity_key(item[1]),
                item[1].proposal_id,
            )
        )
        run: list[tuple[HouseStateTemporalContext, ReactionProposal]] = []
        previous_hour: int | None = None
        for item in items:
            hour = item[0].hour_bucket
            if previous_hour is None or hour == previous_hour + 1:
                run.append(item)
            else:
                bundle = _bundle_from_run(grouping_key, run)
                if bundle is not None:
                    bundles.append(bundle)
                    bundled_ids.update(bundle.proposal_ids)
                run = [item]
            previous_hour = hour

        bundle = _bundle_from_run(grouping_key, run)
        if bundle is not None:
            bundles.append(bundle)
            bundled_ids.update(bundle.proposal_ids)

    bundles.sort(
        key=lambda bundle: (
            bundle.weekday,
            bundle.start_hour_bucket,
            bundle.predicted_state,
            not bundle.anyone_home,
            bundle.bundle_id,
        )
    )
    all_ids = [
        str(getattr(proposal, "proposal_id", "") or "").strip()
        for proposal in proposal_list
        if str(getattr(proposal, "proposal_id", "") or "").strip()
    ]
    unbundled_ids = [
        proposal_id
        for proposal_id in all_ids
        if proposal_id not in bundled_ids
    ]

    return ProposalReviewBundleView(
        bundles=tuple(bundles),
        bundled_proposal_ids=tuple(
            proposal_id
            for bundle in bundles
            for proposal_id in bundle.proposal_ids
        ),
        unbundled_proposal_ids=tuple(unbundled_ids),
    )


def _bundle_from_run(
    grouping_key: str,
    run: list[tuple[HouseStateTemporalContext, ReactionProposal]],
) -> ProposalReviewBundle | None:
    if len(run) < 2:
        return None

    members = tuple(
        ProposalReviewBundleMember(
            proposal_id=proposal.proposal_id,
            identity_key=_proposal_identity_key(proposal),
            hour_bucket=context.hour_bucket,
            confidence=float(proposal.confidence or 0.0),
            support=context.support,
            total=context.total,
        )
        for context, proposal in run
    )
    first_context = run[0][0]
    confidence_values = [member.confidence for member in members]
    start_hour = members[0].hour_bucket
    end_hour = members[-1].hour_bucket
    bundle_id = (
        "house_state_temporal_bundle:"
        f"{grouping_key}:hours:{start_hour}-{end_hour}"
    )
    return ProposalReviewBundle(
        bundle_id=bundle_id,
        bundle_type="house_state_temporal",
        grouping_key=f"house_state_temporal:{grouping_key}",
        weekday=first_context.weekday,
        start_hour_bucket=start_hour,
        end_hour_bucket=end_hour,
        anyone_home=first_context.anyone_home,
        predicted_state=first_context.predicted_state,
        proposal_ids=tuple(member.proposal_id for member in members),
        identity_keys=tuple(member.identity_key for member in members),
        member_count=len(members),
        confidence_min=round(min(confidence_values), 4),
        confidence_max=round(max(confidence_values), 4),
        confidence_avg=round(sum(confidence_values) / len(confidence_values), 4),
        support_total=sum(member.support for member in members),
        total_observations=sum(member.total for member in members),
        members=members,
    )


def _house_state_temporal_context(value: Any) -> HouseStateTemporalContext | None:
    if not isinstance(value, ReactionProposal):
        return None
    if value.reaction_type != HOUSE_STATE_PROPOSAL_TYPE:
        return None

    cfg = _safe_dict(value.suggested_reaction_config)
    proposal_type = str(cfg.get("proposal_type") or value.reaction_type or "").strip()
    if proposal_type != HOUSE_STATE_PROPOSAL_TYPE:
        return None

    context = _safe_dict(cfg.get("context_snapshot"))
    weekday = context.get("weekday", cfg.get("weekday"))
    hour_bucket = context.get("hour_bucket", cfg.get("hour_bucket"))
    anyone_home = context.get("anyone_home", cfg.get("anyone_home"))
    predicted_state = (
        context.get("predicted_state") or cfg.get("predicted_state") or cfg.get("house_state")
    )
    if weekday is None or hour_bucket is None or anyone_home is None or predicted_state is None:
        return None

    try:
        weekday_i = int(weekday)
        hour_bucket_i = int(hour_bucket)
    except (TypeError, ValueError):
        return None
    if weekday_i < 0 or weekday_i > 6 or hour_bucket_i < 0 or hour_bucket_i > 23:
        return None

    state = str(predicted_state or "").strip().lower()
    if not state:
        return None

    return HouseStateTemporalContext(
        weekday=weekday_i,
        hour_bucket=hour_bucket_i,
        anyone_home=_coerce_bool(anyone_home),
        predicted_state=state,
        support=_coerce_non_negative_int(cfg.get("support"), 0),
        total=_coerce_non_negative_int(cfg.get("total"), 0),
    )


def _proposal_identity_key(proposal: ReactionProposal) -> str:
    return str(proposal.identity_key or proposal.proposal_id or "").strip()


def _safe_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _coerce_non_negative_int(value: Any, default: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, numeric)


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    return bool(value)
