"""Strict chat mode — conversation-only turns, server-enforced.

Plain "chat" mode already calls the LLM with tools=None, but both the
frontend (workspace-intent regex) and this backend (tool-intent / web
auto-escalation) can quietly promote a chat turn to agent mode. Strict chat
makes the guarantee explicit and server-enforced:

  (1) mode=strict / strict_chat=true pins the turn to the chat path at parse
      time AND at the routing chokepoint (client escalation can't override),
  (2) the tool policy denies every known tool except web_search/web_fetch and
      disables MCP,
  (3) web pre-search stays available (use_web defaults on),
  (4) a static conversation-only system note is added to the preface.

Source-level guards (repo convention) + unit tests for the new helper.
"""

import ast
from pathlib import Path

import pytest

from src.tool_policy import (
    WEB_TOOL_NAMES,
    build_effective_tool_policy,
    known_tool_names,
    strict_chat_disabled_tools,
    STRICT_CHAT_SYSTEM_NOTE,
)

_CHAT_ROUTES = Path(__file__).resolve().parent.parent / "routes" / "chat_routes.py"
_CHAT_HELPERS = Path(__file__).resolve().parent.parent / "routes" / "chat_helpers.py"
_APP_JS = Path(__file__).resolve().parent.parent / "static" / "app.js"
_CHAT_JS = Path(__file__).resolve().parent.parent / "static" / "js" / "chat.js"
_INDEX_HTML = Path(__file__).resolve().parent.parent / "static" / "index.html"


# ── Helper unit tests ─────────────────────────────────────────


def test_strict_set_denies_everything_except_web_tools():
    denied = strict_chat_disabled_tools()
    known = known_tool_names()
    assert denied == known - WEB_TOOL_NAMES
    assert not (denied & WEB_TOOL_NAMES)


def test_strict_policy_blocks_shell_and_mcp_but_keeps_web():
    policy = build_effective_tool_policy(
        disabled_tools=strict_chat_disabled_tools(),
        disable_mcp=True,
    )
    assert policy.blocks("bash")
    assert policy.blocks("read_file")
    assert policy.blocks("manage_memory")
    assert not policy.blocks("web_search")
    assert not policy.blocks("web_fetch")
    assert policy.disable_mcp
    assert not policy.block_all_tool_calls  # web search must stay usable


def test_strict_note_is_static_and_conversation_framed():
    # KV-cache contract: no per-turn content (timestamps, counts, user text).
    assert STRICT_CHAT_SYSTEM_NOTE.strip()
    assert "{" not in STRICT_CHAT_SYSTEM_NOTE
    assert "strict chat" in STRICT_CHAT_SYSTEM_NOTE.lower()
    assert "agent mode" in STRICT_CHAT_SYSTEM_NOTE.lower()


# ── Source-level guards: server ───────────────────────────────


def test_chat_stream_reads_strict_flag():
    source = _CHAT_ROUTES.read_text(encoding="utf-8")
    assert 'strict_chat = str(form_data.get("strict_chat")' in source
    assert "(body or {}).get(\"strict_chat\")" in source


def test_strict_pins_mode_before_escalation():
    """The strict pin must run at parse time — BEFORE any auto-escalation and
    regardless of the client-sent mode. (A pin at the routing site would sit
    inside the nested stream generator and risk UnboundLocalError on chat_mode;
    the parse-time pin is what makes the guarantee safe.)"""
    source = _CHAT_ROUTES.read_text(encoding="utf-8")
    assert "strict_chat = str(form_data.get(\"strict_chat\")" in source
    assert 'if strict_chat:\n            chat_mode = "chat"' in source
    # The pin must come before the first escalation site.
    i_pin = source.find('if strict_chat:\n            chat_mode = "chat"')
    i_esc = source.find('chat→agent auto-escalation: category=')
    assert 0 < i_pin < i_esc


def test_strict_blocks_all_escalation_sites():
    """Every chat→agent auto-escalation site must be unreachable in strict mode."""
    source = _CHAT_ROUTES.read_text(encoding="utf-8")
    # plan-mode force
    assert "if plan_mode and not strict_chat:" in source
    # tool-intent / web / search escalations (first block) — pinned at parse
    assert 'if strict_chat:\n            chat_mode = "chat"' in source
    # contextual web follow-up
    assert "not strict_chat\n                and chat_mode == \"chat\"" in source
    # contextual browser follow-up
    assert "if not strict_chat and isinstance(message, str) and _is_contextual_browser_followup" in source
    # explicit-path workspace
    assert "if not strict_chat and not workspace and isinstance(message, str):" in source


def test_strict_tool_policy_applied():
    source = _CHAT_ROUTES.read_text(encoding="utf-8")
    assert "disabled_tools.update(strict_chat_disabled_tools())" in source
    assert "disable_mcp=strict_chat" in source


def test_strict_defaults_web_search_on():
    source = _CHAT_ROUTES.read_text(encoding="utf-8")
    assert "if strict_chat and not (use_web or '').lower() == 'true':" in source
    assert "use_web = 'true'" in source


def test_strict_note_injected_into_preface():
    source = _CHAT_HELPERS.read_text(encoding="utf-8")
    assert "strict_chat: bool = False" in source
    assert "STRICT_CHAT_SYSTEM_NOTE" in source
    assert 'preface.append({"role": "system", "content": STRICT_CHAT_SYSTEM_NOTE})' in source


# ── Source-level guards: frontend ─────────────────────────────


def test_ui_has_strict_button_and_toggle_state():
    html = _INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="mode-strict-btn"' in html
    js = _APP_JS.read_text(encoding="utf-8")
    assert "mode-strict-btn" in js
    assert "if (strictUrl) currentMode = 'strict';" in js  # phone override wins
    chat_js = _CHAT_JS.read_text(encoding="utf-8")
    assert "const isStrictMode = (toggleState.mode || 'chat') === 'strict';" in chat_js
    assert "fd.append('strict_chat', 'true');" in chat_js
    assert "isAgentMode ? 'agent' : (isStrictMode ? 'strict' : 'chat')" in chat_js
    # client-side escalations suppressed in strict mode
    assert "!isStrictMode && !isIncognito &&" in chat_js
    # web search stays available in strict mode
    assert "el('web-toggle').checked || isStrictMode" in chat_js


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
