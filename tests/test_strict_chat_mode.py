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


# ── Regression guards (2026-09-25: strict sends died silently) ──


def test_strict_helper_is_imported_in_chat_routes():
    """Regression (2026-09-25): chat_routes.py called strict_chat_disabled_tools()
    without importing it — every strict turn 500'd with NameError. The helper is
    defined in src/tool_policy.py, so the import block must name it."""
    src = _CHAT_ROUTES.read_text(encoding="utf-8")
    i0 = src.find("from src.tool_policy import (")
    assert i0 != -1, "tool_policy import block missing"
    i1 = src.find(")", i0)
    block = src[i0:i1]
    assert "strict_chat_disabled_tools" in block, (
        "strict_chat_disabled_tools is called at the strict policy site but not "
        "imported — strict turns would NameError at runtime"
    )


def test_chat_js_isPlanMode_is_not_const():
    """Regression (2026-09-25): the strict block assigns isPlanMode = false, but
    the declaration was const — handleChatSubmit threw TypeError
    'Assignment to constant variable' for EVERY strict send (silent, no POST).
    The declaration must be let."""
    src = _CHAT_JS.read_text(encoding="utf-8")
    assert "let isPlanMode = !!toggleState.plan_mode" in src, (
        "isPlanMode must be declared let — the strict block reassigns it"
    )
    assert "const isPlanMode" not in src


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
    # contextual browser follow-up (2026-10: restructured as a bool(...)
    # block — the strict gate must still precede the followup check)
    import re as _re
    _m = _re.search(
        r"_contextual_browser_turn_followup\s*=\s*bool\(\s*"
        r"not\s+strict_chat\s+and\s+isinstance\(message, str\)\s+"
        r"and\s+_is_contextual_browser_followup\(message, sess\)",
        source,
    )
    assert _m, "browser follow-up escalation lost its strict_chat gate"
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
    # The send path is driven by the mode toggle ONLY. Journal 2026-10-10:
    # re-reading the ?strict_chat=1 URL param here pinned the phone to
    # strict chat even on explicit Agent selections (agent turns died in
    # the app, worked in the browser). The param stays a per-launch UI
    # default (initModeToggle preselects the Strict pill on load).
    assert "const isStrictMode = (toggleState.mode || 'chat') === 'strict';" in chat_js
    assert "_strictUrl ||" not in chat_js
    assert "fd.append('strict_chat', 'true');" in chat_js
    assert "isAgentMode ? 'agent' : (isStrictMode ? 'strict' : 'chat')" in chat_js
    # client-side escalations suppressed in strict mode
    assert "!isStrictMode && !isIncognito &&" in chat_js
    # web search stays available in strict mode
    assert "el('web-toggle').checked || isStrictMode" in chat_js


def test_strict_url_param_is_default_only_not_send_override():
    """Regression (2026-10-10): the ?strict_chat=1 deep link must preselect
    the Strict pill on load (the phone's Chat-mode default) but must NOT
    override an explicit Agent/Chat selection at send time."""
    app_js = _APP_JS.read_text(encoding="utf-8")
    assert "if (strictUrl) currentMode = 'strict';" in app_js  # load-time default
    # The launch default must reach storage (the send path is storage-driven).
    # persist:false would let the send path revert to the stale stored mode.
    assert "setMode(currentMode, { persist: !strictUrl });" not in app_js
    assert "setMode(currentMode);" in app_js
    chat_js = _CHAT_JS.read_text(encoding="utf-8")
    assert "const isStrictMode = (toggleState.mode || 'chat') === 'strict';" in chat_js
    assert "isStrictMode = _strictUrl" not in chat_js
    assert "_strictUrl ||" not in chat_js


def test_strict_blocks_tool_intent_escalation():
    """The tool-intent/search/web escalation branches key off chat_mode ==
    "chat" — exactly what the strict pin sets — so each must check
    strict_chat itself (journal 2026-09-22: a strict turn escalated via the
    search branch because strict defaults use_web on)."""
    source = _CHAT_ROUTES.read_text(encoding="utf-8")
    assert 'if not strict_chat and chat_mode == "chat" and _tool_intent and _tool_intent.needs_tools:' in source
    assert 'elif not strict_chat and chat_mode == "chat" and _search_enabled:' in source
    assert 'elif not strict_chat and chat_mode == "chat" and _explicit_web_intent:' in source


def test_strict_mcp_gate_in_agent_loop():
    """MCP blocks must be rejected in the loop: the execution layer
    re-resolves the MCP manager per call, so the loop's mcp_mgr=None is not
    enforced there (journal 2026-09-22: strict turn executed
    mcp__builtin_browser__browser_navigate)."""
    source = (Path(__file__).resolve().parent.parent / "src" / "agent_loop.py").read_text(encoding="utf-8")
    assert "blocked_by_mcp_policy" in source
    assert 'block.tool_type.startswith("mcp__")' in source


def test_strict_mcp_gate_in_tool_execution():
    """Defense in depth: the execution layer itself refuses MCP calls when
    the turn policy disables MCP."""
    source = (Path(__file__).resolve().parent.parent / "src" / "tool_execution.py").read_text(encoding="utf-8")
    assert 'block.tool_type.startswith("mcp__")' in source
    assert "MCP tools are disabled for this request." in source


def test_ui_overflow_mirrors_follow_mode_hidden_buttons():
    js = _APP_JS.read_text(encoding="utf-8")
    assert "function hideModeHiddenMirrors()" in js
    assert "document.dispatchEvent(new CustomEvent('odysseus-mode-change'));" in js
    assert "document.addEventListener('odysseus-mode-change'" in js


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
