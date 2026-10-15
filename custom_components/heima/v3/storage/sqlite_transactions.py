"""SQLite transaction boundary for a single worker; no queue or schema ownership."""

import asyncio
from collections.abc import Callable
from functools import partial
from pathlib import Path
from sqlite3 import (
    SQLITE_DENY,
    SQLITE_OK,
    SQLITE_SAVEPOINT,
    SQLITE_TRANSACTION,
    Connection,
    connect,
)
from threading import get_ident
from typing import NoReturn


def _outside_event_loop() -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    raise RuntimeError("SQLite writer I/O requires a worker outside the event loop")


def _operation_authorizer(
    connection: Connection,
    action: int,
    _argument1: str | None,
    _argument2: str | None,
    _database: str | None,
    _source: str | None,
) -> int:
    if not connection.in_transaction or action in (SQLITE_TRANSACTION, SQLITE_SAVEPOINT):
        return SQLITE_DENY
    return SQLITE_OK


def _discard_and_raise(
    connection: Connection, failure: BaseException, *, rollback: bool
) -> NoReturn:
    errors = [failure]
    if rollback:
        try:
            connection.set_authorizer(None)
        except BaseException as authorization_error:
            errors.append(authorization_error)
        try:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
        except BaseException as cleanup_error:
            errors.append(cleanup_error)
    try:
        connection.close()
    except BaseException as close_error:
        errors.append(close_error)
    if len(errors) > 1:
        raise BaseExceptionGroup("SQLite transaction and cleanup failures", errors)
    raise failure


class SQLiteTransactionWriter:
    """Worker-owned WAL/FULL connection; return an operation result only after COMMIT.

    The host must use one dedicated worker and its existing bounded admission queue.
    Operations are trusted internal SQL callbacks: do not change transaction control,
    connection settings/authorizer, publish receipts, or return cursors/connections
    from them. An operation authorizer rejects accidental SQL transaction control.
    No database schema, retry cadence, executor queue or default lock timeout is added.
    """

    def __init__(self, path: Path, *, busy_timeout_ms: int) -> None:
        _outside_event_loop()
        if not isinstance(path, Path):
            raise TypeError("SQLite writer requires an explicit database path")
        if type(busy_timeout_ms) is not int:
            raise TypeError("SQLite lock timeout must be a non-boolean integer in milliseconds")
        if busy_timeout_ms < 0 or busy_timeout_ms > 2_147_483_647:
            raise ValueError("SQLite lock timeout is outside its integer-millisecond range")
        # Authorization runs at preparation, not execution. Cached statements could
        # otherwise write in autocommit after SQLite rolls back the whole batch.
        connection = connect(path, timeout=0.0, autocommit=True, cached_statements=0)
        try:
            connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
            if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
                raise RuntimeError("SQLite lock timeout was not established")
            if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
                raise RuntimeError("SQLite WAL mode was not established")
            connection.execute("PRAGMA synchronous=FULL")
            if connection.execute("PRAGMA synchronous").fetchone() != (2,):
                raise RuntimeError("SQLite FULL synchronization was not established")
        except BaseException as error:
            _discard_and_raise(connection, error, rollback=False)
        self._connection = connection
        self._owner_thread = get_ident()
        self._closed = False

    def _assert_owner(self) -> None:
        _outside_event_loop()
        if get_ident() != self._owner_thread:
            raise RuntimeError("SQLite writer belongs to another worker thread")

    def run[T](self, operation: Callable[[Connection], T]) -> T:
        self._assert_owner()
        if self._closed:
            raise RuntimeError("SQLite writer is closed")
        if not callable(operation):
            raise TypeError("SQLite operation must be callable")
        if self._connection.in_transaction:
            raise RuntimeError("SQLite writer does not allow nested transactions")
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._connection.set_authorizer(partial(_operation_authorizer, self._connection))
            result = operation(self._connection)
            self._connection.set_authorizer(None)
            if not self._connection.in_transaction:
                raise RuntimeError("SQLite operation changed transaction ownership")
            self._connection.execute("COMMIT")
        except BaseException as error:
            # A failed/uncertain transaction is never reused or automatically retried.
            self._closed = True
            _discard_and_raise(self._connection, error, rollback=True)
        return result

    def close(self) -> None:
        self._assert_owner()
        if self._closed:
            return
        if self._connection.in_transaction:
            raise RuntimeError("Cannot close SQLite writer during an operation")
        self._closed = True
        self._connection.close()
