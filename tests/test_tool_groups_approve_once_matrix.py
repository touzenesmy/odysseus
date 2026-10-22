"""Fork tool-groups x afecd44d approve-once — dedicated matrix (PORT-GUIDE §C.2).

The per-group grant (ODYSSEUS_TOOL_GROUPS) and the afecd44d launch-scope
seal interact at exactly one seam: an UNGRANTED launch tool (bash/python)
still goes through ToolApprovalStore.create() at approval time, where
afecd44d seals its launch scope in the request's workspace. Ticked groups
must not disturb that path, and the seal must not leak across groups.

Style mirrors tests/test_tool_groups_contract_guard.py + the afecd44d suite
(test_exact_approval_ungranted_process.py): real frozen classes, real
ToolApprovalStore, source-pins for the wiring.
"""
from __future__ import annotations

import os
from dataclasses import replace

import pytest

from src.agent_runtime.authority import (
    BUTTON_TOOLS,
    OperationGrant,
    RequestAuthority,
    create_request_authority,
)
from src.agent_runtime.process_resources import LAUNCH_TOOLS
from src.tool_approvals import ToolApprovalStore
from src.tool_capabilities import ToolRunSecurityContext, capabilities_for_action
from src.tool_types import ToolBlock


@pytest.fixture(autouse=True)
def _scrub_fork_env_vars(monkeypatch):
    """Fork opt-in vars must never leak from the operator/host environment
    into these tests (same scrub as tests/test_request_authority.py)."""
    monkeypatch.delenv("ODYSSEUS_TOOL_GROUPS", raising=False)
    monkeypatch.delenv("ODYSSEUS_CORE_TOOL_GRANTS", raising=False)
    monkeypatch.delenv("ODYSSEUS_ALLOW_SERVER_HOME_LAUNCH", raising=False)


@pytest.fixture(autouse=True)
def admin_owner(monkeypatch):
    from src import tool_execution as execution
    monkeypatch.setattr(execution, "_owner_is_admin", lambda owner: True)


def _authority(workspace, *tools, **kw):
    return RequestAuthority("approval-request", "alice", "s", str(workspace),
                            tuple(OperationGrant(t) for t in tools), **kw)


def _grant_tools(authority) -> set[str]:
    return {g.tool for g in authority.grants}


def _approve(authority, tool, content, store=None):
    store = store or ToolApprovalStore()
    pending = store.create(owner=authority.owner, session_id=authority.session_id, origin_run_id="run",
        tool_name=tool, content=content, workspace=authority.workspace, request_authority=authority,
        external_untrusted_context_seen=True, capabilities=capabilities_for_action(tool, content))
    return pending, store


# --- Row 1: gate OFF, bash button ON (pre-feature baseline) ------------------

def test_row1_gate_off_bash_button_grants_and_seals_launch(tmp_path, monkeypatch):
    """Gate OFF: the pre-feature bash-button grant path. bash + file tools are
    granted at request time, so launch scopes are sealed at request time and
    the afecd44d approval seal is skipped (launch_scopes non-empty)."""
    monkeypatch.delenv("ODYSSEUS_TOOL_GROUPS", raising=False)
    grant = create_request_authority(
        "Testing, did it work?",
        client_runtime_context={"web_ui_state": {"bash": True}},
        workspace=str(tmp_path))
    assert set(BUTTON_TOOLS["bash"]) <= _grant_tools(grant)
    # Launch scopes sealed at request time => approve-once path unchanged.
    assert grant.launch_scopes, "granted bash must seal launch scopes at request time"


# --- Row 2: gate ON, bash group ticked ---------------------------------------

