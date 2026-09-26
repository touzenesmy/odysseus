"""Empty assistant turns must never reach the outbound model context.

Root cause: when the user aborts a stream before the first token, the client
persists a display-only placeholder (``role="assistant"``, ``content=""``,
``metadata={stopped: true, cancelled: true}``) via
``POST /api/session/{sid}/inject_messages`` so the "[Cancelled by user]"
indicator survives a refresh. Those rows then flow verbatim into the
``messages`` array of every later turn. Lenient providers ignore them, but
Moonshot/Kimi rejects the request::

    HTTP 400: Invalid request: the message at position 23 with role
    'assistant' must not be empty

…poisoning the whole conversation. The fix excludes empty assistant turns
(without ``tool_calls``) both at the context boundary
(``Session.get_context_messages``) and in the request-shaping sanitizer
(``src.context_compactor._sanitize_tool_messages``) for paths that bypass
the boundary (incognito, group chat).
"""

import sys
from unittest.mock import MagicMock

import pytest

from core.models import ChatMessage, Session


def _session(history):
    return Session(
        id="session-1",
        name="Chat",
        endpoint_url="http://example.invalid",
        model="test",
        history=history,
    )


class TestGetContextMessages:
    def test_empty_assistant_placeholder_excluded(self):
        sess = _session([
            ChatMessage("user", "hello"),
            ChatMessage("assistant", "hi there"),
            ChatMessage("user", "actually stop"),
            ChatMessage("assistant", "", {"stopped": True, "cancelled": True, "model": "kimi-k3"}),
            ChatMessage("user", "new question"),
        ])
        msgs = sess.get_context_messages()
        assert [m["content"] for m in msgs] == ["hello", "hi there", "actually stop", "new question"]
        assert all(
            m["role"] != "assistant" or (m["content"] or "").strip()
            for m in msgs
        )

    def test_whitespace_only_assistant_excluded(self):
        sess = _session([
            ChatMessage("user", "hi"),
            ChatMessage("assistant", "   \n "),
            ChatMessage("user", "again"),
        ])
        msgs = sess.get_context_messages()
        assert len(msgs) == 2

    def test_normal_assistant_content_kept(self):
        sess = _session([
            ChatMessage("user", "hi"),
            ChatMessage("assistant", "answer", {"stopped": True}),  # partial stop keeps content
            ChatMessage("user", "next"),
        ])
        msgs = sess.get_context_messages()
        assert [m["content"] for m in msgs] == ["hi", "answer", "next"]

    def test_empty_assistant_with_tool_calls_kept(self):
        """Tool-only turns persist content as empty with tool_calls attached;
        dropping them would orphan the following tool result messages."""
        sess = _session([
            ChatMessage("user", "run it"),
            ChatMessage("assistant", "", {"tool_calls": [{"id": "tc1", "function": {"name": "bash", "arguments": "{}"}}]}),
            ChatMessage("user", "done"),
        ])
        msgs = sess.get_context_messages()
        assert len(msgs) == 3
        assert msgs[1]["metadata"]["tool_calls"]

    def test_history_itself_is_untouched(self):
        """The transcript keeps the placeholder for the UI; only the
        outbound context copy filters it."""
        placeholder = ChatMessage("assistant", "", {"stopped": True, "cancelled": True})
        sess = _session([ChatMessage("user", "hi"), placeholder])
        sess.get_context_messages()
        assert sess.history[-1] is placeholder


# --- context_compactor sanitizer (paths that bypass get_context_messages) ---

for mod in [
    'sqlalchemy', 'sqlalchemy.orm', 'sqlalchemy.ext', 'sqlalchemy.ext.declarative',
    'sqlalchemy.ext.hybrid', 'sqlalchemy.sql', 'sqlalchemy.sql.expression',
    'src.database', 'core.database',
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from src.context_compactor import _sanitize_tool_messages


class TestSanitizeToolMessages:
    def test_empty_assistant_dropped(self):
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "", "metadata": {"stopped": True, "cancelled": True}},
            {"role": "user", "content": "next"},
        ]
        out = _sanitize_tool_messages(msgs)
        assert [m["content"] for m in out] == ["hi", "next"]

    def test_empty_assistant_with_tool_calls_survives_pass0(self):
        """Pass 0 must not drop tool-carrying turns (pass 1/2 own those)."""
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "",
             "tool_calls": [{"id": "tc1", "function": {"name": "bash", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "tc1", "content": "ok"},
        ]
        out = _sanitize_tool_messages(msgs)
        assert len(out) == 3
        assert out[1].get("tool_calls")

    def test_pairing_unaffected_by_removed_empties(self):
        """An empty placeholder sitting between a tool_calls turn and its
        tool result must not orphan the result after removal."""
        msgs = [
            {"role": "user", "content": "go"},
            {"role": "assistant", "content": "",
             "tool_calls": [{"id": "tc1", "function": {"name": "bash", "arguments": "{}"}}]},
            {"role": "assistant", "content": "", "metadata": {"stopped": True, "cancelled": True}},
            {"role": "tool", "tool_call_id": "tc1", "content": "ok"},
        ]
        out = _sanitize_tool_messages(msgs)
        assert [m["role"] for m in out] == ["user", "assistant", "tool"]
