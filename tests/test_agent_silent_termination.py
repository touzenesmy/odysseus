"""Backlog #12 (silent-termination detection) — regression tests.

The 2026-10-28 20:11 EDT audit turn: 8 rounds / 16 tool events / 23.2K output
tokens, but rounds 2-8 all had empty visible text and the final round stopped
mid-plan in its reasoning stream ("Alright, I'll write the final audit
report…") with no visible content and no tool call — the turn terminated
silently: no error, no retry, no warning frame. The 71K-char report lives
only in the persisted thinking field.

Fix (detection only, ROADMAP #12 plan steps c/d): when the FINAL round has no
tool call, empty visible content, and a long reasoning field, emit a visible
warning frame before the loop breaks — instead of ending silently. The answer
is NOT moved into the bubble (that would reproduce the transcript wall); the
user is told where it is (the thinking section).

Detection is final-round-scoped on purpose: the 20:11 turn had 16 tool events
in EARLIER rounds, so a post-loop check against turn-wide tool_events would
never fire. The guard lives at the loop's `not tool_blocks: break` exit.

These tests pin the detection predicate and the emitted warning frame shape
(same extracted-helper pattern as test_llm_core_reasoning_content_fallback.py).
"""

import json

# No module-level stubs: conftest already isolates the DB environment and
# pre-imports the real heavy modules, and src.agent_loop imports cleanly on
# top of that (0.6 s). Stubbing src.agent_tools with MagicMock here broke the
# real strip_tool_blocks (a MagicMock call returns a Mock, not a string),
# which sent _strip_think_blocks into an infinite .find() loop on the Mock.
from src.agent_loop import (  # noqa: E402
    SILENT_TERMINATION_MIN_REASONING,
    silent_termination_warning,
)

# ---------------------------------------------------------------------------
# Detection predicate
# ---------------------------------------------------------------------------

def test_silent_termination_detected_on_long_reasoning_empty_content():
    """The 20:11 shape: final round with no visible answer and long thinking."""
    warning = silent_termination_warning(
        final_visible="",
        round_reasoning="x" * 2000,
        final_round_tool_events=[],
    )
    assert warning is not None
    assert "thinking" in warning.lower()


def test_no_warning_when_final_visible_content_present():
    """A real final answer suppresses the warning even with long thinking."""
    warning = silent_termination_warning(
        final_visible="Here is the audit report you asked for.",
        round_reasoning="x" * 2000,
        final_round_tool_events=[],
    )
    assert warning is None


def test_no_warning_below_reasoning_threshold():
    """Short thinking is a normal quiet turn, not a silent termination."""
    warning = silent_termination_warning(
        final_visible="",
        round_reasoning="x" * (SILENT_TERMINATION_MIN_REASONING - 1),
        final_round_tool_events=[],
    )
    assert warning is None


def test_no_warning_when_final_round_has_tool_call():
    """A final round that called a tool is not a silent termination — the
    tool path owns its own completion/failure semantics."""
    warning = silent_termination_warning(
        final_visible="",
        round_reasoning="x" * 2000,
        final_round_tool_events=[{"tool": "host_shell", "output": "ok"}],
    )
    assert warning is None


# ---------------------------------------------------------------------------
# Warning frame shape
# ---------------------------------------------------------------------------

def _parse_sse_frame(frame):
    assert isinstance(frame, str)
    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
    return json.loads(frame[len("data: "):-len("\n\n")])


def test_warning_frame_shape_and_reasoning_not_re_emitted():
    reasoning = "The full audit report that never became visible text." * 20
    frame = silent_termination_warning(
        final_visible="",
        round_reasoning=reasoning,
        final_round_tool_events=[],
    )
    payload = _parse_sse_frame(frame)
    assert payload["type"] == "warning"
    assert "thinking" in payload["message"].lower()
    # The reasoning was already streamed as {thinking:true} chunks and
    # persisted in the thinking field — the frame must not re-emit it as
    # visible prose (that would reproduce the transcript wall).
    assert reasoning not in frame
    assert len(payload["message"]) < 1000, "the warning is a pointer, not the answer"
