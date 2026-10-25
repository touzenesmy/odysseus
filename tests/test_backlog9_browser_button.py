"""Fork (Backlog #9): the ticked Browser button owns the raw Playwright MCP
surface end to end -- offered in the model prompt, granted by request
authority, and admitted at execution.

Before the fix, ``BUTTON_TOOLS["browser"]`` granted only ``private_browser``
(a metadata-only wrapper in local-launch mode), the offer-side hide rule
*added* the wire names to the MCP disabled map whenever the wrapper was
usable (i.e. exactly when the button was ON), and the execution gate denied
every raw ``mcp__builtin_browser__*`` transport unconditionally.

Gate-OFF default (no stamp, no env) must stay byte-identical: hidden from the
prompt, denied at execution -- pinned by test_raw_mcp_browser_execution_
cannot_evade_disabled_page_contract (upstream) and
test_raw_browser_mcp_is_hidden_when_private_browser_is_available.
"""

import json
from pathlib import Path

import pytest

import src.tool_execution as tool_execution
from src import browser_identity as browser
from src.agent_runtime.authority import OperationGrant, RequestAuthority
from src.tool_policy import BROWSER_MCP_TOOLS, browser_mcp_raw_surface_allowed
from src.tool_types import ToolBlock
from tests.test_private_browser_tool import _FakeBrowserMcp

TICKED_CTX = {"web_ui_state": {"browser_button": True}}
DENIAL_FK = browser.PAGE_FAILURE


# -- offer side: prompt + schemas ---------------------------------------------

def test_browser_button_offers_raw_mcp_when_ticked() -> None:
    from src.agent_loop import _build_system_prompt

    messages, schemas = _build_system_prompt(
        [{"role": "user", "content": "open https://example.com and take a screenshot"}],
        "gpt-5.5",
        None,
        _FakeBrowserMcp(),
        disabled_tools=set(),
        relevant_tools={
            "private_browser",
            "builtin_browser",
            "mcp__builtin_browser__browser_navigate",
        },
        compact=True,
        client_runtime_context=TICKED_CTX,
    )
    prompt_text = "\n".join(str(message.get("content") or "") for message in messages)
    schema_names = {schema.get("function", {}).get("name") for schema in schemas}
    assert "mcp__builtin_browser__browser_navigate" in schema_names
    assert "mcp__builtin_browser__browser_navigate" in prompt_text


def test_browser_button_env_override_offers_raw_mcp(monkeypatch) -> None:
    from src.agent_loop import _build_system_prompt
    monkeypatch.setenv("ODYSSEUS_EXPOSE_RAW_BROWSER_MCP", "1")
    _, schemas = _build_system_prompt(
        [{"role": "user", "content": "open https://example.com and take a screenshot"}],
        "gpt-5.5",
        None,
        _FakeBrowserMcp(),
        disabled_tools=set(),
        relevant_tools={
            "private_browser",
            "builtin_browser",
            "mcp__builtin_browser__browser_navigate",
        },
        compact=True,
    )
    schema_names = {schema.get("function", {}).get("name") for schema in schemas}
    assert "mcp__builtin_browser__browser_navigate" in schema_names


# -- grant side: the button owns the full wire family --------------------------

def test_button_grant_is_the_full_wire_family() -> None:
    from src.agent_runtime.authority import BUTTON_TOOLS
    granted = set(BUTTON_TOOLS["browser"])
    assert granted == {"private_browser"} | set(BROWSER_MCP_TOOLS)


def test_wire_names_match_the_execution_guard_surface() -> None:
    """Single source of truth: the constant and the execution guard set agree."""
    import re
    guard_source = (Path(__file__).resolve().parent.parent / "src" / "tool_execution.py").read_text()
    guard_block = guard_source.split("transport.rsplit", 1)[1].split("}")[0]
    guard_names = {
        "mcp__builtin_browser__" + name
        for name in re.findall(r'"(browser_[a-z_]+)"', guard_block)
    }
    assert guard_names == set(BROWSER_MCP_TOOLS)


# -- execution side ------------------------------------------------------------

from src.tool_capabilities import ToolRunSecurityContext


async def _run(name, ctx):
    authority = RequestAuthority("request", "alice", "thread", "", (OperationGrant(name),))
    return await tool_execution.execute_tool_block(
        ToolBlock(name, json.dumps({})),
        owner="alice", session_id="thread", workspace="",
        security_context=ToolRunSecurityContext(external_untrusted_context_seen=False),
        request_authority=authority, client_runtime_context=ctx,
    )


@pytest.mark.parametrize("ctx", [None, {}])
async def test_raw_mcp_browser_still_denied_by_default(ctx):
    """Upstream behavior preserved: no stamp, no env -> fail closed."""
    name = "mcp__builtin_browser__browser_navigate"
    _, result = await _run(name, ctx)
    assert result["failure_kind"] == DENIAL_FK and result["executed"] is False


