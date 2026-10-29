"""Repro for Backlog #11: deleted messages must leave the LIVE session context.

2026-10-28 incident: two user messages were deleted in the UI (DB rows gone),
yet the next turn's agent context still carried the deleted text (app.log
[agent-intent] latest= / retrieval_query= both showed it).

This test drives the REAL delete route handler (routes.history.history_routes)
against a real SessionManager + temp DB, then asserts what the NEXT turn's
model context (Session.get_context_messages) contains.
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.helpers.database import isolated_session_database  # noqa: E402


class _FakeRequest:
    """Minimal request for the delete route.

    Auth is effectively disabled in the test env: owner None + no API token
    makes _verify_session_owner take the single-user path (only checks the
    session exists).
    """

    def __init__(self, payload: dict):
        self._payload = payload

    class _State:
        api_token = False
        api_token_owner = None
        current_user = "owner"

    state = _State()

    async def json(self):
        return self._payload


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_deleted_user_message_absent_from_live_context(tmp_path, monkeypatch):
    from core.models import ChatMessage
    import core.database as database
    import routes.session_routes as session_routes
    import routes.history.history_routes as history_routes

    with isolated_session_database(tmp_path) as (sm, _dbmod):
        # The route handlers resolve SessionLocal from THEIR module
        # namespaces, so bind the temp-DB factory there too.
        monkeypatch.setattr(session_routes, "SessionLocal", database.SessionLocal)
        monkeypatch.setattr(history_routes, "SessionLocal", database.SessionLocal)

        sid = sm.create_session(
            session_id="s11", name="t", endpoint_url="", model="m", owner="owner"
        ).id

        # Simulate a live session: user + assistant turns persisted through
        # the manager (stamps _db_id after commit, like the stream path).
        for role, text in [
            ("user", "Somthing isn't right. What's wrong with your prompts"),
            ("assistant", "I checked the prompts, all nominal."),
            ("user", "You just threw in a bunch of bash commands without any result"),
            ("assistant", "Apologies — here is the output."),
        ]:
            sm.add_message(sid, ChatMessage(role, text, metadata={}))

        sess = sm.get_session(sid)
        assert len(sess.history) == 4
        target_id = sess.history[0].metadata.get("_db_id")
        assert target_id, "user message must carry a _db_id stamp"

        # Build the REAL delete route with OUR manager, then call its handler.
        router = history_routes.setup_history_routes(sm)
        route = None
        for r in router.routes:
            if getattr(r, "path", "") == "/api/session/{session_id}/delete-messages":
                route = r
                break
        assert route is not None, "delete-messages route missing"

        _run(route.endpoint(_FakeRequest({"msg_ids": [target_id]}), session_id=sid))

        # What the NEXT turn's model context contains:
        sess = sm.get_session(sid)
        ctx = sess.get_context_messages()
        blob = json.dumps(ctx)
        assert "Somthing isn't right" not in blob, (
            "BUG #11: deleted user text still present in live model context"
        )
        # The DB row must be gone too (this already worked; guard against
        # the in-memory fix regressing the DB side).
        db = database.SessionLocal()
        try:
            n = db.query(database.ChatMessage).filter(
                database.ChatMessage.session_id == sid
            ).count()
        finally:
            db.close()
        assert n == 3
