## Instance map — Odysseus project on Improvements branch (as of 2026-08-22)
This maps the layout of the active Improvements branch. It is NOT a table of contents for the codebase; rather, it is a reference for what pieces exist where when custom features are added or removed. Use it to understand the current state after merges, resets, and personal patches. When comparing against the tree, verify each path with git ls-tree HEAD or ls -R; do not assume. When adding a new feature, update this map to show the new file(s) and their purpose.

### Frontend static assets and runtime behavior
- index.html loads app.js and other scripts; modulepreload hints are used but may stale after upstream merges that rename/reorder modules. Hard-refresh (Ctrl+Shift+R) after deployments if UI acts strange.
- app.js, chat.js, chatRenderer.js live under static/; their cache-buster version strings must stay in sync. Upstream #6113 introduced a mismatch that was locally reverted (see Lessons below).
- chatRenderer.js rebuilds assistant turns on reload from the DB (round_texts + tool events + metadata). It renders metadata.thinking (reasoning-content stored by the server) in BOTH paths now — single-bubble and multi-bubble (see Lessons 2026-08-21 and 2026-08-22).
- service-worker.js caches bundles; its CACHE_NAME constant must match the deployed app version to avoid serving stale JS/CSS.
- docs/index.html serves the documentation site and mirrors some app.js cache-buster patterns; keep in sync with static/ when bumping versions.

