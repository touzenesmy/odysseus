# Changelog

Human-readable summary of notable changes to this fork. The git commit history remains
the authoritative record; this file exists so "what changed and when" is readable
without `git log`.

## 2026-08-27 — Search reliability: engine-degradation detection + merge

**Problem.** `web_search` returned SEO-spam results. The search code was byte-identical
to upstream; the real issue was the SearXNG engine pin. `SEARXNG_GENERAL_ENGINES`
defaults to `bing,mojeek,presearch`, but from this instance's egress IP two of the three
were dead (Mojeek: silent 0 results; Presearch: timeout), leaving Bing alone — and
Bing's ranking for verb-led / "how to" queries is dominated by spam. The DuckDuckGo
provider fallback never fired because SearXNG returned *results* (not empty), just bad ones.

**Changes.**

- **Config** (`.env`, git-ignored): `SEARXNG_GENERAL_ENGINES=bing,duckduckgo,brave`
  (three engines confirmed live from this IP). Override documented in `.env.example`.
- **Code** (`services/search/core.py`, `services/search/providers.py`): the pipeline now
  reads SearXNG's own `unresponsive_engines` signal and detects *degraded* responses
  (a single contributing engine). When degraded, it keeps the SearXNG results, falls
  through to the DuckDuckGo provider, and merges + re-ranks both sets instead of
  accepting the first non-empty response. Healthy responses (≥2 engines) short-circuit
  unchanged.
- **Tests** (`tests/test_search_content_block_source_index.py`): re-pointed one mock at
  the new `_call_provider_with_meta` seam; assertions unchanged. Full search suite passes.

**Known upstream issue (out of scope).** The SearXNG `bing` engine returns
dictionary-definition spam for verb-led queries (e.g. "how to cook pasta" → "COOK
Definition"). That is Bing's own ranking, not this fork's code.
