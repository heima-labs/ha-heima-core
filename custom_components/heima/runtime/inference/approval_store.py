"""ApprovalStore — stub for Phase F user-approval gating of inference signals."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store


class ApprovalStore:
    """Persists (context_key_hash, predicted_value) approval/rejection records.

    Full implementation deferred to Phase F. Stub always returns unapproved.
    Storage key: heima_inference_approvals.
    """

    STORAGE_KEY = "heima_inference_approvals"
    STORAGE_VERSION = 1

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass,
            version=self.STORAGE_VERSION,
            key=self.STORAGE_KEY,
        )

    async def async_load(self) -> None:
        """Load persisted approvals — stub, no-op until Phase F."""

    def is_approved(self, context_key_hash: str, predicted_value: str) -> bool:
        """Return True if this (context, prediction) pair has been approved."""
        del context_key_hash, predicted_value
        return False

    def is_rejected(self, context_key_hash: str, predicted_value: str) -> bool:
        """Return True if this (context, prediction) pair has been rejected."""
        del context_key_hash, predicted_value
        return False

    def get_approved(self, kind: str) -> list[Any]:
        """Return all approved entries of the given kind."""
        del kind
        return []
