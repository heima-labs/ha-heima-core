"""Routing for behavior analyzer findings."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from .analyzers.base import ReactionProposal
from .plugin_contracts import AnomalySignal, BehaviorFinding
from .proposal_engine import ProposalEngine

_LOGGER = logging.getLogger(__name__)

AnomalyHandler = Callable[[AnomalySignal], Awaitable[None] | None]
CorrelationHandler = Callable[[Any], Awaitable[None] | None]


class FindingRouter:
    """Route typed analyzer findings to their owning runtime component."""

    def __init__(
        self,
        *,
        proposal_engine: ProposalEngine,
        anomaly_handler: AnomalyHandler | None = None,
        correlation_handler: CorrelationHandler | None = None,
    ) -> None:
        self._proposal_engine = proposal_engine
        self._anomaly_handler = anomaly_handler
        self._correlation_handler = correlation_handler

    async def async_route(self, findings: list[BehaviorFinding]) -> None:
        """Route findings by kind."""
        for finding in findings:
            if finding.kind in {"pattern", "proposal", "activity"}:
                await self._route_proposal(finding)
                continue
            if finding.kind == "anomaly":
                await self._route_anomaly(finding)
                continue
            if finding.kind == "correlation":
                await self._route_correlation(finding)
                continue
            _LOGGER.warning("Unknown behavior finding kind: %s", finding.kind)

    async def _route_proposal(self, finding: BehaviorFinding) -> None:
        payload = finding.payload
        if not isinstance(payload, ReactionProposal):
            _LOGGER.warning(
                "Behavior finding %s has non-proposal payload for kind=%s",
                finding.analyzer_id,
                finding.kind,
            )
            return
        await self._proposal_engine.async_submit_proposal(payload)

    async def _route_anomaly(self, finding: BehaviorFinding) -> None:
        payload = finding.payload
        if not isinstance(payload, AnomalySignal):
            _LOGGER.warning("Behavior finding %s has invalid anomaly payload", finding.analyzer_id)
            return
        if self._anomaly_handler is None:
            _LOGGER.info("Anomaly finding ignored without handler: %s", payload.anomaly_type)
            return
        result = self._anomaly_handler(payload)
        if result is not None:
            await result

    async def _route_correlation(self, finding: BehaviorFinding) -> None:
        if self._correlation_handler is None:
            _LOGGER.info("Correlation finding ignored without handler: %s", finding.analyzer_id)
            return
        result = self._correlation_handler(finding.payload)
        if result is not None:
            await result
