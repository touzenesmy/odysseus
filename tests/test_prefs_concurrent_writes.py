"""Concurrent-write tests for the serialized preference store.

Pins the behavior ported from upstream 9fdeb64a (step 3d, nugget 1):

- (a) two overlapping partial updates are serialized, so both survive —
  no more read-modify-write lost writes;
- (b) a multi-key PATCH applies all of its keys in one store write:
  all or nothing;
- (c) a null value removes only its own key.

Tests run against OUR routes/prefs_routes.py (fork-divergent), not
upstream's file.
"""
import json
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.prefs_routes as pr


@pytest.fixture
def prefs_file(tmp_path, monkeypatch):
    f = tmp_path / "user_prefs.json"
    f.write_text(json.dumps({"_users": {"alice": {
        "theme": "light",
        "endpoint_id": "e0",
        "chat_model": "m0",
    }}}), encoding="utf-8")
    monkeypatch.setattr(pr, "PREFS_FILE", str(f))
    return f


def _raw(prefs_file):
    return json.loads(prefs_file.read_text(encoding="utf-8"))


@pytest.fixture
def client(prefs_file):
    app = FastAPI()

    @app.middleware("http")
    async def set_user(request, call_next):
        request.state.current_user = "alice"
        return await call_next(request)

    app.include_router(pr.setup_prefs_routes())
    return TestClient(app)


def _run_concurrent(fns, timeout=30):
    """Run all fns from threads, started together, and wait for them."""
    barrier = threading.Barrier(len(fns))
    errors = []

    def runner(fn):
        barrier.wait()
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 — surface in the joiner
            errors.append(exc)

    threads = [threading.Thread(target=runner, args=(fn,)) for fn in fns]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout)
    assert not errors, errors


# ---------------------------------------------------------------------------
# (a) overlapping partial updates both survive
# ---------------------------------------------------------------------------

def test_overlapping_partial_updates_both_survive(prefs_file):
    """Two overlapping locked read-modify-write transactions must not lose
    each other's key (the pre-port read-modify-write race)."""
    _run_concurrent([
        lambda: pr._update_for_user("alice", {"endpoint_id": "e1"}),
        lambda: pr._update_for_user("alice", {"chat_model": "m1"}),
    ])

    prefs = _raw(prefs_file)["_users"]["alice"]
    assert prefs["endpoint_id"] == "e1"
    assert prefs["chat_model"] == "m1"
    assert prefs["theme"] == "light"


def test_concurrent_http_puts_both_survive(client, prefs_file):
    """The same overlap through the real routes: PUT of two different keys
    at the same time — both values must be in the store afterwards."""
    _run_concurrent([
        lambda: client.put("/api/prefs/endpoint_id", json={"value": "e1"}),
        lambda: client.put("/api/prefs/chat_model", json={"value": "m1"}),
    ])

    prefs = _raw(prefs_file)["_users"]["alice"]
    assert prefs["endpoint_id"] == "e1"
    assert prefs["chat_model"] == "m1"
    assert prefs["theme"] == "light"


# ---------------------------------------------------------------------------
# (b) multi-key PATCH applies all keys atomically, or none
# ---------------------------------------------------------------------------

def test_patch_applies_all_keys_in_one_store_write(client, prefs_file):
    """An endpoint and its model land together: one store write, no
    half-applied pair."""
    resp = client.patch("/api/prefs", json={
        "values": {"endpoint_id": "e9", "chat_model": "m9"},
    })
    assert resp.status_code == 200
    assert resp.json() == {"values": {"endpoint_id": "e9", "chat_model": "m9"}}

    prefs = _raw(prefs_file)["_users"]["alice"]
    assert prefs["endpoint_id"] == "e9"
    assert prefs["chat_model"] == "m9"
    assert prefs["theme"] == "light"


def test_mutate_failure_writes_nothing(prefs_file):
    """All-or-nothing: a mutator that raises mid-transaction leaves the
    store byte-identical."""
    before = _raw(prefs_file)

    def boom(target):
        target["endpoint_id"] = "eX"
        raise RuntimeError("mid-transaction failure")

    with pytest.raises(RuntimeError):
        pr._mutate_for_user("alice", boom)

    assert _raw(prefs_file) == before


def test_mutate_success_persists_all_keys(prefs_file):
    def ok(target):
        target["endpoint_id"] = "e7"
        target["chat_model"] = "m7"
        return "done"

    assert pr._mutate_for_user("alice", ok) == "done"

    prefs = _raw(prefs_file)["_users"]["alice"]
    assert prefs["endpoint_id"] == "e7"
    assert prefs["chat_model"] == "m7"
    assert prefs["theme"] == "light"


# ---------------------------------------------------------------------------
# (c) a null value removes only its key
# ---------------------------------------------------------------------------

def test_update_null_removes_only_its_key(prefs_file):
    pr._update_for_user("alice", {"endpoint_id": None})

    prefs = _raw(prefs_file)["_users"]["alice"]
    assert "endpoint_id" not in prefs
    assert prefs == {"theme": "light", "chat_model": "m0"}


def test_put_null_value_removes_only_its_key(client, prefs_file):
    resp = client.put("/api/prefs/endpoint_id", json={"value": None})
    assert resp.status_code == 200
    assert resp.json() == {"key": "endpoint_id", "value": None}

    prefs = _raw(prefs_file)["_users"]["alice"]
    assert "endpoint_id" not in prefs
    assert prefs == {"theme": "light", "chat_model": "m0"}
