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

## Status (2026-10-15, ~19:30 EDT)
- **Running:** `improvements-20261014` @ `f77a0359` (rebased + all fork fixes;
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
- **Sandbox contract (verified live 2026-10-15):** assistant commands run under
  bwrap, mode enforcing. `/workspace` (= user home) rw; repo `.venv` and
  `/usr`/`/etc` read-only; network inherited; no sudo/systemctl from inside.
  Use `cd /workspace/odysseus` inside (not `~` — host home is not mounted as `~`).

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
- [ ] **2. Full test suite on the 2014 branch** (fresh run; the pre-rebase baseline suite was 13,868 passed / 60 failed, 59 upstream pre-existing).
- [ ] **3. Five open upstream PRs** — #6226 #6230 #6232 #6234 #6236. Watch reviews; fold into the next rebase.
- [ ] **4. Known upstream flake** — kimi full-suite failure (parked since before the rebase; not ours).
- [ ] **5. Drop-check on next rebase:** `dd900647` (core-tool grants) and the two 2026-10-14/15 patches — drop any fork patch upstream has since fixed properly.
- [ ] **6. Prune legacy branches** (only after the service has run a few days on the 2014 branch): `Improvements-backup` (00196069), `Improvements-backup-20261012`, `Improvements-backup-20261012-2`, `pre-squash-improvements-20260825`. Dated-branch convention makes these redundant.

## Conventions (pointers — details in the fork skill + the files)
- **Dated branches:** `improvements-<YYYYMMDD>` per rebase; `Improvements` is a
  moving alias (`git branch -f Improvements improvements-<date>`); the previous
  dated branch IS the backup. `update.sh`'s `BRANCH="Improvements"` never changes.
- **Commit map:** `specs/commit-map.md` — feature → SHA, keep current (append +
  commit whenever branch work is committed; regenerate fully after a rebase).
- **This roadmap:** update Status + Backlog on state change, commit + push.
- **Skills/memory:** point here; volatile values stay in this file.

## Session log
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
