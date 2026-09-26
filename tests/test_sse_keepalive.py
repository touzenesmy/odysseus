"""Tests for _sse_keepalive in routes/chat_routes.py.

Regression class: long model-thinking gaps (> proxy read timeout) on the MAIN
chat/agent SSE streams. The wrapper must emit comment heartbeats on idle
WITHOUT cancelling the upstream generator (an earlier wait_for-on-__anext__
implementation would have killed the in-flight model request on the first
timeout — that is explicitly tested here).
"""

import asyncio
import inspect

import pytest

from routes.chat_routes import _sse_keepalive


async def _collect(agen, n):
    out = []
    for _ in range(n):
        out.append(await anext(agen))
    return out


async def _drain(agen):
    out = []
    async for item in agen:
        out.append(item)
    return out


@pytest.mark.asyncio
async def test_idle_longer_than_interval_yields_heartbeats_and_keeps_stream():
    async def slow_source():
        yield "a"
        await asyncio.sleep(0.6)   # > interval (0.2) -> at least one heartbeat
        yield "b"
        await asyncio.sleep(0.25)
        yield "c"

    out = await _drain(_sse_keepalive(slow_source(), interval=0.2))
    assert out[0] == "a"
    assert out[-1] == "c"
    data_items = [x for x in out if not x.startswith(":")]
    heartbeats = [x for x in out if x.startswith(":")]
    assert data_items == ["a", "b", "c"]
    assert len(heartbeats) >= 2
    # heartbeats are SSE comments and never disturb data ordering
    assert out.index("a") < out.index("b") < out.index("c")


@pytest.mark.asyncio
async def test_fast_source_no_heartbeats_passthrough():
    async def fast_source():
        for i in range(5):
            yield f"m{i}"

    out = await _drain(_sse_keepalive(fast_source(), interval=5.0))
    assert out == ["m0", "m1", "m2", "m3", "m4"]


@pytest.mark.asyncio
async def test_timeout_does_not_cancel_upstream_generator():
    """THE regression: after an idle heartbeat the source must still be able
    to produce its remaining items (a wait_for(__anext__) wrapper cancels the
    pending iteration and the source dies on the first timeout)."""
    async def slow_then_many():
        yield "a"
        await asyncio.sleep(0.5)  # forces >= 1 heartbeat at interval=0.1
        for i in range(3):
            yield f"x{i}"

    out = await _drain(_sse_keepalive(slow_then_many(), interval=0.1))
    assert out[-3:] == ["x0", "x1", "x2"]
    assert any(x.startswith(":") for x in out)


@pytest.mark.asyncio
async def test_source_exception_propagates():
    async def bad_source():
        yield "a"
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await _drain(_sse_keepalive(bad_source(), interval=5.0))


@pytest.mark.asyncio
async def test_short_source():
    async def one():
        yield "only"

    out = await _drain(_sse_keepalive(one(), interval=5.0))
    assert out == ["only"]


@pytest.mark.asyncio
async def test_early_consumer_close_does_not_raise():
    """Consumer breaks early (client disconnect) -> finally() runs.
    Regression: the finally previously did `await pump.cancel()` — Task.cancel()
    returns a bool, so awaiting it raised TypeError on EVERY early close."""
    async def endless():
        i = 0
        while True:
            yield f"c{i}"
            i += 1
            # Real streams always await (network I/O). A source with zero
            # awaits starves the event loop in the pump task (tight
            # __anext__/put loop never yields control) and hangs pytest —
            # keep this source realistic.
            await asyncio.sleep(0)

    wrap = _sse_keepalive(endless(), interval=0.05)
    got = await anext(wrap)  # one chunk, then abandon the stream
    assert got == "c0"
    # aclose() triggers GeneratorExit -> finally (pump cleanup).
    # Must NOT raise TypeError('object bool can't be used in 'await' ...').
    try:
        await wrap.aclose()
    except TypeError as e:
        pytest.fail(f"early close raised TypeError: {e}")
    # Let the fire-and-forget pump.cancel() actually land before the loop closes.
    await asyncio.sleep(0.05)


def test_wrapped_streams_are_async_generators():
    """Both hot loops wrap the real streams — assert the module wiring kept
    the call sites (source-guard: a refactor that unwraps them stays green
    only if this guard is updated deliberately)."""
    src = inspect.getsource(inspect.getmodule(_sse_keepalive))
    assert "async for chunk in _sse_keepalive(stream_llm_with_fallback(" in src
    assert "async for chunk in _sse_keepalive(stream_agent_loop(" in src
