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

## Status (2026-10-16, ~06:30 EDT)
- **Running (pending restart):** `improvements-20261014` @ `1879e7de`
  (rebased + all fork fixes + full-suite test-hermeticity fix + live answer
  streaming opt-out `ODYSSEUS_LIVE_ANSWER_STREAM`, commit `f738b263`;
  == `Improvements` alias == `touzenesmy/Improvements`) — switched 2026-10-15
  ~19:05 EDT via `./update.sh` after bwrap install; bash containment verified
  ENFORCING (see Active issue, now RESOLVED).
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
- [x] **1. Install bwrap + switch to `improvements-20261014` + verify** — DONE 2026-10-15 (bwrap 0.12.0; enforcing receipts verified). Voice/strict smoke checks: [x] bash / [ ] voice / [ ] strict.
- [x] **2. Full test suite on the 2014 branch** — DONE 2026-10-16 (host run,
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
- [ ] **3. Five open upstream PRs** — #6226 #6230 #6232 #6234 #6236. Watch reviews; fold into the next rebase.
- [ ] **4. Known upstream flake** — kimi full-suite failure (parked since before the rebase; not ours).
- [ ] **5. Drop-check on next rebase:** `f738b263` (live answer streaming opt-out),
  `dd900647` (core-tool grants), `01cece53` (bash-button gate + launch opt-out),
  and `51a5ab5d` (test hermeticity + env-reference entries) — drop any fork
  patch upstream has since fixed properly. Upstream +18 commits since 2026-10-16
  check touched none of `authority.py`/`process_resources.py`/`containment.py`/
  `update.sh`; `afecd44d` (approve-once runs ungranted bash/python) is upstream
  moving in our direction in the *approvals* subsystem — re-check on rebase.
- [ ] **6. Prune legacy branches** (only after the service has run a few days on the 2014 branch): `Improvements-backup` (00196069), `Improvements-backup-20261012`, `Improvements-backup-20261012-2`, `pre-squash-improvements-20260825`. Dated-branch convention makes these redundant.

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