async def test_raw_mcp_browser_admitted_when_button_ticked(monkeypatch):
    """The fix: ticked button -> the transport reaches the MCP manager."""
    calls = []

    class _Session:
        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            return {"content": [{"type": "text", "text": "navigated"}], "exit_code": 0}

    manager = _FakeBrowserMcp()
    manager._sessions = {"builtin_browser": _Session()}
    manager.resource_identity = _fake_identity

    async def _call_tool(qualified, args):
        return await manager._sessions["builtin_browser"].call_tool(
            qualified.rsplit("__", 1)[-1], args
        )

    manager.call_tool = _call_tool
    monkeypatch.setattr(tool_execution, "get_mcp_manager", lambda: manager)
    # The browser button's audience is the owner's own box: simulate an
    # admin/single-user owner so the orthogonal admin-only public gate
    # (is_public_blocked_tool) is bypassed and the transport actually reaches
    # the MCP manager. That gate is independent of the Backlog #9 fix.
    monkeypatch.setattr(tool_execution, "_owner_is_admin", lambda owner: True)

    name = "mcp__builtin_browser__browser_navigate"
    authority = RequestAuthority("request", "alice", "thread", "", (OperationGrant(name),))
    description, result = await tool_execution.execute_tool_block(
        ToolBlock(name, json.dumps({"url": "https://example.com"})),
        owner="alice", session_id="thread", workspace="",
        security_context=ToolRunSecurityContext(external_untrusted_context_seen=False),
        request_authority=authority, client_runtime_context=TICKED_CTX,
    )
    assert "UNSUPPORTED" not in str(description)
    assert result.get("failure_kind") != DENIAL_FK
    assert calls and calls[0][0] == "browser_navigate"
    assert calls[0][1].get("url") == "https://example.com"


async def test_env_override_admits_at_execution(monkeypatch):
    """ODYSSEUS_EXPOSE_RAW_BROWSER_MCP=1 is the global opt-in; the stamp is not required."""
    monkeypatch.setenv("ODYSSEUS_EXPOSE_RAW_BROWSER_MCP", "1")
    name = "mcp__builtin_browser__browser_snapshot"

    class _Session:
        async def call_tool(self, n, a):
            return {"content": [{"type": "text", "text": "ok"}], "exit_code": 0}

    manager = _FakeBrowserMcp()
    manager._sessions = {"builtin_browser": _Session()}
    manager.resource_identity = _fake_identity

    async def _call_tool(qualified, args):
        return await manager._sessions["builtin_browser"].call_tool(
            qualified.rsplit("__", 1)[-1], args
        )

    manager.call_tool = _call_tool
    monkeypatch.setattr(tool_execution, "get_mcp_manager", lambda: manager)
    # Same admin-owner simulation as the ticked test: the public gate is
    # orthogonal to the env opt-in this test pins.
    monkeypatch.setattr(tool_execution, "_owner_is_admin", lambda owner: True)

    authority = RequestAuthority("request", "alice", "thread", "", (OperationGrant(name),))
    description, result = await tool_execution.execute_tool_block(
        ToolBlock(name, json.dumps({})),
        owner="alice", session_id="thread", workspace="",
        security_context=ToolRunSecurityContext(external_untrusted_context_seen=False),
        request_authority=authority,
    )
    assert "UNSUPPORTED" not in str(description)
    assert result.get("failure_kind") != DENIAL_FK


def _fake_identity(qualified):
    from src.agent_runtime.resources import ExternalResource
    parts = qualified.split("__", 2)
    if len(parts) != 3 or parts[1] != "builtin_browser":
        return None
    return ExternalResource("mcp", "ep-test", "builtin_browser", qualified, "epoch-1")


# -- helper semantics ------------------------------------------------------------

def test_surface_allowed_reads_only_the_server_stamp(monkeypatch):
    monkeypatch.delenv("ODYSSEUS_EXPOSE_RAW_BROWSER_MCP", raising=False)
    assert browser_mcp_raw_surface_allowed(None) is False
    assert browser_mcp_raw_surface_allowed({}) is False
    assert browser_mcp_raw_surface_allowed({"web_ui_state": {"browser_button": False}}) is False
    assert browser_mcp_raw_surface_allowed(TICKED_CTX) is True
    monkeypatch.setenv("ODYSSEUS_EXPOSE_RAW_BROWSER_MCP", "1")
    assert browser_mcp_raw_surface_allowed(None) is True
    assert browser_mcp_raw_surface_allowed({"web_ui_state": {"browser_button": False}}) is True
