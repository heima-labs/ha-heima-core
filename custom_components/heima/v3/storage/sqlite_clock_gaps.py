"""Composable immutable clock-boundary SQL; publish only after writer.run succeeds."""

from dataclasses import dataclass
from sqlite3 import Connection
from typing import Literal

from ..contracts.instants import EvidenceInstant
from .clock_gaps import ClockGapBoundaryReceipt


def prepare_clock_gap_schema(connection: Connection) -> None:
    """Prepare the first metadata table inside a worker-owned transaction.

    The versioned name does not assign a global schema/migration version. Call via
    SQLiteTransactionWriter.run during storage staging, outside evaluation cycles.
    """
    if not connection.in_transaction:
        raise RuntimeError("Clock gap schema requires an explicit transaction")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS clock_gap_boundaries_v1 (
            gap_id TEXT NOT NULL CHECK(gap_id <> ''),
            boundary TEXT NOT NULL CHECK(boundary IN ('opening', 'closing')),
            when_utc TEXT NOT NULL,
            includes_boundary INTEGER NOT NULL CHECK(includes_boundary IN (0, 1)),
            PRIMARY KEY (gap_id, boundary)
        ) STRICT"""
    ).close()


@dataclass(frozen=True, slots=True)
class ClockGapBoundaryWrite:
    """One immutable SQL operation, with (gap_id,boundary) as its replay identity.

    A callback may compose several operations in one end-of-cycle transaction.
    Its receipt candidate is valid for publication only after writer.run returns.
    Repeating the exact boundary safely reconciles an uncertain commit; a changed
    payload under that identity fails. The owner validates its full ClockGap intent.
    """

    gap_id: str
    boundary: Literal["opening", "closing"]
    when: EvidenceInstant
    includes_boundary: bool

    def __post_init__(self) -> None:
        ClockGapBoundaryReceipt(self.gap_id, self.boundary, self.when, self.includes_boundary)

    def __call__(self, connection: Connection) -> ClockGapBoundaryReceipt:
        # Revalidate even a reconstructed/forged operation before touching the DB.
        candidate = ClockGapBoundaryReceipt(
            self.gap_id, self.boundary, self.when, self.includes_boundary
        )
        if not connection.in_transaction:
            raise RuntimeError("Clock gap writes require an explicit transaction")
        expected = (
            candidate.gap_id,
            candidate.boundary,
            candidate.when,
            int(candidate.includes_boundary),
        )
        connection.execute(
            """INSERT INTO clock_gap_boundaries_v1
               (gap_id, boundary, when_utc, includes_boundary) VALUES (?, ?, ?, ?)
               ON CONFLICT(gap_id, boundary) DO NOTHING""",
            expected,
        ).close()
        cursor = connection.execute(
            """SELECT gap_id, boundary, when_utc, includes_boundary
               FROM clock_gap_boundaries_v1 WHERE gap_id = ? AND boundary = ?""",
            (candidate.gap_id, candidate.boundary),
        )
        try:
            stored = cursor.fetchone()
        finally:
            cursor.close()
        if stored != expected:
            raise ValueError("Clock gap identity already has different boundary data")
        return candidate
