"""Real on-disk SQLite commits/rollback, publication order and worker ownership."""

import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import get_ident

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from custom_components.heima.v3.storage import sqlite_transactions
from custom_components.heima.v3.storage.clock_gaps import ClockGapBoundaryReceipt
from custom_components.heima.v3.storage.sqlite_transactions import SQLiteTransactionWriter

WHEN = "2026-01-01T00:00:00.000001+00:00"


class WorkerAbort(BaseException):
    """Exercise BaseException cleanup without aborting pytest on surviving mutants."""


def database(directory):
    path = directory / "v3-test.db"
    with closing(sqlite3.connect(path, autocommit=True)) as connection:
        connection.execute("CREATE TABLE facts (id INTEGER PRIMARY KEY, value INTEGER)")
        connection.execute("CREATE TABLE markers (cycle INTEGER PRIMARY KEY)")
    return path


def rows(path):
    with closing(sqlite3.connect(path, autocommit=True)) as connection:
        return (
            tuple(connection.execute("SELECT id, value FROM facts ORDER BY id")),
            tuple(connection.execute("SELECT cycle FROM markers ORDER BY cycle")),
        )


def faulty_connection(monkeypatch, failures):
    connections = []

    class FaultConnection(sqlite3.Connection):
        def set_authorizer(self, callback):
            super().set_authorizer(callback)
            if callback is None and "authorizer_clear" in failures:
                raise sqlite3.OperationalError("injected authorizer cleanup failure")

        def execute(self, sql, parameters=()):
            command = sql.strip().upper()
            if command == "PRAGMA BUSY_TIMEOUT" and "timeout" in failures:
                return super().execute("SELECT -1")
            if command == "PRAGMA JOURNAL_MODE=WAL" and "wal" in failures:
                return super().execute("SELECT 'delete'")
            if command == "PRAGMA SYNCHRONOUS" and "full" in failures:
                return super().execute("SELECT 0")
            if command == "BEGIN IMMEDIATE" and "begin" in failures:
                raise sqlite3.OperationalError("injected begin failure")
            if command == "COMMIT" and "commit_before" in failures:
                raise sqlite3.OperationalError("injected pre-commit failure")
            if command == "ROLLBACK" and "rollback" in failures:
                raise sqlite3.OperationalError("injected rollback failure")
            result = super().execute(sql, parameters)
            if command == "COMMIT" and "commit_after" in failures:
                raise sqlite3.OperationalError("injected uncertain commit outcome")
            return result

        def close(self):
            super().close()
            if "close" in failures:
                raise OSError("injected close failure")

    def connect(path, **kwargs):
        connection = sqlite3.connect(path, factory=FaultConnection, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(sqlite_transactions, "connect", connect)
    return connections


def test_result_receipt_is_returned_only_after_atomic_commit_visible_to_another_connection(
    tmp_path,
):
    path = database(tmp_path)
    writer = SQLiteTransactionWriter(path, busy_timeout_ms=0)
    receipt = ClockGapBoundaryReceipt("gap", "closing", WHEN, False)

    def operation(connection):
        assert connection.in_transaction
        connection.execute("INSERT INTO facts VALUES (?, ?)", (1, 42))
        assert rows(path) == ((), ())
        connection.execute("INSERT INTO markers VALUES (?)", (1,))
        assert rows(path) == ((), ())
        return receipt

    try:
        assert writer.run(operation) is receipt
        assert rows(path) == (((1, 42),), ((1,),))
    finally:
        writer.close()
    assert rows(path) == (((1, 42),), ((1,),))


@pytest.mark.parametrize(
    "timeout,expected_ms",
    [(0, 0), (1, 1), (125, 125), (2_147_483_646, 2_147_483_646), (2_147_483_647, 2_147_483_647)],
)
def test_explicit_wal_full_autocommit_and_lock_timeout_configuration(
    tmp_path, timeout, expected_ms
):
    path = database(tmp_path)
    writer = SQLiteTransactionWriter(path, busy_timeout_ms=timeout)
    try:
        result = writer.run(
            lambda connection: (
                connection.execute("PRAGMA journal_mode").fetchone(),
                connection.execute("PRAGMA synchronous").fetchone(),
                connection.execute("PRAGMA busy_timeout").fetchone(),
                connection.autocommit,
            )
        )
        assert result == (("wal",), (2,), (expected_ms,), True)
    finally:
        writer.close()


@pytest.mark.parametrize("failure_type", [ValueError, WorkerAbort, asyncio.CancelledError])
def test_operation_failure_rolls_back_all_rows_and_closes_writer(tmp_path, failure_type):
    path = database(tmp_path)
    writer = SQLiteTransactionWriter(path, busy_timeout_ms=0)
    failure = failure_type("operation failed")

    def operation(connection):
        connection.execute("INSERT INTO facts VALUES (1, 42)")
        raise failure

    with pytest.raises(failure_type) as caught:
        writer.run(operation)
    assert caught.value is failure
    assert rows(path) == ((), ())
    with pytest.raises(RuntimeError):
        writer.run(lambda connection: "not allowed")
    writer.close()


@pytest.mark.parametrize(
    "stage,committed", [("begin", False), ("commit_before", False), ("commit_after", True)]
)
def test_failure_stages_never_return_a_result_even_if_commit_outcome_is_uncertain(
    tmp_path, monkeypatch, stage, committed
):
    path = database(tmp_path)
    connections = faulty_connection(monkeypatch, {stage})
    writer = SQLiteTransactionWriter(path, busy_timeout_ms=0)
    calls = []

    def operation(connection):
        calls.append("started")
        connection.execute("INSERT INTO facts VALUES (1, 42)")
        connection.execute("INSERT INTO markers VALUES (1)")
        return "candidate receipt"

    with pytest.raises(sqlite3.OperationalError):
        writer.run(operation)
    assert calls == ([] if stage == "begin" else ["started"])
    assert rows(path) == ((((1, 42),), ((1,),)) if committed else ((), ()))
    with pytest.raises(sqlite3.ProgrammingError):
        connections[0].execute("SELECT 1")
    with pytest.raises(RuntimeError):
        writer.run(operation)


@pytest.mark.parametrize(
    "rollback_failure,close_failure", [(False, True), (True, False), (True, True)]
)
def test_cleanup_failure_preserves_original_and_all_cleanup_errors(
    tmp_path, monkeypatch, rollback_failure, close_failure
):
    path = database(tmp_path)
    failures = ({"rollback"} if rollback_failure else set()) | (
        {"close"} if close_failure else set()
    )
    faulty_connection(monkeypatch, failures)
    writer = SQLiteTransactionWriter(path, busy_timeout_ms=0)
    original = ValueError("original failure")

    def operation(connection):
        connection.execute("INSERT INTO facts VALUES (1, 42)")
        raise original

    with pytest.raises(ExceptionGroup) as caught:
        writer.run(operation)
    assert caught.value.exceptions[0] is original
    assert [type(error) for error in caught.value.exceptions] == (
        [ValueError]
        + ([sqlite3.OperationalError] if rollback_failure else [])
        + ([OSError] if close_failure else [])
    )
    assert rows(path) == ((), ())
    with pytest.raises(RuntimeError):
        writer.run(lambda connection: 1)


@pytest.mark.parametrize("stage", ["timeout", "wal", "full"])
def test_setup_refuses_unverified_settings_and_closes_connection(tmp_path, monkeypatch, stage):
    path = database(tmp_path)
    connections = faulty_connection(monkeypatch, {stage})
    with pytest.raises(RuntimeError):
        SQLiteTransactionWriter(path, busy_timeout_ms=0)
    with pytest.raises(sqlite3.ProgrammingError):
        connections[0].execute("SELECT 1")


def test_setup_close_failure_preserves_configuration_failure(tmp_path, monkeypatch):
    path = database(tmp_path)
    faulty_connection(monkeypatch, {"wal", "close"})
    with pytest.raises(ExceptionGroup) as caught:
        SQLiteTransactionWriter(path, busy_timeout_ms=0)
    assert isinstance(caught.value.exceptions[0], RuntimeError)
    assert isinstance(caught.value.exceptions[1], OSError)


def test_in_memory_database_is_rejected_because_wal_is_not_available():
    with pytest.raises(RuntimeError):
        SQLiteTransactionWriter(Path(":memory:"), busy_timeout_ms=0)


def test_locked_writer_fails_before_operation_and_requires_explicit_reconnection(tmp_path):
    path = database(tmp_path)
    writer = SQLiteTransactionWriter(path, busy_timeout_ms=0)
    calls = []
    with closing(sqlite3.connect(path, autocommit=True)) as blocker:
        blocker.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError):
            writer.run(lambda connection: calls.append("unexpected operation"))
        blocker.execute("ROLLBACK")
    assert calls == []
    assert rows(path) == ((), ())
    with pytest.raises(RuntimeError):
        writer.run(lambda connection: 1)
    replacement = SQLiteTransactionWriter(path, busy_timeout_ms=0)
    try:
        assert replacement.run(lambda connection: 42) == 42
    finally:
        replacement.close()


