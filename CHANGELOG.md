# Changelog

Human-readable summary of notable changes to this fork. The git commit history remains
the authoritative record; this file exists so "what changed and when" is readable
without `git log`.

## 2026-10-10 — Phone app: Agent mode turns were silently pinned to strict chat (no tools)

**Problem.** In the APK, selecting **Agent** and sending a message produced a
plain conversation reply — no tool calls, the turn just ended. The same message
sent from the desktop browser worked (full agent turn).

**Root cause.** The v2.7 phone "Chat mode only" deep link (`?strict_chat=1`) was
re-read by the *send path* on every turn
(`chat.js`: `isStrictMode = _strictUrl || ...`), so the phone sent
`strict_chat=true` **even when the user had explicitly tapped Agent**. The
server pin then ran every turn as no-tools strict chat. The browser never had
the URL param, so it was unaffected — exactly the reported asymmetry.

**Fix.**
- Send path is now driven by the **mode toggle only**:
  `isStrictMode = (toggleState.mode || 'chat') === 'strict'`.
- The URL param stays a **per-launch UI default**: `initModeToggle` still
  preselects the Strict pill on phone load, and now **persists it** like any
  selection (the phone's WebView profile has its own localStorage, so the
  desktop preference is untouched). This also closes the original 2026-09-23
  hole (phone sending the shared desktop 'agent' mode for strict sessions).
- Cache buster `20260925strictconst1` → `20261010strictagent2` (all four refs
  moved together, per the 2026-09-25 lesson).
- Tests: updated `test_ui_has_strict_button_and_toggle_state` + new
  `test_strict_url_param_is_default_only_not_send_override`
  (17 passed).

Static JS only — **no service restart** (files served from disk per request;
verified the live server serves the fixed lines). Browsers with the old module
cached get the new one via the bumped buster on next load.

## 2026-09-26 — Empty "Cancelled" assistant turns no longer poison strict providers (Moonshot/Kimi)

**Problem.** Hitting Stop before the model emitted its first token made the
client (`static/js/chat.js` → `_renderCancelledBubble`) persist a display-only
placeholder — `role="assistant"`, `content=""`,
`metadata={stopped: true, cancelled: true}` — via
`POST /api/session/{id}/inject_messages`, so the "[Cancelled by user]"
indicator survives a refresh. Those empty assistant rows then flowed verbatim
into the outbound `messages` array of every later turn: nothing between
persisted history and the HTTP payload filtered them. Lenient providers
(OpenAI, DeepSeek, local backends) ignore `content: ""`, but Moonshot/Kimi
reject the whole request with
`HTTP 400: ... the message at position N with role 'assistant' must not be empty`.
Any conversation containing one such placeholder was permanently un-sendable
with a Kimi model — including placeholders Kimi itself had produced before
being stopped — while brand-new sessions (no placeholders) worked fine. The
live DB held 106 of these rows across ~40 sessions.

**Fix** (`161ba0a4`). Filter empty assistant turns out of the outbound model
context in two places:

- **`core/models.py` → `Session.get_context_messages()`** (the canonical
  boundary every chat/agent path funnels through, which already excluded
  display-only `metadata.source == "slash"` messages): now also excludes
  assistant messages whose content is empty/whitespace-only **and** that carry
  no `tool_calls`. The filter keys off *content*, not the client-controllable
  `cancelled` metadata flag, so forged `inject_messages` metadata cannot hide
  real assistant turns from the model. Tool-calls-only turns (content `""`
  with `tool_calls`) are kept, since dropping them would orphan their tool
  result messages.
- **`src/context_compactor.py` → `_sanitize_tool_messages()`**: the same
  filter as "Pass 0", defense-in-depth for paths that bypass the boundary
  (incognito, group chat).

The transcript/display is untouched — the "[Cancelled by user]" bubbles still
render, because UI/history paths read raw `history`, not the filtered outbound
copy. The fix is retroactive: pre-existing poisoned conversations work again
after a server restart, no DB cleanup needed.

**Tests** (`tests/test_empty_assistant_context.py`): 8 regression tests —
placeholder excluded, whitespace-only excluded, partial-stop content kept,
tool-calls turns kept, transcript untouched, and tool-pairing intact after
removal.

## 2026-09-01 — Ticked bash now also survives the explicit-web-intent strip

**Problem.** The ticked bash toggle was *still* flaky, for a second reason.
Session `98d4cd8f` ("…update the skill with what we've learned **today**…")
lost `bash`/`python`/`read_file`/`write_file` for the whole turn despite the
bash toggle being ticked. The word "today" tripped the route's web-intent
regex (`…|today|…`), and the explicit-web-intent strip in
`routes/chat_routes.py` removed the four shell/file tools unconditionally —
again ignoring the ticked toggle. The light auto-escalation strip was fixed
yesterday, but this is a separate strip that ran first.

**Changes.**

- **Bash fix** (`routes/chat_routes.py`): hoisted a single `_bash_explicitly_on`
  flag (ticked `allow_bash=true`) above both intent strips. The web-intent
  strip now only removes `bash`/`python`/`read_file`/`write_file` when the
  toggle is *not* ticked; every other tool in that strip (`edit_file`,
  memory/skills/chats/email/notes/calendar/tasks/doc tools, `api_call`) still
  applies regardless. Explicit off, privilege denials, and compare mode keep
  stripping bash. The light auto-escalation strip reuses the same flag.
- **Tests** (`tests/test_chat_route_tool_policy.py`): 4 new regression tests —
  ticked bash survives the web-intent strip, unticked and explicit-off are
  still stripped, plus a source guard that the flag is defined before the
  strip consumes it.
- **Docs** (`specs/chat.md`): documented the explicit-web-intent strip and the
  ticked-bash exemption, with the `98d4cd8f` "today" incident as the worked
  example.

**Note.** The 2026-08-31 entry below said "the explicit-web-intent strip
still remove[s] bash as before"; that no longer holds — a ticked bash toggle
now exempts the web-intent strip too.

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
  bash + file companions survive; explicit off, privilege denials, and compare
  mode still remove bash. (The explicit-web-intent strip gained the same
  exemption on 2026-09-01 — see that entry.)
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
