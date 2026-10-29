# Commit map — `ImprovementsDev`

Feature → commit index for the `ImprovementsDev` work branch (port target), relative to its
chunk-0 base `f786bcdf` (2026-10-21). Format: `- `dev-sha` ← `scaffold-sha(s)` subject`.
Single-SHA cherry-picks carry the original `(cherry picked from commit …)` trailer;
multi-SHA rows are ADAPTED ports (see PORT-GUIDE §D for chunk boundaries and §B for
per-commit classification).

- **Keep-current rule:** whenever work is finished and committed to this branch, append the new
  commit(s) here **and commit the map**. The map can never list the commit that updates it, so
  `ahead count = entries + 1` is always true — that is normal, not drift.
- Live ahead count: `git rev-list --count f786bcdf..HEAD`
- SHAs are valid **until the next rebase** (a rebase rewrites all of them). One commit per line,
  oldest → newest within each group. Detail: `git show <sha>`.
- Port source: the frozen `improvements-20261014` branch (its own `specs/commit-map.md` there lists
  the 173 pre-port SHAs; this map lists the post-port SHAs — keep both current).

## A. Deployment scripts & fork tooling (update.sh lineage merged as one adapt commit)

- `d2791f64` ← `a95a6346 5d94c187 3a8c3237 ad262c33 50a5682b dd1528ad 393d7efa 5b485ae3` feat(deploy): merge update.sh lineage + boot.sh + setup.sh system-deps (PORT-GUIDE group A adapt — the 8-commit update.sh lineage lands as one merge onto the base's update.sh)
- `302d2ff9` ← `c0a83ca4` feat: add setup.sh for first-run friend deployment
- `19a2b7f1` ← `3e954dda` Remove port 5053 from service readiness check (old standalone app no longer exists)
- `be60a274` ← `5c750fae` gitignore: block docker-compose-baremetal.* from ever being pushed

## B. Tool policy & model registry

- `5ac969e4` ← `5c74b7d2` fix: disable aggressive low-signal tool gate
- `1a3008ee` ← `da7c4118` fix: add deepseek-v4 family to known context windows
- `58e5ada5` ← `8dae790c` fix: add Kimi model family (k3, k2.7, k2.6, k2.5, k2) to known context windows
- `c1975a97` ← `258e6fd0` fix: add bash to ALWAYS_AVAILABLE tools so it never gets dropped by RAG
- `0492367d` ← `eb861007` fix: force-include bash in toolset when agent-mode bash toggle is ON
- `eac0c24e` ← `53542b72` perf: backport OOM rAF-throttle + stream-delta from PR #4661
- `7921cbe7` ← `b60856e9` fix(vision): detect Qwen3.5 as natively multimodal and de-dupe vision model select

## C. Auto-scroll (#5611)

- `aae43374` ← `5ff068b0` fix: move scrollHistoryInstant after DOM insertion (closes #5611)
- `99614580` ← `09442f1a` fix: auto-scroll — restart smooth-scroll when new content arrives between tool calls (closes #5611)
- `918d9e94` ← `676da1da` fix: lower auto-scroll contentGrew threshold 200→20 + post-finish re-check (closes #5611)

## D. Cookbook serve & hwfit

- `f56f4ebb` ← `bba6bb0d` feat(cookbook): add GPU Layers + Max Tokens serve fields, restore manual cmd
- `130cc012` ← `790eb144` fix(hwfit): stop clamping multimodal LLMs to 4k context
- `c01bdd91` ← `24bdd54b` docs(setup): document Cookbook Serve panel fields and context-clamp behavior
- `96a07020` ← `de8f430d` fix(cookbook): let live server tasks override stale tombstones in running panel

## E. Vision (Qwen3.5 / LM Studio)

- `4cb83018` ← `dae9706e` fix(vision): stop VL timeout on reasoning models, raise caps
- `f23f34e3` ← `779aee5d` revert(vision): stop forcing enable_thinking=false on VL captions
- `22f983a4` ← `cf81047f` feat(vision): make VL timeout/token caps configurable (settings + localmodel conf)
- `1efa330c` ← `5306a8f3` fix(vision): detect llama.cpp multimodal capability so local vision models get direct image input

## F. Docs home & instance map

- `3f4832b9` ← `3f5d5e9d` docs: restore upstream README; move instance map to docs/instance-map.md
- `d128be20` ← `d745a7e1` docs: restructure instance map for Improvements branch (2026-08-20)
- `ff577adc` ← `e3e4bd95` docs(instance-map): update date reference to 2026-08-22
- `9bb503bc` ← `a583af3e` docs(instance-map): record Qwen vs DeepSeek storage parity + serve command for the thinking-reload fix
- `21e0946b` ← `1308f135` docs(instance-map): record Qwen serve context reduction 85096 -> 56000
- `89b45a51` ← `78848ee1` chore: move personal instance-map.md out of repo (kept in ~/localmodel)
- `cfcc3255` ← `7c0db5ef` docs: document agent_stream_timeout_seconds (stream inactivity + per-round wall-clock cap)
- `6c8b690d` ← `1a316f87` docs(specs): document Terminus toolset confinement and intent-derived prompt blocks
- `97c073de` ← `2562751c` docs(specs): consolidate documentation home in specs/
- `47f00fc2` ← `92b07194` chore: gitignore specs/instance/ (personal machine-specific planning docs)

## G. Chat core (KV #4317, Documents toggle, tab recovery, delete whole turn, …)

- `4233aa41` ← `f48d9660` fix(chat): keep KV prefix byte-stable across turns (#4317)
- `9ead135e` ← `74bb6624` Add Documents toolbar toggle + honor ticked bash on light auto-escalation
- `4cc01d1b` ← `00586fe7` docs: document Documents toolbar toggle + ticked-bash exemption
- `dc273a8a` ← `1a8d3c7b` fix(chat): honor ticked bash toggle in the explicit-web-intent strip
- `0258d758` ← `33203f56` fix(chat): restore streaming state on resume so Stop survives a mid-stream refresh (#6233)
- `bea53e08` ← `8ab7c993` test(chat): extend resumeStream sandboxes with streaming-state symbols (3 sandboxes)
- `c9bd8751` ← `21fa94cf` fix(chat): show the specific upload rejection reason once instead of a generic + specific pair
- `3a79fb36` ← `30b648ba` fix(chat): stamp message row ids on DB-served history and user_message_saved so delete/edit persist
- `2cd1210d` ← `496fccef` docs(specs): document chat message row-id contract (dataset.dbId) in specs/chat.md
- `f154c288` ← `1c214181` fix(chat): delete the whole turn, not just the first AI bubble
- `00995492` ← `ba1ad45c` fix(chat): render stored reasoning on reload for all turn shapes
- `faf7a5ae` ← `beb7296a` test(routing): hermetic skill library so agent-loop tests don't hit the approval gate
- `7788d498` ← `8c2e5bec` fix(chat): don't abort healthy streams during prefill (tab-recovery)
- `627d3da7` ← `bbaf66be` chat: probe the server before tab-recovery aborts a frozen stream

## H. Search (degraded SearXNG, FlareSolverr engines)

- `da3b8fe4` ← `d38f45cd` Search: detect degraded SearXNG responses and merge fallback results
- `88c1949d` ← `b041c3b3` docs(.env.example): document SEARXNG_GENERAL_ENGINES engine-pinning override
- `863bce1e` ← `c59837f5` feat(search): FlareSolverr-backed SearXNG engines for CAPTCHA-blocked search
- `83b8b854` ← `008db731` test(search): pre-commit private-data guard + SearXNG engine tests
- `7ab02d59` ← `094098ff` test(search): check every docker-compose file by name pattern, not a hardcoded one
- `f36635c6` ← `1a21106c` docs(specs): document FlareSolverr SearXNG engines in search spec

## I. Voice mode Phases 1–4

- `cb8e57be` ← `817c18bd` feat(tts): add Piper local-CPU provider with voice selection
- `ecdbcf90` ← `08d311cb` docs(specs): document Piper TTS provider and restored settings card (specs/speech.md)
- `642c129a` ← `ac16a26a` feat(voice): add voice mode — hands-free dictation over a VAD WebSocket (Phase 2)
- `00a22779` ← `c9e116f1` docs(specs): document voice mode — VAD WebSocket, STT settings, activation
- `a067c7d9` ← `3fe7a9d7` fix(voice): audit hardening — keep the model load off the event loop
- `3b6a10f9` ← `d70fb747` docs(specs): voice-mode audit — status endpoint contract (settings-only, model check at WS connect)
- `353d0e3e` ← `a6d4f181` feat(voice): full loop — auto-send, spoken replies, barge-in (Phase 3)
- `be45b649` ← `bc0375f7` feat(voice): mic sensitivity — expose the Silero VAD threshold
- `48553494` ← `e74835b2` fix(voice): TTS reads only the reply, never the model's thinking
- `f7feb0d1` ← `54efb57e` fix(voice): TTS off = silence now; barge-in at speech onset, not the transcript
- `9886461c` ← `ac29ed8b` fix(voice): TTS end-flush no longer reads the model's thinking
- `3f57578f` ← `700b4b2b` fix(voice): VAD utterance audio is the original stream, not spliced
- `5b08f5e1` ← `1b28ee0e` docs(specs): speech.md — VAD audio-integrity contract + protocol/status corrections
- `85b1db0c` ← `72a95ce9` fix(voice): audit pass — mic double-capture, TTS cache cap, VAD config clamp
- `de90f7fc` ← `2fa6c130` perf(voice): STT/TTS off the event loop; drop the STT temp file
- `26971d1e` ← `9ea3a9f1` chore(voice): audit round 4 — key the client TTS cache by settings, drop dead code, fix stale comments
- `32399ab3` ← `15e5c2c7` docs(speech): sync spec to implemented state (Phase 4 drift review)
- `7023ba28` ← `07f91402` settings UI: Piper voice downloader (name or .onnx link) + auto-audition
- `b23033b8` ← `0254ad3d` docs(speech): document POST /api/tts/voices/add + the settings UI voice downloader
- `3ee25837` ← `f8e0e679` voice: echo gate — drop mic-captured TTS echo from the transcript path (Phase 3.7)
- `03bdbdc8` ← `5b774702` voice: audit round 5 — echo-gate flag consumption, teardown reset, downloader SSRF + filename hardening
- `fc313568` ← `75d41fd4` docs(speech): round-5 contracts — downloader SSRF + name-charset guard, empty-transcript echo-gate semantics
- `5eb60ff7` ← `4f43bfbc` tooling(voice): audit verifier, make target, detached bg wrapper
- `cdec4106` ← `659a1715` feat(ui): voiceMode — guarded native-host bridge hook (APK v2.9 keep-alive)
- `f62398c4` ← `0b56ae9a` feat(tts): delete Piper voice (UI button + DELETE /api/tts/voices/delete)
- `c9d9066e` ← `2c227891` docs(tts): document POST /api/tts/voices/delete in speech.md route behavior
- `c309b574` ← `6ad2e918` Voice mode: gate the barge-in abort on TTS-audible onsets (phantom-onset cancel fix)

## J. SSE keepalive

- `ba4b663c` ← `11ed6f13` sse: keepalive on main chat/agent streams (proxy-read-timeout fix)
- `5f3cffdc` ← `1928f283` fix(sse): keepalive close-path cancel semantics (await bool + swallowed upstream cancel)

## K. DB hardening (WAL, leak detector)

- `9d2ddf52` ← `2c7d0e75` db: add red-handed write-transaction leak detector (core.db_leak)
- `aa567c60` ← `13f4e95c` db: enable WAL + 30s busy_timeout for SQLite (leaked-lock resilience)

## L. Empty assistant turns / context compaction

- `71fad2a7` ← `8526cc31` fix(chat): keep empty assistant turns out of outbound model context
- `3c3a71cb` ← `95eb18bb` docs(specs): document empty-assistant-turn filter + Moonshot empty-content rejection

## M. NameError fixes (caldav exdate, cookbook HF log)

- `6b6cc102` ← `98c86903` fix: two silent NameError bugs (caldav exdate import + cookbook HF error-log)

## N. env-knob docs

- `13f9dab9` ← `9ac7ae2c` docs(env): document the three speech-model env knobs the reference was missing

## P2. Authority cluster & tool-group buttons (Chunk 2)

- `7eef013e` ← `dd900647` feat(authority): opt-in CONTRACT_CORE_TOOLS recovery grants for unknown intent (ODYSSEUS_CORE_TOOL_GRANTS)
- `476780e9` ← `01cece53` feat(authority): bash button is the only bash gate; opt-out server-home launch guard (ODYSSEUS_ALLOW_SERVER_HOME_LAUNCH)
- `bd3947cd` ← `51a5ab5d` test(authority): keep fork env vars hermetic in structural tests; document fork env vars in env reference
- `ce97546f` ← `383c6ca7` feat(authority): bash button also gates workspace file tools; ODYSSEUS_SHOW_THINKING restores Qwen thinking stream (fork opt-outs, default upstream)
- `a07b64a2` ← `175073ca` feat(authority): tool-group buttons — ODYSSEUS_TOOL_GROUPS-gated per-group grant (BUTTON_TOOLS map)
- `ed4c541c` ← `f4c4681c` feat(chat): ODYSSEUS_SHOW_THINKING also bypasses route-level thinking_mode=off gates
- `42f9a83e` ← `813c982d` feat(authority): manage_memory core floor under ODYSSEUS_CORE_TOOL_GRANTS
- `7b4ddb66` ← `ae57e6be d4925ca4 d76fe821 ce6aeb2f 2e3ba498 abd2713a 934b8366 8184bebf 1fe20ffc` (+static `7d028f48`, +tests `83185b20`) — ADAPTED route cluster: stamp + floor + forced-include + frozen-contract rewrite; strict_chat refs re-anchored (Chunk 3 feature, absent on new base); static lands at final state buster 20261020tg2; RE-VERIFY re-aim of the web-intent bash-guard source pin (multi-line condition on new base)
- `79b3d3f8` — test(tool-groups): §C.2 dedicated matrix — tool-group grants × afecd44d approve-once (10 rows; NEW coverage, no Scaffold origin)

## K. Strict chat mode (Chunk 3)

- `12ca5a64` ← `4c966269` chat: strict chat mode — server-enforced conversation-only turns
- `56b3768f` ← `03f7eb93` chat: strict mode fixes — phone override wins, pill position via existing CSS
- `5b57419d` ← `670b4ca3` fix(chat): strict mode — guard remaining auto-escalations + enforce MCP-off end-to-end
- `8081a7d7` ← `294ceaa4` fix(chat): honor ?strict_chat=1 in the send path (phone strict sessions were running as agent)
- `6de51be2` ← `d10ad733` fix(strict): strict sends died silently — const isPlanMode (client) + missing strict_chat_disabled_tools import (server)
- `b0779827` ← `87ab6200` fix(chat): phone Agent turns were pinned to strict chat by the send path
- (Scaffold `6f267eb0` — fix(cache): index.html chat.js buster parity — landed as an **empty pick**: the new base's strict cluster already carried final-state busters, and the full 23-file parity set was bumped to `20261023parity1` in the P1 restore below.)

## P1. Post-rebase restore (Chunk 3, ADAPTED onto the new base)

- `84ccb03e` ← `d332e859` test: re-aim source guards at the restructured stream paths (post-rebase)
- `6a01e352` ← `38c86045` fix(post-rebase): restore branch-specific behavior on the upstream rebuild (ADAPTED — models.py empty-turn keep, search _call_provider seam, agent_loop route_tools-None guard, 23-file buster parity → `20261023parity1`, dead-code drop, test re-aims)

## P3. Completion streaming (Chunk 3)

- `cda4db89` ← `f738b263` feat(completion): opt-out live answer streaming (ODYSSEUS_LIVE_ANSWER_STREAM)
- `c5914a15` ← `15542d9f` feat(completion): ODYSSEUS_COMPLETION_GATE=0 bypasses the whole gate (replaces non-functional LIVE_ANSWER_STREAM flag; per-request read, upstream default unchanged)
- `f27ca5c6` ← `9164b030` fix(completion): bypass rewrite keeps terminal bubble = streamed prose (transcript wall fix)

ABANDON (5, superseded within Scaffold — never ported): `2236c70e 95422d48 2908e02c d259efc3 ca3fda9e` (net-zero E2E diagnostic + its reverts; fixes re-landed as 2e3ba498 / 934b8366+8184bebf, which ARE ported above).

## Dev-only (no Scaffold origin)

- `ab46aa94` docs(specs): ROADMAP moved to ImprovementsDev as the live port tracker (chunk 1 in progress)
- `f3b1aea2` test: re-aim 3 source-pinned harnesses at the post-security base (chunk 1 RE-VERIFY; behavior unchanged)
- `9bd70302` docs: chunk 1 complete on ImprovementsDev (346/346 gate green) + ROADMAP tracker + guide filename fix
- `ae2b6030` docs(specs): P4 backfill — ImprovementsDev commit-map (post-port SHAs) + ROADMAP chunk-2-complete status
- `add86ba3` — fix(search): drop time_range before reporting empty — silent zero-row engines (post-smoke, dev-only; SearXNG time-range-agnostic engines return 0 rows)
- `4532de56` — fix(voice): resume AudioContext on the mic-permission gesture path (post-smoke, dev-only; first-click-dead mic fix)
- `ae12d8f7` — chore(static): bump voiceMode.js buster → 20261022micresume1 (cache invalidation for the voice fix)
- `0a9dc2e0` docs(specs): ROADMAP + commit-map — post-smoke search/voice fixes (add86ba3, 4532de56, ae12d8f7)
- `3ee615e7` docs(specs): ROADMAP — upstream/dev rewritten (7 behind incl. incident-CA TLS series); deploy safe (update.sh no-rebase)
- `d722639f` — test(authority): scrub ODYSSEUS_COMPLETION_GATE in test_agent_runtime_context (hermetic; host env leaked the fork flag into upstream-pinned disclosure assertions — same class as bd3947cd)
- `7cb56aa6` — docs(specs): commit-map + ROADMAP — Chunk 3 complete (strict 7 + P1 2 + P3 3 code + hermetic scrub; 1609 green)
- `a85f09b0` — docs(specs): commit-map — backfill 3 unmapped docs commits (ae2b6030, 0a9dc2e0, 3ee615e7) to restore the ahead=entries+1 invariant
- `043a686e` — fix(agent): blocked preemptive explicit tool call no longer becomes the reply (Backlog #8)
- `d989636d` — feat(browser): ticked Browser button owns the raw Playwright MCP surface (Backlog #9)
- `03e0a612` — docs(specs): ROADMAP #8/#9 fixed status + commit-map backfill (4 rows: 7cb56aa6, a85f09b0, 043a686e, d989636d)
- `9f20f505` — feat(browser): execution-side raw-MCP opt-in reuses ODYSSEUS_EXPOSE_RAW_BROWSER_MCP (Backlog #9; aligns the two opt-in vars to one)
- `874ef867` — docs(specs): commit-map — 9f20f505 (execution-side opt-in var alignment)
- `94edfa88` — fix(agent): preemptive calendar lookup blocked by an execution gate defers to the model round (Backlog #8; same leak, second branch)
- `23351ef4` — docs(specs): ROADMAP #8/#9 COMPLETE status (calendar tail 94edfa88, env alignment 9f20f505) + commit-map rows
- `20cd9b41` — docs(specs): commit-map — backfill 3 unmapped docs commits (03e0a612, 874ef867, 23351ef4) + fix tail ordering; restores ahead=entries+1
- `f6f38fea` — docs(specs): ROADMAP #9 — correct superseded 'no native private_browser' claim (real native tool, metadata-only in local mode)
- `46272616` — fix(agent): scope completion-gate bypass terminal rewrite to the final round's prose (Backlog #10; final-bubble transcript wall on long agent turns)
- `ec015031` — docs(specs): commit-map — backfill 20cd9b41 + f6f38fea rows (restores ahead=entries+1)
- `a1fec8c2` — docs(specs): ROADMAP #10 FIXED status (46272616) + commit-map row
- `91a8f71c` — docs(specs): commit-map — backfill ec015031 + a1fec8c2 rows (audit; restores ahead=entries+1)
- `98e7707c` — docs(specs): ROADMAP — smoke verified 2026-10-28 (user confirmed #10 works post-restart; #8/#9 live); status updated per keep-current
- `2c535b47` — docs(specs): ROADMAP — Backlog #11 logged (deleted user messages still reach live session agent context) + status line
- `057f4d2e` — docs(specs): commit-map — backfill 91a8f71c, 98e7707c, 2c535b47 rows (audit keep-current; restores ahead=entries+1)
- `1c23ba38` — docs(specs): ROADMAP — Backlog #12 logged (final answer routed to thinking field) + status line + commit-map row (057f4d2e)
- `afdf2b56` — docs(specs): commit-map — 1c23ba38 row (Backlog #12)
- `d8b67c01` — test(chat): repro guard — deleted stamped message leaves live context (Backlog #11 verification)
- `16cb3e22` — docs(specs): ROADMAP — Backlog #11 CLOSED as misdiagnosed (app.log resurfacing, not context leak) + commit-map row (d8b67c01)
- `f77550fd` — docs(specs): commit-map — backfill afdf2b56, d8b67c01, 16cb3e22 rows (Backlog #11 closure; restores ahead=entries+1)
- `4f91907d` — docs(specs): ROADMAP — status line: #11 CLOSED as misdiagnosed (2026-10-29)
- `df1a71cb` — docs(specs): commit-map — f77550fd + 4f91907d rows (restores ahead=entries+1)