@pytest.mark.parametrize("which", ["run", "close"])
def test_operation_cannot_nest_or_close_the_owning_transaction(tmp_path, which):
    path = database(tmp_path)
    writer = SQLiteTransactionWriter(path, busy_timeout_ms=0)

    def operation(connection):
        connection.execute("INSERT INTO facts VALUES (1, 42)")
        if which == "run":
            writer.run(lambda nested: 42)
        else:
            writer.close()

    with pytest.raises(RuntimeError):
        writer.run(operation)
    assert rows(path) == ((), ())


@pytest.mark.parametrize("command", ["COMMIT", "ROLLBACK", "BEGIN", "SAVEPOINT nested"])
def test_callback_transaction_ownership_violation_never_returns_a_receipt(tmp_path, command):
    path = database(tmp_path)
    writer = SQLiteTransactionWriter(path, busy_timeout_ms=0)

    def operation(connection):
        connection.execute(command)
        return "not published"

    with pytest.raises(sqlite3.DatabaseError):
        writer.run(operation)
    with pytest.raises(RuntimeError):
        writer.run(lambda connection: 42)


def test_close_is_idempotent_and_invalid_operations_do_not_damage_an_open_writer(tmp_path):
    writer = SQLiteTransactionWriter(database(tmp_path), busy_timeout_ms=0)
    with pytest.raises(TypeError):
        writer.run(None)
    assert writer.run(lambda connection: 42) == 42
    writer.close()
    writer.close()
    with pytest.raises(RuntimeError):
        writer.run(lambda connection: 42)


