"""Security invariant checks."""

from __future__ import annotations

from typing import Any

from ..domain_result_bag import DomainResultBag
from ..plugin_contracts import InvariantViolation


class SecurityPresenceMismatch:
    """Detect armed-away security while someone is home."""

    @property
    def check_id(self) -> str:
        return "security_presence_mismatch"

    @property
    def default_debounce_s(self) -> float:
        return 60.0

    def check(self, snapshot: Any, domain_results: DomainResultBag) -> InvariantViolation | None:
        del domain_results
        security_state = str(getattr(snapshot, "security_state", "") or "")
        if security_state != "armed_away" or not bool(getattr(snapshot, "anyone_home", False)):
            return None
        return InvariantViolation(
            check_id=self.check_id,
            severity="critical",
            anomaly_type=self.check_id,
            description="Security is armed away while someone is home.",
            context={"security_state": security_state},
        )
