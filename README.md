# Odysseus — Instance Map & Lessons Learned

**This file is the primary orientation document for working on this instance.** It replaces the upstream README. Read it FIRST before any codebase work, debugging, or feature location. It records where things live and what was learned, so future sessions do not re-derive it.

## Layout — role of each file/directory

**Root**
- app.py — main entry point (uvicorn app, port 7000, run via systemd unit odysseus.service)
- launcher.py — alternate launcher entry
- boot.sh / setup.sh / update.sh — deployment scripts carried on the Improvements branch (upstream removed boot.sh)
- README.md — THIS FILE (map + lessons)
- odysseus-ui.service / odysseus.service — systemd units; the live server is odysseus.service
- docker-compose*.yml / Dockerfile / docker/ — Docker packaging (NOT used here; instance runs bare-metal)
- venv/ — Python virtualenv (venv/bin/python3)
- data/ — runtime data (uploads at data/uploads/YYYY/MM/DD/<hash>.png, app.db, skills at data/skills/, logs/)
- config/ — configuration
- static/ — frontend assets; static/js/app.js holds the UI toggle logic (see below)
- routes/ — web route handlers
- services/ — service-layer code
- integrations/ — external integrations
- mcp_servers/ — MCP server definitions
- companion/ — companion app code
- core/ — core subsystem
- tests/ — tests
- docs/, specs/, scripts/, swift/, Ollama/, searxng-config/ — docs, specs, helper scripts, macOS app, local models, searxng config

**src/ (core Python package)**
- agent_loop.py — the agent loop: turn processing, tool orchestration, security-gate hooks (run_security ~L3465, observe_tool_result ~L5813)
- tool_capabilities.py — tool capability classification: ResultIntegrity (SYSTEM / EXTERNAL_UNTRUSTED / WORKSPACE_UNTRUSTED), _PRIVATE_ACTION_READS, _UNKNOWN_CAPABILITIES, POST_EXTERNAL_BLOCKED_EFFECTS, messages_contain_external_untrusted_context(), tool_result_should_arm_gate(), _EXTERNAL_MESSAGE_SOURCES
- tool_approvals.py — the "Allow once" approval gate — REMOVED 2026-08-18 (see Lessons below)
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
- database.py — DB layer (app.db)
- url_safety.py / url_security.py — URL safety checks
- event_bus.py, bg_jobs.py, bg_monitor.py, cleanup_service.py, rate_limiter.py, readiness.py, service_health.py — background/ops
- embedding_lanes.py / embeddings.py / session_search.py — embeddings/search
- settings.py / config.py / constants.py / runtime_paths.py / secret_storage.py / auth_helpers.py — config/auth
- (remaining files are feature-specific modules — verify role on first use, then refine this map)

**static/js/app.js — UI toggles**
- web-toggle / web-toggle-btn (web search), bash-toggle / bash-toggle-btn (shell, agent-mode only), research-toggle, group-toggle, agent-mode-toggle / mode-toggle
- saveToolPref() / loadToggleState() — persist/restore toggle state

## Operational facts
- Server: systemd unit odysseus.service, uvicorn on port 7000, user samy. Restart: sudo systemctl restart odysseus.service
- Bare-metal, NOT Docker. venv at venv/
- Remotes: origin = git@github.com:touzenesmy/odysseus.git (SSH, has creds); touzenesmy = https (no creds); upstream = odysseus-dev/odysseus
- Branches: Improvements (personal work branch, tracks origin/Improvements), dev (tracks upstream/dev)
- Vision model: InternVL3.5-14B.Q4_K_M.gguf served at http://localhost:8004/v1/chat/completions; images land in data/uploads/YYYY/MM/DD/

## Lessons learned — 2026-08-18: the "Allow once" gate, and its removal
- The "Allow once" approval gate (src/tool_approvals.py, upstream commit 1b09c568 "authorize exact actions after untrusted context") entered Improvements via the big upstream/dev merge (7fbf54db), then two personal patches were layered on: a60e9834 ("narrow external-context gate to genuinely external sources") and d1898efa ("allow reading user-owned data after external context", HEAD before removal).
- How arming worked: tool_result_should_arm_gate() arms on EXTERNAL_UNTRUSTED tool results; messages_contain_external_untrusted_context() arms on tool_gate_untrusted=True metadata, provenance_origin="external", or _EXTERNAL_MESSAGE_SOURCES (web/email/research). The flag was a one-way ratchet (False→True only), re-derived from full conversation history each turn — so one web_search earlier in a session gated everything afterward.
- Verified facts (do not re-derive): auto-injected memory/skills context ALWAYS used arm_tool_gate=False (never armed, any version). But the agent actively CALLING manage_memory/manage_skills read tools DID arm the gate before d1898efa (results were classified EXTERNAL_UNTRUSTED; d1898efa reclassified them WORKSPACE_UNTRUSTED and removed READ_PRIVATE from POST_EXTERNAL_BLOCKED_EFFECTS).
- web_search / web_fetch / email / research are genuinely external — they armed the gate in ALL versions. Reverting d1898efa alone would NOT have fixed "local browsing got gated": the trigger was an earlier web_search, and browser_navigate/click/evaluate are not among the 4 read-only browser tools (browser_snapshot, browser_console_messages, browser_network_requests, browser_take_screenshot) so they fell to _UNKNOWN_CAPABILITIES (high-impact) and each required "Allow once".
- Outcome: user decided the feature was unwanted. Improvements was reset to e03c3891 (removing the 7fbf54db merge + both patches), force-pushed to origin, backup refs deleted. tool_approvals.py no longer exists in the tree. If this feature is ever re-added (e.g. rebuilt differently), this map shows exactly where the pieces live.
