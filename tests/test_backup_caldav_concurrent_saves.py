"""Regression tests for step-3d nugget 2 (upstream 9fdeb64a).

Backup restores, CalDAV account changes and legacy migration, and task
onboarding used to read a whole preference record and later write that stale
snapshot back. SettingsSaveRace forces a Settings write into that exact window.
When the handler reads under the store lock, the Settings write waits; when the
read is unprotected, it completes before the handler writes. Both writes must
survive in either case.
"""
import asyncio
import json
import os
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import routes.backup_routes as br
import routes.calendar_routes as cr
import routes.prefs_routes as pr
import routes.task.task_routes as tr
from src import caldav_sync


ACCOUNTS = [
    {
        "id": "acc-1",
        "label": "Home",
        "url": "https://cal.example.com/a",
        "username": "a",
        "password": "enc:1",
    },
    {
        "id": "acc-2",
        "label": "Work",
        "url": "https://cal.example.com/b",
        "username": "b",
        "password": "enc:2",
    },
]


def _store_lock_is_held(prefs_file) -> bool:
    """Whether another file description holds the preference store flock."""
    fcntl = pytest.importorskip("fcntl")
    with open(os.path.abspath(str(prefs_file)) + ".lock", "a+b") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(handle, fcntl.LOCK_UN)
        return False


class SettingsSaveRace:
    """Run a locked Settings update after the handler's first raw read."""

    def __init__(self, prefs_file, monkeypatch, updates):
        self._prefs_file = prefs_file
        self._updates = updates
        self._reads = 0
        self._read_done = threading.Event()
        self._save_done = threading.Event()
        self._errors = []
        self.fired = False
        real_load = pr._load

        def gated_load():
            data = real_load()
            self._reads += 1
            if self._reads == 1:
                self.fired = True
                self._read_done.set()
                if not _store_lock_is_held(self._prefs_file):
                    # An unprotected read exposes the old lost-update window.
                    assert self._save_done.wait(timeout=5.0)
            return data

        monkeypatch.setattr(pr, "_load", gated_load)
        self._thread = threading.Thread(target=self._save, daemon=True)
        self._thread.start()

    def _save(self):
        try:
            self._read_done.wait(timeout=5.0)
            pr._update_for_user("alice", self._updates)
        except BaseException as exc:  # surfaced by finish()
            self._errors.append(exc)
        finally:
            self._save_done.set()

    def finish(self):
        self._thread.join(timeout=5.0)
        assert self.fired, "the handler never read the preference store"
        assert not self._thread.is_alive(), "the Settings save did not finish"
        assert not self._errors, self._errors


@pytest.fixture
def prefs_file(tmp_path, monkeypatch):
    path = tmp_path / "user_prefs.json"
    path.write_text(json.dumps({
        "_users": {
            "alice": {
                "theme": "light",
                "language": "en",
                "keep_alice": "kept",
                "caldav_accounts": ACCOUNTS,
            },
            "bob": {
                "theme": "paper",
                "language": "fr",
                "keep_bob": "kept",
            },
        }
    }), encoding="utf-8")
    monkeypatch.setattr(pr, "PREFS_FILE", str(path))
    return path


def _users(prefs_file):
    return json.loads(prefs_file.read_text(encoding="utf-8"))["_users"]


def _request(body=None, user="alice"):
    async def read_json():
        return body or {}

    return SimpleNamespace(
        json=read_json,
        headers={},
        state=SimpleNamespace(current_user=user),
    )


@pytest.fixture
def backup_endpoint(prefs_file, monkeypatch):
    monkeypatch.setattr(br, "require_admin", lambda request: None)
    monkeypatch.setattr(br, "get_current_user", lambda request: "alice")
    router = br.setup_backup_routes(MagicMock(), MagicMock(), MagicMock())
    return next(
        route.endpoint for route in router.routes
        if route.path == "/api/import" and "POST" in route.methods
    )


@pytest.fixture
def calendar_endpoint(prefs_file, monkeypatch):
    monkeypatch.setattr(
        cr,
        "_require_user",
        lambda request: request.state.current_user,
    )
    router = cr.setup_calendar_routes()

    def endpoint(method, path):
        return next(
            route.endpoint for route in router.routes
            if route.path == f"/api/calendar{path}" and method in route.methods
        )

    return endpoint


