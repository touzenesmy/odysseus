"""Regression test for the wedged-turn stall (Backlog #13).

A turn that WEDGES mid-stream — the upstream generator hangs on an ``await`` that
never resolves (a local-model prefill that stops producing, a wedged round-prep)
— must be TERMINATED by the SSE keepalive wrapper: it must close the upstream
generator (so the route's partial-save handler runs) and emit a terminal error
frame + ``[DONE]``.

Before the fix, ``_sse_keepalive`` only emitted comment heartbeats on idle with
NO upper bound. A hung generator raises nothing, so ``agent_runs._drain``'s
exception handlers never fire and nothing can detect the hang — the SSE stays
open and the run stays ``running`` forever. That is the user-facing "stall
forever, no error, no partial save" (observed 2026-10-31, three times in one
session: a 23-min and a 52-min dead turn with zero log output after the last
real chunk).

The primary test below HANGS (and therefore FAILS via asyncio.wait_for's
timeout) if the bug is present: consuming a keepalive-wrapped hung generator
never returns unless the idle-stop is implemented.
"""
import asyncio
import inspect

import pytest

from routes.chat_routes import _sse_keepalive


def _wrap(source, interval, max_idle):
    """Call ``_sse_keepalive`` with the idle-stop bound when the fix is present.

    If ``max_idle`` is not in the signature the fix is absent: fall back to a
    plain heartbeat wrapper so the wedged test goes RED by HANGING (the actual
    bug — the stream never terminates) instead of a TypeError.
    """
    if "max_idle" in inspect.signature(_sse_keepalive).parameters:
        return _sse_keepalive(source, interval=interval, max_idle=max_idle)
    return _sse_keepalive(source, interval=interval)


@pytest.mark.asyncio
async def test_wedged_turn_is_terminated_and_upstream_closed():
    """A hung upstream must be stopped: the stream terminates, emits a terminal
    error frame + [DONE], and the upstream generator's cleanup (the route's
    partial-save path) runs.

    If the bug is present (no idle-stop), the ``async for`` never returns, so
    ``asyncio.wait_for`` times out and this test FAILS.
    """
    closed = []

    async def hung_source():
        yield "data: first\n\n"
        try:
            # Wedged: the model/round-prep hangs here and never produces again.
            await asyncio.Event().wait()
        finally:
            # The route's except/finally (partial save) would run as this
            # generator is closed.
            closed.append(True)

    gen = _wrap(hung_source(), interval=0.01, max_idle=0.1)

    async def consume():
        out = []
        async for chunk in gen:
            out.append(chunk)
        return out

    # 5s >> max_idle (0.1s) but << "forever": with the fix this returns in ~0.1s;
    # without it, this raises asyncio.TimeoutError -> test fails.
    out = await asyncio.wait_for(consume(), timeout=5.0)

    text = "".join(out)
    assert closed, "upstream generator was not closed -> partial save would not run"
    assert "event: error" in text, "no terminal error frame was emitted"
    assert out[-1].strip() == "data: [DONE]", "stream did not terminate with [DONE]"


@pytest.mark.asyncio
async def test_healthy_stream_is_not_stopped():
    """A stream that keeps producing data must NOT trip the idle stop — it must
    deliver every chunk and end normally, with no spurious error frame."""
    async def healthy_source():
        for i in range(5):
            yield f"data: chunk{i}\n\n"
            await asyncio.sleep(0.01)  # well within max_idle

    gen = _wrap(healthy_source(), interval=0.05, max_idle=1.0)
    out = []
    async for chunk in gen:
        out.append(chunk)

    text = "".join(out)
    for i in range(5):
        assert f"chunk{i}" in text, f"chunk{i} was dropped"
    assert "event: error" not in text, "a healthy stream was wrongly stopped"
