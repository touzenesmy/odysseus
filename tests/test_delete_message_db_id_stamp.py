"""Regression: message edit/delete must survive a page refresh.

Deleting a message in the UI targets ``dataset.dbId`` on the bubble. That id
comes from two server paths:

* live turns: the stream now emits ``user_message_saved`` (assistant bubbles
  already got ``message_saved`` on completion),
* refresh/reload: ``GET /api/history`` served from the DB. The DB row never
  stores ``_db_id`` (session_manager stamps it onto the in-memory message
  *after* commit), so the DB-shaped response previously carried no id at all
  and deletion silently degraded to DOM-only removal.

``_db_history_entry`` (nested in setup_history_routes) is the shared
serializer for every DB-served history response (paginated open, DB
fallback), so it must stamp the row id.
"""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAT_JS = ROOT / "static" / "js" / "chat.js"
HIST = ROOT / "routes" / "history" / "history_routes.py"


def _function_source(path, name):
    text = Path(path).read_text()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(text, node)
    raise AssertionError(f"{name} not found in {path}")


def _load_db_history_entry():
    """Exec the nested serializer with its real closure dependencies."""
    import re as _re
    display_src = _function_source(HIST, "_history_display_content")
    entry_src = _function_source(HIST, "_db_history_entry")
    ns = {
        "json": json,
        "Dict": dict,
        "Any": object,
        "DbChatMessage": object,  # annotation only; rows are SimpleNamespace
        "re": _re,
        "_HISTORY_INLINE_MEDIA_THRESHOLD": 200_000,
        "_DATA_IMAGE_RE": _re.compile(r"data:image/[^;,\"]+;base64,[A-Za-z0-9+/=\s]+"),
    }
    exec(compile(ast.parse(display_src), str(HIST), "exec"), ns)
    ns["_history_display_content"] = ns["_history_display_content"]
    exec(compile(ast.parse(entry_src), str(HIST), "exec"), ns)
    return ns["_db_history_entry"]


def _fake_row(meta_data=None):
    from types import SimpleNamespace
    return SimpleNamespace(
        id="row-1",
        role="user",
        content="hello",
        meta_data=meta_data,
        timestamp=None,
    )


def test_db_history_entry_stamps_db_id():
    entry = _load_db_history_entry()(_fake_row())
    assert entry["metadata"]["_db_id"] == "row-1"


def test_db_history_entry_stamps_db_id_over_stored_metadata():
    # A stale/corrupt stored _db_id must not win over the actual row id.
    entry = _load_db_history_entry()(
        _fake_row(meta_data='{"_db_id": "stale", "timestamp": "2026-01-01T00:00:00Z"}')
    )
    assert entry["metadata"]["_db_id"] == "row-1"
    assert entry["metadata"]["timestamp"] == "2026-01-01T00:00:00Z"


def test_build_chat_context_captures_user_message_id():
    src = _function_source(ROOT / "routes" / "chat_helpers.py", "build_chat_context")
    # The persisted user row id is read back from the in-memory message that
    # _persist_message just stamped, and handed to the route via ChatContext.
    assert 'user_message_db_id = last.metadata.get("_db_id")' in src
    assert "user_message_db_id=user_message_db_id" in src


def test_stream_emits_user_message_saved():
    src = _function_source(ROOT / "routes" / "chat_routes.py", "stream_with_save")
    # Emitted via getattr to match the codebase convention for optional
    # ctx fields (route_messages), so older stub contexts keep working.
    assert "user_message_saved" in src
    assert 'getattr(ctx, "user_message_db_id", None)' in src


def test_chat_js_stamps_user_bubble_db_id():
    js = CHAT_JS.read_text()
    # Contract: the user_message_saved handler exists, guards background
    # streams, and stamps _userMsgEl. It sits before the assistant
    # message_saved handler (the user id is emitted at stream start).
    assert "json.type === 'user_message_saved'" in js
    block = js.split("json.type === 'user_message_saved'", 1)[1].split(
        "json.type === 'message_saved'", 1
    )[0]
    assert "_userMsgEl.dataset.dbId = json.id" in block
    assert "if (_isBg) continue;" in block
