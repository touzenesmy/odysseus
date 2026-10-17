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

## Status (2026-10-17, ~04:40 EDT)
- **Branch `Improvements` = `improvements-20261014` = remote @ `b496cb6a`**
  — rebased + all fork fixes, PUSHED + synced (tree clean). Since
  `9164b030`: `821c55fd` (stall diagnosis), `383c6ca7` (bash button now ALSO
  gates workspace file tools read/write/edit/patch/glob/grep — file tools no
  longer denied by text-guessing while bash is ON; + `ODYSSEUS_SHOW_THINKING=1`
  restores the Qwen 3.8 thinking stream upstream hides), `f4c4681c` (thinking
  fix PART 2: tool-profile models force `thinking_mode=off` so the ROUTE
  gates drop thinking too — loop gate alone was insufficient; all 4 route
  gates now honor the flag). Both are fork opt-outs, default upstream,
  drop-check at next rebase. `.env` flags: CORE_TOOL_GRANTS=1,
  SERVER_HOME_LAUNCH=1, COMPLETION_GATE=0, SHOW_THINKING=1 (line 29).
- **Running service:** restarted 2026-10-16 ~20:00 EDT at `f4c4681c`.
  **THINKING STREAM CONFIRMED LIVE by user (2026-10-16 22:05 EDT)** —
  "Oh, I see thinking now!" Batch closed: transcript-wall fix, completion
  gate bypass, file-tool button gate, thinking stream all working.
- **Known behaviors (diagnosed, verified in app.log + chat_messages):**
  1. "Stalls" are mostly SLOW turns (200–285s/round, 27B q3 on 16GB VRAM)
     with thinking hidden → invisible work. FIXED in code by SHOW_THINKING
     (pending push+restart).
  2. `[Cancelled]` errors = rebase-born close-path cancel semantics
     (`11ed6f13`+`1928f283`): client disconnect (tab switch, phone lock,
     refresh, stop) cancels the running turn. RULE: no refresh/lock/tab-
     switch mid-turn; if cancelled, just resend.
  3. Wall-of-text = context overload (>70% start). RULE: fresh session per
     work block, ≤10 tool calls per turn, hand off here at ~70%.
- **`improvements-20261012`** @ `207df1c0` (pre-rebase baseline) — rollback
  target, untouched.
- Service `odysseus` (systemd, uvicorn :7000); host PID not visible from the
  assistant's sandbox (PID namespace) — query it with
  `systemctl show odysseus -p MainPID`. Model is the separate `boot-model` unit
  (llama-server :8050).
- `.env` flags in place (both needed on the 2014 branch):
  `ODYSSEUS_CORE_TOOL_GRANTS=1` (authority recovery grants) and
  `ODYSSEUS_ALLOW_SERVER_HOME_LAUNCH=1` (control-state guard opt-out).
  `ODYSSEUS_LIVE_ANSWER_STREAM=1` (stream answer prose live instead of the
  completion gate holding it until the turn ends — restores pre-wave-3 UX).
- **Sandbox contract (verified live 2026-10-15):** assistant commands run under
  bwrap, mode enforcing. `/workspace` (= user home) rw; repo `venv` (named
  `venv`, not `.venv`) and `/usr`/`/etc` read-only; network inherited; no
  sudo/systemctl from inside.
  Use `cd /workspace/odysseus` inside (not `~` — host home is not mounted as `~`).
  `git push` inside needs `GIT_SSH_COMMAND="ssh -F /dev/null -o IdentitiesOnly=yes
  -o IdentityFile=~/.ssh/id_ed25519"` — plain ssh trips over host `/etc/ssh` perms.

## RESOLVED 2026-10-15 ~19:10 EDT — bash containment blocked the 2014 branch
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
- [ ] **1. Tool-group buttons — replace RAG *guessing* for core tool families (TOP PRIORITY, user directive 2026-10-17).**
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
- **2026-10-15 (04:26):** Rolled back to `improvements-20261012` (bash
  containment unavailable). Root cause: `bwrap` missing (containment.py
  enforcing mode, bubblewrap is the only filesystem+process_tree mechanism).
  This document created as the standing work tracker.
- **2026-10-14:** Rebase of the improvement branch onto upstream (540 commits),
  post-rebase integration fixes, authority work: `dd900647` core-tool opt-in
  grants, `01cece53` bash-button-as-only-gate + `ODYSSEUS_ALLOW_SERVER_HOME_LAUNCH`
  opt-out, `update.sh` discard guard, dated-branch convention, commit map.
  Details: `specs/instance-map.md` + fork skill session ledger.

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
