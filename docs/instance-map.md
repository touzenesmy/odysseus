## Instance map — Odysseus project on Improvements branch (as of 2026-08-22)
This maps the layout of the active Improvements branch. It is NOT a table of contents for the codebase; rather, it is a reference for what pieces exist where when custom features are added or removed. Use it to understand the current state after merges, resets, and personal patches. When comparing against the tree, verify each path with git ls-tree HEAD or ls -R; do not assume. When adding a new feature, update this map to show the new file(s) and their purpose.

### Frontend static assets and runtime behavior
- index.html loads app.js and other scripts; modulepreload hints are used but may stale after upstream merges that rename/reorder modules. Hard-refresh (Ctrl+Shift+R) after deployments if UI acts strange.
- app.js, chat.js, chatRenderer.js live under static/; their cache-buster version strings must stay in sync. Upstream #6113 introduced a mismatch that was locally reverted (see Lessons below).
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
- Frontend cache bug (ours, fixed locally 2026-08-19): #6113 bumped app.js's internal imports but left app.js's own cache-buster in index.html stale, so browsers kept serving the pre-#6113 JS and approval clicks arrived as literal text (loop). Fixed by bumping the app.js modulepreload + script-tag busters and the service-worker CACHE_NAME.
