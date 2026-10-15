"""On-disk immutable boundaries, atomic composition and uncertain commit replay."""

import sqlite3
from contextlib import closing
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.history_intervals import HistoryInterval
from custom_components.heima.v3.runtime.clock import ClockGap
from custom_components.heima.v3.storage import sqlite_transactions
from custom_components.heima.v3.storage.clock_gaps import (
    ClockGapBoundaryReceipt,
    ClockGapDurability,
    clock_gap_observation_coverage,
)
from custom_components.heima.v3.storage.sqlite_clock_gaps import (
    ClockGapBoundaryWrite,
    prepare_clock_gap_schema,
)
from custom_components.heima.v3.storage.sqlite_transactions import SQLiteTransactionWriter

START = "2026-01-01T00:00:00.000000+00:00"
END = "2026-01-01T00:00:00.000001+00:00"
AFTER = "2026-01-01T00:00:00.000002+00:00"


def operation(gap_id="gap", side="opening", when=START, included=True):
    return ClockGapBoundaryWrite(gap_id, side, when, included)


def storage(path):
    writer = SQLiteTransactionWriter(path, busy_timeout_ms=0)
    writer.run(prepare_clock_gap_schema)
    return writer


def rows(path):
    with closing(sqlite3.connect(path, autocommit=True)) as connection:
        return tuple(
            connection.execute(
                "SELECT gap_id, boundary, when_utc, includes_boundary "
                "FROM clock_gap_boundaries_v1 ORDER BY gap_id, boundary"
            )
        )


@pytest.mark.parametrize("side", ["opening", "closing"])
@pytest.mark.parametrize("change", [None, "when", "includes_boundary"])
def test_identity_replay_decision_table_preserves_original_boundary(tmp_path, side, change):
    path = tmp_path / "v3.db"
    writer = storage(path)
    first = operation(side=side)
    try:
        receipt = writer.run(first)
        assert receipt == ClockGapBoundaryReceipt("gap", side, START, True)
        assert rows(path) == (("gap", side, START, 1),)
        changes = {"when": END} if change == "when" else {"includes_boundary": False}
        if change is None:
            assert writer.run(first) == receipt
        else:
            with pytest.raises(ValueError):
                writer.run(replace(first, **changes))
        assert rows(path) == (("gap", side, START, 1),)
    finally:
        writer.close()


@pytest.mark.parametrize("gap_id", ["a", " ", "e\u0301", "é", "' OR 1=1; --", "\0", "a\0b"])
@pytest.mark.parametrize("included", [False, True])
def test_ids_are_bound_verbatim_and_endpoints_are_explicit(tmp_path, gap_id, included):
    path = tmp_path / "v3.db"
    writer = storage(path)
    try:
        result = writer.run(operation(gap_id=gap_id, included=included))
        assert result.gap_id == gap_id
        assert result.includes_boundary is included
        assert rows(path) == ((gap_id, "opening", START, int(included)),)
    finally:
        writer.close()


@pytest.mark.parametrize(
    "when", ["0001-01-01T00:00:00.000000+00:00", "9999-12-31T23:59:59.999999+00:00"]
)
def test_first_and_last_representable_instants_round_trip(tmp_path, when):
    path = tmp_path / "v3.db"
    writer = storage(path)
    try:
        assert writer.run(operation(when=when)).when == when
        assert rows(path)[0][2] == when
    finally:
        writer.close()


def test_independent_ids_and_sides_survive_out_of_order_atomic_composition(tmp_path):
    path = tmp_path / "v3.db"
    writer = storage(path)
    closing = operation(side="closing", when=END, included=False)
    opening = operation()
    other = operation(gap_id="other")

    def batch(connection):
        candidates = (closing(connection), other(connection), opening(connection))
        assert rows(path) == ()
        return candidates

    try:
        receipts = writer.run(batch)
        assert len(rows(path)) == 3
        assert [r.boundary for r in receipts] == ["closing", "opening", "opening"]
        assert {r.gap_id for r in receipts} == {"gap", "other"}
        # Schema staging is repeatable without erasing records.
        writer.run(prepare_clock_gap_schema)
        assert len(rows(path)) == 3
    finally:
        writer.close()


@pytest.mark.parametrize("failure", ["after_boundary", "conflicting_boundary"])
def test_shared_batch_rolls_back_boundary_and_other_sql_together(tmp_path, failure):
    path = tmp_path / "v3.db"
    writer = storage(path)
    writer.run(
        lambda connection: connection.execute("CREATE TABLE fixture_facts(id INTEGER)").close()
    )

    def batch(connection):
        connection.execute("INSERT INTO fixture_facts VALUES (1)")
        operation()(connection)
        if failure == "conflicting_boundary":
            operation(when=END)(connection)
        raise ValueError("later batch failure")

    with pytest.raises(ValueError):
        writer.run(batch)
    assert rows(path) == ()
    with closing(sqlite3.connect(path)) as reader:
        assert reader.execute("SELECT * FROM fixture_facts").fetchall() == []
    writer.close()