### Tool approval gate (RE-ADDED 2026-08-19 via upstream #6113)
- src/tool_approvals.py — the tool-approval gate — RE-ADDED 2026-08-19 via upstream #6113, now with "Allow for this task" / "Allow for this chat session" options (see Lessons below)
- tool_execution.py / tool_security.py / tool_policy.py / tool_index.py / tool_schemas.py / tool_utils.py / tool_parsing.py / tool_implementations.py — tool machinery (execution, security classification, policy, schemas, utilities)
- prompt_security.py — prompt-injection protection
- task_scheduler.py / task_action_policy.py / task_endpoint.py — scheduled tasks
- teacher_escalation.py — writes draft skills after failures
- memory.py / memory_provider.py / memory_vector.py / rag_manager.py / rag_singleton.py / rag_vector.py / chroma_client.py — memory + RAG
- model_context.py — KNOWN_CONTEXT_WINDOWS (model token limits; longest-substring-match wins; see fork skill)
- model_discovery.py / model_capabilities.py / model_capability_readers/ — model info
- chat_handler.py / chat_processor.py / chat_helpers.py / ai_interaction.py / llm_core.py — chat pipeline
- deep_research.py / research_handler.py / research_utils.py — research jobs
- cookbook_serve_lifecycle.py / preset_manager.py — model serving lifecycle
- core/*.py — core runtime utilities
- swift/*.py — Swift integration helpers

### Bash and system helpers
- boot.sh, launcher.py — entrypoints for the daemon and the web UI
- scripts/*.sh — various operational scripts (health checks, backups, etc.)
- systemd units (odysseus-ui.service, etc.) manage the service lifecycle

### Data, config, and tests
- data/, config/ — runtime data and configuration directories
- tests/ — test suite
- specs/ — specification documents

### Documentation and specifications
- docs/ — user-facing docs (includes instance-map.md itself)
- specs/ — technical specifications

---
## History of the tool-approval gate on Improvements
- The "Allow once" approval gate (src/tool_approvals.py, upstream commit 1b09c568 "authorize exact actions after untrusted context") entered Improvements via the big upstream/dev merge (7fbf54db), then two personal patches were layered on: a60e9834 ("narrow external-context gate to genuinely external sources") and d1898efa ("allow reading user-owned data after external context", HEAD before removal).
- How arming worked: tool_result_should_arm_gate() arms on EXTERNAL_UNTRUSTED tool results; messages_contain_external_untrusted_context() arms on tool_gate_untrusted=True metadata, provenance_origin="external", or _EXTERNAL_MESSAGE_SOURCES (web/email/research). The flag was a one-way ratchet (False→True only), re-derived from full conversation history each turn — so one web_search earlier in a session gated everything afterward.
- Verified facts (do not re-derive): auto-injected memory/skills context ALWAYS used arm_tool_gate=False (never armed, any version). But the agent actively CALLING manage_memory/manage_skills read tools DID arm the gate before d1898efa (results were classified EXTERNAL_UNTRUSTED; d1898efa reclassified them WORKSPACE_UNTRUSTED and removed READ_PRIVATE from POST_EXTERNAL_BLOCKED_EFFECTS).
- web_search / web_fetch / email / research are genuinely external — they armed the gate in ALL versions. Reverting d1898efa alone would NOT have fixed "local browsing got gated": the trigger was an earlier web_search, and browser_navigate/click/evaluate are not among the 4 read-only browser tools (browser_snapshot, browser_console_messages, browser_network_requests, browser_take_screenshot) so they fell to _UNKNOWN_CAPABILITIES (high-impact) and each required "Allow once".
- Outcome: user decided the feature was unwanted. Improvements was reset to e03c3891 (removing the 7fbf54db merge + both patches), force-pushed to origin, backup refs deleted. At that point, tool_approvals.py was removed.

## Lessons learned — 2026-08-19: upstream rebuilt the gate (#6113), our custom patch dropped
- Upstream merged PR #6113 ("allow remaining actions for an approved task", commit 98165235) into dev: the approval gate returned, but with two scope options instead of the old per-call "Allow once" — "Allow for this task" (bypass for the resumed in-memory run) and "Allow for this chat session" (bypass for later requests in the same chat). It also preserves retrieval context + tool candidates across the approval continuation (fixes the old RAG tool-loss).
- Improvements was rebased onto upstream/dev (85297cee) to bring #6113 in, keeping the 20 personal commits stacked on top. Our own custom gate patch (test/gate-approval-fix branch: session grants via tool_approval_mode / tool_approval_tool_policy, off/once/session toggle, per-tool pins) was deliberately NOT merged — dropped in favor of upstream's #6113 to avoid divergence. The off-switch / per-tool-policy ideas remain tracked in upstream issue #6084.
- Still absent upstream: no global off-switch and no per-tool policy (tracked in upstream issue #6084).
- Frontend cache bug (upstream, tracked — reverted locally to stay in sync): #6113 bumped app.js's internal imports (chat.js/chatRenderer.js → 20260819approvalcontrol1) but left app.js's own cache-buster in index.html at 20260815toolapproval4 (both the modulepreload and the script tag), so browsers that had cached the pre-#6113 app.js kept serving it and approval clicks arrived as literal text (the "loop"). We briefly patched this locally (bumped the app.js busters + service-worker CACHE_NAME) but that broke upstream's own regression test (test_frontend_tool_approval_uses_opaque_id_and_fixed_decisions asserts the old buster appears exactly 2×), so we reverted index.html/sw.js to match upstream/dev. Workaround: hard-refresh (Ctrl+Shift+R) after deploying. Proper fix belongs upstream — worth an issue/comment on #6113.

## Lessons learned — 2026-08-21: reasoning-model thinking lost on reload (fixed)
- Symptom: with reasoning models (DeepSeek / Qwen thinking), reloading a conversation showed only the tool-call cards — the assistant's text seemed "missing". The stored reasoning was also invisible.
- Root cause: reasoning models stream their chain of thought through `reasoning_content`, which the server stores in `metadata.thinking` (with `metadata.thinking_time`), NOT in `round_texts`. `addMessage()` in static/js/chatRenderer.js has two reconstruction paths: the single-bubble path already rendered `metadata.thinking`, but the multi-bubble path (turns with tool events) only read `round_texts` — so those turns collapsed to bare tool cards on reload. DB evidence: e.g. message `ba053975` has `round_texts=[('')]`, `thinking`=1637 chars; `050f7edc` has 8 empty rounds + 34 tool events, `thinking`=6819 chars.
- Fix: in the multi-bubble path of chatRenderer.js — (1) if no visible round text exists but `metadata.thinking` is present, emit a standalone `<think time="...">` bubble via `processWithThinking`; (2) otherwise prepend the stored thinking to the first visible text bubble, guarded by `!txt.includes(storedThinking)` for the rare approval-gate case where reasoning was already folded into the round text. Bumped chatRenderer.js's cache-buster in static/index.html to `20260821thinkingreload1` (later reverted — see 2026-08-22 below). Backup: /home/samy/backups/chatRenderer.js.bak.20260821_210733. Verified in browser (bubbles render, collapsed by default).
- Still open (bug #1, separate): during LIVE streaming, the final answer often lands in the thinking box instead of the chat body — a server/model-side issue (reasoning_content routing into the UI's thinking area), distinct from this reload-rendering fix. Investigate server-side `reasoning_content` handling (chat_helpers.py / streaming) in a separate session.

## Lessons learned — 2026-08-22: reload re-parsed literal `<think>` tags (fixed, no cache-buster)
- Symptom: after the 2026-08-21 fix, some reasoning-model turns STILL lost their thinking on reload — and worse, the reasoning leaked into the visible answer. The trigger was this very session: its chain-of-thought was *about* the `<think>`/`</think>` tags, so the stored reasoning contained hundreds of literal `<think>`/`</think>` substrings.
- Root cause: the reload path wrapped `metadata.thinking` in `<think time=...>…</think>` and handed it to `processWithThinking()`, whose `extractThinkingBlocks()` regex is non-greedy. It matched the wrapper's opening `<think>` up to the FIRST literal `</think>` inside the reasoning — truncating the thinking bubble and dumping the remainder into the answer. Measured against live messages: `f51fe3a6` thinking=12220 chars → only 798 rendered as thinking, 11421 leaked into the answer; `8cccc659` 225595 → 71700 rendered / 152828 leaked.
- Fix: added `markdownModule.processStoredThinking(thinking, reply, thinkingTime)` in static/js/markdown.js — a drop-in copy of `processWithThinking()` that takes the already-separated (thinking, reply) halves directly and skips the regex round-trip entirely (same `[DONE]` handling, `createThinkingSection`, emoji pass). Swapped the 3 reload call-sites in chatRenderer.js (multi-bubble standalone, multi-bubble prepend, single-bubble) from `<think>`-wrapping + `processWithThinking` to `processStoredThinking`.
- Cache-buster policy (why this fix ships NO version bump): app.py serves .js/.css/.html via `_RevalidatingStatic` with `Cache-Control: no-cache` (see app.py), so the browser revalidates on every load — a normal reload picks up the new bundle. Upstream regression tests (`test_tool_approval_task_scope.py`, `test_tool_approval_frontend_routing.py`, `test_startup_session_bootstrap_js.py`) PIN the exact `?v=` strings, so any buster bump breaks `test_route_context_agent_frontend_and_cache_bust_wire_the_contract`. Do NOT bump cache-busters locally; the 2026-08-21 bump (`20260821thinkingreload1`) was reverted for exactly this reason. If a stale bundle ever appears, hard-refresh (Ctrl+Shift+R).
- Verified: `node --check` clean on markdown.js + chatRenderer.js; 28 markdown/thinking pytest cases + 13 live-thinking scheduler tests pass; a direct render of a stored message containing 213 literal `<think>` tags now shows the full reasoning + answer intact.