def test_normal_close_failure_is_visible_and_does_not_undo_a_successful_commit(
    tmp_path, monkeypatch
):
    path = database(tmp_path)
    faulty_connection(monkeypatch, {"close"})
    writer = SQLiteTransactionWriter(path, busy_timeout_ms=0)

    def insert(connection):
        connection.execute("INSERT INTO facts VALUES (1, 42)")

    writer.run(insert)
    with pytest.raises(OSError):
        writer.close()
    assert rows(path) == (((1, 42),), ())
    writer.close()


def test_wrong_worker_is_rejected_before_sql_and_owner_remains_usable(tmp_path):
    writer = SQLiteTransactionWriter(database(tmp_path), busy_timeout_ms=0)
    try:
        with ThreadPoolExecutor(max_workers=1) as worker:
            with pytest.raises(RuntimeError):
                worker.submit(writer.run, lambda connection: 42).result()
            with pytest.raises(RuntimeError):
                worker.submit(writer.close).result()
        assert writer.run(lambda connection: get_ident()) == get_ident()
    finally:
        writer.close()


def test_event_loop_calls_are_rejected_before_database_creation_or_io(tmp_path):
    writer = SQLiteTransactionWriter(database(tmp_path), busy_timeout_ms=0)
    forbidden = tmp_path / "forbidden.db"

    async def attempt():
        with pytest.raises(RuntimeError):
            SQLiteTransactionWriter(forbidden, busy_timeout_ms=0)
        with pytest.raises(RuntimeError):
            writer.run(lambda connection: 42)
        with pytest.raises(RuntimeError):
            writer.close()

    asyncio.run(attempt())
    assert not forbidden.exists()
    writer.close()


def test_dedicated_worker_runs_real_transactions_while_event_loop_remains_available(tmp_path):
    path = database(tmp_path)
    main_thread = get_ident()

    async def scenario():
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            writer = await loop.run_in_executor(
                executor, partial(SQLiteTransactionWriter, path, busy_timeout_ms=0)
            )
            ticks = []
            loop.call_soon(ticks.append, "scheduled")

            def operation(connection):
                connection.execute("INSERT INTO facts VALUES (1, 42)")
                return get_ident()

            try:
                worker_thread = await loop.run_in_executor(executor, writer.run, operation)
                assert worker_thread != main_thread
                assert ticks == ["scheduled"]
            finally:
                await loop.run_in_executor(executor, writer.close)

    asyncio.run(scenario())
    assert rows(path) == (((1, 42),), ())


@pytest.mark.parametrize(
    "timeout,error",
    [
        (-1, ValueError),
        (2_147_483_648, ValueError),
        (1.0, TypeError),
        (float("nan"), TypeError),
        (float("inf"), TypeError),
        (True, TypeError),
        (None, TypeError),
        ("1", TypeError),
    ],
)
def test_lock_timeout_validation_before_creating_database(tmp_path, timeout, error):
    path = tmp_path / "not-created.db"
    with pytest.raises(error):
        SQLiteTransactionWriter(path, busy_timeout_ms=timeout)
    assert not path.exists()


