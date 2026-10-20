# Commit map — `improvements-20261014`

Feature → commit index for the `improvements-20261014` branch, cut 2026-10-14, relative to `upstream/dev` (`a8c147b2`).

- **Keep-current rule:** whenever work is finished and committed to this branch, append the new commit(s) here (new feature group if needed) **and commit the map**. The map can never list the commit that updates it, so `ahead count = entries + 1` is always true — that is normal, not drift.
- Live ahead count (trust this over any number written here): `git rev-list --count upstream/dev..improvements-20261014`
- Regenerate/append after **every work-batch commit** and always regenerate after a rebase (user-odysseus-fork skill, step 4g).
- SHAs are valid **until the next rebase** (a rebase rewrites all of them). One commit per line, oldest → newest within each group. Detail: `git show <sha>`.

## A. Deployment scripts & fork tooling (update.sh / boot.sh / setup.sh)

- `5b485ae3` update.sh: show doomed untracked files before [d] discard (dry-run + confirm)
- `393d7efa` update.sh: offer --force-with-lease push (default) when local commits are ahead of fork
- `dd1528ad` fix: use $REMOTE_NAME in update.sh push warning instead of hardcoded origin
- `3e954dda` Remove port 5053 from service readiness check (old standalone app no longer exists)
- `50a5682b` fix: remove personal hub.service references from update.sh
- `5c750fae` gitignore: block docker-compose-baremetal.* from ever being pushed
- `ad262c33` Fix: auto-detect compose file instead of hardcoding baremetal.samy
- `3a8c3237` Fix: self-reset update.sh before pull to avoid checkout conflict
- `5d94c187` Fix: setup.sh and update.sh now install missing system deps before proceeding
- `a95a6346` Add update.sh and boot.sh deployment scripts
- `c0a83ca4` feat: add setup.sh for first-run friend deployment

## B. Tool policy & model registry

- `5c74b7d2` fix: disable aggressive low-signal tool gate
- `da7c4118` fix: add deepseek-v4 family to known context windows
- `8dae790c` fix: add Kimi model family (k3, k2.7, k2.6, k2.5, k2) to known context windows
- `258e6fd0` fix: add bash to ALWAYS_AVAILABLE tools so it never gets dropped by RAG
- `eb861007` fix: force-include bash in toolset when agent-mode bash toggle is ON
- `53542b72` perf: backport OOM rAF-throttle + stream-delta from PR #4661
- `b60856e9` fix(vision): detect Qwen3.5 as natively multimodal and de-dupe vision model select

## C. Auto-scroll (#5611)

