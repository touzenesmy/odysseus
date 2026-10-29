# Odysseus fork — roadmap & work tracker

> **Canonical "what's pending / what's the state" document for this project.**
> Read this FIRST when picking up work ("let's continue working on odysseus",
> "check our task list", "what's pending?"). If the file is not in the working
> tree (service running on an older branch), read it with:
> `git show improvements-<YYYYMMDD>:specs/ROADMAP.md`
>
> Rules of this document:
> - Volatile state (SHAs, PIDs, what's running) lives HERE, not in memory —
>   memory and skills only *point* here.
> - Update the **Status** line and tick **Backlog** items whenever state
>   changes, then commit + push (keep-current rule, same as the commit map).
> - Conventions (dated branches, commit map, PR flow) live in the fork skill
>   (`user-odysseus-fork`) and in the files themselves — don't duplicate them
>   here; link.

## Status (2026-10-28, ~20:15 EDT) — #8, #9 AND #10 FIXED, DEPLOYED, SMOKE-VERIFIED BY USER (pushed + service restarted 2026-10-28; user confirmed the #10 streaming fix works; #8/#9 re-verified via the focused nets). All three live on the service from `ImprovementsDev`; hold period running. (dev-only commits in `commit-map.md`; backlog entries updated). #10 root cause: the loop's terminal `final_response` carries `full_response` (every round's prose, never reset per round) and the client treats it as a whole-bubble replacement of the LAST round's bubble, so the final bubble renders as one solid block — the `ODYSSEUS_COMPLETION_GATE=0` bypass rewrite fixed the tool-output wall but accumulated prose across the whole turn; fix scopes the rewrite to the final round via the loop's `agent_step` round-boundary frames (plus structured-snapshot pass-through + fresh-scope reset). Focused net green (60 completion-boundary incl. 2 new regression tests; 195 across completion/evidence surface). #8 extended to the calendar preemptive tail (`94edfa88`, same leak, second branch); #9 execution-side opt-in aligned to `ODYSSEUS_EXPOSE_RAW_BROWSER_MCP` (`9f20f505`), env-reference regenerated. **2026-10-28 ~21:15 EDT: Backlog #11 LOGGED** (deleted user messages still reach the live session's agent context — DB/UI deletion verified working, so the leak is the in-memory transcript / retrieval sync, not the delete route; diagnosis plan in the entry). **2026-10-28 ~22:25 EDT: Backlog #12 LOGGED** (final answer routed to the thinking/reasoning field — the 20:11 EDT audit turn ran 8 rounds / 23.2K output tokens but the persisted reply is 208 chars and the full report sits in the turn's thinking field; model-side behavior + no server-side empty-final-round detection; diagnosis plan in the entry). **2026-10-29 ~10:30 EDT: Backlog #11 CLOSED as MISDIAGNOSED** (audit-turn context was clean — the cited `latest=` line was the deleted message's own trigger turn; the text resurfaced because the agent read app.log, which retains full user-message text; the stamped-delete path is verified working by a committed repro test; residual latent edge — unstamped in-memory messages — documented in the entry).
- #8 (preemptive-denial leak) + #9 (Browser button grants Playwright MCP, not the metadata-only wrapper) fixed (2026-10-24) and committed — SHAs in commit-map.md; focused net re-run green (1,309 incl. the 13 new regression tests). COMPLETE (2026-10-25): #8 extended to the calendar preemptive tail (`94edfa88`), #9 execution-side env aligned + env-reference regenerated (`9f20f505`); focused nets re-run green (backlog #8/#9 files + calendar cluster + browser guard files, pre-existing [calendar] sweep pollution excluded and A/B-verified against the clean tree).
- #10 logged from the user's observation 2026-10-24 ~02:25 EDT: the last assistant chat bubble of a long agent turn arrived as one solid block instead of streaming ("supposedly should be fixed" — the transcript-wall cluster `cda4db89`/`c5914a15`/`f27ca5c6` with `ODYSSEUS_COMPLETION_GATE=0` already in `.env`).
- #8/#9 pushed + service restarted 2026-10-25 (user), then #10 fixed 2026-10-26 on `ImprovementsDev` (this worktree; dev worktree detached at the pre-#8/#9 baseline `a85f09b0`). Focused nets green (1,309 at #8/#9; 195 completion/evidence surface at #10). Smoke + hold: user confirmed 2026-10-28 that #10 works post-restart — smoke passed; hold period running (branch becomes prod at the next rebase if stable).

### Status (2026-10-23, ~14:50 EDT) — SUPERSEDED (history) — CHUNK 3 COMPLETE on ImprovementsDev @ `d722639f` (12 commits; full focused net 1609 green; awaiting smoke + hold period)
- **Chunk 3 (PORT-GUIDE §D) landed — all 18 planned commits resolved (12 land, 6 folded):** strict cluster K (7 Scaffold: `4c966269 03f7eb93 670b4ca3 294ceaa4 d10ad733 6f267eb0 87ab6200` → `12ca5a64 56b3768f 5b57419d 8081a7d7 6de51be2 b0779827` + one **empty pick** — `6f267eb0` was a Scaffold buster-parity fix already satisfied on the new base); P1 ADAPT (2: `d332e859`→`84ccb03e`, `38c86045`→`6a01e352` re-derived on the new base: models.py empty-turn keep, search `_call_provider` seam, agent_loop `route_tools is None` guard, 23-file buster parity → `20261023parity1` [21 css + app.js + chat.js; admin.js content-unchanged so its precache buster stays], dead `_abortFrozenLocalStream` + 2× 300px blocks dropped, test re-aims); P3 completion (3 code: `f738b263 15542d9f 9164b030` → `cda4db89 c5914a15 f27ca5c6`; 4 docs backfills `1879e7de c906e3b0 b3b3abe3 821c55fd` folded into this regen per plan); dev-only `d722639f` (hermetic scrub of `ODYSSEUS_COMPLETION_GATE` in test_agent_runtime_context — host env leaked the fork flag into upstream-pinned disclosure assertions, same class as bd3947cd).
- **Adaptation notes (P1, commit `6a01e352`):** Scaffold's 38c86045 buster `20261010strictagent2` superseded by the 23-file parity set at today's date; `website/configuration-reference.md` env-count conflict resolved to 91 (the gate-bypass adds one `os.getenv` read); `app.js` chat.js import key bumped alongside (import buster must track content buster — the strict cluster had left them split on the new base).
- **Gate state (§D/§E):** full focused net **1609 passed** (chunk 1 15 + chunk 2 8 + chunk 3 3 + 4 P1-reaimed + 4 upstream invariants + dev-only routing/context files). GO per §E go/no-go: focused green ✓, invariants green ✓; smoke is the remaining rung.
- **NEXT (user):** (1) Deploy + smoke per §D — `cd /home/samy/odysseus && ./deploy.sh ImprovementsDev`: strict session sends (phone + web), one agent turn with MCP tools (MCP-off backstop must not false-block), completion streaming on/off via `ODYSSEUS_LIVE_ANSWER_STREAM` / `ODYSSEUS_COMPLETION_GATE`. (2) **HOLD ImprovementsDev for days before production** (§E chunk-3 rule) — prod stays on `improvements-20261012` @ `207df1c0`.

### Status (2026-10-22, ~22:00 EDT) — SUPERSEDED by the chunk-3-complete status above (history) — CHUNKS 1+2 SMOKE-TESTED + 2 POST-SMOKE FIXES on ImprovementsDev @ `ae12d8f7` (full focused gate 1501 green; redeploy pending)
- **Smoke results (deployed 20:15 EDT, tested both chunks):** authority gate works (bash approve-once observed in-session ✓; manage_memory floor ✓); **search returned 0 rows** on "latest PHP vulnerability" → root cause: SearXNG time_range-agnostic engines silently return zero rows on time-filtered news queries → fix `add86ba3` (drop time_range before reporting empty; verified: 28 rows after, 0 before); **mic first-click-dead** → root cause: Chrome suspends AudioContexts created after the permission dialog → fix `4532de56` (resume inside the gesture path, 1.5 s race, gated on `running`) + buster `ae12d8f7`.
- **Upstream moved (detected 22:15 EDT):** `upstream/dev` was REWRITTEN (force-pushed) — old base `f786bcdf` is no longer an ancestor (fork-doc commits orphaned, harmless). 7 new upstream commits now behind, incl. an **incident-CA/TLS security series** (distrust incident CEs in Chromium/gRPC, refresh outbound HTTPS trust) + CI fix `01566b15`. `update.sh` does NOT rebase (checkout -B from remote only) → **deploy of this branch is safe as-is**; the 7 fold in at the next rebase (backlog #4 fold-upstream window).
- **Prod `.env`** already carries the fork search pins (`SEARXNG_GENERAL_ENGINES=ddgfs,bravefs,bingfs`) — inert on 2012, live on this branch.
- **Redeploy for the fixes:** `cd /home/samy/odysseus && ./deploy.sh ImprovementsDev`, then retest: (a) "Search the web for the latest PHP vulnerability" → results; (b) mic: fresh tab (hard reload), one click → listening immediately.

### Status (2026-10-22, ~13:10 EDT) — SUPERSEDED (history) — CHUNK 2 COMPLETE on ImprovementsDev @ `7b4ddb66` + `79b3d3f8` (17/17 ported + 5 ABANDON skipped + §C.2 matrix new; focused tests 1155 green)
- **Chunk 2 (PORT-GUIDE §D) landed** — authority cluster 5 + thinking-bypass 1 + hermetic-env 1 + route cluster 1 ADAPTED commit (9 Scaffold SHAs: `ae57e6be d4925ca4 d76fe821 ce6aeb2f 2e3ba498 abd2713a 934b8366 8184bebf 1fe20ffc` + static `7d028f48` + tests `83185b20`) + memory floor 1 + §C.2 matrix (new, no Scaffold origin). ABANDON per guide (5, net-zero diagnostic pair + reverts): `2236c70e 95422d48 2908e02c d259efc3 ca3fda9e` — never ported.
- **Adaptations (route cluster, commit `7b4ddb66`):** no `strict_chat`/`disable_mcp=` on the new base (Chunk-3 feature) — hunk A re-anchored to the plan_mode-disabled-tools region, final-consumption policy rebuild drops the `disable_mcp` kwarg; static lands at final state (self-healing stamp, no diagnostic remnants) with busters straight to `20261020tg2` over the css-split base; RE-VERIFY re-aim of the web-intent bash-guard source pin (new base's web block is multi-line `if (\n    _explicit_web_intent`).
- **§C.1 ground:** `authority.py` file-identical to Scaffold after `a07b64a2`/`42f9a83e` (verified by `git diff HEAD Scaffold` = 0 on the 4 authority files pre-cluster).
- **§C.2 matrix (`79b3d3f8`):** 10 rows — gate-OFF bash baseline / gate-ON bash-ticked byte-identical / afecd44d seal+approve-once (bash & python) / inherited no-widen / multi-root no-seal / no cross-group leak / floors compose. 10/10 green.
- **Gate state (§D/§E):** focused chunk-2 set **1155 passed** (9 files, venv pytest); chunk-1 focused set unchanged green.
- **NEXT (user):** deploy + smoke per guide — `cd /home/samy/odysseus && ./deploy.sh ImprovementsDev`; with `ODYSSEUS_TOOL_GROUPS=1` + `ODYSSEUS_CORE_TOOL_GRANTS=1` in `.env`: tick web → ask for a search (no approval); untick all → ask for bash (approval appears, approve-once works); unknown-intent turn → `manage_memory` callable. Then **Chunk 3** (strict cluster 7 + P1 2 + P3 completion 7 + final ROADMAP/commit-map regen).

### Status (2026-10-21, ~22:30 EDT) — SUPERSEDED by the chunk-2-complete status above (history) — CHUNK 1 COMPLETE on ImprovementsDev @ `f3b1aea2` (94/94 commits; focused tests green; awaiting deploy + smoke)
- **Chunk 1 (PORT-GUIDE §D) landed:** all 94 commits cherry-picked oldest→newest onto base `f786bcdf` (86 cherry-picks incl. 13 conflict resolutions, all RE-VERIFY class — no code behavior dropped, only header-line/param-merge/spec-body merges) + group A's 8 update.sh-lineage commits as one adapted merge commit `d2791f64` (boot.sh, setup.sh system-deps Step 0, update.sh `[d]` discard confirm; base keeps `BRANCH="ImprovementsDev"`).
- **Conflict resolutions (13):** `dae9706e`/`779aee5d` llm_core.py (upstream `reasoning_effort` + our `extra_body` additive merge, then the revert removed `extra_body` keeping `reasoning_effort`); docs header-line conflicts ×7 (upstream `bead6a67` consolidation wins the `Last updated` line; fork body preserved: agent-tools.md, context-building.md, chat.md ×4, speech.md ×5, search.md); `1c214181` chat.md whole-turn-delete paragraph merge; `0b56ae9a` blank-line; `bbaf66be` index.html (kept upstream css-split block + our `20260924tabrecovery1` buster ×2).
- **RE-VERIFY test re-aims (commit `f3b1aea2`, 3 files, behavior unchanged):** test_kv_prefix_layout_4317 fake signature; test_delete_message_db_id_stamp exec harness +real `strip_tui_local_context`; test_sse_keepalive guard → `_stream_agent_with_execution_bridge` call site (new-base agent loop).
- **Gate state (§D/§E):** focused fork set **252 passed** (15 files); upstream invariants **94 passed** (test_chromadb_volume_path [singular!], test_context_compactor, test_history_truncate_validation, test_admin_routes_auth_disabled). Branch pushed to touzenesmy/ImprovementsDev.
- **NEXT (user):** deploy + smoke — `cd /home/samy/odysseus && ./deploy.sh ImprovementsDev`, then one turn each: chat send/scroll, search query, voice dictation round-trip, tab recovery (F5 mid-stream), upload rejection, KV-prefill turn. Then Chunk 2 (authority cluster + §C.2 matrix, 61 commits).
- **Rollback:** `git -C ~/odysseus-dev reset --hard f786bcdf` (chunk start) → redeploy, or `deploy.sh` (no arg → Improvements = 2012 baseline).

### Status (2026-10-21, ~21:00 EDT) — SUPERSEDED by the chunk-1-complete status above (history) — Port in progress: Chunk 1 of 3 starting on ImprovementsDev
- **Tracker moved:** this ROADMAP is now the live work tracker on `ImprovementsDev` (the active work branch); the copy on `improvements-20261014` (Scaffold @ `1d7a89a5`) is the frozen historical record through the 10-20 revert.
- **Chunk 1** (PORT-GUIDE §D): 94 commits cherry-picked oldest→newest from `Scaffold` onto base `f786bcdf`. Group A handled as designed: the 8 `update.sh`-lineage commits land as **one adapted merge commit** (base's `update.sh` already carries most of the lineage from `2ca1e255`; net additions = `[d]` discard dry-run/confirm block + `boot.sh` + setup.sh system-deps block; base keeps `BRANCH="ImprovementsDev"`). The 3 group-A CLEAN commits (`c0a83ca4` setup.sh, `3e954dda`, `5c750fae`) cherry-pick normally.
- **Gate (PORT-GUIDE §D/§E):** focused tests (15 fork + 4 upstream invariant) run in this worktree with `/home/samy/odysseus/venv/bin/python`; user then deploys `deploy.sh ImprovementsDev` + one-turn smoke per affected surface. Prod stays on `improvements-20261012` @ `207df1c0` until the stability bar is met.

### Status (2026-10-21, ~18:40 EDT) — SUPERSEDED by the port-in-progress status above (history) — BRANCH MOVE: ImprovementsDev is the active work branch; 2014 FROZEN as port source
- **Layout (live-verified):** PROD worktree `/home/samy/odysseus` detached @ `improvements-20261012` = `207df1c0` — service `odysseus` active, PID 3165292 (started Tue 2026-10-20 15:51:17 EDT). DEV worktree `/home/samy/odysseus-dev` on `ImprovementsDev` @ `80c2d98a` (base `2ca1e255`, parent = upstream/dev `8877273e` = post-#6742 + pre-Ajax runtime migration + Oct 2–6 fix(security) series) — the post-security port branch.
- **Execution plan:** `ImprovementsDev:specs/PORT-GUIDE.md` (pushed `fc3f14cb` → `80c2d98a`): 173-commit delta classified per commit (CLEAN 55 / RE-VERIFY 61 / ADAPT 52 / ABANDON 5 / ALREADY-IN-UPSTREAM 0), 25 upstream∩Scaffold overlap files, 3-chunk plan (chunk 1 = 94 mechanical), `afecd44d` launch-scope test matrix (§C.2), rollback ladder (§E), dual-version deploy state (§F).
- **`improvements-20261014` (this branch) = FROZEN PORT SOURCE @ `1d7a89a5`:** its `specs/commit-map.md` (173 commits, groups A–P) + this ROADMAP (through the 10-20 revert) are the historical record — no new work lands here. The 10-20 Status NEXT(2) below ("treat improvements-20261014 as the work branch of record") is SUPERSEDED by this entry.
- **Deploy:** branch switching = `/home/samy/odysseus/deploy.sh [dev|Improvements|ImprovementsDev]` (gitignored, in the prod worktree, survives checkouts): snapshots `data/` → `data.snapshots/`, detaches the prod worktree to the target, runs the target branch's `update.sh`, restarts the service. Prod stays on 2012 until ImprovementsDev proves stable for DAYS (PORT-GUIDE §E).
- **NEXT:** execute PORT-GUIDE chunk 1 in `/home/samy/odysseus-dev` (focused tests per chunk via `/home/samy/odysseus/venv/bin/python`); user deploys via `deploy.sh ImprovementsDev` once a chunk is green.

### Status (2026-10-20, ~18:40 EDT) — SUPERSEDED by the 10-21 branch-move status above (history) — REVERTED, running on pre-rebase baseline
- **HEAD:** `Improvements` = `improvements-20261012` @ `207df1c0` (2026-10-10), tree clean, pushed (3-way sync with touzenesmy/Improvements). Service restarted on it 2026-10-20 15:51 EDT (PID 3165292).
- **What the revert rolled back:** all 712 commits from 2026-10-12→10-20 — the completed **tool-group buttons** (5 groups, tick-wins chain, verified live 10-19), the **memory floor** (`813c982d`), thinking-stream + file-tool button, stall work, specs backfill. None of it is lost: all preserved in `improvements-20261014` @ `16b20795` (pushed; `git branch -f Improvements improvements-20261014` re-lands it after a service restart, per the dated-branch convention).
- **Why (user, 10-20):** the rebase onto upstream was reverted; "the whole new security patch is hell" and upstream isn't even done — see **Upstream security patch — not done** below.
- **Live consequences:** the 5 tool-group buttons, tick-wins floor, and memory floor are NOT in the running tree. `ODYSSEUS_TOOL_GROUPS` / `ODYSSEUS_CORE_TOOL_GRANTS` in `.env` are inert no-ops on this tree; `manage_memory` is back to intent-gated only (expect `request_authority_denied` on memory turns again — known, not a new fault). bwrap 0.12.0 remains installed and enforcing (containment.py was in the 2012 tree already — that blocker predated the baseline).
- **NEXT:** (1) Hold on the next rebase until the upstream security work settles (watch #6357 / afonso's series, see below); then cut `improvements-<date>` from `upstream/dev`, cherry-pick/merge the 20261014 delta, run the fork-skill rebase procedure (commit-map full regeneration, step 4g). (2) Until then: treat `improvements-20261014` as the work branch of record — new work lands there, not on the 2012 baseline. (3) Old open backlog still stands: #2 voice/strict smoke, #4 upstream PRs, #5 flake watch, #7 branch prune.

### Status (2026-10-19, ~17:10 EDT) — SUPERSEDED by the revert above (history)
- **HEAD (then):** `Improvements` = `improvements-20261014` @ this docs commit; both pushed to touzenesmy (3-way sync). Tree clean.
- **Tool-groups (Backlog #1) — DONE, verified in production.** Full tick-wins chain landed and confirmed live: per-group stamp + selection floor + RAG force-include (after clobbers) + final-consumption floor (closure-safe `tg_final_disabled`) + floored policy rebuild + **contract-boundary offer** (`934b8366`/`8184bebf`: the frozen `TurnContract` receives ticked tools via `object.__setattr__` on `offered`/`executable`/`schema_json` immediately after `resolve_turn_contract`). Live verification 2026-10-19: all 5 groups ON -> all 5 groups present in the agent surface (bash/web/sessions/media/browser).
- **Diagnostic removed** (`1fe20ffc`): the `.tg_debug.json` dump + `tool_groups_dbg` wire field are gone; gate sites 6->5, wire reads stay 4; buster `20261019tg1`.
- **Guards (complete set):** AST closure guard (no Store-context write to `disabled_tools`/`tool_policy` inside `stream_with_save` — pins the 2026-10-18 incident class) + source pins + **contract-boundary execution test** (`tests/test_tool_groups_contract_guard.py`: runs the exact `object.__setattr__` tick-wins mutation on the real frozen `TurnContract`, incl. `permits()` + idempotency, and pins the route order resolve -> offer -> clobbers -> floor -> bridge).
- **Memory floor (`813c982d`):** `manage_memory` is now a core channel under `ODYSSEUS_CORE_TOOL_GRANTS=1` — granted on EVERY request (like `ask_user`/`update_plan`), not only on memory-family intent. Root cause of the recurring `request_authority_denied` (memory was intent-gated via the `memory` family only; the 5-button patch never touched that path — verified in `9d025713` vs `175073ca`). `tests/test_request_authority.py` 80/80 (incl. 2 new tests: always-granted with flag, not-in-floor without). Pre-existing pollution: 2 `test_tool_policy.py` web-preamble tests fail only in the big `-k` batch run, pass isolated, on pristine tree too — NOT this change.
- **NEXT:** (1) ~~RESTART~~ **DONE** (user restarted; `manage_memory` granted on every request since — verified live 2026-10-19 ~19:20 EDT, no `request_authority_denied`). (2) Memory snapshot update — **DONE 2026-10-19 ~23:40 EDT**: instruction-memory snapshot refreshed (HEAD `915ab5d4`, 4-ref sync, Backlog #1 DONE + verified live, bwrap resolved + enforcing, memory floor live since restart). The ~22:40 `manage_memory` misroute to web_search output (2/2) was a model-layer dispatch quirk (see 22:50 entry), not a floor fault — floor verified live since 19:20. Skill ledger bumped to v1.16.16 (memory-floor fix + stall investigation + pitfall 6). This ROADMAP remains the source of truth memory should point at. (3) Open backlog: #2 voice/strict smoke, #4 upstream PRs, #5 flake watch, #7 branch prune.

## Upstream security patch — not done (verified 2026-10-20 ~18:30 EDT)
Why the rebase was reverted. Evidence from `upstream/dev` + GitHub (fetched live):
- **Security burst in `dev`:** ~15 `fix(security)` / `test(security)` commits landed 10-02→10-06 (subprocess env scrubbing `2a3d0c67`, parser/regex DoS elimination, host-bridge boundary hardening, browser boundary hardening, endpoint authority, cost-ledger key isolation, CodeQL migration findings), then a **second wave on 10-06** (`3d91ad82` Python service boundaries, `ee48c9c5` regex DoS, `c7961d17` workspace existence checks, `82cfd7d6` delegated authority in local web fetches, `ee13ed1e` approval-gate-on-by-default) — i.e. the "new security patch" is a multi-wave, still-evolving series, not a single stable commit.
- **#6268** (generated-image ownership denial) merged 10-14; **#6357** (afonso, "stop the agent from re-enabling tools an admin disabled") **still open** since 09-18 — and its discussion shows unfinished edges: reviewer (ghreprimand, 10-20 14:19, bot review of head merged-onto-dev `8363919a`) flags (a) the "turn image generation back on" shortcut still builds an `enable_tool` call that now fails + `tool_capabilities.py` still lists the action, (b) **`POST /api/tools` still replaces the whole denylist** — not covered, "please confirm the agent cannot reach it, or close it the same way", (c) CI/scan workflows ran zero jobs on the head. That's a live gap in the same denylist boundary our tool-groups feature sits on top of.
- **More churn on top:** iOS safe-area post-#6396 hardening (`#6774` + new upstream branch `fix/ios-safe-area-postmerge-hardening`), and the big email-export PR **#6742** merged into `dev` today 10-20 16:37 (`8877273e`) with its own security-harden commits (account ownership, memory safety, RFC822.SIZE preflight).
- **Decision:** do NOT rebase our 712-commit delta onto a moving security-hardening target mid-stream. Hold on the 2012 baseline; re-cut the next dated branch from `upstream/dev` only when (a) #6357 is merged with its follow-ups closed, and (b) the security series has quieted (no new `fix(security)` commits on `dev` for a week). Re-check with: `git log upstream/dev --grep=secur -i --oneline -15` + `gh pr view 6357` (or the GitHub API).

## RESOLVED 2026-10-15 ~19:10 EDT — bash containment blocked the 20261014 branch
- **Resolution:** `bwrap` installed (0.12.0), probe passed, `./update.sh` switch
  run, bash verified running with `mechanism: bubblewrap, mode: enforcing,
  enforced: [filesystem, process_tree, wall_clock], executed: true` receipts.
  History of the issue below.
- **Symptom:** `bash: containment unavailable (filesystem, process_tree); command not executed`
- **Root cause (verified 2026-10-15):** `src/containment.py` runs in
  `MODE_ENFORCING` by default (`CONTAINMENT_MODE = MODE_ENFORCING`, line 84);
  the only mechanism that provides `filesystem` + `process_tree` is **bubblewrap**,
  and **`bwrap` is not installed on this machine** (`which bwrap` → not found).
  Fallback mechanisms (process_group / windows_tree) only provide wall_clock,
  so enforcing mode refuses every spawn. Unprivileged user namespaces ARE
  enabled (`kernel.unprivileged_userns_clone = 1`), so the bwrap probe
  (`bwrap --die-with-parent --unshare-pid --ro-bind / / --proc /proc --dev /dev /bin/true`)
  should pass once the package is installed.
- **Fix (next action, ~1 min):**
  ```
  sudo apt-get install -y bubblewrap
  bwrap --die-with-parent --unshare-pid --ro-bind / / --proc /proc --dev /dev /bin/true && echo PROBE-OK
  ```
  then run the switch procedure below.
- **Sandbox contract once fixed** (set expectations): commands run under bwrap
  with `/usr` + `/etc` read-only, tmpfs `/` and `/tmp`, workspace bind-mounted
  (writable), network inherited. Inside the sandbox: **no sudo, no docker
  socket** — those stay in the user's terminal. pip/git/pytest from the
  workspace venv work fine.

## Switch procedure (when bwrap is in)
```
cd ~/odysseus && ./update.sh          # checks out Improvements alias + restarts
```
(or `git checkout --detach improvements-20261014 && sudo systemctl restart odysseus`)
Hard-refresh (Ctrl+Shift+R). **Test:** send a short message + "run pwd" —
must print a real path. Then check voice + strict mode once each.
**Rollback (one command):**
`git checkout --detach improvements-20261012 && sudo systemctl restart odysseus`

## Backlog
- [x] **1. Tool-group buttons — replace RAG *guessing* for core tool families (TOP PRIORITY, user directive 2026-10-17).** ✅ DONE 2026-10-19: all 4 slices + tick-wins chain (contract-boundary offer, closure-safe floor, floored policy). Verified in production: all 5 groups ON -> all 5 groups granted in the live agent surface. `ODYSSEUS_TOOL_GROUPS=1` in `.env`. Spec below:
  Generalize the existing bash button into a data-driven **tool-group button row** so
  tool grants are *explicit user intent* (a click), not per-message RAG retrieval +
  text-classification. Solves the three recurring pains: (a) file tools "denied even
  though bash is on", (b) a fresh session "can't see other sessions", (c) RAG
  retrieval lottery (a tool is granted only if retrieval surfaces it AND the message
  text classifies into its family). **Two layers must both be hit** — retrieval
  (force-include the group's tools into selection so the model can see them) and
  permission (grant them in the authority layer).
  - **`BUTTON_TOOLS` map** in `authority.py`: `group -> [tool, ...]`. Start:
    `bash` (existing: bash + read/write/edit/apply/glob/grep), `sessions`
    (list_sessions, search_chats, create_session, manage_session, send_to_session),
    `web` (web_search, web_fetch), `media` (inspect_media, transcribe_media,
    extract_text), `browser` (the `mcp__builtin_browser__*` family). Add more only
    when a real session needs one.
  - **UI** (chat.js): a toggle row next to the existing Bash toggle, per-session
    persisted, **default all OFF** (only Bash keeps its current default).
  - **Request stamp** = list of active groups (same plumbing as the existing bash
    stamp that `authority.py` already reads).
  - **Grant** in `authority.py`: each active group's tools are granted
    (actions=None, inputs=None = unlimited within the tool, like Bash today).
  - **Selection floor** in the tool-selection path: active groups' tools are always
    offered (RAG may ADD extras but may never REMOVE a button-ON tool). This is the
    actual "bypass RAG" — RAG loses veto over explicitly-enabled tools.
  - **Gate:** `ODYSSEUS_TOOL_GROUPS=1`, default OFF = byte-identical upstream
    (every group OFF, no stamp). Drop-check on rebase.
  - **Context cost (honest):** each ON group adds its tool schemas to every round
    (~13.7K chars for the 14 tools sent today; email-family ~25 tools is the big
    one). UI should make ON groups visible; habit = enable what the session needs,
    disable after. That's *better* than RAG — the context tax is paid deliberately.
  - **Watch upstream `afecd44d` (approve-once / sticky approval)** before finalizing
    — our buttons are the pre-configured version of that; if upstream ships a native
    group toggle, prefer it.
  - **Build in a fresh, low-context session** (this session's context is degraded).
- [x] **2. Install bwrap + switch to `improvements-20261014` + verify** — DONE 2026-10-15 (bwrap 0.12.0; enforcing receipts verified). Voice/strict smoke checks: [x] bash / [ ] voice / [ ] strict.
- [x] **3. Full test suite on the 2014 branch** — DONE 2026-10-16 (host run,
  `fullsuite-20261016.log`): 77 failed / 13,870 passed. **12 failures were
  ours**: the two fork env vars leak from the host environment into upstream's
  pinned structural tests (4x `test_request_authority` via
  `ODYSSEUS_CORE_TOOL_GRANTS`, 4x `test_wave3_launch_cost_lifecycle` via
  `ODYSSEUS_ALLOW_SERVER_HOME_LAUNCH`, 4x `test_env_reference` — our vars were
  missing from `VARIABLE_NOTES`). Fixed `51a5ab5d` (autouse scrubs in the
  affected test surfaces + env-reference entries + regenerated
  `website/configuration-reference.md`), verified green with both flags set in
  the environment. Remaining 65 are upstream-area (browser/JS rendering
  suites, live-fallback, inspect_media, kimi flake #4) — pre-rebase baseline
  was 60 failed, so ~5 are new upstream test surface from the rebase's 540
  commits. Optional re-run to confirm 65:
  `venv/bin/python -m pytest tests/ -q > fullsuite-20261016b.log 2>&1` (host-side;
  my sandbox kills the process tree when my command returns — full suite must
  run from the user's terminal).
- [ ] **4. Five open upstream PRs** — #6226 #6230 #6232 #6234 #6236. Watch reviews; fold into the next rebase.
- [ ] **5. Known upstream flake** — kimi full-suite failure (parked since before the rebase; not ours).
- [ ] **6. Drop-check on next rebase** — current fork opt-out set (all default-upstream, env-gated):
  - `15542d9f` `ODYSSEUS_COMPLETION_GATE=0` (whole-gate bypass; supersedes+replaces REMOVED `f738b263` LIVE_ANSWER_STREAM)
  - `9164b030` terminal-bubble = streamed prose (transcript-wall fix; rides the gate bypass)
  - `dd900647` `ODYSSEUS_CORE_TOOL_GRANTS` (unknown-intent recovery grants)
  - `01cece53` bash-button-as-only-gate + `ODYSSEUS_ALLOW_SERVER_HOME_LAUNCH`
  - `383c6ca7` bash button ALSO gates file tools + `ODYSSEUS_SHOW_THINKING` (loop gate)
  - `f4c4681c` `ODYSSEUS_SHOW_THINKING` route gates (bypass thinking_mode=off)
  - `51a5ab5d` test hermeticity + env-reference entries (fork-specific, not an opt-out)
  Drop any upstream has since fixed properly. Upstream +18 since the 2026-10-16
  check touched none of `authority.py`/`process_resources.py`/`containment.py`/
  `completion.py`/`agent_loop.py`/`chat_routes.py`/`update.sh`; `afecd44d`
  (approve-once) is upstream moving in our direction in the *approvals*
  subsystem — re-check on rebase.
- [ ] **7. Prune legacy branches** (only after the service has run a few days on the 2014 branch): `Improvements-backup` (00196069), `Improvements-backup-20261012`, `Improvements-backup-20261012-2`, `pre-squash-improvements-20260825`. Dated-branch convention makes these redundant.
- [x] **8. Preemptive tool-call denial leaks as the final reply (diagnosed 2026-10-23 ~22:00 EDT; fixed 2026-10-24).** User report: an automated assistant message `qwen3.8-27b / The exact operation is outside server request authority.` appeared right after their 21:39 message ("there should be an MCP browser tool … can you check that?"). **Chain (verified in app.log + app.db + code):** (1) the word "MCP" in the user text matched the agent loop's preemptive explicit-request regex (`agent_loop.py:2845` `re.search(r"\bmcp(?:\s+servers?)?\b", q)` → fires `manage_mcp {"action":"list"}` itself, before any model round); (2) the request-authority gate denied it — `manage_mcp` is `cookbook_admin` family, but the intent classifier granted this turn the web/files surface (turn text classified as a web question), so `restrict()` produced `request_authority_denied` ("The exact operation is outside server request authority."); (3) the preemptive path then sets `full_response = <tool error output>` and `break`s the loop — the raw denial string was emitted as the assistant reply (0.3 s after the user message; model's real answer landed ~80 s later as a second bubble). **Fixed (2026-10-24):** the preemptive path now detects any hard block (`blocked: true` or `failure_kind` in {request_authority_denied, resource_identity_denied, turn_contract_denied}): it drops the preemptive result (the attempt stays in the tool trace) and lets the normal model round proceed, so the raw denial is never emitted as the assistant reply and the model round is never starved; an admitted preemptive still short-circuits. Regression: `tests/test_backlog8_preemptive_denial.py` (denial never a `final_response`, model round proceeds, admitted preemptive still short-circuits). **Extended (2026-10-25, `94edfa88`):** the calendar branch (pre-executed `list_events`) had the identical leak as a separate code path — same hard-block detection + defer added there, with deny-path and short-circuit regression tests; the explicit-admin and calendar tails are now both covered.
- [x] **9. Browser tool-group button grants a dead wrapper, not the built-in Playwright MCP (diagnosed 2026-10-23 ~22:30 EDT; fixed 2026-10-24).** User report: Browser button ON in UI, yet `mcp__builtin_browser__*` not granted / model says it's not wired. **Root cause (verified in code; the two are stacked):** (a) **Grant side — `private_browser` is a dead end.** `BUTTON_TOOLS["browser"] = ("private_browser",)` (authority.py, commit `a07b64a2`). `private_browser` is only a *prompt-level alias*: `agent_loop.py:673` maps `open_url/browser_open → private_browser`, `:721` requires `original_name in _NATIVE_TOOL_ALIASES`, `:742/:754` only rewrites `inspect_media→private_browser` when the *wrapper* is offered. [Corrected 2026-10-25 during verification: `private_browser` **is** a real native tool — schema `tool_schemas.py:395`, grant checks `browser_identity.py`, `NativeBackendResource` backend — but in local-launch mode it is **metadata-only** (`SESSION_ACTIONS = {"session_info"}`; every page action returns `page_unavailable()` because the native producer binary is absent on this host), so the wrapper alone still could not do what the button promises.] The real browser is the built-in Playwright MCP (`builtin_mcp.py` NPX `@playwright/mcp@latest --headless --caps vision`, wire names `mcp__builtin_browser__*`). So the button's grant/floor/force-include all operate on a name nothing executes. **The comment above BUTTON_TOOLS ("the MCP wire names are resolved in the chat_routes floor") is wrong** — no such resolution exists in chat_routes (grep-verified; `_BROWSER_MCP_TOOLS` at :1574 is only a strip *set*, and `BUTTON_TOOLS.get(_g)` at :3653/:4788/:4826/:4847 never expands it). (b) **Offer side — the fork's hide-rule kills the raw MCP whenever the button is ON.** `_should_hide_raw_browser_mcp(disabled_tools)` = `"private_browser" not in disabled_tools` (agent_loop.py:4334; upstream, from `84aa9a91` squash): the button ON floors `private_browser` **out of** `disabled_tools` → hide-rule TRUE → `_with_raw_browser_mcp_hidden` (call site :14548 inside `_build_system_prompt`, :21029 `stream_agent_loop`) adds **every** `builtin_browser` tool to the MCP disabled map AND `_filter_raw_browser_mcp_schemas` (:14555) strips their schemas; `_expand_browser_mcp_tools` (:22695) also discards them. Net effect: **Browser ON = zero browser tools offered, zero grants** — the exact opposite of the tick-wins contract. (The hide rule was designed for the reverse: hide raw MCP when the *wrapper* is usable; with the wrapper gone, ON means "nothing".) **Fixed (2026-10-24):** the ticked Browser button owns the raw Playwright MCP surface end to end — `BROWSER_MCP_TOOLS` moved to `src/tool_policy.py` as the single source (chat_routes imports it); the route-side floor/force-include/ceiling expand the browser group to all 22 wire names (`authority.py`); the offer side threads `client_runtime_context` through `_should_hide_raw_browser_mcp` / `_expand_browser_mcp_tools` / `_filter_raw_browser_mcp_schemas` / `_with_raw_browser_mcp_hidden` so a ticked button exposes the raw MCP while the gate-OFF default stays byte-identical; the execution gate admits `mcp__builtin_browser__*` whenever `browser_mcp_raw_surface_allowed` (stamp or env) admits the raw surface, before any page is created. Regression: `tests/test_backlog9_browser_button.py` (+ contract guards re-pinned in `tests/test_tool_groups_contract_guard.py`, `tests/test_chat_route_tool_policy.py`).
- [x] **10. Final assistant bubble arrives all-at-once (transcript-wall regression; logged 2026-10-24 ~02:25 EDT; fix AFTER #8/#9 per user; FIXED 2026-10-26).** **Verified root cause (2026-10-26, end-to-end code trace, no live SSE capture needed):** the loop accumulates `full_response += delta` across ALL rounds (no per-round reset; `round_texts` is the per-round record) and its terminal `final_response` frame carries that whole-turn transcript; the client (`static/js/turnRendering.js` `render()` + `chat.js` terminal handler) treats `final_response` with `replacement_scope: 'turn'` as a WHOLE-BUBBLE replacement of the last round's bubble. The `ODYSSEUS_COMPLETION_GATE=0` bypass rewrite (`f27ca5c6`) fixed the tool-output wall but accumulated `prose_parts` across the entire turn (never reset at round boundaries) — so on any multi-round turn the terminal frame still replaced the final bubble with every round's prose = one solid block. Live deltas streamed fine; only the terminal swap re-rendered the wall. **Fix (`completion.py` bypass, ~20 lines):** reset `prose_parts` at each `agent_step` frame (the loop emits one at every round boundary, `agent_loop.py:27733` et seq — all 8 sites verified as true boundaries, no mid-round/status-only variants exist), so the terminal rewrite is scoped to the final round's prose (matching the bubble it replaces); structured-snapshot `final_response` frames (`render_owner: 'structured'`) now pass through untouched (they own the bubble; the old code clobbered their server-owned content with prose — same wall shape) and start a fresh prose scope. **Regression:** `tests/test_completion_boundary.py::test_completion_gate_bypass_terminal_scoped_to_last_round` (3-round turn: terminal == last round only, tool output excluded, all frames stream in order) + `::test_completion_gate_bypass_structured_snapshot_resets_prose_scope`; 60/60 in file, 195 across the completion/evidence surface. **Smoke:** on a long agent turn the final bubble should now stream its own prose and end identical to what streamed (no wall). User observation: the last assistant chat bubble of a long agent turn (this chat, model `qwen3.8-27b` local) rendered as one solid block instead of streaming token-by-token — "a bug that supposedly should be fixed." **Known state:** the transcript-wall cluster `cda4db89` (opt-out live answer streaming) → `c5914a15` (`ODYSSEUS_COMPLETION_GATE=0` bypass) → `f27ca5c6` (bypass keeps terminal bubble = streamed prose) is in the base, and `ODYSSEUS_COMPLETION_GATE=0` IS set in `.env` — so the regression is either (a) a path the bypass flag doesn't cover (e.g. the qwen38 tool-router route, a fallback/round-N path, or the completion-rewrite/terminal-bubble substitution running before the bypass check), (b) the SSE live-stream frames not being flushed on that route (buffering at the proxy/`_direct_fallback`/SSE boundary), or (c) the client rendering the terminal bubble wholesale (tab-recovery resume path or the terminal message replacing the live bubble instead of merging). **Diagnosis plan:** (1) capture one reproduction — user opens a long agent turn, watches whether the bubble streams; check `app.log` for the completion-gate/bypass decision lines on that turn; (2) verify the flag is read on the exact route the turn takes (grep the flag's read sites; confirm the qwen38 router path reads it); (3) curl the SSE stream for a small agent turn and time the `message`/terminal frames vs the live `delta` frames — if deltas arrive but the terminal frame carries the full text and the client swaps instead of merges, it's client-side; (4) fix the gap on whichever side, with a regression test pinning "deltas precede terminal frame AND terminal == accumulated prose."
- [x] **11. Deleted chat messages still reach the live session's agent context (logged 2026-10-28 ~21:15 EDT; CLOSED as MISDIAGNOSED 2026-10-29).** The logged premise — that the audit turn's model context carried the deleted text — is contradicted by the evidence: the audit turn (20:11:19 EDT) built a **clean** context (its `[agent-intent]` line's newest user messages are the post-delete ones only; had the deleted messages leaked they'd have been the newest and would appear first), and the cited `latest="Somthing isn't right…"` line is from the 20:10:37 turn — the turn that was *responding to* that message (a turn's `latest=` is the message that triggered it, not a leak). Reproduction against the real delete route + `SessionManager`/temp DB confirms a deleted `_db_id`-stamped message is absent from `get_context_messages()` on the next turn — the in-memory delete filter works. **Actual resurfacing channel:** the model read `app.log` (20:31:57 turn, reply 00:58:05 UTC: "The log reveals a turn I wasn't part of … not in my context"), where the deleted text persists in old `[agent-intent] latest=`/`retrieval_query=` lines — app.log retains full user-message text, which is a privacy-adjacent surface worth noting but not a context bug. **Residual latent edge (documented, not fixed):** the in-memory delete filter only drops messages carrying a `_db_id` stamp, so an in-memory message added via a never-stamped path (e.g. a swallowed persist) would survive a UI delete; the delete route (`history_routes.py` DELETE handler) filters `session.history` by `_db_id` match. If a future report claims a deleted message re-entered context, check this stamp gap first, then the app.log channel.
- [ ] **12. Final answer routed to the thinking/reasoning field — turn ends with a near-empty visible reply (logged 2026-10-28 ~20:30 EDT; user report: "Your report was put in your thinking bubble").** User requested a code-vs-docs/skills/memory audit at 20:11 EDT; the turn ran 8 rounds / 16 tool events over ~19.5 min / 23.2K output tokens, but the persisted assistant message is **208 chars** (the opener sentence only) and rounds 2–8 all have **empty visible text**. The full audit report (71,320 chars) lives in the turn's **thinking field**, which ends mid-plan ("Alright, I'll write the final audit report…") — the model never emitted the answer as content, so the turn terminated. The client's thinking bubble renders reasoning as designed, so the visible symptoms are (a) the answer is only readable inside the thinking bubble and (b) the turn ends silently with a truncated reply — no error, no retry, no warning frame. **Suspected causes:** (1) model-side — the local model (`qwen3.8-27b`, boot-model llama-server :8050) wrote the final answer into the reasoning stream and stopped without visible content (template/prompt behavior, not a server bug); (2) server-side gap — the loop has no detection of "final round: empty visible content + non-empty thinking", so a turn can end with a near-empty reply without any flag. **Diagnosis plan:** (a) reproduce on a heavy multi-round turn; inspect the DB row (content length vs thinking length, per-round `round_texts`); (b) check the boot-model template's reasoning routing (`reasoning_content` / `think` markers) and whether the prompt steers the final answer into thinking; (c) decide the hardening: if the final round has no tool call, empty visible content, and a long thinking field, treat the turn as incomplete — emit a visible warning frame (or retry the round with a nudge) instead of ending silently; (d) regression test pinning the detection. **Handoff note:** the original audit request (code vs docs / skills / memory) was NEVER completed — its findings exist only in that turn's thinking field, never persisted; re-run from a fresh compact session (lesson: fewer parallel tool fan-outs, persist findings incrementally).
## Design — tool-group buttons (2026-10-17 ~04:30 EDT; seams live-verified, no code yet)
Backlog #1. Requirements (exact spec): see Backlog item 1 above. Gate: `ODYSSEUS_TOOL_GROUPS=1`;
unset = byte-identical current behavior. Groups: bash/sessions/web/media/browser; all-OFF default
when ON; per-session UI persistence; grant = unlimited within the group's tools; floor = RAG can
never strip a button-ON group's tools.

Verified seam map (line numbers as of `a15d8ab9`):
- UI registry pattern: `static/app.js` `MODE_TOOLS` (~:1771) `[{btnId, checkboxId, stateKey}]`
  (web/bash/docs) + per-mode persistence (`loadToolPref`/`saveToolPref` via Storage module) +
  `TOOL_TOGGLE_TOAST_LABELS`. Generalization point for the group row.
- Name collision: `static/js/assistant.js:122` `TOOL_GROUPS` is the assistant-settings
  *enabled_tools selector* (Email/Calendar/… categories) — different feature. Our map must be
  named differently (spec: `BUTTON_TOOLS`).
- UI→server stamp: `static/js/chat.js:2637-2638` (`fd.append('allow_bash')` +
  workspaceAgentIntent force-true); `static/js/compare/stream.js:440` sends `'true'` (compare view).
- Server read: `routes/chat_routes.py:2504` (form → JSON-body fallback); forced `'true'` at
  :2692/:2890/:2993 (agent-intent paths).
- Policy accumulation: chat_routes.py ~:3336-3410 — allow_bash→disabled_tools('bash') gate :3340;
  `allow_documents`→DOCUMENT_TOOL_NAMES ~:3404; `_bash_explicitly_on` :3401 (survives intent strips).
- Floor seam: chat_routes.py ~:4625-4626 — existing bash strip-exemption
  ("allow_bash explicitly true → not stripped"). Generalize to per-group discard from disabled_tools.
- Route→authority stamp: chat_routes.py:3583 `client_runtime_context["web_ui_state"] = {...}`
  (server-side effective policy; the client's raw value never reaches authority).
- Authority grant: `src/agent_runtime/authority.py:397-412` — `web_ui_state.bash` → grant bash +
  6 workspace file tools (fork rule: button is the ONLY request-authority gate for bash;
  ON → grant whatever the text says; OFF → `restrict()` denies). Fork opt-in env precedent:
  `ODYSSEUS_CORE_TOOL_GRANTS` block directly above.
- Selection path (RAG): `src/turn_contract.py` `selected_tools_for_request` — intersects with intent
  inside `create_request_authority` (`tools &= selected`). Floor must apply AFTER that intersection.
- Tests: `tests/test_chat_route_tool_policy.py` mirrors the route's inline logic + source-string
  asserts against chat_routes.py — keep asserted strings stable or update tests in the same commit.

Implementation plan (bounded turns):
1. authority.py: `BUTTON_TOOLS` = {group: [tools…]} (5 groups); read per-group stamp from
   `web_ui_state` → add all tools of ON groups. Gate OFF ⇒ block is a no-op.
2. chat_routes.py: generalize the allow_bash read/stamp to per-group (keep the `allow_bash` wire
   key working with gate OFF); floor = discard BUTTON_TOOLS[group] from disabled_tools for each
   ON group (generalizes the :4626 exemption).
3. UI: config-driven group row in app.js (MODE_TOOLS pattern) + per-session persistence (existing
   Storage pattern); cache-buster bump in ALL refs (index.html ×2 + JS import) — grep old URL first.
4. Tests: mirror test_chat_route_tool_policy.py — gate-OFF byte-identical cases + gate-ON
   grant/floor cases.

Open (verify first thing in impl turn 1): exact `web_ui_state` dict contents at chat_routes.py:3583;
the function enclosing :3336-3410 (name + signature) so tests can call it directly.

## Conventions (pointers — details in the fork skill + the files)
- **Dated branches:** `improvements-<YYYYMMDD>` per rebase; `Improvements` is a
  moving alias (`git branch -f Improvements improvements-<date>`); the previous
  dated branch IS the backup. `update.sh`'s `BRANCH="Improvements"` never changes.
- **Commit map:** `specs/commit-map.md` — feature → SHA, keep current (append +
  commit whenever branch work is committed; regenerate fully after a rebase).
- **This roadmap:** update Status + Backlog on state change, commit + push.
- **Skills/memory:** point here; volatile values stay in this file.

- 2026-10-16 ~06:30: b-run confirms the hermeticity fix — 65 failed / 13882 passed
  (was 77/13870); the 12 removed = exactly the env-leak set (4 request_authority +
  4 wave3_launch_cost + 4 env_reference); 0 new; all 65 remaining are upstream-area
  (JS/browser suites, resource identity, live-fallback, inspect_media, kimi flake;
  baseline pre-rebase was 60 → ~5 new from the rebase's 540 commits of upstream
  test surface). Fork-patched areas: clean.
  **Wall-of-text incident (05:52) root cause:** NOT a renderer bug. DB shows the
  05:52:06 assistant message (the raw pytest dump) came from a 35-min, 30-tool-call
  turn that STARTED at context_percent=71.5 (qwen3.8-27b, 112K window); the actual
  work in that turn all succeeded (fix 51a5ab5d + commit 3ed86515 + push) but the
  model's final answer degenerated into echoing a raw log block that was in context.
  Lesson: at ~70% context, stop and hand off — the ROADMAP is the handoff doc;
  a fresh session starts at ~15% and degrades far less.
## Session log
- 2026-10-18 (21:20 EDT) — **Diagnostic round ANSWERED + stamp fix.** `.tg_debug.json` proved the server chain is 100% correct (raw stamp arrived as `bash,web` — the 3 new groups' checkboxes were desynced from the visible buttons; ceiling/floor/forced all behaved exactly per design for the stamp received). Root cause = UI: stamp trusted checkbox `.checked` only. Fix `d76fe821`: self-healing stamp (button `.active` = truth, re-sync checkbox), `tool_groups_dbg` per-group cb/btn reporting into the diagnostic, cache-buster `20261018tgfix`. NEXT: push + `update.sh` + hard-refresh (Ctrl+Shift+R — cache-buster is in the HTML, so a normal reload picks it up), all 5 ON, send "list my sessions" → expect all 5 groups granted; `tool_groups_dbg` shows cb/btn truth at send time.

- **2026-10-17 ~02:50 EDT:** Backlog re-prioritized per user directive: new **item 1 (TOP PRIORITY)** = tool-group buttons (generalize the bash button into a data-driven group row — `BUTTON_TOOLS` map, stamp, grants, selection floor, `ODYSSEUS_TOOL_GROUPS` gate; spec inlined above). Build in a fresh low-context session; watch upstream `afecd44d` approve-once first. Also logged this session's degeneration incident: 36-min 24-round turn peaked at ~70% context, then a repeating no-tool-call loop (20+ min, same text) that produced a garbage `rm -rf /` tool call — blocked twice (rm's own `--no-preserve-root` refusal + bwrap confinement), zero damage. Confirmed `rm` was sampling breakdown, not intent; compaction threshold (0.85) is an overflow guard and does not catch sub-threshold repetition loops — candidate fork: no-progress circuit breaker (N consecutive zero-tool-call rounds → clean early exit). New-session authority finding: grants are per-message (sealed at `create_request_authority`), no mid-turn upgrades — the "new session can't see other sessions" wall is the RAG-retrieval + text-classification combo the button feature replaces.
- **2026-10-16 (~23:00 EDT):** Thinking-stream batch CLOSED + verified live.
  User confirmed: **agent mode shows thinking** (restored by SHOW_THINKING),
  **chat/strict stay clean** — intended: the flag only lifts the *forced*
  Qwen-3.8 tool-router hide; chat/strict use the normal per-chat thinking toggle
  (default off), so they behave like stock. **The fork opt-out pattern** (all
  default-upstream, env-gated, drop-check at rebase) is now 4 flags in `.env`:
  `ODYSSEUS_COMPLETION_GATE=0` (15542d9f + 9164b030 transcript-wall),
  `ODYSSEUS_CORE_TOOL_GRANTS=1` (dd900647), `ODYSSEUS_ALLOW_SERVER_HOME_LAUNCH=1`
  (01cece53), `ODYSSEUS_SHOW_THINKING=1` (383c6ca7 loop gate + f4c4681c route
  gates). **Branch drift fixed:** `improvements-20261014` re-pointed to the
  alias (it had drifted 1 commit behind). **Memory superseded:** the old
  project memory's "blocker = bwrap not installed" is GONE (running
  bwrap-enforcing since 2026-10-15); running = improvements-20261014 @ b496cb6a.
  **Follow-up:** skill `user-odysseus-fork` does NOT yet capture the opt-out
  flag pattern (it's write-protected — needs the full user-skill-management
  procedure: gate → backup → view → edit → verify → bump); do that, don't patch
  it ad hoc.

- **2026-10-16 (04:00-09:00 EDT):** Completion-gate communication fix. The hold-until-gate behavior was NOT the only problem: the gate also REWRITES the terminal answer (claim stripping) and releases it in one burst - that is what the user saw as "mangled". `ODYSSEUS_LIVE_ANSWER_STREAM` (f738b263) was removed (it was non-functional: a duplicate-def bug made the bypass dead code). Replaced by **`ODYSSEUS_COMPLETION_GATE=0`** (15542d9f): whole-gate per-request bypass, .env toggles live, upstream default unchanged, 207 tests pass. .env now sets it. Also noted: new code hides Qwen 3.8 private reasoning from the client by design (agent_loop.py ~27486) - the old "thinking before action" flow is gone upstream-side, separate from the gate.

- **2026-10-16 (01:2x):** Full suite (host run) 77 failed / 13,870 passed.
  12 were ours (fork env vars leaking into upstream's pinned structural tests
  + missing `VARIABLE_NOTES` entries) → fixed `51a5ab5d`, verified green with
  both flags set. Remaining ~65 upstream-area (5 more than baseline — new
  upstream test surface). Optional host-side re-run to confirm.
- **2026-10-15 (19:0x):** bwrap 0.12.0 installed; probe passed; switched to
  `improvements-20261014` @ `f77a0359` via `./update.sh`; bash containment
  verified enforcing (bubblewrap receipts). Sandbox boundaries probed and
  documented (see Status). Roadmap itself updated to RESOLVED. Next: full test
  suite (backlog 2), then PRs (3).
**2026-10-17 (tool-groups 3/4, session 2):** UI slice `7d028f48` — sessions/media/browser buttons in index.html, TOOL_GROUPS data-driven row + per-mode persistence in app.js, tool_groups stamp in chat.js, cache-busters bumped. Committed map gap fixed: f0ba4128/ae57e6be/48e9e805 were missing from commit-map (slice 2 docs commit didn't append). HEAD `7d028f48`, ahead 8 after this commit, unpushed (user terminal). NEXT: slice 4/4 — gate-ON tests (grant + floor cases, mirror test_chat_route_tool_policy.py) + full venv suite, then service restart + UI verify. Gate-OFF verified: 70/70 authority, 141/141 route+authority.
- - **2026-10-15 (04:26):** Rolled back to `improvements-20261012` (bash
  containment unavailable). Root cause: `bwrap` missing (containment.py
  enforcing mode, bubblewrap is the only filesystem+process_tree mechanism).
  This document created as the standing work tracker.
- **2026-10-14:** Rebase of the improvement branch onto upstream (540 commits),
  post-rebase integration fixes, authority work: `dd900647` core-tool opt-in
  grants, `01cece53` bash-button-as-only-gate + `ODYSSEUS_ALLOW_SERVER_HOME_LAUNCH`
  opt-out, `update.sh` discard guard, dated-branch convention, commit map.
  Details: `specs/instance-map.md` + fork skill session ledger.

- 2026-10-19 ~14:20 EDT: **Backlog #1 closeout** — diagnostic dump removed from route+chat.js (gate 6->5, buster 20261019tg1) + `tests/test_tool_groups_contract_guard.py` (executes the frozen-contract tick-wins mutation on the real class; pins route wiring order). Feature verified live with all 5 groups. commit-map backfilled (a360fd71..1fe20ffc); dated branch ff'd to alias; pushed.
- 2026-10-19 ~15:00 EDT: **Docs backfill + final verification.** commit-map backfilled for `af8c542c` + `65931be8` (the two post-closeout docs commits). Confirmed guard test `tests/test_tool_groups_contract_guard.py` = 3/3 green (real frozen-contract execution, not string pins). Confirmed 4-ref sync: Improvements = improvements-20261014 = touzenesmy/Improvements = touzenesmy/improvements-20261014, all @ `65931be8`, tree clean, 165 ahead of upstream/dev. Service running (user-confirmed PID 2762080). Fixed the pending-memory note to point at the live HEAD instead of a stale SHA. Remaining open item: memory snapshot update (needs a turn where `manage_memory` is granted — denied this closeout turn by tool-group authority).
- 2026-10-19 ~19:35 EDT: **Memory floor verified live + bookkeeping close.** User restarted the service; `manage_memory` granted on the next turn (no `request_authority_denied`) — `813c982d` floor confirmed live. Tree clean @ `d75553e1`, 4-ref sync. This entry + the memory snapshot edit resolve the two pending items from 14:20/15:00. Pre-existing known pollution (NOT the memory change): 2 web-preamble tests in `tests/test_tool_policy.py` fail under full-suite `-k` runs on the pristine tree too (ordering effect; pass in isolation).
- 2026-10-19 ~22:50 EDT: **Stall/intermittent-tool-failure investigation + docs.** User report: "apply patch failed, sometimes bash failed, and that gets you to stall." Measured, not guessed: (a) sandbox layer CLEAN — bash 0.003s, bwrap spawn 2–3ms, multi-minute runs complete, teardown dead=true, wall_clock enforcing; (b) failure class = model layer — local Qwen @ :8050 returned HTTP 502 mid-turn (`[Agent stopped: Model request failed (HTTP 502)]`), which kills in-flight tool calls → user sees random "apply patch failed"/"bash failed"; plus long prefill (830–2,200 tok/s measured; 30k-ctx turn → 15–60s TTFT; re-prefill near 112k cap; total_slots=1). User switched session to Kimi-over-API after reporting. (c) NEW symptom: `manage_memory` calls returned web_search output keyed to the user's message (2/2, ~22:40) — tool-dispatch/response-association issue in the app, distinct from the model 502s. commit-map backfilled (`ff5e090f`); NEXT(2) still pending (needs a clean `manage_memory` turn).
- 2026-10-16 ~07:30 EDT: live answer streaming opt-out landed (`f738b263`).
  User opted B: restore pre-wave-3 streaming (the completion gate held ALL
  answer prose until the generator unwinds → one big end-of-turn bubble;
  same root as the wall-of-text incident). `ODYSSEUS_LIVE_ANSWER_STREAM=1`
  streams deltas + final_response as they arrive; the gate still runs and
  shapes the terminal event, it just can't retract already-released prose.
  Default OFF = upstream unchanged (18 upstream buffering tests pass with the
  flag set via hermetic scrub). Verify after restart: prose should stream
  token-by-token again instead of arriving in one burst.

### Stall/Cancelled-turn diagnosis (2026-10-16, verified in app.log + chat_messages)
Three distinct causes, all confirmed in data — "stall" is NOT one bug:
1. **Slow turns + hidden thinking (main "stall" feel):** qwen3.8-27b-q3 on 16GB VRAM takes 200-285s per model round at 65-73K prompt tokens; upstream deliberately hides Qwen 3.8 private reasoning from the client (agent_loop ~line 27486). So 2-5 min stretches render NOTHING in the UI. Not a crash — just invisible work.
2. **Cancel semantics (rebase-born, 11ed6f13 + 1928f283 close-path):** any client disconnect (phone lock, tab switch, stop button, hard refresh) cancels the running turn -> UI error + `cancelled: true` row in DB (e.g. 19:23:18Z, dead in 6s). Clean; nothing lost; just resend.
3. **Context-overload degeneration (the wall-of-text):** long turns starting >70% ctx make the final answer collapse into raw log dumps. Rules: fresh session per work block; keep turns <= ~10 tool calls; hand off via ROADMAP at ~70% ctx.
Rules: no refresh/lock/tab-switch mid-turn; fresh session per work block; if a turn dies -> just resend.
### 2026-10-17 ~04:35 EDT — Tool-group buttons: design pass. All seams live-verified (app.js MODE_TOOLS ~:1771; assistant.js:122 name collision; chat.js:2637; chat_routes.py :2504/:3340/:3401/:3583/:4626; authority.py :397-412; turn_contract.selected_tools_for_request). Design section written. CORRECTION: src/agent_runtime/authority.py + src/turn_contract.py DO exist in the fork (earlier "does not exist" note was a path-miss, not absence). No code changed. Next: impl turn 1 — read chat_routes.py:3583 dict + enclosing function, then authority.py BUTTON_TOOLS.
### 2026-10-17 ~18:40 EDT — Tool-group buttons impl slice 1/4: `BUTTON_TOOLS` map (5 groups) + `ODYSSEUS_TOOL_GROUPS`-gated per-group grant in `create_request_authority` (`175073ca`). Gate-OFF byte-identical — 70/70 tests/test_request_authority.py pass (venv/bin/python). Next: slice 2 = chat_routes per-group stamp + selection floor.

- 2026-10-17 ~19:40 EDT: tool-group buttons **slice 2/4 (route stamp+floor)** — ae57e6be. chat_routes.py: `tool_groups` wire key → per-group disabled_tools floor before policy build; web_ui_state per-group keys; RAG _forced_tools force-include. All three blocks gate-OFF no-ops (42 insertions, 0 deletions); 141/141 on both affected suites. Next: slice 3/4 UI (app.js group row + persistence + cache-buster), then slice 4/4 tests (gate-ON cases).
- 2026-10-17 ~20:40 EDT: tool-group buttons **slice 3/4 (UI)** — 7d028f48. app.js data-driven 5-group row (MODE_TOOLS pattern, per-mode persistence, default all OFF); chat.js:2646 `tool_groups` stamp (all 5 groups, appends only when non-empty); index.html 3 new buttons; cache-buster `?v=20261017toolgroups` on all 4 html refs. node --check clean on both JS files. Docs 6318fba0.
- 2026-10-17 ~22:45 EDT: tool-group buttons **slice 4/4 (tests)** — 83185b20. 14 new tests: 8 authority gate-ON grants (per-group, multi-group, nothing-ticked baseline, gate-OFF inertness, bash parity vs gate-OFF) + 6 route/UI source pins (wire key, 3 gate sites, floor, stamp, RAG force-include, frontend stamp). 155/155 on both affected suites (venv/bin/python). **FEATURE COMPLETE — all 4 slices.** Next: push (user terminal), manual UI check, flip ODYSSEUS_TOOL_GROUPS=1.- 2026-10-17 ~23:05 EDT: **pre-push double-check — PASSED.** Re-read all 4 slice diffs verbatim vs base a15d8ab9 (authority grant, route stamp+floor, UI row+stamp, 14 tests); cache-buster on all 4 html refs; 708 passed on 5 authority/route/tool-policy suites (venv/bin/python); full suite in bg (exceeds sandbox foreground cap; results to be logged on arrival). Upstream moved ~15 commits (a15d8ab9..upstream/dev) incl. refactor PRs overlapping our changed files — note for next rebase.
- 2026-10-17 ~23:30 EDT: **push-name rule check + dated-branch sync** — user confirmed fork rule: every push carries the DATED name (`improvements-<date>`; alias `Improvements` tracks it, pushed alongside). Found slice work had landed on the checked-out alias with the dated branch lagging 11 commits; `git branch -f improvements-20261014 Improvements` (local ff, ancestry linear-verified, remote dated ref 3ba8e964 also linear ancestor). Commit-map gap fixed (be4573cd missing) + stale Status line corrected (was @83185b20/ahead 10, now 6d255cf2+ahead 12). NEXT: user pushes `git push touzenesmy improvements-20261014 Improvements` (12 commits, ff on both refs), then manual UI check + flip ODYSSEUS_TOOL_GROUPS=1 + restart.

**2026-10-18 (tool-groups slice 2.5 — tick-wins, E2E debug):** User E2E test: with all 5 buttons ON, agent surface still lacked sessions+browser groups every cycle. Root cause found by reading the live chain verbatim: the ticked-group force-include (slice 2) was placed BEFORE the two wholesale `_forced_tools` replacements (`_explicit_selected_tools`, `_turn_contract.offered`) — on contract turns it was silently discarded; only RAG-retrievable groups (bash/media/web) survived. User rule: **tick wins, both directions** (unticked group must never be offered by RAG). Fix `d4925ca4`: (1) CEILING — when the client sends tool_groups, unticked groups go into disabled_tools (stamp derives from disabled_tools → authority grant auto-disabled too); (2) force-include re-homed AFTER the clobbers, alongside upstream allow_documents. 157/157 (route+authority suites), gate sites still exactly 3, new pins: ceiling + clobber-order. NEXT: user pushes d4925ca4 + docs, restart service (`./update.sh`), all buttons ON, send 'list my sessions' → sessions tools must appear.

**2026-10-18 (evening, EDT) — E2E diagnostic in flight (`2236c70e`):** tick-wins fix confirmed deployed (service PID 2400464, started 17:32:04 EDT, post-fix) but sessions/browser STILL absent from agent surface — and the force-include's downstream fate was never measured. Option B executed: gate-ON diagnostic dump in `chat_stream` right before the agent-launch call (the real chokepoint — one level below the force-include): raw `tool_groups` stamp, allow_bash, turn-contract offered, final disabled_tools, forced_tools, web_ui_state → `/home/samy/.tg_debug.json` (readable from sandbox; no journal needed). Gate pin temporarily 4. NEXT: user push + `./update.sh` (verify PID change) → all 5 buttons ON → send 'list my sessions' → agent reads `.tg_debug.json` next turn → verdict: stamp partial (UI) vs forced-set correct but tools stripped downstream (deeper filter) → fix, remove diagnostic, revert pin 4→3.

**2026-10-18 (tool-groups floor re-land):** crash postmortem + fix. ce6aeb2f rebound the `disabled_tools` closure inside nested `stream_with_save` -> UnboundLocalError every agent run (reverted 2908e02c + d259efc3; user restored service health). Re-landed as 2e3ba498: floor at final consumption via NEW local `tg_final_disabled` (closure read-only), 159/159 green, AST guard test pins the incident. Map backfilled 6 pushed commits (bda6c65c..2e3ba498). Ahead 2, unpushed. NEXT: user push+update.sh+hard-refresh+"list my sessions" -> expect 5/5 -> cleanup pass (remove diagnostic, pins 5->4 / 3->2).
- 2026-10-20 ~00:30 EDT: **Final polish.** Session re-verified from zero: 4-ref sync @ `c87bdfb9`, tree clean, 171 ahead, NEXT(1)+(2) both DONE, Backlog #1 [x], map backfilled (915ab5d4/c87bdfb9), stale `tool_groups_dbg` comment removed from chat.js:2645, buster → `20261020tg2`. Session closes with every bookkeeping channel (map, ROADMAP, skill v1.16.16, memory snapshot) current.
