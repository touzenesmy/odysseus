# Changelog

Human-readable summary of notable changes to this fork. The git commit history remains
the authoritative record; this file exists so "what changed and when" is readable
without `git log`.

## 2026-08-31 — Documents toolbar toggle + ticked-bash fix on light auto-escalation

**Problem.** The bash toolbar toggle ("always available") was flaky: `bash`
appeared only when a message's wording happened to classify as
shell/workspace. Root cause: the light auto-escalation strip in
`routes/chat_routes.py` removed `bash`/`python`/`read_file`/`write_file`
after tool retrieval, regardless of the ticked toggle. Separately, the
editor-panel document tools (notably `edit_document`, the preferred
patch-the-open-document path) could drop out of a turn when tool retrieval
missed them, even though `ALWAYS_AVAILABLE` membership should protect them.

**Changes.**

- **Bash fix** (`routes/chat_routes.py`): the light auto-escalation strip now
  checks `allow_bash` first — a ticked toggle (`true`) exempts the strip so
  bash + file companions survive; explicit off, privilege denials, compare
  mode, and the explicit-web-intent strip still remove bash as before.
- **New Documents toggle** (`static/index.html`, `static/app.js`,
  `static/js/chat.js`): icon button after the bash button and before the
  workspace name, same `input-icon-btn` style, agent-mode-only, mobile
  overflow collapse, localStorage persistence, splash card, toast. Ticking it
  sends `allow_documents=true`, which force-includes `DOCUMENT_TOOL_NAMES`
  (`create_document`, `edit_document`, `update_document`, `suggest_document`,
  `manage_documents`) so `edit_document` survives retrieval variance;
  unticked sends `false` and strips the set. The active-document prune in
  `src/agent_loop.py` only touches disk file tools, so the toggle holds on
  "edit this document" turns too.
- **Tests** (`tests/test_chat_route_tool_policy.py`): 5 new tests covering
  the ticked-bash exemption and the documents toggle on/off/unset paths.
- **Docs** (`specs/chat.md`, `specs/agent-tools.md`, `specs/frontend.md`):
  tri-state semantics of `allow_bash`/`allow_documents`, the strip-exemption
  rule, `ALWAYS_AVAILABLE` retrieval-vs-force-include distinction, and
  composer toolbar toggle wiring.

**Verification.** `py_compile` + `node --check` clean; targeted policy
tests 57 passed; full suite 5821 passed with 6 pre-existing failures that
fail identically on the unmodified tree.

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
