# PORT-GUIDE — post-security port (Scaffold → ImprovementsDev)

- Date: 2026-10-20
- `ImprovementsDev` = `2ca1e255` (1 commit over `upstream/dev` = `8877273e`, post-security-migration base: #6503 pre-Ajax runtime migration, Oct 2–6 `fix(security)` series, #6742 email export)
- `Scaffold` = `1d7a89a5` = branch `improvements-20261014` (our old work branch — buggy in prod, reverted, but holds the scaffolding we want)
- Merge-base `a8c147b2` (2026-10-07); upstream moved **44 commits** (35 non-merge) since; Scaffold is **173 commits** ahead
- Production: `improvements-20261012` @ `207df1c0` — **not touched by this guide**
- Full Scaffold inventory: `specs/commit-map.md` on the Scaffold ref (`git show Scaffold:specs/commit-map.md`, groups A–P)

**Strategy.** Port the 173-commit delta onto the new runtime in **three chunks** — no big-bang rebase.
Each chunk: cherry-pick/adapt commits oldest→newest, run focused tests in this worktree
(`/home/samy/odysseus/venv/bin/python -m pytest -p no:cacheprovider …` — the worktree has no venv of its own),
then user deploys via `~/odysseus/deploy.sh` → `ImprovementsDev` (snapshots `data/`, detaches this worktree,
runs the branch's `update.sh`, restarts the service) and smoke-tests. Production stays on
`improvements-20261012` until `ImprovementsDev` has run stable for days.

Every claim below was re-verified against the actual diffs on 2026-10-21 (see "Corrections" at the end).

---

## A — Upstream delta (a8c147b2..upstream/dev, 44 commits)

### A.1 Per-commit classification

All 44 are single-parent squash merges; `git show --name-only` gives exact per-commit files.
**O** = touches ≥1 of the 25 files the Scaffold delta also touches (net sets via
`git diff --name-only a8c147b2..upstream/dev` ∩ `…a8c147b2..Scaffold`).
**11 of 44** upstream commits overlap (prior estimate "~14" was wrong — see Corrections).

| SHA | date | subject (abridged) | files (abridged) | O |
|---|---|---|---|---|
| ac449612 | 10-01 | fix(mcp) expired OAuth state page (#5598) | routes/mcp, tests | |
| 35e3b298 | 10-03 | fix(scheduler) non-numeric research settings | src/task_scheduler.py, tests | |
| b49f66cb | 10-12 | README community section | README.md | |
| 8feb50e8 | 10-13 | feat(notes) attach Notes/Todos as Agent context (#6495) | chat_helpers, chat_routes, agent_loop, index.html, chat.js, notes.js, sessions.js | **O(5)** |
| **afecd44d** | 10-13 | **fix(approvals) "approve once" runs ungranted bash/python (#6635)** | skills_routes, **src/tool_approvals.py**, 2 tests | |
| 0e2c0830 | 10-13 | feat(settings) utility reasoning effort (#6572) | chat_helpers, email*, history, memory, session, skills routes, context_compactor, llm_core, settings.py, index.html, settings.js | **O(6)** |
| b5b76fe4 | 10-13 | fix(skills) inject published skills w/ Auto-approve off (#6643) | skills.py, agent_loop | **O(1)** |
| 1cc56cb9 | 10-13 | refactor(frontend) source ownership + gates (#6701) | frontend/src/** (Notes + actionMenuOrder only), build/check scripts | |
| f902be18 | 10-13 | fix(ci) restore dev pytest baseline (#6704) | 11-tasks.css, 4 tests | |
| 86b886c6 | 10-14 | feat(skills) remote-only tag (#6693) | skills.py, agent_loop | **O(1)** |
| c23b1be3 | 10-14 | fix(history) reject coerced truncation (#6565) | history_routes, test | **O(1)** |
| 0c56527d | 10-14 | fix(email) preserve mail on bulk-trash failure (#6633) | email_routes, test | |
| 353ea007 | 10-14 | fix(auth) honor AUTH_ENABLED=false (#6029) | auth_routes, settings.js, 2 tests | **O(2)** |
| 50105980 | 10-14 | fix(cleanup) stale message counts (#6610) | cleanup_service, test | |
| **6fceb6cc** | 10-14 | **fix(security) deny generated-image on failed ownership check (#6268)** | app.py, image_gen_server, ai_interaction, generated_images, tool_execution, 2 tests | **O(2)** |
| c3819e3c | 10-14 | fix(docker) ChromaDB volume mount (#6166) | 3× docker-compose*.yml, docs, test | **O(3)** |
| 9f8eae72 | 10-15 | merge PR #6691 (readme) | (merge) | |
| f1a47f38 | 10-15 | refactor(notes) decompose into feature modules (#6713) | 121 files, mostly frontend/ | **O(1: sw.js)** |
| b2e717e2 | 10-15 | refactor(skills) extract audit orchestration (#6711) | skills/*, skills_routes | |
| c74f4756 | 10-15 | fix(upload) no-login mode (#6528) | upload_routes, 2 tests | |
| a0137b47 | 10-15 | docs maintainers handbook | docs/maintainers/* | |
| 6cf676df | 10-15 | feat(email) export as email/PDF | email_routes, emailLibrary js, test | |
| b97c1ee5, 55b5b7f4, bead6a67 | 10-15 | docs maintainer/specs | docs, **8 specs/ files** | **O(bead6a67)** |
| 0590edd4, 9712a540 | 10-16 | merges (#6744, #6434) | (merge) | |
| 15099eba | 10-16 | refactor(mcp) unify OAuth resolution (#5598) | mcp_routes, test | |
| 88772b32 | 10-19 | fix(tasks) admin-only action policy (#6358) | tools/system.py, test | |
| 89461006, c1d90bee | 10-19 | merge + fix(scheduler) OverflowError | task_scheduler | |
| b2613b21 | 09-23* | fix(ui) iOS safe areas, landscape | 20 files incl. **01-agent-chat.css, index.html, chat.js** | **O(3)** |
| 268636c9, 63e18a46 | 10-19/20 | merge + CSS snapshot update | css_snapshot baseline | |
| ae238b73, 8363919a | 10-20 | merges (#6396, #6736) | (merge) | |
| 8eaf742b, 550ac015, c7d1555e, 75df7663, 057ae92c, 377070ab, f06ec5d9 | 10-20 | #6742 email export fix series | email_routes, emailLibrary | |
| 8877273e | 10-20 | merge PR #6742 | (merge = branch tip) | |

\* b2613b21 is dated 09-23 but landed via #6396 on 10-20 (PR backport) — it is the one that
re-touched `static/js/chat.js`/`index.html`/`01-agent-chat.css` after the fork's heavy use of them.

### A.2 Authority-model cheat-sheet (NEW base, all line refs verified at 2ca1e255)

| Piece | Location |
|---|---|
| `CONTRACT_CORE_TOOLS` (recovery surface) | `src/turn_contract.py:48`; consumed at `src/agent_loop.py:23641` |
| `TurnContract` — **frozen** dataclass (offered ⊆ executable invariant) | `src/turn_contract.py:6278` |
| `OperationGrant` | `src/agent_runtime/authority.py:82` |
| `RequestAuthority` (seals: resource_roots :148, launch_scopes :168) | `src/agent_runtime/authority.py:110` |
| `restrict()` — applies ToolPolicy disabled set | `src/agent_runtime/authority.py:215` |
| `SemanticIntent` | `src/agent_runtime/authority.py:323` |
| `interpret_request(text, history, workspace, active_document, image_attachment) → SemanticIntent` | `src/agent_runtime/authority.py:330` (return :361) |
| `create_request_authority(…, client_runtime_context=…)` | `src/agent_runtime/authority.py:364` |
| **the grant floor loop** `for name in sorted(tools \| {"ask_user","update_plan"})` | `src/agent_runtime/authority.py:387` |
| route stamp `client_runtime_context["web_ui_state"] = …` | `routes/chat_routes.py:3550` |
| route `allow_bash` read / forced-on | `routes/chat_routes.py:2503` / `:2671` |
| route `_forced_tools` force-include block | `routes/chat_routes.py:4574–4578` |
| `LAUNCH_TOOLS = {bash, python}` / `seal_launch_scope` | `src/agent_runtime/process_resources.py:28` / `:54` |
| afecd44d approval-time seal | `src/tool_approvals.py` `ToolApprovalStore.create()` (~:415) |

Flow: chat request → route builds `client_runtime_context["web_ui_state"]` from server-side
effective policy (`chat_routes.py:3550`) → `create_request_authority` (:364) calls
`interpret_request` (:330) → `SemanticIntent{capabilities, selected_tools, required_read}` →
`tools = FAMILY_TOOLS[family] ∩ selected` narrowed by required-read op (:364–386) → grants loop
(:387) builds one `OperationGrant` (:82) per tool → `RequestAuthority` (:110) seals roots/launch
scopes → `restrict()` (:215) removes policy-disabled tools → `tool_execution.py` checks the grant
per call. **`src/agent_runtime/authority.py` has ZERO upstream commits since the merge-base**
(`git log a8c147b2..upstream/dev -- src/agent_runtime/authority.py` → empty) — our hooks land on
file-identical ground; `src/turn_contract.py` is likewise untouched by both sides since MB.

### A.3 The two security commits that matter to us

- **afecd44d** (NOT `should_force()` — that function does not exist; see Corrections): in
  `ToolApprovalStore.create()`, when the authority is *not* inherited and the op is a
  `LAUNCH_TOOL` (bash/python) with no launch scope yet, seal one in the request's single workspace
  root at approval time — so "approve once" for an *ungranted* bash/python now executes.
  Interaction with our per-group grants: a **ticked** group already has a grant ⇒ launch scope
  exists ⇒ afecd44d's seal path is skipped (its guard requires `not any(s.backend == backend …)`);
  an **unticked** group's bash/python is ungranted ⇒ afecd44d now makes approve-once work for it.
  Scaffold touches `src/tool_approvals.py` **nowhere** — no textual conflict; only semantic
  interaction (test matrix in §C.2).
- **6fceb6cc**: fail-closed `serve_generated_image` (app.py ~:516–590) + `_odysseus_owner`
  sanitization/ownership threading in `tool_execution.py` MCP path + image MCP server.
  Scaffold's only `app.py` delta is the voice-route registration (disjoint region); Scaffold's only
  `tool_execution.py` delta is the strict-mode MCP backstop at `execute_tool_block`
  (a new `if … disable_mcp …` block after the resource_identity_denied return) — disjoint from
  6fceb6cc's `_parse_qualified_mcp_args`/`_build_mcp_args`/`_call_mcp_tool` hunks. No textual conflict.

---

## B — Feature-by-feature port table (Scaffold groups A–P, 173 commits)

Verdicts (computed per-commit against the 25 overlap files, then hand-classified):
**CLEAN 55 · RE-VERIFY 61 · ADAPT 52 · ABANDON 5 · ALREADY-IN-UPSTREAM 0** (Σ=173; per-commit rule: RE-VERIFY iff the commit touches ≥1 of the 25 overlap files).

- **CLEAN** = every file the commit touches is untouched by upstream since MB → cherry-pick as-is.
- **RE-VERIFY** = commit touches ≥1 file upstream also changed → cherry-pick, then resolve the
  specific hunk region and re-run the group's tests.
- **ADAPT** = commit's intent must be re-applied by hand (superseded base file / merge conflict /
  re-aim at new structure). **ABANDON** = superseded within Scaffold itself (revert/re-land pairs,
  net-zero diagnostic). **ALREADY-IN-UPSTREAM** = none found (checked: zero scaffold commits share
  an upstream subject; the one backport, `53542b72`/PR #4661, is verified *absent* from
  `upstream/dev` chat.js — 0 hits of `_purgeStaleBackgroundStreams` at MB, upstream/dev, HEAD).

Test runner everywhere: `cd /home/samy/odysseus-dev && /home/samy/odysseus/venv/bin/python -m pytest -p no:cacheprovider <files>`.

| Grp | Feature (commits) | n | Verdict | Target files on new base | Evidence (what the diff showed) | Verification |
|---|---|---|---|---|---|---|
| A | Deploy/tooling: `a95a6346 5d94c187 3a8c3237 ad262c33 50a5682b dd1528ad 393d7efa 5b485ae3` (update.sh lineage) + `c0a83ca4` setup.sh, `3e954dda`, `5c750fae` | 11 | **ADAPT** (8 — update.sh lineage; base file already on new base) / CLEAN (3) | `update.sh` **already exists on the new base** (added by ImprovementsDev commit `2ca1e255`, 133 lines, `BRANCH="ImprovementsDev"`) — merge the fork's diffs into it, don't cherry-pick | `git diff HEAD Scaffold -- update.sh` = only BRANCH name + `git clean -nd` confirm block + `$REMOTE_NAME`; base file has no boot.sh/setup.sh | manual: `bash -n update.sh`; dry-run in worktree (no deploy) |
| B | Tool policy & model registry: `5c74b7d2` low-signal gate, `da7c4118` deepseek-v4, `8dae790c` Kimi, `258e6fd0` bash ALWAYS_AVAILABLE, `eb861007` force-include bash, `53542b72` rAF OOM backport, `b60856e9` Qwen3.5 vision | 7 | RE-VERIFY (4: `5c74b7d2` agent_loop, `eb861007` chat_routes, `53542b72` chat.js, `b60856e9` settings.js) / CLEAN (3) | `src/agent_loop.py` (5c74b7d2), `src/model_context.py`, `src/tool_index.py`, `routes/chat_routes.py` (eb861007), `static/js/chat.js,document.js` (53542b72), `static/js/settings.js` (b60856e9) | each diff is a self-contained addition (family lists, ALWAYS_AVAILABLE entry, `_forced_tools`-style block, rAF throttle) | `tests/test_foreground_model_routing.py` (beb7296a, grp G) + `tests/test_request_authority.py` sanity |
| C | Auto-scroll #5611: `5ff068b0` `09442f1a` `676da1da` | 3 | RE-VERIFY (1: 5ff068b0 chat.js) / CLEAN (2) | `static/js/chat.js`, `static/js/ui.js` | 3-part fix series (DOM-insert ordering, restart smooth-scroll, threshold 200→20) | client: `tests/helpers/check_client_js.mjs` (landed w/ voice, grp J) — or manual browser check |
| D | Cookbook/hwfit: `bba6bb0d` `790eb144` `24bdd54b` `de8f430d` | 4 | CLEAN (0 overlap files) | `static/js/cookbook*.js`, `services/hwfit/hf_discovery.py`, `website/setup.md` | self-contained UI/hwfit additions | manual: cookbook serve panel |
| E | Vision: `dae9706e` `779aee5d` `cf81047f` `5306a8f3` | 4 | RE-VERIFY (1: `cf81047f` — auth_routes.py + settings.py) / CLEAN (3; `src/llm_core.py` & `document_processor.py` untouched by upstream since MB) | `src/document_processor.py`, `src/llm_core.py`, `routes/auth_routes.py`, `src/settings.py`, `static/js/settings.js` | timeout/caps config plumbing; `cf81047f` overlaps 353ea007 (auth_routes) + 0e2c0830 (settings.py) regions — resolve by hunk | `tests/test_vision_owner_scope.py`, `tests/test_lmstudio_vision.py` |
| F | Docs home & instance map: `3f5d5e9d d745a7e1 e3e4bd95 a583af3e 1308f135 78848ee1 7c0db5ef 1a316f87 2562751c 92b07194` | 10 | RE-VERIFY (2: `1a316f87`,`2562751c` touch specs/ touched by bead6a67) / CLEAN (8) | `docs/instance-map.md`, `website/setup.md`, `specs/*`, `.gitignore` | docs only; `2562751c` consolidates specs/ home — must keep upstream's bead6a67 content | n/a (docs) |
| G | Chat core: `f48d9660` KV #4317, `74bb6624` Documents toggle, `00586fe7` docs, `1a8d3c7b` ticked-bash web-strip, `33203f56`+`8ab7c993` resume, `21fa94cf` upload reason, `1a316f87`→F, `30b648ba` dbId stamp, `496fccef` docs, `1c214181` delete whole turn, `ba1ad45c` reasoning reload, `beb7296a` hermetic routing test, `8c2e5bec` tab-recovery, `bbaf66be` tab-recovery probe | 14 | RE-VERIFY (12 — all but `ba1ad45c`, `beb7296a`; chat.js/index.html/chat_routes/specs all overlap w/ 8feb50e8, b2613b21, bead6a67) | `routes/chat_routes.py`, `routes/chat_helpers.py`, `routes/history/history_routes.py`, `static/js/chat.js,fileHandler.js,chatRenderer.js,markdown.js`, `static/index.html`, `static/app.js` | each diff self-contained; conflict risk is *region* (both sides edit chat.js send-path) not *content* | `tests/test_kv_prefix_layout_4317.py`, `tests/test_delete_message_whole_turn.py`, `tests/test_delete_message_db_id_stamp.py`, `tests/test_chat_route_tool_policy.py` |
| H | Documents toggle (see G — `74bb6624`,`00586fe7`,`1a8d3c7b` listed here in commit-map; ported with G) | — | (in G) | | | |
| I | Search: `d38f45cd` degraded-SearXNG, `b041c3b3` env doc, `c59837f5` FlareSolverr, `008db731`+`094098ff` tests, `1a21106c` spec | 6 | RE-VERIFY (2: `c59837f5` — the 3 docker-compose files were also changed by c3819e3c's ChromaDB volume mount; `1a21106c` — specs/search.md) / CLEAN (4) | `services/search/*`, `config/searxng/settings.yml`, `docker-compose*.yml` | `c59837f5` adds FlareSolverr service + engine config; c3819e3c changes volume mounts in same files → hand-merge compose | `tests/test_searxng_flaresolverr_engines.py`, `tests/test_no_private_data_tracked.py`, `tests/test_chromadb_volume_path.py` (upstream, must stay green) |
| J | Voice mode Phases 1–4 (27 commits: `817c18bd 08d311cb ac16a26a c9e116f1 3fe7a9d7 d70fb747 a6d4f181 bc0375f7 e74835b2 54efb57e ac29ed8b 700b4b2b 1b28ee0e 72a95ce9 2fa6c130 9ea3a9f1 15e5c2c7 07f91402 0254ad3d f8e0e679 5b774702 75d41fd4 4f43bfbc 659a1715 0b56ae9a 2c227891 6ad2e918`) | 27 | RE-VERIFY (18 — `app.py`,`src/settings.py`,`static/index.html`,`chat.js`,`auth_routes.py`,`specs/speech.md` all overlap) / CLEAN (9 — services/stt, services/vad, tts_routes, voice_routes, voiceMode.js, Makefile, scripts) | `app.py` (voice WS registration), `routes/voice_routes.py,voice_routes,stt_routes,tts_routes`, `services/stt,vad,tts`, `src/settings.py`, `static/js/chat.js,voiceMode.js,tts-ai.js,app.js,settings/speech.js`, `static/index.html`, `tests/helpers/check_client_js.mjs,check_pcm_processor.mjs`, `tests/fixtures/voice_mode_speech.wav` | net app.py diff = only the `setup_voice_routes` include (disjoint from 6fceb6cc's image endpoint); settings.py overlap is additive fields vs 0e2c0830's reasoning-effort fields | `tests/test_voice_mode.py`, `tests/test_tts_piper_provider.py`, `tests/helpers/check_client_js.mjs` |
| K | Strict chat mode (see Chunk 3): `4c966269 03f7eb93 670b4ca3 294ceaa4 d10ad733 6f267eb0 87ab6200` | 7 | RE-VERIFY (all 7: chat_routes, app.js, index.html, chat.js, agent_loop, 01-agent-chat.css) — **deferred to Chunk 3** | `routes/chat_routes.py` (`strict_chat_disabled_tools` import + branch guards), `routes/chat_helpers.py`, `src/tool_policy.py`, `src/agent_loop.py`, `src/tool_execution.py` (MCP-off backstop, new block in `execute_tool_block`), `static/app.js,index.html,chat.js,css/01-agent-chat.css` | `670b4ca3`'s tool_execution.py hunk is the only one that coexists with 6fceb6cc in the same file — verified disjoint regions (A.3) | `tests/test_strict_chat_mode.py`, `tests/test_exact_approval_ungranted_process.py` |
| L | SSE keepalive: `11ed6f13` `1928f283` | 2 | RE-VERIFY (chat_routes overlap w/ 8feb50e8) | `routes/chat_routes.py` | keepalive on main/agent streams; `1928f283` fixes cancel semantics | `tests/test_sse_keepalive.py` |
| M | DB hardening: `2c7d0e75` leak detector, `13f4e95c` WAL+busy_timeout | 2 | CLEAN | `core/database.py`, `core/db_leak.py` | upstream never touched core/database.py in the window | `tests/test_sqlite_wal_busy_timeout.py`, `tests/test_sqlite_leak_detector.py` |
| N | Empty assistant turns: `8526cc31` `95eb18bb` | 2 | RE-VERIFY (context_compactor.py overlap w/ 0e2c0830) | `core/models.py`, `src/context_compactor.py` | filter + Moonshot quirk | `tests/test_empty_assistant_context.py`, `tests/test_context_compactor.py` (upstream, must stay green) |
| O | NameError fixes: `98c86903` | 1 | CLEAN | `routes/cookbook_routes.py`, `src/caldav_writeback.py` | | `tests/test_caldav_writeback.py` |
| P1 | Post-rebase restore: `38c86045` (restore branch behavior on upstream rebuild), `d332e859` (re-aim test guards) | 2 | **ADAPT** — re-derive on the NEW base (both were aimed at the 2026-10-14 rebuild) | `core/models.py`, `services/search/core.py`, `src/agent_loop.py`, `static/index.html,chat.js`, `tests/test_sse_keepalive.py`, `tests/test_strict_chat_mode.py` | diff = re-applying fork behavior after the *previous* rebase; same job, new base | full focused suite of Chunk 1+3 |
| P2 | Authority cluster (see Chunk 2): `dd900647 01cece53 383c6ca7 f4c4681c 175073ca ae57e6be 7d028f48 83185b20 51a5ab5d` + tick-wins series `d4925ca4 2236c70e 95422d48 d76fe821 ce6aeb2f 2908e02c 2e3ba498 abd2713a 934b8366 8184bebf 1fe20ffc` + memory floor `813c982d` | 23 (18 ported + 5 ABANDON) | mixed — see §C; ADAPT: `ae57e6be` (route cluster) + `1fe20ffc` (guard re-aim); ABANDON: `2236c70e 95422d48 2908e02c` (net-zero diagnostic + its reverts pair `d259efc3`/`ca3fda9e` = 5 total) | `src/agent_runtime/authority.py`, `routes/chat_routes.py`, `static/app.js,index.html,chat.js`, `tests/test_request_authority.py,test_chat_route_tool_policy.py,test_tool_groups_contract_guard.py` | net authority.py diff = +72/−1 lines: BUTTON_TOOLS map + 3 gated blocks (C) | §C.2 matrix + existing authority/approval suites |
| P3 | Completion streaming: `f738b263 15542d9f 9164b030` + docs `1879e7de c906e3b0 b3b3abe3 821c55fd` | 7 | CLEAN (completion.py untouched by upstream) — Chunk 3 | `src/agent_runtime/completion.py`, `scripts/generate_env_reference.py` | `ODYSSEUS_LIVE_ANSWER_STREAM`, gate bypass, boundary fix | `tests/test_completion_boundary.py` |
| P4 | Docs machinery: commit-map + ROADMAP backfills (37) + tool-groups design docs (3): `36359ef8 605db810 3ba8e964 59015d37 f77a0359 6dc12dd0 f4a4fe6c 3ed86515 e61a4e5c 52cf20cd 14161169 f0ba4128 48e9e805 6318fba0 bda6c65c 441e7860 7ff72f50 ffa69928 a360fd71 60a120a0 af8c542c be4573cd 6d255cf2 33de6e61 219f0932 fdd7cb4c 65931be8 b5a1e70d d75553e1 ff5e090f 915ab5d4 c87bdfb9 16b20795 1d7a89a5 9fdc88a5 b496cb6a 142cef50` + `a15d8ab9 c11e7d12 ca25a35c` | 40 | **ADAPT (as a group)** — do NOT cherry-pick the 37 backfill commits; port the final state of `specs/ROADMAP.md` + `specs/commit-map.md` (the 3 design docs land with Chunk 2) (`git show Scaffold:specs/…`) and **regenerate the map with new post-port SHAs** (keep-current rule) | `specs/ROADMAP.md`, `specs/commit-map.md` | each backfill is a map/roadmap text edit; only final state matters | n/a (docs); map invariant: `ahead = entries + 1` |
| — | `9ac7ae2c` env-knob docs | 1 | CLEAN | `scripts/generate_env_reference.py`, `website/configuration-reference.md` | | n/a |

**ABANDON (5)** — superseded within Scaffold, never port: `2236c70e` (E2E diagnostic add),
`95422d48` (diagnostic hardening), `2908e02c` (Revert of ce6aeb2f), `d259efc3` (Revert of 7ff72f50),
`ca3fda9e` (Revert of 60a120a0). Their fixes were re-landed as `2e3ba498` (floor), `934b8366`+`8184bebf`
(contract boundary) — port the re-lands, skip the aborted rounds.

**ALREADY-IN-UPSTREAM (0)** — evidence: zero scaffold commits share a subject with the 44 upstream
commits (string comparison over both logs); the one true backport, `53542b72` (PR #4661 rAF OOM),
is verified absent from `upstream/dev` (`_purgeStaleBackgroundStreams` = 0 hits at MB, at upstream/dev,
and at HEAD; 4 hits at Scaffold).

---

## C — Gate design note: tool-groups + memory floor on the NEW authority.py

### C.1 What lands where (verified file-identical ground)

`git log a8c147b2..upstream/dev -- src/agent_runtime/authority.py` → **empty**. The new base's
`create_request_authority` is line-for-line the MB version; the 5 Scaffold authority commits
(`dd900647 01cece53 383c6ca7 175073ca 813c982d`) net to **+72/−1 lines** (full diff re-inspected):

1. `import os` + `CONTRACT_CORE_TOOLS` import (top of file).
2. **`BUTTON_TOOLS` map** after `interpret_request` (~:362): bash / sessions / web / media / browser
   → tool tuples (browser = canonical `private_browser`; MCP wire names resolved in the route floor).
3. In `create_request_authority`, after the `operation` block (:386) and before the grants loop:
   - **memory floor** (`813c982d` + `dd900647`): if `ODYSSEUS_CORE_TOOL_GRANTS` ∈ {1,true,yes}:
     unknown-intent turns get `tools |= CONTRACT_CORE_TOOLS`, and the floor set becomes
     `{"ask_user","update_plan","manage_memory"}` (replaces the `{"ask_user","update_plan"}` union in
     the :387 loop — the only `−1` line in the net diff).
   - **tool-groups grant** (`175073ca`): if `ODYSSEUS_TOOL_GROUPS` is set, each ON group in
     `client_runtime_context["web_ui_state"]` (stamped at `chat_routes.py:3550`) does
     `tools.update(BUTTON_TOOLS[g])`; `elif web_ui_state["bash"]` keeps the pre-feature bash-button
     grant byte-identical (plus `383c6ca7`'s file-tool extension when the gate is OFF).
4. **Route side** (`ae57e6be` cluster, ADAPT): `tool_groups` wire key (comma list) + `allow_bash` →
   `_tool_groups_on`; ticked groups' tools are **discarded from `disabled_tools`** (the floor) at the
   `_forced_tools` block (`chat_routes.py:4574`) and again at final consumption; the
   `web_ui_state` stamp (:3550) gains the per-group keys.
5. **Frozen-contract fix** (`934b8366`+`8184bebf`): the turn contract's FROZEN offered set is built
   before the route floor, so ticked tools would be silently under-granted — fixed by rewriting
   `TurnContract` via `object.__setattr__` (legal: frozen dataclass, `turn_contract.py:6278`,
   identical at MB/HEAD/Scaffold — the `934b8366` incident pattern ports as-is).

### C.2 afecd44d approve-once × per-group grant — dedicated test matrix

New file `tests/test_tool_groups_approve_once_matrix.py` (style mirrors
`tests/test_tool_groups_contract_guard.py`: source-pins on the real frozen class + real
`ToolApprovalStore`), run with the venv above. Existing upstream tests that must stay green:
`tests/test_exact_approval_ungranted_process.py`, `tests/test_skill_test_stream_closed.py`,
`tests/test_tool_approvals.py`.

| # | Gate | Group state | Request | Expected (why) |
|---|---|---|---|---|
| 1 | OFF | bash button ON | bash | granted at authority (`tools.add("bash")`), launch scope sealed at request time ⇒ afecd44d path skipped (`launch_scopes` non-empty) — pre-feature behavior, approve-once works as before |
| 2 | ON | bash group ticked | bash | grant via `BUTTON_TOOLS["bash"]`; route floor removes bash from `disabled_tools` ⇒ same as #1 (regression pin: floor + grant agree) |
| 3 | ON | **no** group ticked | bash | bash ungranted → approval asked → afecd44d seals workspace-root launch scope at approval (single-root workspace) → approve-once **succeeds and is confined to the sealed root** |
| 4 | ON | none ticked | python | same as #3 (python ∈ `LAUNCH_TOOLS`) |
| 5 | ON | none ticked, **inherited** authority | bash | afecd44d guard `not request_authority.inherited` ⇒ **no** seal ⇒ executor refuses ("no sealed process identity") — inherited authorities still cannot widen (upstream invariant preserved) |
| 6 | ON | none ticked, multi-root workspace | bash | afecd44d guard `len(roots) == 1` fails ⇒ no seal ⇒ refuse (upstream behavior; document in spec) |
| 7 | ON | sessions ticked, bash not | bash | ticked *other* groups must not leak a bash grant (map is per-group; no cross-group union) |
| 8 | ON | bash ticked + `ODYSSEUS_CORE_TOOL_GRANTS=1`, unknown intent | manage_memory | both floors compose: manage_memory from `_core_floor` + bash group from BUTTON_TOOLS, no double-grant conflict |

Source-pins to add (guard style): count of `os.environ.get("ODYSSEUS_TOOL_GROUPS"` in
`routes/chat_routes.py` (Scaffold pins `== 5`), presence of the afecd44d seal block in
`src/tool_approvals.py` (`seal_launch_scope` import inside `create()`), and the
`object.__setattr__` TurnContract rewrite in `routes/chat_routes.py`.

---

## D — Execution order (chunks)

Every chunk ends: **(1)** focused tests in this worktree with
`/home/samy/odysseus/venv/bin/python -m pytest -p no:cacheprovider …`; **(2)** user deploys
`~/odysseus/deploy.sh` → `ImprovementsDev` (snapshots `data/` → `data.snapshots/`, detaches this
worktree, runs the branch's `update.sh`, restarts the service); **(3)** live smoke: one chat turn
per affected surface. Chunk commit order = Scaffold order (oldest→newest) within each chunk.

### Chunk 1 — clean mechanical groups (no authority/route-interaction): 94 commits
A(11 — 8 ADAPT update.sh lineage + 3 CLEAN), B(7), C(3), D(4), E(4), F(10; `1a316f87` shared with G), G(14), I(6), J(27), L(2), M(2), N(2), O(1), `9ac7ae2c` (1).
- Commit list (oldest→newest): `5ff068b0 5c74b7d2 da7c4118 8dae790c 258e6fd0 eb861007 53542b72 c0a83ca4 a95a6346 5d94c187 3a8c3237 ad262c33 5c750fae 50a5682b 09442f1a 676da1da 3e954dda dd1528ad 3f5d5e9d b60856e9 d745a7e1 e3e4bd95 bba6bb0d 790eb144 24bdd54b de8f430d dae9706e 779aee5d cf81047f 5306a8f3 8c2e5bec beb7296a ba1ad45c a583af3e 1308f135 78848ee1 7c0db5ef b041c3b3 d38f45cd f48d9660 74bb6624 00586fe7 1a8d3c7b 33203f56 8ab7c993 21fa94cf 1a316f87 393d7efa 30b648ba 496fccef 1c214181 2562751c 92b07194 817c18bd 08d311cb ac16a26a c9e116f1 3fe7a9d7 d70fb747 a6d4f181 bc0375f7 e74835b2 54efb57e ac29ed8b 700b4b2b 1b28ee0e 72a95ce9 2fa6c130 9ea3a9f1 15e5c2c7 07f91402 0254ad3d f8e0e679 5b774702 75d41fd4 4f43bfbc c59837f5 008db731 1a21106c 094098ff 659a1715 0b56ae9a 2c227891 6ad2e918 13f4e95c bbaf66be 2c7d0e75 98c86903 11ed6f13 1928f283 8526cc31 95eb18bb 9ac7ae2c 5b485ae3` (94)
- Note: the 5 "tick-wins" SHAs named in the original chunk-1 list belong to the tool-groups
  cluster (same `chat_routes.py` region, same feature) — they are in **Chunk 2**, not Chunk 1.
  "yaml allow_unicode" is **not in the delta at all** (verified absent at MB, upstream/dev, Scaffold)
  — nothing to port.
- Focused tests: `tests/test_kv_prefix_layout_4317.py tests/test_delete_message_whole_turn.py tests/test_delete_message_db_id_stamp.py tests/test_foreground_model_routing.py tests/test_searxng_flaresolverr_engines.py tests/test_no_private_data_tracked.py tests/test_voice_mode.py tests/test_tts_piper_provider.py tests/test_sse_keepalive.py tests/test_sqlite_wal_busy_timeout.py tests/test_sqlite_leak_detector.py tests/test_empty_assistant_context.py tests/test_caldav_writeback.py tests/test_vision_owner_scope.py tests/test_lmstudio_vision.py` + upstream invariants `tests/test_chromadb_volume_path.py tests/test_context_compactor.py tests/test_history_truncate_validation.py tests/test_admin_routes_auth_disabled.py`
- Smoke: one turn each — chat send/scroll, search query, voice dictation round-trip, tab recovery (F5 mid-stream), upload rejection, KV-prefill turn.

### Chunk 2 — tool-groups + memory floor cluster (with §C.2 matrix): 61 commits (56 ported + 5 ABANDON)
(ported: 18 authority-cluster + 3 design docs + 35 P4 backfills; the 5 ABANDON skipped below are listed for traceability)
Design docs `a15d8ab9 c11e7d12 ca25a35c`; authority `dd900647 01cece53 383c6ca7 175073ca 813c982d`;
route `ae57e6be` + tick-wins `d4925ca4 d76fe821 ce6aeb2f 2e3ba498 abd2713a 934b8366 8184bebf 1fe20ffc`
(skip ABANDON `2236c70e 95422d48 2908e02c d259efc3 ca3fda9e`); UI `7d028f48`; tests `83185b20`;
hermetic-env `51a5ab5d`; thinking bypass `f4c4681c`; all P4 docs backfills for this cluster
(`52cf20cd 14161169 f0ba4128 48e9e805 6318fba0 bda6c65c 441e7860 7ff72f50 ffa69928 a360fd71 60a120a0 af8c542c be4573cd 6d255cf2 33de6e61 219f0932 fdd7cb4c 65931be8 b5a1e70d d75553e1 ff5e090f 915ab5d4 c87bdfb9 16b20795 1d7a89a5` + `605db810 3ba8e964 59015d37 f77a0359 6dc12dd0 f4a4fe6c 3ed86515 e61a4e5c 9fdc88a5 b496cb6a`).
- Apply `ae57e6be`+tick-wins as **one ADAPTED commit** (their 8 commits interleave in the same
  `chat_routes.py` region; net effect = stamp + floor + `_forced_tools` inclusion + frozen-contract
  rewrite, verified in the net diff) + the §C.2 matrix file.
- Focused tests: `tests/test_request_authority.py tests/test_tool_approvals.py tests/test_tool_groups_contract_guard.py tests/test_tool_groups_approve_once_matrix.py tests/test_chat_route_tool_policy.py tests/test_exact_approval_ungranted_process.py tests/test_skill_test_stream_closed.py tests/test_turn_contract.py tests/test_completion_boundary.py`
- Smoke: with `ODYSSEUS_TOOL_GROUPS=1` and `ODYSSEUS_CORE_TOOL_GRANTS=1` in `.env`: tick web → ask
  for a search (works, no approval); untick all → ask for bash (approval appears, approve-once
  succeeds per matrix row 3); unknown-intent turn → `manage_memory` callable.

### Chunk 3 — remainder + regen docs: 18 commits
(K 7 strict + P1 2 + P3 7 completion + 2 P4 backfills folded into the regen)
Strict chat cluster `4c966269 03f7eb93 670b4ca3 294ceaa4 d10ad733 6f267eb0 87ab6200`;
`d332e859` (re-aimed at the new base's stream paths); `38c86045` (ADAPT — re-derive branch-specific
restores for the NEW base, not a cherry-pick); completion `f738b263 15542d9f 9164b030` (+docs
`1879e7de c906e3b0 b3b3abe3 821c55fd`); **regenerate** `specs/ROADMAP.md` + `specs/commit-map.md`
with the new post-port SHAs (final state from Scaffold as template; map invariant
`ahead = entries + 1`); P4 tail backfills (`36359ef8`, `142cef50`) folded into the regen — port final state, do not cherry-pick.
- Focused tests: `tests/test_strict_chat_mode.py tests/test_completion_boundary.py tests/test_exact_approval_ungranted_process.py` + re-run Chunk 1+2 focused sets (regression net).
- Smoke: strict session sends (phone + web), one agent turn with MCP tools (backstop must not false-block), completion streaming on/off via `ODYSSEUS_LIVE_ANSWER_STREAM`.

---

## E — Rollback ladder & go/no-go

Ladder (each rung is one `deploy.sh` invocation, never a manual service touch):

1. **Chunk N NO-GO (tests or smoke fail, service still on ImprovementsDev@chunk-N):**
   `git -C ~/odysseus-dev reset --hard <chunk-start SHA>` (worktree only) → redeploy same branch,
   or step to 2.
2. **Revert to production baseline:** `cd ~/odysseus && ./deploy.sh` → `Improvements`
   (→ `improvements-20261012` @ `207df1c0`). Deploy snapshots `data/` to `data.snapshots/` on every
   switch; verify the PID changed and one chat turn works.
3. **Data recovery:** restore from the newest `~/odysseus/data.snapshots/` entry if a chunk
   corrupted state (DB hardening in Chunk 1 makes this unlikely; WAL + busy_timeout land early).

Per-chunk go/no-go: **NO-GO** if (a) any focused test fails, or (b) the live smoke test
(one chat turn per affected surface) misbehaves, or (c) any upstream invariant test regressed
(`test_chromadb_volume_path`, `test_exact_approval_ungranted_process`, `test_context_compactor`,
`test_history_truncate_validation`, `test_admin_routes_auth_disabled`). **GO** = all three pass →
next chunk, or for Chunk 3: hold ImprovementsDev for days before touching production.

---

## Corrections to the pre-verified context (all re-checked against diffs, 2026-10-21)

1. "~14 of 44 upstream commits touch Scaffold-overlap files" → **11 of 44** (`8feb50e8 0e2c0830 b5b76fe4 86b886c6 c23b1be3 353ea007 6fceb6cc c3819e3c f1a47f38 bead6a67 b2613b21`).
2. "afecd44d widened `should_force()`" → **`should_force()` does not exist** (grep: 0 hits at HEAD and Scaffold). afecd44d seals a launch scope for ungranted `LAUNCH_TOOLS` at approval time in `ToolApprovalStore.create()` — interaction with our per-group grants is the one in §C.2.
3. `ea0bd3e6`, `ef2e6faf`, `1c9d1671` → **not in the repo**. The tool-groups slice is `175073ca` (authority) / `ae57e6be` (route) / `7d028f48` (UI) / `83185b20` (tests).
4. "yaml allow_unicode" misc fix → **not in the 173 delta** (0 hits at MB, upstream/dev, Scaffold, and no matching commit subject).
5. Confirmed correct: `authority.py` zero upstream changes since MB; `Scaffold=1d7a89a5`; prod ref `207df1c0`; 44/173 counts; MB `a8c147b2` (2026-10-07); `813c982d` memory floor; `6fceb6cc` fail-closed images.
6. New finding: the new base **already carries the fork's `update.sh`** (commit `2ca1e255`) — group A is a merge, not a cherry-pick (see §B row A).

## F — Dual-version deploy state (live-verified 2026-10-21)

| Item | Value |
|---|---|
| PROD worktree | `/home/samy/odysseus` — detached @ `improvements-20261012` = `207df1c0`; service `odysseus` active, PID 3165292 (started Tue 2026-10-20 15:51:17 EDT); venv, `.env`, `data/`, `logs/` all live here |
| DEV worktree | `/home/samy/odysseus-dev` — `ImprovementsDev` @ `80c2d98a` (this guide); no venv of its own — run its tests with `/home/samy/odysseus/venv/bin/python`; no service runs from it |
| Port source | `improvements-20261014` = `Scaffold` @ `1d7a89a5` — FROZEN; its `specs/commit-map.md` (173 commits, A–P) + `specs/ROADMAP.md` (through the 10-20 revert) = historical record; no new work lands there |
| Switcher | `/home/samy/odysseus/deploy.sh [dev\|Improvements\|ImprovementsDev]` (gitignored, in the prod worktree, survives checkouts): snapshots `data/` → `data.snapshots/`, detaches the prod worktree to the target, runs the target branch's `update.sh`, restarts the service |
| `Improvements` alias | = `207df1c0` (deliberate, at 2012) — do NOT re-alias without the user |
| Snapshots | `data.snapshots/` not yet created — created on the first `deploy.sh` switch |

Chunk go/no-go (§E) is evaluated on ImprovementsDev in the dev worktree; the user deploys with `deploy.sh ImprovementsDev` only after a chunk's focused tests are green and the live smoke test passes. Prod stays on 2012 until §E's stability bar (days, not hours) is met.