def test_row2_gate_on_bash_group_matches_gate_off(tmp_path, monkeypatch):
    """Gate ON: the bash group grants via BUTTON_TOOLS["bash"] and the route
    floor keeps bash out of disabled_tools — byte-identical to row 1's
    pre-feature grant set (regression pin: floor + grant agree)."""
    monkeypatch.setenv("ODYSSEUS_TOOL_GROUPS", "1")
    ctx = {"web_ui_state": {"bash": True}}
    grant = create_request_authority("Testing, did it work?", client_runtime_context=ctx,
                                     workspace=str(tmp_path))
    monkeypatch.delenv("ODYSSEUS_TOOL_GROUPS")
    baseline = create_request_authority("Testing, did it work?", client_runtime_context=ctx,
                                        workspace=str(tmp_path))
    assert set(BUTTON_TOOLS["bash"]) <= _grant_tools(grant)
    assert _grant_tools(grant) == _grant_tools(baseline)
    assert grant.launch_scopes


# --- Rows 3-4: gate ON, nothing ticked — afecd44d approve-once (sealed) -----

def test_row3_gate_on_ungranted_bash_approval_seals_workspace_root(tmp_path, monkeypatch):
    """Gate ON, no group ticked: bash is ungranted, so the approval path runs.
    afecd44d seals the launch scope in the single-root workspace at approval
    time; approve-once then succeeds, confined to the sealed root."""
    monkeypatch.setenv("ODYSSEUS_TOOL_GROUPS", "1")
    authority = _authority(tmp_path, "get_workspace")
    assert "bash" not in _grant_tools(authority)
    assert authority.launch_scopes == ()

    pending, store = _approve(authority, "bash", "printf approved-run")
    bound = pending.process_operation
    assert bound is not None, "afecd44d must seal an ungranted launch at approval"
    assert bound.launch is not None
    assert bound.launch.scope.root.path == str(tmp_path.resolve())
    assert bound.request_id == authority.request_id

    from src import tool_execution as execution
    exact = store.consume(pending.approval_id, decision="approve",
                          owner=authority.owner, session_id=authority.session_id)
    import asyncio
    description, result = asyncio.run(execution.execute_tool_block(
        ToolBlock("bash", "printf approved-run"), owner=authority.owner,
        session_id=authority.session_id, workspace=authority.workspace,
        request_authority=authority, exact_approval=exact,
        security_context=ToolRunSecurityContext(external_untrusted_context_seen=True)))
    assert result.get("failure_kind") != "resource_identity_denied", result
    assert result.get("exit_code") == 0, result
    assert "approved-run" in str(result.get("output", "")) + description


def test_row4_gate_on_ungranted_python_seals_like_bash(tmp_path, monkeypatch):
    """Gate ON, nothing ticked: python is in LAUNCH_TOOLS too, so the same
    afecd44d seal applies (single-root workspace)."""
    assert "python" in LAUNCH_TOOLS
    monkeypatch.setenv("ODYSSEUS_TOOL_GROUPS", "1")
    authority = _authority(tmp_path, "get_workspace")
    assert "python" not in _grant_tools(authority)

    pending, _store = _approve(authority, "python", "print('ok')")
    bound = pending.process_operation
    assert bound is not None, "afecd44d must seal an ungranted python launch"
    assert bound.launch.scope.root.path == str(tmp_path.resolve())


# --- Row 5: gate ON, inherited authority — no widening ------------------------

def test_row5_gate_on_inherited_authority_stays_unsealed(tmp_path, monkeypatch):
    """afecd44d guard `not request_authority.inherited`: child (inherited)
    authorities still cannot widen — no seal, executor refuses
    ('no sealed process identity')."""
    monkeypatch.setenv("ODYSSEUS_TOOL_GROUPS", "1")
    child = replace(_authority(tmp_path, "get_workspace"), inherited=True)
    pending, _store = _approve(child, "bash", "printf approved-run")
    assert pending.process_operation is None
    import asyncio
    from src import tool_execution as execution
    exact = _store.consume(pending.approval_id, decision="approve",
                           owner=child.owner, session_id=child.session_id)
    _, result = asyncio.run(execution.execute_tool_block(
        ToolBlock("bash", "printf approved-run"), owner=child.owner,
        session_id=child.session_id, workspace=child.workspace,
        request_authority=child, exact_approval=exact,
        security_context=ToolRunSecurityContext(external_untrusted_context_seen=True)))
    assert result.get("blocked") is True or result.get("failure_kind") == "resource_identity_denied", result


