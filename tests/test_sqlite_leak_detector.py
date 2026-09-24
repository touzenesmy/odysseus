"""Regression tests for the SQLite write-transaction leak detector.

2026-09-23 incident: a leaked session held the write lock ~3 h and every
other writer failed with `OperationalError: database is locked` (only the
victims' stacks survived in the journal — the holder's line was never
identified). `core.db_leak` adds red-handed detection:

  * pool checkout registration with thread + call stack;
  * watchdog (or scan_once) warning when a checked-out connection keeps an
    open transaction past a threshold;
  * full registry dump when a "database is locked" error is handled.

Engine-touching tests run in a subprocess with an isolated temp DB (same
pattern as test_sqlite_wal_busy_timeout.py).
"""
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from core import db_leak  # noqa: E402


def _subproc_script(tmp_db: str) -> str:
    return textwrap.dedent("""
        import logging, os, sys, time, threading
        sys.path.insert(0, {root!r})
        from sqlalchemy import create_engine, text
        from core import db_leak

        captured = []
        class _Capture(logging.Handler):
            def emit(self, record):
                captured.append(record.getMessage())
        logging.getLogger("core.db_leak").addHandler(_Capture())
        logging.getLogger("core.db_leak").setLevel(logging.DEBUG)

        db_path = {db!r}
        engine = create_engine(f"sqlite:///{{db_path}}")

        # --- Test 1: watchdog flags a long-held open transaction, stack included
        db_leak.attach_leak_detection(
            engine, threshold_s=0.3, start_watchdog=True, watchdog_interval_s=0.2
        )

        with engine.connect() as c:
            c.execute(text("CREATE TABLE IF NOT EXISTS t(x)"))
            c.commit()

        def _leak_site():
            conn = engine.connect()
            conn.execute(text("BEGIN IMMEDIATE"))
            conn.execute(text("INSERT INTO t VALUES (1)"))
            return conn

        holder = _leak_site()
        deadline = time.time() + 5
        while time.time() < deadline:
            if any("OPEN TRANSACTION" in m for m in captured):
                break
            time.sleep(0.1)
        assert any("OPEN TRANSACTION" in m for m in captured), "watchdog never flagged the leak"
        flag_msg = next(m for m in captured if "OPEN TRANSACTION" in m)
        assert "_leak_site" in flag_msg, f"holder stack missing from warning:\\n{{flag_msg}}"

        # after commit + close, the connection is no longer flagged
        holder.commit()
        holder.close()
        deadline = time.time() + 3
        while time.time() < deadline and db_leak.scan_once():
            time.sleep(0.1)
        assert db_leak.scan_once() == [], "conn still flagged after commit+close"

        # --- Test 2: handle_error dumps the registry on 'database is locked'
        # (raw engine + busy_timeout=0 so the victim fails instantly, like the
        # pre-hardening production behavior)
        raw = create_engine(f"sqlite:///{{db_path}}")
        from sqlalchemy import event
        @event.listens_for(raw, "connect")
        def _no_wait(dbapi_con, _):
            dbapi_con.execute("PRAGMA busy_timeout=0")
        db_leak.attach_leak_detection(raw, threshold_s=999.0)  # no watchdog noise

        with raw.connect() as c:
            c.execute(text("CREATE TABLE IF NOT EXISTS t2(x)"))
            c.commit()

        def _leak_site2():
            conn = raw.connect()
            conn.execute(text("BEGIN IMMEDIATE"))
            conn.execute(text("INSERT INTO t2 VALUES (1)"))
            return conn

        holder2 = _leak_site2()
        before = len(captured)
        raised = False
        try:
            with raw.connect() as v:
                v.execute(text("INSERT INTO t2 VALUES (2)"))
        except Exception:
            raised = True
        assert raised, "expected OperationalError on the victim"
        dumps = [m for m in captured[before:] if "'database is locked' handled" in m]
        assert dumps, "no registry dump logged for the locked error"
        assert "_leak_site2" in dumps[0], f"holder stack missing from dump:\\n{{dumps[0]}}"
        assert "in_transaction=True" in dumps[0]
        holder2.commit()
        holder2.close()

        db_leak.stop_watchdog()
        raw.dispose()
        engine.dispose()
        print("SUBPROC_OK")
    """).format(root=str(REPO_ROOT), db=tmp_db)


def test_detector_subprocess(tmp_path):
    """Watchdog flag + stack + registry dump + clean recovery, end to end."""
    with tempfile.TemporaryDirectory() as tmp:
        code = _subproc_script(os.path.join(tmp, "app.db"))
        r = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=60,
        )
        assert r.returncode == 0, f"subprocess failed:\n{r.stdout}\n{r.stderr}"
        assert "SUBPROC_OK" in r.stdout


def test_registry_prunes_at_cap():
    """Defensive cap: the registry can never grow unbounded."""
    old_cap, db_leak._MAX_REGISTRY = db_leak._MAX_REGISTRY, 3
    try:
        for i in range(10):
            db_leak._register(f"conn{i}", {
                "conn": None, "in_pool": False, "checked_out_at": 100.0 + i,
                "thread": "t", "stack": "", "threshold_s": 300.0,
                "last_warn": 0.0, "checkouts": 1,
            })
        assert len(db_leak._entries) <= db_leak._MAX_REGISTRY
    finally:
        db_leak._MAX_REGISTRY = old_cap
        with db_leak._registry_lock:
            db_leak._entries.clear()
