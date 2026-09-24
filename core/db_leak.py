"""SQLite write-transaction leak detector.

Background (2026-09-23 incident): a single connection with an uncommitted
write transaction held the SQLite write lock for ~3 h. With default journal
mode every *other* writer in the process failed after the CPython default
~5 s busy wait ("database is locked") — task scheduler heartbeats, chat persistence, session
creation. The leaked holder line was never identified (only victim stacks
survived in the journal), so this module adds red-handed detection:

  * every pool checkout is registered with its thread + call stack;
  * a watchdog (or explicit :func:`scan_once`) flags any connection that
    stays checked out with an *open transaction* past a threshold;
  * when a "database is locked" error is handled, the current state of every
    registered connection is dumped to the log — holder stacks included.

The detector is passive (it never closes, commits or rolls anything back) and
process-wide: one registry, one watchdog thread, attached per file-backed
SQLite engine.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
import traceback
from typing import Optional

from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Default: flag connections checked out >5 min with an open transaction.
# Normal turns commit per unit of work; a 5-minute *write transaction* is
# anomalous even for a long agent turn (the 2026-09-23 leak ran ~3 h).
DEFAULT_THRESHOLD_S = 300.0
DEFAULT_SCAN_INTERVAL_S = 60.0
# Re-warn per flagged connection at most every 5 min (log hygiene).
_REWARN_INTERVAL_S = 300.0
_MAX_STACK_LINES = 25
_MAX_REGISTRY = 1000  # hard cap; prune oldest on overflow (defensive only)

_entries: dict[int, dict] = {}
_registry_lock = threading.Lock()
_watchdog_thread: Optional[threading.Thread] = None
_watchdog_stop = threading.Event()
_attached_engines = 0
_watchdog_interval_s = DEFAULT_SCAN_INTERVAL_S


def _stack_snapshot() -> str:
    frames = traceback.format_stack(limit=_MAX_STACK_LINES)
    return "".join(frames).strip()


def _register(conn, info: dict) -> None:
    with _registry_lock:
        if len(_entries) >= _MAX_REGISTRY:
            # Defensive: drop the oldest entries so a pathological loop
            # (checkouts without checkins leaking *registry* entries) cannot
            # grow memory. Normal operation never approaches the cap.
            for key in sorted(_entries, key=lambda k: _entries[k]["checked_out_at"])[:10]:
                _entries.pop(key, None)
        _entries[id(conn)] = info


def attach_leak_detection(
    engine: Engine,
    *,
    threshold_s: float = DEFAULT_THRESHOLD_S,
    start_watchdog: bool = False,
    watchdog_interval_s: Optional[float] = None,
) -> None:
    """Attach the detector to a file-backed SQLite engine.

    Safe to call once per engine (the process's main engine gets it from
    :mod:`core.database`; tests create their own engines and pass
    ``start_watchdog=False`` then call :func:`scan_once` directly).
    """
    global _attached_engines, _watchdog_interval_s, _watchdog_thread
    _attached_engines += 1
    if watchdog_interval_s is not None:
        _watchdog_interval_s = watchdog_interval_s

    @event.listens_for(engine.pool, "checkout")
    def _on_checkout(dbapi_con, connection_record, connection_proxy):  # noqa: ARG001
        _register(dbapi_con, {
            "conn": dbapi_con,
            "in_pool": False,
            "checked_out_at": time.monotonic(),
            "thread": threading.current_thread().name,
            "stack": _stack_snapshot(),
            "threshold_s": threshold_s,
            "last_warn": 0.0,
            "checkouts": 1,
        })

    @event.listens_for(engine.pool, "checkin")
    def _on_checkin(dbapi_con, connection_record):  # noqa: ARG001
        with _registry_lock:
            info = _entries.get(id(dbapi_con))
            if info is not None:
                info["in_pool"] = True

    @event.listens_for(engine.pool, "close")
    def _on_close(dbapi_con, connection_record):  # noqa: ARG001
        with _registry_lock:
            _entries.pop(id(dbapi_con), None)

    @event.listens_for(engine, "handle_error")
    def _on_handle_error(exception_context):  # SA 2.0: DialectEvents.handle_error(ctx)
        exc = getattr(exception_context, "original_exception", None)
        if isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc).lower():
            stmt = getattr(exception_context, "statement", "")
            _log_locked_diagnostics(str(exc), str(stmt)[:400])

    if start_watchdog and _watchdog_thread is None:
        t = threading.Thread(
            target=_watchdog_loop, name="sqlite-leak-watchdog", daemon=True
        )
        t.start()
        _watchdog_thread = t


def _watchdog_loop() -> None:
    while not _watchdog_stop.wait(_watchdog_interval_s):
        try:
            scan_once()
        except Exception:  # noqa: BLE001 - detector must never crash the process
            logger.exception("[db-leak] watchdog scan failed")


def stop_watchdog() -> None:
    """Stop the background watchdog (tests / shutdown)."""
    global _watchdog_thread, _watchdog_stop
    _watchdog_stop.set()
    t, _watchdog_thread, _watchdog_stop = _watchdog_thread, None, threading.Event()
    if t is not None:
        t.join(timeout=2.0)


def _flagged_entries(now: float) -> list[tuple[int, dict]]:
    out: list[tuple[int, dict]] = []
    with _registry_lock:
        items = list(_entries.items())
    for key, info in items:
        if info["in_pool"]:
            continue
        age = now - info["checked_out_at"]
        if age < info["threshold_s"]:
            continue
        try:
            if not info["conn"].in_transaction:
                continue
        except Exception:  # noqa: BLE001
            continue
        out.append((key, info))
    return out


def scan_once() -> list[dict]:
    """Scan all registered connections; warn about long-held open transactions.

    Returns the list of currently flagged connection summaries (for tests).
    """
    now = time.monotonic()
    flagged: list[dict] = []
    for _key, info in _flagged_entries(now):
        if now - info["last_warn"] >= _REWARN_INTERVAL_S:
            info["last_warn"] = now
            logger.warning(
                "[db-leak] connection checked out %.0fs (thread %s) with an OPEN "
                "TRANSACTION — if this is not a deliberate long transaction the "
                "holder is leaking a DB session. Checkout stack:\n%s",
                now - info["checked_out_at"],
                info["thread"],
                info["stack"],
            )
        age = now - info["checked_out_at"]
        try:
            in_tx = bool(info["conn"].in_transaction)
        except Exception:  # noqa: BLE001
            in_tx = False
        flagged.append({
            "thread": info["thread"],
            "age_s": round(age, 1),
            "in_transaction": in_tx,
            "checkouts": info["checkouts"],
            "stack": info["stack"],
        })
    return flagged


def _log_locked_diagnostics(error: str, statement: str) -> None:
    """Log the full registry state when a 'database is locked' error is handled."""
    now = time.monotonic()
    lines = [f"statement: {statement}"]
    with _registry_lock:
        items = sorted(
            _entries.values(), key=lambda i: i["checked_out_at"], reverse=True
        )
    for info in items:
        try:
            in_tx = bool(info["conn"].in_transaction)
        except Exception:  # noqa: BLE001
            in_tx = False
        lines.append(
            f"  conn {id(info['conn']):#x} in_pool={info['in_pool']} "
            f"in_transaction={in_tx} age={now - info['checked_out_at']:.1f}s "
            f"thread={info['thread']} checkouts={info['checkouts']}"
        )
        if in_tx and not info["in_pool"]:
            lines.append(f"    open-transaction checkout stack:\n{info['stack']}")
    logger.warning(
        "[db-leak] 'database is locked' handled (%s). Registry state (%d connections):\n%s",
        error,
        len(items),
        "\n".join(lines),
    )
