"""Backlog #12 (silent-termination detection) — regression tests.

The 2026-10-28 20:11 EDT audit turn: 8 rounds / 16 tool events / 23.2K output
tokens, but rounds 2-8 all had empty visible text and the final round stopped
mid-plan in its reasoning stream ("Alright, I'll write the final audit
report…") with no visible content and no tool call — the turn terminated
silently: no error, no retry, no warning frame. The 71K-char report lives
only in the persisted thinking field.

Fix (detection only, ROADMAP #12 plan steps c/d): when the FINAL round has no
tool call, empty visible content, and a large volume of thinking — in the
reasoning_content field OR in inline think markup inside the round text (Qwen
chat templates write the analysis in the content stream) — emit a visible
warning frame before the loop breaks, instead of ending silently. The answer
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
    silent_termination_persistence,
    silent_termination_warning,
)

# The think-markup tags are built from \u003c/\u003e escapes so the raw tag
# text never appears in this source file — the file tooling mangles raw tags
# (splits them across lines, which is a SyntaxError in single-line literals).
_THINK_OPEN = "\u003cthink\u003e"
_THINK_CLOSE = "\u003c/think\u003e"

# ---------------------------------------------------------------------------
# Detection predicate
# ---------------------------------------------------------------------------

def test_silent_termination_detected_on_long_reasoning_empty_content():
    """The 20:11 shape: final round with no visible answer and long thinking."""
    warning = silent_termination_warning(
        final_round_text="",
        round_reasoning="x" * 2000,
        final_round_tool_events=[],
    )
    assert warning is not None
    assert "thinking" in warning.lower()


def test_no_warning_when_final_visible_content_present():
    """A real final answer suppresses the warning even with long thinking."""
    warning = silent_termination_warning(
        final_round_text="Here is the audit report you asked for.",
        round_reasoning="x" * 2000,
        final_round_tool_events=[],
    )
    assert warning is None


def test_no_warning_below_reasoning_threshold():
    """Short thinking is a normal quiet turn, not a silent termination."""
    warning = silent_termination_warning(
        final_round_text="",
        round_reasoning="x" * (SILENT_TERMINATION_MIN_REASONING - 1),
        final_round_tool_events=[],
    )
    assert warning is None


def test_no_warning_when_final_round_has_tool_call():
    """A final round that called a tool is not a silent termination — the
    tool path owns its own completion/failure semantics."""
    warning = silent_termination_warning(
        final_round_text="",
        round_reasoning="x" * 2000,
        final_round_tool_events=[{"tool": "host_shell", "output": "ok"}],
    )
    assert warning is None


# ---------------------------------------------------------------------------
# Inline think markup (Qwen chat templates)
# ---------------------------------------------------------------------------

def test_silent_termination_detected_on_inline_think_blocks():
    """The Qwen finetunes write thinking INSIDE the content stream, so
    ``round_reasoning`` (the reasoning_content channel) stays empty. The
    answer still lives in the think markup and the turn still ends silently
    — the guard must measure the inline channel too."""
    inline = _THINK_OPEN + "analysis that never became visible" * 40 + _THINK_CLOSE
    warning = silent_termination_warning(
        final_round_text=inline,
        round_reasoning="",
        final_round_tool_events=[],
    )
    assert warning is not None
    assert "thinking" in warning.lower()


def test_silent_termination_detected_on_orphaned_closer_analysis():
    """Some local Qwen chat templates suppress the opening think tag while
    still emitting the closer — the analysis before the ORPHANED closer is
    hidden output (``_visible_response_text`` drops it), with nothing visible
    after it. That shape is a silent termination too."""
    orphaned = "orphaned analysis before the closer" * 40 + _THINK_CLOSE
    warning = silent_termination_warning(
        final_round_text=orphaned,
        round_reasoning="",
        final_round_tool_events=[],
    )
    assert warning is not None


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
        final_round_text="",
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


# ---------------------------------------------------------------------------
# Persistence composition (pointer + hidden raw text, idempotent per surface)
# ---------------------------------------------------------------------------

def _thinking_mass():
    return _THINK_OPEN + "hidden analysis" * 100 + _THINK_CLOSE


def test_persistence_reappends_hidden_raw_when_surfaces_stripped():
    """Qwen cleanup shape: round cleanup replaced the raw round text with
    visible-only text in BOTH surfaces (empty here), so the hidden raw text
    must be re-appended BEFORE the pointer on both — otherwise the pointer
    references output that is nowhere on reload."""
    hidden = _thinking_mass()
    pointer = "pointer to the thinking section"
    new_full, new_round = silent_termination_persistence(
        full_response="earlier visible round text",
        round_text="",
        round_response=hidden,
        pointer_message=pointer,
    )
    assert hidden in new_full
    assert pointer in new_full
    assert new_full.index(hidden) < new_full.index(pointer)
    assert hidden in new_round
    assert new_round.index(hidden) < new_round.index(pointer)


def test_persistence_does_not_duplicate_hidden_raw_already_persisted():
    """Standard path: both surfaces keep the raw think markup (strip_tool_blocks
    preserves it so it renders in the thinking section on reload). Re-appending
    would duplicate it — only the pointer is added, per surface, via endswith."""
    hidden = _thinking_mass()
    pointer = "pointer to the thinking section"
    new_full, new_round = silent_termination_persistence(
        full_response="earlier visible round text\n\n" + hidden,
        round_text=hidden,
        round_response=hidden,
        pointer_message=pointer,
    )
    assert new_full.count(hidden) == 1
    assert new_round.count(hidden) == 1
    assert new_full.endswith(pointer)
    assert new_round.endswith(pointer)


def test_persistence_pointer_only_without_hidden_mass():
    """Reasoning-channel shape: the thinking lives in the thinking field (already
    persisted there) and the raw round text is empty — pointer only, on both
    surfaces."""
    pointer = "pointer to the thinking section"
    new_full, new_round = silent_termination_persistence(
        full_response="earlier visible round text",
        round_text="",
        round_response="   ",
        pointer_message=pointer,
    )
    assert new_full == "earlier visible round text\n\n" + pointer
    assert new_round == pointer
