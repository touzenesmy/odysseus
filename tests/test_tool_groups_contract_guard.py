"""Fork tool-group buttons (Backlog #1) — contract-boundary guard.

Incident 2026-10-18/19: the ticked-group tools were force-included into
_forced_tools (legacy path) and floored at final consumption, but the
turn contract's FROZEN offered set was built earlier by
resolve_turn_contract and never received the ticked tools -- so contract
turns silently under-granted. The fix (934b8366 + 8184bebf) rewrites the
frozen TurnContract via object.__setattr__ right after resolution.

These guards execute that exact pattern against the REAL frozen dataclass
and pin the route wiring, so a regression surfaces in pytest instead of
as silent under-granting (or an AttributeError) at request time.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from src.agent_runtime.authority import BUTTON_TOOLS
from src.turn_contract import TurnContract

_ROOT = Path(__file__).resolve().parent.parent
_CHAT_ROUTES = _ROOT / "routes" / "chat_routes.py"
_GATE = 'os.environ.get("ODYSSEUS_TOOL_GROUPS"'


def _tick_tools(*groups: str) -> set[str]:
    out: set[str] = set()
    for g in groups:
        out |= set(BUTTON_TOOLS.get(g, ()))
    return out


def test_contract_tick_wins_mutation_on_real_frozen_class():
    """Run the exact mutation the route performs, on the real class."""
    from src.tool_policy import BROWSER_MCP_TOOLS
    ticked = _tick_tools("sessions", "browser")
    # Fork (Backlog #9): the ticked browser button owns the full raw
    # Playwright MCP surface, not just the metadata-only wrapper.
    assert ticked == (
        {"list_sessions", "search_chats", "create_session",
         "manage_session", "send_to_session", "private_browser"}
        | set(BROWSER_MCP_TOOLS)
    )
    contract = object.__new__(TurnContract)  # frozen dataclass: bypass ctor
    object.__setattr__(contract, "capabilities", frozenset())
    object.__setattr__(contract, "required", frozenset())
    object.__setattr__(contract, "offered", frozenset({"read_file", "write_file"}))
    object.__setattr__(contract, "executable", frozenset({"read_file", "write_file"}))
    object.__setattr__(contract, "unavailable", frozenset())
    object.__setattr__(contract, "schema_json", (json.dumps({"function": {"name": "read_file", "parameters": {}}} , sort_keys=True),))

    added = ticked - set(contract.offered)
    object.__setattr__(contract, "executable", contract.executable | added)
    object.__setattr__(contract, "offered", contract.offered | added)
    object.__setattr__(contract, "schema_json", contract.schema_json + tuple(
        json.dumps({"function": {"name": n, "parameters": {}}}, sort_keys=True)
        for n in sorted(added)
    ))

    assert contract.offered == {"read_file", "write_file"} | ticked
    assert contract.executable == {"read_file", "write_file"} | ticked
    for name in ticked:
        assert contract.permits(name), name
    # Idempotency: re-running the mutation must not duplicate or fail.
    object.__setattr__(contract, "offered", contract.offered | ticked)
    assert contract.offered == {"read_file", "write_file"} | ticked


def test_contract_boundary_wiring_in_chat_route():
    src = _CHAT_ROUTES.read_text(encoding="utf-8")
    resolve = src.index("resolve_turn_contract(")
    boundary = src.index('object.__setattr__(_turn_contract, "offered"')
    clobber = src.index("_forced_tools = set(_turn_contract.offered)")
    floor = src.index("tg_final_disabled = (disabled_tools or set()) - _tg_final_floor")
    bridge = src.index("_stream_agent_with_execution_bridge(", floor)
    assert resolve < boundary < clobber < floor < bridge, (
        "order must be: resolve contract -> contract-boundary offer -> "
        "forced-tools clobbers -> final-consumption floor -> bridge"
    )
    assert "_tg_c_added -= set(_turn_contract.offered)" in src, "idempotent added-set"
    assert '_tg_json.dumps(s, sort_keys=True)' in src, "schema_json must be unioned"
    assert src.count('object.__setattr__(_turn_contract,') == 3, "offered+executable+schema_json"
    # The block must be gate-gated and parse the same wire key as the floors.
    block = src[boundary - 2000:boundary]
    assert _GATE in block and 'form_data.get("tool_groups")' in block
    # Gate OFF invariant: every tick-wins block sits under the same gate string.
    assert src.count(_GATE) == 5, (
        "5 gated sites: selection floor + per-group stamp + RAG force-include "
        "+ final-consumption floor + contract-boundary offer"
    )


def test_gate_off_is_inert():
    src = _CHAT_ROUTES.read_text(encoding="utf-8")
    for marker in (
        'object.__setattr__(_turn_contract, "offered"',
        "tg_final_policy = build_effective_tool_policy(",
        "_forced_tools.update(BUTTON_TOOLS[_g])",
    ):
        idx = src.index(marker)
        assert src.rindex(_GATE, 0, idx) > idx - 3000, (
            f"{marker!r} must sit under the ODYSSEUS_TOOL_GROUPS gate"
        )
    os.environ.pop("ODYSSEUS_TOOL_GROUPS", None)
    assert os.environ.get("ODYSSEUS_TOOL_GROUPS", "").strip().lower() not in {"1", "true", "yes"}