# --- Row 6: gate ON, multi-root workspace — no seal ---------------------------

def test_row6_gate_on_multi_root_workspace_stays_unsealed(tmp_path, monkeypatch):
    """afecd44d guard `len(roots) == 1` fails on a multi-root authority, so no
    launch scope is sealed and the approval cannot run (upstream behavior)."""
    monkeypatch.setenv("ODYSSEUS_TOOL_GROUPS", "1")
    from src.agent_runtime.resources import FilesystemRoot
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    roots = (FilesystemRoot.seal(str(tmp_path / "a"), owner="alice"),
             FilesystemRoot.seal(str(tmp_path / "b"), owner="alice"))
    authority = _authority(tmp_path, "get_workspace", resource_roots=roots)
    pending, _store = _approve(authority, "bash", "printf approved-run")
    assert pending.process_operation is None


# --- Row 7: ticked OTHER groups must not leak a bash grant --------------------

def test_row7_sessions_tick_does_not_leak_bash(monkeypatch):
    """The map is per-group with no cross-group union: ticking sessions must
    grant exactly the sessions group + core floor, never bash or any launch
    tool."""
    monkeypatch.setenv("ODYSSEUS_TOOL_GROUPS", "1")
    grant = create_request_authority(
        "Testing, did it work?",
        client_runtime_context={"web_ui_state": {"sessions": True}})
    tools = _grant_tools(grant)
    assert set(BUTTON_TOOLS["sessions"]) <= tools
    for launch in LAUNCH_TOOLS:
        assert launch not in tools, f"{launch} leaked from the sessions tick"
    assert not (set(BUTTON_TOOLS["bash"]) & tools)


# --- Row 8: floors compose (bash tick + core-tool grants) ---------------------

def test_row8_bash_tick_composes_with_core_tool_grants(monkeypatch):
    """ODYSSEUS_TOOL_GROUPS + ODYSSEUS_CORE_TOOL_GRANTS=1: the manage_memory
    core floor and the ticked bash group both land. RequestAuthority's ctor
    rejects duplicate tool grants, so a clean construction proves the two
    floors compose without a double-grant conflict."""
    monkeypatch.setenv("ODYSSEUS_TOOL_GROUPS", "1")
    monkeypatch.setenv("ODYSSEUS_CORE_TOOL_GRANTS", "1")
    grant = create_request_authority(
        "Testing, did it work?",
        client_runtime_context={"web_ui_state": {"bash": True}})
    tools = _grant_tools(grant)
    assert "manage_memory" in tools, "core floor must add manage_memory"
    assert set(BUTTON_TOOLS["bash"]) <= tools
    assert {"ask_user", "update_plan"} <= tools


# --- Wiring source-pins (guard style) -----------------------------------------

def test_wiring_seal_block_present_in_tool_approvals():
    """afecd44d seam: the seal import + guard must exist in
    ToolApprovalStore.create() (single-root workspace seal at approval)."""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "src" / "tool_approvals.py").read_text(encoding="utf-8")
    assert "seal_launch_scope" in src
    assert "not request_authority.inherited and operation.tool in LAUNCH_TOOLS" in src
    assert "len(roots) == 1" in src


def test_wiring_button_tools_map_complete():
    """Every button group maps to a non-empty tool tuple; the bash group is
    the launch group's carrier (approve-once interaction point)."""
    assert set(BUTTON_TOOLS) == {"bash", "sessions", "web", "media", "browser"}
    for group, tools in BUTTON_TOOLS.items():
        assert tools, group
    assert "bash" in BUTTON_TOOLS["bash"]
