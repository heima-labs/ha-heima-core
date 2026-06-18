"""Persistent lifecycle monitoring state for accepted learning proposals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store


@dataclass(frozen=True)
class ProposalLifecycleRecord:
    """Restart-safe monitoring state for one accepted learned proposal."""

    proposal_id: str
    identity_key: str
    plugin_family: str
    proposal_type: str
    accepted_at: str
    linked_reaction_id: str = ""
    linked_reaction_type: str = ""
    reaction_link_state: str = ""
    lifecycle_generation: int = 1
    monitoring_window_start: str = ""
    last_confirmed_at: str = ""
    confirmed_count: int = 0
    outcome_contradiction_count: int = 0
    context_miss_count: int = 0
    unknown_transient_count: int = 0
    dependency_unavailable_count: int = 0
    last_lifecycle_review_at: str = ""
    replaced_by: str = ""
    retired_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Serialize record to HA storage."""
        return {
            "proposal_id": self.proposal_id,
            "identity_key": self.identity_key,
            "plugin_family": self.plugin_family,
            "proposal_type": self.proposal_type,
            "accepted_at": self.accepted_at,
            "linked_reaction_id": self.linked_reaction_id,
            "linked_reaction_type": self.linked_reaction_type,
            "reaction_link_state": self.reaction_link_state,
            "lifecycle_generation": self.lifecycle_generation,
            "monitoring_window_start": self.monitoring_window_start,
            "last_confirmed_at": self.last_confirmed_at,
            "confirmed_count": self.confirmed_count,
            "outcome_contradiction_count": self.outcome_contradiction_count,
            "context_miss_count": self.context_miss_count,
            "unknown_transient_count": self.unknown_transient_count,
            "dependency_unavailable_count": self.dependency_unavailable_count,
            "last_lifecycle_review_at": self.last_lifecycle_review_at,
            "replaced_by": self.replaced_by,
            "retired_at": self.retired_at,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ProposalLifecycleRecord | None":
        """Deserialize one lifecycle record, ignoring malformed rows."""
        proposal_id = str(raw.get("proposal_id") or "").strip()
        identity_key = str(raw.get("identity_key") or "").strip()
        proposal_type = str(raw.get("proposal_type") or "").strip()
        accepted_at = str(raw.get("accepted_at") or "").strip()
        if not proposal_id or not identity_key or not proposal_type or not accepted_at:
            return None
        return cls(
            proposal_id=proposal_id,
            identity_key=identity_key,
            plugin_family=str(raw.get("plugin_family") or "").strip(),
            proposal_type=proposal_type,
            accepted_at=accepted_at,
            linked_reaction_id=str(raw.get("linked_reaction_id") or "").strip(),
            linked_reaction_type=str(raw.get("linked_reaction_type") or "").strip(),
            reaction_link_state=str(raw.get("reaction_link_state") or "").strip(),
            lifecycle_generation=max(1, _safe_int(raw.get("lifecycle_generation"), default=1)),
            monitoring_window_start=str(raw.get("monitoring_window_start") or "").strip(),
            last_confirmed_at=str(raw.get("last_confirmed_at") or "").strip(),
            confirmed_count=max(0, _safe_int(raw.get("confirmed_count"), default=0)),
            outcome_contradiction_count=max(
                0, _safe_int(raw.get("outcome_contradiction_count"), default=0)
            ),
            context_miss_count=max(0, _safe_int(raw.get("context_miss_count"), default=0)),
            unknown_transient_count=max(
                0, _safe_int(raw.get("unknown_transient_count"), default=0)
            ),
            dependency_unavailable_count=max(
                0, _safe_int(raw.get("dependency_unavailable_count"), default=0)
            ),
            last_lifecycle_review_at=str(raw.get("last_lifecycle_review_at") or "").strip(),
            replaced_by=str(raw.get("replaced_by") or "").strip(),
            retired_at=str(raw.get("retired_at") or "").strip(),
        )


class ProposalLifecycleStore:
    """Durable lifecycle state for accepted learned proposal monitoring."""

    STORAGE_KEY = "heima_proposal_lifecycle"
    STORAGE_VERSION = 1

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass,
            version=self.STORAGE_VERSION,
            key=self.STORAGE_KEY,
        )
        self._records: dict[str, ProposalLifecycleRecord] = {}
        self._loaded = False
        self._load_errors = 0

    async def async_load(self) -> None:
        """Load lifecycle records into memory."""
        raw = await self._store.async_load()
        records_raw = []
        if isinstance(raw, dict):
            data = raw.get("data")
            if isinstance(data, dict):
                records_raw = data.get("records", [])

        self._records.clear()
        self._load_errors = 0
        if isinstance(records_raw, list):
            for item in records_raw:
                if not isinstance(item, dict):
                    self._load_errors += 1
                    continue
                record = ProposalLifecycleRecord.from_dict(item)
                if record is None:
                    self._load_errors += 1
                    continue
                self._records[record.proposal_id] = record
        self._loaded = True

    async def async_flush(self) -> None:
        """Persist current lifecycle records immediately."""
        await self._store.async_save(self._serialize())

    async def async_upsert_missing(self, record: ProposalLifecycleRecord) -> bool:
        """Insert a record only if it is not already tracked."""
        if not self._loaded:
            await self.async_load()
        if record.proposal_id in self._records:
            return False
        self._records[record.proposal_id] = record
        await self.async_flush()
        return True

    def records(self) -> list[ProposalLifecycleRecord]:
        """Return lifecycle records sorted by accepted time and proposal id."""
        return sorted(
            self._records.values(),
            key=lambda item: (item.accepted_at, item.proposal_id),
        )

    def diagnostics(self) -> dict[str, Any]:
        """Return lifecycle store diagnostics."""
        return {
            "storage_key": self.STORAGE_KEY,
            "storage_version": self.STORAGE_VERSION,
            "loaded": self._loaded,
            "load_errors": self._load_errors,
            "record_count": len(self._records),
            "records": [record.as_dict() for record in self.records()],
        }

    def _serialize(self) -> dict[str, Any]:
        return {"data": {"records": [record.as_dict() for record in self.records()]}}


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