@pytest.mark.parametrize("committed", [False, True])
def test_explicit_replay_reconciles_uncertain_commit_without_overwriting(
    tmp_path, monkeypatch, committed
):
    path = tmp_path / "v3.db"
    storage(path).close()

    class UncertainConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql == "COMMIT":
                if committed:
                    super().execute(sql, parameters).close()
                raise sqlite3.OperationalError("uncertain commit")
            return super().execute(sql, parameters)

    def connect(database, **kwargs):
        return sqlite3.connect(database, factory=UncertainConnection, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(sqlite_transactions, "connect", connect)
        writer = SQLiteTransactionWriter(path, busy_timeout_ms=0)
        with pytest.raises(sqlite3.OperationalError):
            writer.run(operation())
        writer.close()
    assert len(rows(path)) == int(committed)
    replacement = storage(path)
    try:
        result = replacement.run(operation())
        assert result == ClockGapBoundaryReceipt("gap", "opening", START, True)
        assert rows(path) == (("gap", "opening", START, 1),)
    finally:
        replacement.close()


def test_only_committed_closing_receipt_releases_coverage_restriction(tmp_path):
    path = tmp_path / "v3.db"
    writer = storage(path)
    gap = ClockGap(START, END, False)
    query = HistoryInterval(AFTER, AFTER, True, True)
    opening = writer.run(operation())
    pending = ClockGapDurability("gap", gap, True, False, opening, None)
    assert clock_gap_observation_coverage(query, pending).status == "incomplete"
    try:
        closing_receipt = writer.run(operation(side="closing", when=END, included=False))
        closed = replace(pending, closing_receipt=closing_receipt)
        assert clock_gap_observation_coverage(query, closed).status == "complete"
    finally:
        writer.close()


@pytest.mark.parametrize("action", [prepare_clock_gap_schema, operation()])
def test_operations_require_existing_transaction_before_sql(tmp_path, action):
    path = tmp_path / "v3.db"
    storage(path).close()
    with closing(sqlite3.connect(path, autocommit=True)) as connection:
        with pytest.raises(RuntimeError):
            action(connection)
    assert rows(path) == ()


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("gap_id", "", ValueError),
        ("gap_id", None, TypeError),
        ("boundary", "other", ValueError),
        ("boundary", 1, TypeError),
        ("when", "2026-01-01T00:00:00Z", ValueError),
        ("includes_boundary", 1, TypeError),
        ("includes_boundary", None, TypeError),
    ],
)
def test_staging_and_reconstructed_operation_revalidate_before_sql(tmp_path, field, value, error):
    with pytest.raises(error):
        replace(operation(), **{field: value})
    path = tmp_path / "v3.db"
    writer = storage(path)
    forged = operation()
    object.__setattr__(forged, field, value)
    with pytest.raises(error):
        writer.run(forged)
    assert rows(path) == ()
    writer.close()


def test_staged_operation_is_immutable():
    staged = operation()
    assert not hasattr(staged, "__dict__")
    with pytest.raises(FrozenInstanceError):
        staged.when = END
    with pytest.raises(AttributeError):
        staged.extra = "unexpected"


@settings(max_examples=30, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.sampled_from(["a", "b", "a\0b", "é"]),
            st.sampled_from(["opening", "closing"]),
            st.booleans(),
        ),
        max_size=12,
    )
)
def test_property_exact_replay_is_order_independent_and_conflicts_never_overwrite(items):
    with TemporaryDirectory(prefix="heima-clock-sql-property-") as directory:
        path = Path(directory) / "v3.db"
        writer = storage(path)
        expected = {}
        try:
            for gap_id, side, included in items:
                key = (gap_id, side)
                if key in expected and expected[key] != included:
                    with pytest.raises(ValueError):
                        writer.run(operation(gap_id, side, included=included))
                    writer = storage(path)
                else:
                    writer.run(operation(gap_id, side, included=included))
                    expected[key] = included
                assert rows(path) == tuple(
                    (key[0], key[1], START, int(expected[key])) for key in sorted(expected)
                )
            # A reversed replay must neither duplicate nor overwrite any record.
            for (gap_id, side), included in reversed(tuple(expected.items())):
                writer.run(operation(gap_id, side, included=included))
            assert len(rows(path)) == len(expected)
        finally:
            writer.close()