@pytest.fixture
def onboarding_endpoint(prefs_file, monkeypatch):
    monkeypatch.setattr(tr, "get_current_user", lambda request: "alice")
    scheduler = MagicMock()
    scheduler.ensure_defaults = AsyncMock()
    router = tr.setup_task_routes(scheduler)
    endpoint = next(
        route.endpoint for route in router.routes
        if route.path.endswith("/onboarding") and "POST" in route.methods
    )
    return endpoint, scheduler


def test_settings_save_during_backup_restore_is_kept(backup_endpoint, prefs_file, monkeypatch):
    race = SettingsSaveRace(
        prefs_file,
        monkeypatch,
        {"theme": "dark", "added_in_settings": 1},
    )

    result = asyncio.run(backup_endpoint(_request({
        "preferences": {"language": "pt", "from_backup": True},
    })))
    race.finish()

    assert result["ok"] is True and result["imported"] == ["preferences"]
    alice = _users(prefs_file)["alice"]
    assert alice["theme"] == "dark"
    assert alice["added_in_settings"] == 1
    assert alice["language"] == "pt"
    assert alice["from_backup"] is True
    assert alice["keep_alice"] == "kept"


def test_backup_null_removes_exactly_its_own_key(backup_endpoint, prefs_file):
    bob_before = _users(prefs_file)["bob"]

    result = asyncio.run(backup_endpoint(_request({
        "preferences": {"language": None},
    })))

    assert result["ok"] is True
    users = _users(prefs_file)
    assert "language" not in users["alice"]
    assert users["alice"]["theme"] == "light"
    assert users["alice"]["keep_alice"] == "kept"
    assert users["alice"]["caldav_accounts"] == ACCOUNTS
    assert users["bob"] == bob_before


def test_settings_save_during_caldav_account_change_is_kept(
    calendar_endpoint, prefs_file, monkeypatch
):
    race = SettingsSaveRace(
        prefs_file,
        monkeypatch,
        {"theme": "dark", "added_in_settings": 1},
    )

    result = asyncio.run(calendar_endpoint(
        "DELETE", "/config/accounts/{account_id}"
    )("acc-1", _request()))
    race.finish()

    assert result == {"ok": True}
    alice = _users(prefs_file)["alice"]
    assert [account["id"] for account in alice["caldav_accounts"]] == ["acc-2"]
    assert alice["theme"] == "dark"
    assert alice["added_in_settings"] == 1
    assert alice["keep_alice"] == "kept"


def test_settings_save_during_legacy_caldav_migration_is_kept(prefs_file, monkeypatch):
    pr._update_for_user("alice", {
        "caldav_accounts": None,
        "caldav": {
            "url": "https://legacy.example.com/dav",
            "username": "old",
            "password": "enc:old",
        },
    })
    race = SettingsSaveRace(
        prefs_file,
        monkeypatch,
        {"theme": "dark", "added_in_settings": 1},
    )

    accounts = caldav_sync._load_caldav_accounts("alice")
    race.finish()

    assert [account["url"] for account in accounts] == [
        "https://legacy.example.com/dav"
    ]
    alice = _users(prefs_file)["alice"]
    assert alice["caldav_accounts"] == accounts
    assert "caldav" not in alice
    assert alice["theme"] == "dark"
    assert alice["added_in_settings"] == 1
    assert alice["keep_alice"] == "kept"


def test_settings_save_during_task_onboarding_is_kept(
    onboarding_endpoint, prefs_file, monkeypatch
):
    endpoint, scheduler = onboarding_endpoint
    race = SettingsSaveRace(
        prefs_file,
        monkeypatch,
        {"theme": "dark", "added_in_settings": 1},
    )

    result = asyncio.run(endpoint(_request(), {"enabled": False}))
    race.finish()

    assert result == {"ok": True, "opened": True, "enabled": False, "resumed": 0}
    alice = _users(prefs_file)["alice"]
    assert alice["tasks_opened"] is True
    assert "tasks_enabled" not in alice
    assert alice["theme"] == "dark"
    assert alice["added_in_settings"] == 1
    assert alice["keep_alice"] == "kept"
    scheduler.ensure_defaults.assert_awaited_once_with("alice")


def test_caldav_connection_without_saved_account_returns_clean_error(
    calendar_endpoint, prefs_file
):
    pr._update_for_user("alice", {"caldav_accounts": None})

    result = asyncio.run(calendar_endpoint("POST", "/test")(_request()))

    assert result == {
        "ok": False,
        "error": "Missing URL, username, or password",
    }
