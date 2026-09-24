"""Regression tests for SQLite concurrency hardening (2026-09-23 lock incident).

A leaked session with an open write transaction held the SQLite write lock
for hours: in the default rollback-journal mode, every other writer failed
instantly with `OperationalError: database is locked`. The fix adds WAL +
a busy_timeout so writers queue instead of failing.

The live-engine assertions run in a subprocess with an isolated temp DB
so the test process's core.database import (and other tests' DATABASE_URL
conventions) stay untouched.
"""
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Import only the pure helpers — no env mutation, no engine creation here.
sys.path.insert(0, str(REPO_ROOT))
from core import database as dbmod  # noqa: E402

_SUBPROC = textwrap.dedent("""
    import os, sys, time, threading
    sys.path.insert(0, {root!r})
    os.environ["DATABASE_URL"] = "sqlite:///" + {db!r}
    from core import database as d
    from sqlalchemy import text

    # 1. WAL active on the file engine
    with d.engine.connect() as c:
        mode = c.execute(text("PRAGMA journal_mode")).scalar()
    assert mode.lower() == "wal", f"expected WAL, got {{mode}}"

    # 2. busy_timeout applied on every connection
    with d.engine.connect() as c:
        tmo = c.execute(text("PRAGMA busy_timeout")).scalar()
    assert tmo == d._SQLITE_BUSY_TIMEOUT_MS, f"expected {{d._SQLITE_BUSY_TIMEOUT_MS}}, got {{tmo}}"

    # 3. Lock-wait: a second writer queues through a held write transaction
    #    (the exact 2026-09-23 incident class — pre-fix this raised
    #    `OperationalError: database is locked` instantly).
    with d.engine.connect() as a:
        a.execute(text("CREATE TABLE IF NOT EXISTS _busy_probe (x INTEGER)"))
        a.commit()
        a.execute(text("BEGIN"))
        a.execute(text("INSERT INTO _busy_probe VALUES (1)"))
        with d.engine.connect() as b:
            results = {{}}
            def worker():
                try:
                    b.execute(text("INSERT INTO _busy_probe VALUES (2)"))
                    b.commit()
                    results["ok"] = True
                except Exception as e:
                    results["err"] = f"{{type(e).__name__}}: {{e}}"
            th = threading.Thread(target=worker)
            th.start()
            time.sleep(1.2)          # hold the write well past instant-fail
            a.rollback()             # release
            th.join(timeout=10)
            assert not th.is_alive(), "write never completed"
            assert results.get("ok"), f"write failed while lock held: {{results}}"
    print("SUBPROC_OK")
""")


def test_helpers():
    assert dbmod._sqlite_is_memory("sqlite:///:memory:") is True
    assert dbmod._sqlite_is_memory("sqlite:///tmp/x.db") is False
    assert dbmod._sqlite_connect_args("sqlite:///tmp/x.db") == {
        "check_same_thread": False,
    }
    assert dbmod._sqlite_connect_args("postgresql://u@h/db") == {}
    assert dbmod._SQLITE_BUSY_TIMEOUT_MS == 30000


def test_live_engine_wal_and_busy_timeout():
    with tempfile.TemporaryDirectory() as tmp:
        code = _SUBPROC.format(root=str(REPO_ROOT), db=os.path.join(tmp, "app.db"))
        r = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=60,
        )
        assert r.returncode == 0, f"subprocess failed:\n{r.stdout}\n{r.stderr}"
        assert "SUBPROC_OK" in r.stdout