def test_path_and_missing_parent_fail_explicitly(tmp_path):
    with pytest.raises(TypeError):
        SQLiteTransactionWriter("not-a-Path", busy_timeout_ms=0)
    with pytest.raises(sqlite3.OperationalError):
        SQLiteTransactionWriter(tmp_path / "missing" / "v3.db", busy_timeout_ms=0)


@settings(max_examples=30, deadline=None)
@given(st.lists(st.integers(-1000, 1000), max_size=8), st.data())
def test_property_every_failure_cut_rolls_back_facts_and_marker_atomically(values, data):
    cut = data.draw(st.one_of(st.none(), st.integers(0, len(values) + 1)))
    with TemporaryDirectory(prefix="heima-sqlite-property-") as directory:
        path = database(Path(directory))
        writer = SQLiteTransactionWriter(path, busy_timeout_ms=0)

        def operation(connection):
            for index, value in enumerate(values):
                if cut == index:
                    raise ValueError("injected cut")
                connection.execute("INSERT INTO facts VALUES (?, ?)", (index + 1, value))
            if cut == len(values):
                raise ValueError("cut before marker")
            connection.execute("INSERT INTO markers VALUES (1)")
            if cut == len(values) + 1:
                raise ValueError("cut after marker")
            return "committed"

        try:
            if cut is None:
                assert writer.run(operation) == "committed"
                assert rows(path) == (tuple(enumerate(values, 1)), ((1,),))
            else:
                with pytest.raises(ValueError):
                    writer.run(operation)
                assert rows(path) == ((), ())
        finally:
            writer.close()


def test_accidental_commit_then_begin_cannot_publish_a_partially_committed_batch(tmp_path):
    path = database(tmp_path)
    writer = SQLiteTransactionWriter(path, busy_timeout_ms=0)

    def operation(connection):
        connection.execute("INSERT INTO facts VALUES (1, 42)")
        connection.execute("COMMIT")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("INSERT INTO markers VALUES (1)")
        raise ValueError("later batch failure")

    with pytest.raises((sqlite3.DatabaseError, ValueError)):
        writer.run(operation)
    assert rows(path) == ((), ())


def test_cached_internal_commit_does_not_bypass_next_operations_authorizer(tmp_path):
    path = database(tmp_path)
    writer = SQLiteTransactionWriter(path, busy_timeout_ms=0)
    assert writer.run(lambda connection: 42) == 42

    def operation(connection):
        connection.execute("INSERT INTO facts VALUES (1, 42)")
        connection.execute("COMMIT")
        return "never published"

    with pytest.raises(sqlite3.DatabaseError):
        writer.run(operation)
    assert rows(path) == ((), ())


def test_unexpected_transaction_ownership_loss_is_detected_even_if_callback_removes_guard(tmp_path):
    writer = SQLiteTransactionWriter(database(tmp_path), busy_timeout_ms=0)

    def operation(connection):
        connection.set_authorizer(None)
        connection.execute("ROLLBACK")
        return "not a committed result"

    with pytest.raises(RuntimeError):
        writer.run(operation)


def test_authorizer_cleanup_failure_returns_no_result_and_preserves_cleanup_errors(
    tmp_path, monkeypatch
):
    path = database(tmp_path)
    faulty_connection(monkeypatch, {"authorizer_clear"})
    writer = SQLiteTransactionWriter(path, busy_timeout_ms=0)

    def operation(connection):
        connection.execute("INSERT INTO facts VALUES (1, 42)")
        return "not published"

    with pytest.raises(ExceptionGroup) as caught:
        writer.run(operation)
    assert len(caught.value.exceptions) == 2
    assert rows(path) == ((), ())


def test_base_exception_with_cleanup_failure_is_preserved_as_a_base_exception_group(
    tmp_path, monkeypatch
):
    path = database(tmp_path)
    faulty_connection(monkeypatch, {"rollback"})
    writer = SQLiteTransactionWriter(path, busy_timeout_ms=0)
    original = WorkerAbort("interrupted")

    def operation(connection):
        raise original

    with pytest.raises(BaseExceptionGroup) as caught:
        writer.run(operation)
    assert caught.value.exceptions[0] is original
    assert isinstance(caught.value.exceptions[1], sqlite3.OperationalError)


def test_real_constraint_failure_rolls_back_preceding_statements_and_marker(tmp_path):
    path = database(tmp_path)
    writer = SQLiteTransactionWriter(path, busy_timeout_ms=0)

    def operation(connection):
        connection.execute("INSERT INTO facts VALUES (1, 42)")
        connection.execute("INSERT INTO markers VALUES (1)")
        connection.execute("INSERT INTO facts VALUES (1, 99)")

    with pytest.raises(sqlite3.IntegrityError):
        writer.run(operation)
    assert rows(path) == ((), ())