- `5ff068b0` fix: move scrollHistoryInstant after DOM insertion (closes #5611)
- `09442f1a` fix: auto-scroll — restart smooth-scroll when new content arrives between tool calls (closes #5611)
- `676da1da` fix: lower auto-scroll contentGrew threshold 200→20 + post-finish re-check (closes #5611)

## D. Cookbook serve & hwfit

- `bba6bb0d` feat(cookbook): add GPU Layers + Max Tokens serve fields, restore manual cmd
- `790eb144` fix(hwfit): stop clamping multimodal LLMs to 4k context
- `24bdd54b` docs(setup): document Cookbook Serve panel fields and context-clamp behavior
- `de8f430d` fix(cookbook): let live server tasks override stale tombstones in running panel

## E. Vision (VL) pipeline

- `dae9706e` fix(vision): stop VL timeout on reasoning models, raise caps
- `779aee5d` revert(vision): stop forcing enable_thinking=false on VL captions
- `cf81047f` feat(vision): make VL timeout/token caps configurable (settings + localmodel conf)
- `5306a8f3` fix(vision): detect llama.cpp multimodal capability so local vision models get direct image input

## F. Docs home, instance map & spec consolidation

- `3f5d5e9d` docs: restore upstream README; move instance map to docs/instance-map.md
- `d745a7e1` docs: restructure instance map for Improvements branch (2026-08-20)
- `e3e4bd95` docs(instance-map): update date reference to 2026-08-22
- `a583af3e` docs(instance-map): record Qwen vs DeepSeek storage parity + serve command for the thinking-reload fix
- `1308f135` docs(instance-map): record Qwen serve context reduction 85096 -> 56000
- `78848ee1` chore: move personal instance-map.md out of repo (kept in ~/localmodel)
- `7c0db5ef` docs: document agent_stream_timeout_seconds (stream inactivity + per-round wall-clock cap)
- `1a316f87` docs(specs): document Terminus toolset confinement and intent-derived prompt blocks
- `2562751c` docs(specs): consolidate documentation home in specs/
- `92b07194` chore: gitignore specs/instance/ (personal machine-specific planning docs)

## G. Chat core — delete/edit, tab-recovery, KV, upload, resume

- `30b648ba` fix(chat): stamp message row ids on DB-served history and user_message_saved so delete/edit persist
- `496fccef` docs(specs): document chat message row-id contract (dataset.dbId) in specs/chat.md
- `1c214181` fix(chat): delete the whole turn, not just the first AI bubble
- `8c2e5bec` fix(chat): don't abort healthy streams during prefill (tab-recovery)
- `bbaf66be` chat: probe the server before tab-recovery aborts a frozen stream
- `f48d9660` fix(chat): keep KV prefix byte-stable across turns (#4317)
- `21fa94cf` fix(chat): show the specific upload rejection reason once instead of a generic + specific pair
- `33203f56` fix(chat): restore streaming state on resume so Stop survives a mid-stream refresh (#6233)
- `8ab7c993` test(chat): extend resumeStream sandboxes with streaming-state symbols (3 sandboxes)
- `ba1ad45c` fix(chat): render stored reasoning on reload for all turn shapes
- `beb7296a` test(routing): hermetic skill library so agent-loop tests don't hit the approval gate

## H. Documents toggle & bash toggle

- `74bb6624` Add Documents toolbar toggle + honor ticked bash on light auto-escalation
- `00586fe7` docs: document Documents toolbar toggle + ticked-bash exemption
- `1a8d3c7b` fix(chat): honor ticked bash toggle in the explicit-web-intent strip

## I. Search — SearXNG & FlareSolverr

- `d38f45cd` Search: detect degraded SearXNG responses and merge fallback results
- `b041c3b3` docs(.env.example): document SEARXNG_GENERAL_ENGINES engine-pinning override
- `c59837f5` feat(search): FlareSolverr-backed SearXNG engines for CAPTCHA-blocked search
- `008db731` test(search): pre-commit private-data guard + SearXNG engine tests
- `1a21106c` docs(specs): document FlareSolverr SearXNG engines in search spec
- `094098ff` test(search): check every docker-compose file by name pattern, not a hardcoded one

## J. Voice mode (TTS / STT / VAD, Phases 1–4)

- `817c18bd` feat(tts): add Piper local-CPU provider with voice selection
- `08d311cb` docs(specs): document Piper TTS provider and restored settings card (specs/speech.md)
- `ac16a26a` feat(voice): add voice mode — hands-free dictation over a VAD WebSocket (Phase 2)
- `c9e116f1` docs(specs): document voice mode — VAD WebSocket, STT settings, activation
- `3fe7a9d7` fix(voice): audit hardening — keep the model load off the event loop
- `d70fb747` docs(specs): voice-mode audit — status endpoint contract (settings-only, model check at WS connect)
- `a6d4f181` feat(voice): full loop — auto-send, spoken replies, barge-in (Phase 3)
- `bc0375f7` feat(voice): mic sensitivity — expose the Silero VAD threshold
- `e74835b2` fix(voice): TTS reads only the reply, never the model's thinking
- `54efb57e` fix(voice): TTS off = silence now; barge-in at speech onset, not the transcript
- `ac29ed8b` fix(voice): TTS end-flush no longer reads the model's thinking
- `700b4b2b` fix(voice): VAD utterance audio is the original stream, not spliced
- `1b28ee0e` docs(specs): speech.md — VAD audio-integrity contract + protocol/status corrections
- `72a95ce9` fix(voice): audit pass — mic double-capture, TTS cache cap, VAD config clamp
- `2fa6c130` perf(voice): STT/TTS off the event loop; drop the STT temp file
- `9ea3a9f1` chore(voice): audit round 4 — key the client TTS cache by settings, drop dead code, fix stale comments
- `15e5c2c7` docs(speech): sync spec to implemented state (Phase 4 drift review)
- `07f91402` settings UI: Piper voice downloader (name or .onnx link) + auto-audition
- `0254ad3d` docs(speech): document POST /api/tts/voices/add + the settings UI voice downloader
- `f8e0e679` voice: echo gate — drop mic-captured TTS echo from the transcript path (Phase 3.7)
- `5b774702` voice: audit round 5 — echo-gate flag consumption, teardown reset, downloader SSRF + filename hardening
- `75d41fd4` docs(speech): round-5 contracts — downloader SSRF + name-charset guard, empty-transcript echo-gate semantics
- `4f43bfbc` tooling(voice): audit verifier, make target, detached bg wrapper
- `659a1715` feat(ui): voiceMode — guarded native-host bridge hook (APK v2.9 keep-alive)
- `0b56ae9a` feat(tts): delete Piper voice (UI button + DELETE /api/tts/voices/delete)
- `2c227891` docs(tts): document POST /api/tts/voices/delete in speech.md route behavior
- `6ad2e918` Voice mode: gate the barge-in abort on TTS-audible onsets (phantom-onset cancel fix)

## K. Strict chat mode

- `4c966269` chat: strict chat mode — server-enforced conversation-only turns
- `03f7eb93` chat: strict mode fixes — phone override wins, pill position via existing CSS
- `670b4ca3` fix(chat): strict mode — guard remaining auto-escalations + enforce MCP-off end-to-end
- `294ceaa4` fix(chat): honor ?strict_chat=1 in the send path (phone strict sessions were running as agent)
- `d10ad733` fix(strict): strict sends died silently — const isPlanMode (client) + missing strict_chat_disabled_tools import (server)
- `6f267eb0` fix(cache): index.html chat.js refs missed the strict-fix cache buster
- `87ab6200` fix(chat): phone Agent turns were pinned to strict chat by the send path

## L. SSE keepalive

- `11ed6f13` sse: keepalive on main chat/agent streams (proxy-read-timeout fix)
- `1928f283` fix(sse): keepalive close-path cancel semantics (await bool + swallowed upstream cancel)

## M. DB hardening

- `2c7d0e75` db: add red-handed write-transaction leak detector (core.db_leak)
- `13f4e95c` db: enable WAL + 30s busy_timeout for SQLite (leaked-lock resilience)

## N. Empty assistant turns

- `8526cc31` fix(chat): keep empty assistant turns out of outbound model context
- `95eb18bb` docs(specs): document empty-assistant-turn filter + Moonshot empty-content rejection

## O. Loose fixes

- `98c86903` fix: two silent NameError bugs (caldav exdate import + cookbook HF error-log)

## P. Post-rebase integration (2026-10-13/14)

- `d332e859` test: re-aim source guards at the restructured stream paths (post-rebase)
- `38c86045` fix(post-rebase): restore branch-specific behavior on the upstream rebuild
- `9ac7ae2c` docs(env): document the three speech-model env knobs the reference was missing
- `36359ef8` docs(specs): commit-map — feature-to-SHA index (self-referencing: documents all commits up to the one below it)
- `dd900647` feat(authority): opt-in CONTRACT_CORE_TOOLS recovery grants for unknown intent (ODYSSEUS_CORE_TOOL_GRANTS)
- `605db810` docs(specs): commit-map — add authority opt-in + map-commit entries (105 documented)
- `01cece53` feat(authority): bash button is the only bash gate; opt-out server-home launch guard (ODYSSEUS_ALLOW_SERVER_HOME_LAUNCH)
- `15542d9f` feat(completion): ODYSSEUS_COMPLETION_GATE=0 bypasses the whole gate (replaces non-functional LIVE_ANSWER_STREAM flag)
- `9164b030` fix(completion): bypass rewrite keeps terminal bubble = streamed prose (transcript-wall fix — the terminal final_response carried the full round transcript incl. tool output, so any tool turn collapsed into one wall)
- `59015d37` docs(specs): ROADMAP.md — standing work tracker
- `f738b263` feat(completion): opt-out live answer streaming (ODYSSEUS_LIVE_ANSWER_STREAM) (state, backlog, active issue; update on state change)
- `f77a0359` docs(specs): commit-map — ROADMAP entry
- `51a5ab5d` test(authority): keep fork env vars hermetic in structural tests; document fork env vars in env reference
- `3ed86515` docs(specs): commit-map + roadmap — full-suite results, 12 fork-caused failures fixed (51a5ab5d)
- `383c6ca7` feat(authority): bash button also gates workspace file tools (read/write/edit/patch/glob/grep); ODYSSEUS_SHOW_THINKING=1 restores Qwen thinking stream (fork opt-outs, default upstream)
- `f4c4681c` fix(chat): ODYSSEUS_SHOW_THINKING also bypasses route-level thinking_mode=off gates (tool-profile models force thinking_mode=off; loop gate alone was insufficient — thinking verified live by user 2026-10-16)
- `c11e7d12` docs(specs): ROADMAP — tool-group buttons design pass (verified seam map + impl plan)
- `ca25a35c` docs(specs): commit-map + ROADMAP status — design commit c11e7d12
- `175073ca` feat(authority): tool-group buttons — ODYSSEUS_TOOL_GROUPS-gated per-group grant (BUTTON_TOOLS map)
- `f0ba4128` docs(specs): commit-map + ROADMAP status — slice 1/4 (175073ca)
- `ae57e6be` feat(routes): tool-group buttons — per-group stamp + selection floor (slice 2/4)
- `48e9e805` docs(specs): commit-map + ROADMAP — tool-group buttons slice 2/4 (ae57e6be)
- `7d028f48` feat(ui): tool-group buttons — data-driven row, tool_groups stamp (slice 3/4)
- `6318fba0` docs(specs): commit-map + ROADMAP — slice 3/4 (7d028f48)
- `83185b20` test(fork): tool-group buttons — gate-ON grant tests + route/UI source pins (slice 4/4)
- `be4573cd` docs(specs): commit-map + ROADMAP — tool-group buttons slice 4/4 (83185b20); feature complete
- `6d255cf2` docs(specs): ROADMAP — pre-push double-check PASSED (all 4 slices verified, 708/708 targeted)

- `33de6e61` docs(specs): commit-map gap fix + push-name rule check + dated-branch sync to alias
- `d4925ca4` fix(tools): tick-wins — ceiling for unticked groups + force-include after clobbers (Backlog #1, slice 2.5)
- `219f0932` docs(specs): commit-map (+33de6e61, +d4925ca4) + ROADMAP — tick-wins fix, E2E root cause
- `2236c70e` chore(tools): temporary tick-wins E2E diagnostic — .tg_debug.json dump in chat_stream (gate-ON; gate pin 3→4, revert with it)
- `95422d48` — `fix(tools): diagnostic writes error into .tg_debug.json (Backlog #1)`

- `d76fe821` — fix(tool-groups): self-healing stamp (button state = truth) + tool_groups_dbg + cache-buster 20261018tgfix
- `bda6c65c` — docs(specs): commit-map + ROADMAP for self-healing stamp fix (d76fe821)
- `ce6aeb2f` — fix(tool-groups): tick-wins floor at final consumption point (Backlog #1)
- `7ff72f50` — docs(specs): commit-map + ROADMAP — E2E dump verdict + consumption-point floor (e15099c4)
- `d259efc3` — Revert "docs(specs): commit-map + ROADMAP — E2E dump verdict + consumption-point floor (e15099c4)"
- `2908e02c` — Revert "fix(tool-groups): tick-wins floor at final consumption point (Backlog #1)"
- `2e3ba498` — fix(tool-groups): tick-wins floor at final consumption, closure-safe (re-land)

- `abd2713a` fix(tool-groups): rebuild tool_policy floored — agent honors policy, not kwarg — turn-contract path rebuilt tool_policy from the un-floored set. NEW LOCAL tg_final_policy; AST guard extended to tool_policy. 159/159.

- `a360fd71` docs(specs): commit-map + ROADMAP — tool_policy floored rebuild (abd2713a)
- `934b8366` fix(tool-groups): tick-wins at the contract boundary — offer button-on groups via contract.offered (frozen TurnContract written via object.__setattr__)
- `60a120a0` docs(specs): commit-map + ROADMAP — contract-boundary tick-wins (934b8366)
- `ca3fda9e` Revert of 60a120a0 (rollback cycle 2026-10-19; superseded by 8184bebf re-land)
- `8184bebf` fix(tool-groups): write frozen turn contract via object.__setattr__ (934b8366 follow-up)
- `1fe20ffc` chore(tool-groups): remove tick-wins E2E diagnostic + contract-boundary guard tests (Backlog #1 closeout)
- `af8c542c` docs(specs): commit-map + ROADMAP — diagnostic removal + contract guard + Backlog #1 done (1fe20ffc)
- `65931be8` docs(specs): ROADMAP — record pending memory snapshot update (manage_memory denied by tool authority)
- `b5a1e70d` docs(specs): commit-map + ROADMAP — final backfill (af8c542c/65931be8) + closeout verification entry
- `813c982d` feat(authority): manage_memory core floor under ODYSSEUS_CORE_TOOL_GRANTS (memory granted every request, like ask_user; flag OFF = upstream floor)
- `ff5e090f` docs(specs): ROADMAP — resolve restart-pending item (floor verified live) + closeout log entry
- `915ab5d4` docs(specs): stall-investigation findings + map backfill (ff5e090f) + NEXT(2) memory-dispatch note
- `c87bdfb9` docs(specs): resolve NEXT(2) — memory snapshot updated, skill v1.16.16, 4-ref sync at 915ab5d4
