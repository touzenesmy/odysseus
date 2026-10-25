"""Fork (Backlog #8): a preemptive admin/session tool call that the request
authority (or any hard execution gate) BLOCKS must not be emitted as the
assistant reply, and must not starve the model round.

Incident (2026-10-14, session ec9374c1): the user asked "there should be an
MCP browser tool ... can you check that?" The word "MCP" matched the
preemptive explicit-request regex, the loop pre-executed
``manage_mcp {"action": "list"}``, the request-authority gate denied it
(cookbook_admin not granted for that turn), and the preemptive path set
``full_response`` to the raw denial string and broke the loop -- so the user
saw the server error as an automated assistant message, and the model round
that could actually answer the question never ran.

Fix: when the preemptive result is a hard block, drop it (the attempt stays
in the tool trace) and let the normal model round proceed.

The pins below are deliberately robust to the loop's downstream machinery
(empty-response fallback, deterministic re-routing, delta buffering): they
assert on the control-flow contract -- the model round proceeds and produces
the real answer, and the raw denial is never emitted as a final_response --
rather than on the exact final-reply bytes.
"""

import pytest

from tests.runtime_evidence_helpers import authoritative_executor
from tests.test_stream_error_redaction import _client_chunks, _events

MODEL_ANSWER = "No MCP servers are configured for this workspace."

DENIAL = {
    "error": "The exact operation is outside server request authority.",
    "exit_code": 1,
    "blocked": True,
    "failure_kind": "request_authority_denied",
}


def _patch_common(monkeypatch):
    import src.agent_loop as module
    monkeypatch.setattr(module, "get_setting", lambda key, default=None: default)
    monkeypatch.setattr(module, "get_mcp_manager", lambda: None)
    monkeypatch.setattr(module, "blocked_tools_for_owner", lambda owner: set())
    monkeypatch.setattr(module, "estimate_tokens", lambda *args, **kwargs: 10)
    monkeypatch.setattr(module, "_agent_route_tool_mode", lambda *args, **kwargs: (True, False, False))
    monkeypatch.setattr(module, "_build_system_prompt", lambda messages, *args, **kwargs: (list(messages), []))
    monkeypatch.setattr(module, "_required_safe_read_operation", lambda contract: None)
    # The calendar preemptive is a separate branch; keep this test on the
    # explicit-admin path only.
    monkeypatch.setattr(module, "_parse_simple_calendar_tool_request", lambda *args: None)
    return module


def _delta_texts(events):
    return [e["delta"] for e in events if isinstance(e.get("delta"), str)]


async def _run_denied_preemptive(monkeypatch, denial):
    module = _patch_common(monkeypatch)
    executed = []
    model_calls = []

    async def execute(block, *args, **kwargs):
        executed.append(block.tool_type)
        return block.tool_type, dict(denial)

    async def stream(*args, **kwargs):
        model_calls.append(1)
        yield 'data: {"delta":"No MCP servers are configured for this workspace."}\n\n'
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(module, "execute_tool_block", authoritative_executor(execute))
    monkeypatch.setattr(module, "stream_llm_with_fallback", stream)
    chunks = await _client_chunks(module.stream_agent_loop(
        "http://model.test/v1", "test-model",
        [{"role": "user", "content": "What MCP servers are configured?"}],
        relevant_tools={"manage_mcp"}, owner="fixture", max_rounds=2, _is_teacher_run=True,
    ), False)
    return executed, model_calls, _events(chunks)


@pytest.mark.asyncio
async def test_denied_preemptive_is_not_emitted_as_the_reply(monkeypatch):
    """The regression: the denial used to become the reply and starve the model."""
    executed, model_calls, events = await _run_denied_preemptive(monkeypatch, DENIAL)
    # The preemptive attempt stays visible in the tool trace...
    tool_events = [
        e for e in events
        if e.get("type") == "tool_output" and e.get("fallback") == "preemptive_explicit_admin_session"
    ]
    assert tool_events, events
    assert executed and all(t == "manage_mcp" for t in executed), executed
    # ...and the model round was NOT starved: it proceeded and produced the
    # real answer (the user-visible fix).
    assert model_calls, "the model round must proceed after a denied preemptive"
    deltas = _delta_texts(events)
    assert any(MODEL_ANSWER in d for d in deltas), (deltas, events)
    # The raw denial string is never emitted as a final_response.
    for e in events:
        if e.get("type") == "final_response":
            assert e.get("content") != DENIAL["error"], e


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_kind", ["resource_identity_denied", "turn_contract_denied"])
async def test_other_hard_blocks_also_defer_to_the_model_round(monkeypatch, failure_kind):
    denial = dict(DENIAL)
    denial["failure_kind"] = failure_kind
    executed, model_calls, events = await _run_denied_preemptive(monkeypatch, denial)
    assert executed and all(t == "manage_mcp" for t in executed)
    assert model_calls, "the model round must proceed after a denied preemptive"
    for e in events:
        if e.get("type") == "final_response":
            assert e.get("content") != denial["error"], e


@pytest.mark.asyncio
async def test_successful_preemptive_still_short_circuits(monkeypatch):
    """Behavior guard: an ADMITTED preemptive still answers without a model round."""
    module = _patch_common(monkeypatch)
    executed = []
    model_calls = []

    async def execute(block, *args, **kwargs):
        executed.append(block.tool_type)
        return block.tool_type, {"output": "configured: none", "exit_code": 0}

    async def stream(*args, **kwargs):
        model_calls.append(1)
        pytest.fail("Model round must not run when the preemptive succeeded")
        yield  # pragma: no cover

    monkeypatch.setattr(module, "execute_tool_block", authoritative_executor(execute))
    monkeypatch.setattr(module, "stream_llm_with_fallback", stream)
    chunks = await _client_chunks(module.stream_agent_loop(
        "http://model.test/v1", "test-model",
        [{"role": "user", "content": "What MCP servers are configured?"}],
        relevant_tools={"manage_mcp"}, owner="fixture", max_rounds=2, _is_teacher_run=True,
    ), False)
    events = _events(chunks)
    assert executed and all(t == "manage_mcp" for t in executed)
    assert not model_calls, "an admitted preemptive must short-circuit the model round"
    tool_events = [
        e for e in events
        if e.get("type") == "tool_output" and e.get("fallback") == "preemptive_explicit_admin_session"
    ]
    assert tool_events and tool_events[0].get("exit_code") == 0
