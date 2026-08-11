# Document control

| Field | Value |
|---|---|
| Title | OpenXR Operator — Production Build Kit |
| Version | 2.0 |
| Date | 8 August 2026 |
| Supersedes | "Self-contained OpenXR Operator Build Kit" v1.0 (undated) |
| Status | Design complete; implementation not started |
| Target engine | Godot 4.7.x |
| Licence posture | Split: MIT in-engine addon / AGPL-3.0-or-later out-of-process (see Part 4) |
| Vendor gate | No Meta, OpenAI, or xAI — direct or transitive. Google permitted. |

## Provenance conventions used throughout

This kit distinguishes four epistemic states. Every non-obvious factual claim carries one.

**CONFIRMED** — verified against a primary source (official documentation, repository
source, LICENSE file, specification registry, release page) during research on
8 August 2026. Source given.

**INFERRED** — reasoned from primary evidence, with the reasoning shown. Not directly
stated by any source.

**BLOCKED** — retrieval was attempted and failed. What was tried and how it failed is
recorded in Part 10.

**NOT VERIFIED** — no retrieval was spent on this. Stated plainly rather than disguised
as uncertainty.

The distinction between BLOCKED and NOT VERIFIED is deliberate and load-bearing. A
document that collapses "I looked and could not find it" into "I did not look" is not
auditable. Part 10 lists both categories separately.

## How to use this kit

Parts 0–1 are the verdict and the evidence for it. Read these before deciding whether to
build at all.

Parts 2–5 are the design. They replace the architecture in v1.0 rather than patching it.

Part 6 is reference implementation code. Every listing is complete and runnable, not
illustrative. Where a listing has prerequisites they are stated inline.

Parts 7–8 are the delivery mechanics: pipeline, gates, milestones.

Part 9 contains two agent prompts ready to paste: an adversarial audit prompt and a
production-hardening kickoff prompt. Both are self-contained.

Part 10 is the source ledger and the honest list of what remains unverified.

---

# Part 0 — Verdict

## 0.1 Summary

The v1.0 build kit does not survive audit. It fails both project gates and contains a
remote-code-execution chain reachable from any web page the user visits. Three of its
core technical mechanisms do not work as described against current Godot. The concept is
sound and worth building; the implementation as published should not be run.

The corrected design in this kit differs from v1.0 in five structural ways, not in
details. The most consequential is that **the agent cannot see what the headset sees from
inside Godot**, and no amount of fixing the v1.0 screenshot code changes that. The
observation path has to move outside the engine.

## 0.2 The five structural changes

**One. Frame capture moves out of the engine.** Godot issue #100004 is open as of
8 August 2026 and confirms that with `Viewport.use_xr = true` and an active OpenXR
session, capturing the viewport texture returns black, because the OpenXR compositor
takes the render target via output override. This affects both Vulkan and OpenGL. It is
assigned to Bastiaan Olij with one unmerged linked PR (#109955) and is not fixed in 4.7.
The v1.0 screenshot command therefore returns a black image in exactly the situation the
product exists to handle. Capture moves to an explicit, environment-scoped OpenXR API
layer hooking `xrReleaseSwapchainImage` / `xrEndFrame`, with a non-XR mirror viewport as
the degraded fallback. (CONFIRMED — github.com/godotengine/godot/issues/100004.)

**Two. Input injection moves to the runtime boundary.** Faking `XRPositionalTracker`
objects inside Godot exercises Godot's node glue but bypasses the OpenXR action pipeline
— interaction profiles, action sets, pose spaces — which is the part most likely to be
wrong in a real XR application. Injection moves to `XR_EXT_conformance_automation` where
the runtime supports it, or to the API layer, with the in-engine tracker retained as an
explicitly-labelled low-fidelity tier.

**Three. The control channel gets an authenticated, non-browser-reachable design.**
Godot's `WebSocketPeer.accept_stream()` performs the HTTP upgrade internally and exposes
no way to read the inbound `Origin` header, so Origin allowlisting is not implementable
in GDScript without hand-rolling RFC 6455 framing. The design instead makes the engine
port reachable only by the local agent process, authenticated by a token the browser
cannot learn, and moves all browser-facing surface to the Python plane where headers are
readable.

**Four. The vendor gate is enforced mechanically, not by intention.** v1.0 ships the
OpenAI Python SDK and recommends LLaVA and BakLLaVA, which carry Llama/Vicuna lineage and
OpenAI-generated instruction data respectively. Both are replaced, and a CI gate fails the
build on reintroduction.

**Five. Licensing splits.** A single AGPL-3.0 licence across the whole project would risk
imposing AGPL on any game that installs the in-engine addon, because a GDScript addon
loaded in-process and calling engine and project classes intimately is the kind of
combined work FSF guidance treats as one program. The in-engine addon is MIT; the
out-of-process agent and UI are AGPL-3.0-or-later.

## 0.3 What v1.0 got right and is retained

The three-component decomposition — in-engine instrumentation, an agent loop, a local
model — is correct and survives. So does the commitment to local-only inference, the
choice of Godot over a proprietary engine, the base64-PNG-over-JSON transport shape, and
the decision to expose scene-tree reading and property setting as first-class commands.
The `write_code` → `scan_filesystem` → `assign_script` sequencing is also correct in
principle; only its implementation is wrong, because `EditorInterface` is not available in
the running game process.

## 0.4 Decisions required before implementation

These are yours. This table carries no pre-filled defaults. An earlier draft had a "default
if unanswered" column with every row answered, which is deciding a question while appearing
to defer it — the column is gone and nothing in the design depends on an unanswered row.

Open. Nothing downstream assumes an answer.

| ID | Decision | Options |
|---|---|---|
| D-01 | Primary platform for the API layer | Linux / Windows / both |
| D-02 | Accept Meta funding proximity in the Godot XR toolchain (§4.5) | Accept / investigate / reject |
| D-03 | In-engine addon licence | MIT / Apache-2.0 / BSD-3 |
| D-04 | Whether to build the API layer in v1 | Build / defer to v2, ship mirror-viewport only |
| D-05 | Agent sandbox mechanism | Wasmtime / bubblewrap / container / none |
| D-06 | Whether destructive actions ever auto-apply | Never / behind a flag |
| D-07 | Reuse an existing Godot MCP server vs build the bridge | Reuse / build |
| D-08 | Target the OMBI Scene Object Model in the selector grammar | Yes / no / revisit at v2 |

Decided. These are settled and the design in Parts 2 through 7 reflects them.

| ID | Decision | Answer |
|---|---|---|
| D-09 | Model backend policy | Swappable adapters. Any provider except Meta, OpenAI, xAI. Twelve bespoke adapters, one per provider, not one generic client. |
| D-10 | Does the gate cover the OpenAI request format | No. The gate covers OpenAI's servers, SDK, and models. The JSON request shape is a de facto standard and is permitted. |
| D-11 | Inference locality | Local first, not local only. Hosted providers permitted and opt-in. |
| D-12 | Local-first fallback | Manual configuration only. An unreachable backend fails with a named error; it never switches to another. |
| D-13 | Egress with hosted backends | Allowlist of specific provider domains, exactly one per configured adapter. `api.openai.com` denied unconditionally and not overridable. |

---

# Part 1 — Findings ledger

Severity definitions. **BLOCKER**: build fails, product is wrong, or a legal, security, or
licensing breach. **MAJOR**: significant rework, cost, or risk if not fixed before build.
**MINOR**: fix during build. **NIT**: polish.

Evidence is quoted from v1.0 or marked ABSENT. Finding IDs are stable and are referenced
by the amendments in Part 8.

## 1.1 Security

| ID | Sev | Location | Evidence | Why it matters | Fix |
|---|---|---|---|---|---|
| F-001 | BLOCKER | `server.gd` `_start_server` / `_handle_message` | `_server.listen(_port, "127.0.0.1")`; no `Origin` check, no auth, no token, no rate limit anywhere in the dispatch | WebSockets are not subject to the same-origin policy. Any page the user visits can open `ws://127.0.0.1:9099` and issue `assign_script` or drive `write_code` via the agent. Combined with F-003 this is remote code execution from a visited web page. | Token-first authentication (§3.2); browser never reaches this port |
| F-002 | BLOCKER | `web_agent.py` main | `socketio.run(app, host='0.0.0.0', port=5000)` | Exposes the control panel, and by extension the whole action surface, to every host on the LAN | Bind `127.0.0.1` |
| F-003 | BLOCKER | `agent_server.py` `write_gdscript` | `full_path = Path(project_root) / relative_path` with model-supplied `relative_path` | `pathlib` discards the left operand when the right is absolute, and does not normalise `..`. Model output writes anywhere the process can write. | Containment check (§3.3) |
| F-004 | BLOCKER | `agent_server.py` main loop | `action = json.loads(content)` then direct dispatch to file write and `set_script` | Unvalidated model output drives arbitrary code execution. OWASP LLM01 chained with LLM05 and LLM06. | Schema-constrained decoding, allowlist, diff-then-approve (§3.4, §3.5) |
| F-005 | MAJOR | `web_agent.py` `HTML_TEMPLATE` | `<script src="https://cdn.socket.io/4.5.4/socket.io.min.js">` | Contradicts the "completely offline" claim, and makes the panel dependent on a third-party origin with no SRI | Vendor the asset locally |
| F-006 | MAJOR | `server.gd` `_poll` | ABSENT: no maximum message size, no connection cap, no read deadline | Trivial memory-exhaustion denial of service against the editor process | Size and rate limits (§3.2) |
| F-007 | MAJOR | Whole agent | ABSENT: no audit log of executed actions | No forensic record of what the agent did to the project | Append-only action log (§3.7) |
| F-008 | MAJOR | Whole agent | ABSENT: no egress restriction | A prompt-injected agent can reach any network the host can | Egress allowlist (§3.6) |
| F-009 | MINOR | `server.gd` `_handle_message` | `JSON.parse` result used without depth or type checking beyond `has("command")` | Malformed nesting can cause deep recursion in `_node_to_dict` | Validate shape and depth |

## 1.2 Correctness

| ID | Sev | Location | Evidence | Why it matters | Fix |
|---|---|---|---|---|---|
| F-010 | BLOCKER | `server.gd` `_get_screenshot_base64` | `get_viewport().get_texture().get_image()` | Returns black whenever XR is active (issue #100004, open, not fixed in 4.7). Also unsynchronised: Godot documentation requires awaiting `RenderingServer.frame_post_draw` before readback. The primary observation channel does not work. | Capture tiers (§2.3) |
| F-011 | BLOCKER | `server.gd` `_handle_message` `"scan_filesystem"` | `EditorInterface.get_resource_filesystem().scan()` | `EditorInterface` is not available in the running game process; the autoload runs in the game, not the editor. This call fails, so the documented `write_code` → `scan_filesystem` → `assign_script` sequence cannot complete. | Editor-side handler over the debugger channel (§2.5) |
| F-012 | MAJOR | `server.gd` `_simulate_input` | `tracker.name = controller_name` with default `"RightController"` | `XRController3D` binds by exact tracker name; the Godot convention is `left_hand` / `right_hand`. An arbitrary name binds to nothing and the simulated input silently does nothing. | Constrain to valid tracker names; assert binding |
| F-013 | MAJOR | `server.gd` `_simulate_input` | Fabricates trackers directly on `XRServer` | Bypasses interaction profiles, action sets, and pose spaces — the parts of an XR app most likely to be wrong | Tiered injection (§2.4) |
| F-014 | MAJOR | `agent_server.py` restart handling | `restart_scene(ws); time.sleep(2)` | A fixed sleep is both a race and a waste. This is precisely the failure mode Maestro's design eliminates. | Settle detection (§5.2) |
| F-015 | MINOR | `server.gd` `_node_to_dict` | `"path": node.get_path()` | `get_path()` returns `NodePath`, not `String`; JSON serialisation is implementation-defined | Cast explicitly |
| F-016 | MINOR | `server.gd` `_get_scene_tree` | Recurses from `get_tree().root` with no depth or node cap | On a real scene this produces a tree far larger than the model's context window | Depth limit, subtree selection, filtering |
| F-017 | MINOR | `agent_server.py` `send_ws` | `ws.send(...)` then `json.loads(ws.recv())` with no correlation id | Assumes strict request/response ordering on a channel that has none | Correlation ids |
| F-018 | MINOR | `web_agent.py` | `SYSTEM_PROMPT = """... (insert the same SYSTEM_PROMPT ...) ..."""` | The published file does not run as printed | Single shared module |

## 1.3 Licensing and vendor gate

| ID | Sev | Location | Evidence | Why it matters | Fix |
|---|---|---|---|---|---|
| F-019 | BLOCKER | `agent_server.py`, `web_agent.py` | `from openai import OpenAI` | The official OpenAI SDK is a vendor artifact and a direct gate violation regardless of endpoint. Apache-2.0 licence is not the issue; provenance is. The OpenAI *request format* is not a violation (D-10) — the SDK is. | `ModelBackend` protocol over `httpx`, twelve adapters, no vendor SDK (§6.2) |
| F-020 | BLOCKER | §4.2 model list | `ollama pull llava:13b` | LLaVA 1.5/1.6 at 13B is built on Vicuna, which is Llama-2-derived. Meta lineage; the Llama Community Licence is also not OSI-approved and adds field-of-use terms incompatible with GPL/AGPL redistribution. | Qwen2.5-VL-7B or Gemma 3 (§4.3) |
| F-021 | MAJOR | §4.2 model list | `ollama pull bakllava` | Mistral base is clean, but BakLLaVA-1 was trained on LLaVA's corpus of OpenAI-generated instruction data and the model card carries a `llama2` licence tag | Remove |
| F-022 | MAJOR | "Extending the Kit" | "The entire codebase is open-source (MIT)." | Conflicts with the AGPL posture, and a blanket AGPL would infect games installing the addon | Split licence (§4.1) |
| F-023 | MAJOR | Whole kit | ABSENT: no dependency manifest, lockfile, or SBOM | Vendor and licence gates cannot be enforced or audited | `uv.lock` + SBOM + CI gate (§7.1) |
| F-024 | MINOR | §4.4, §4.5 | `deepseek-vl2`, `minicpm-v` offered without licence statement | Both are usable but carry custom model licences that must be declared | Declare in the SBOM |

## 1.4 Delivery and operability

| ID | Sev | Location | Evidence | Why it matters | Fix |
|---|---|---|---|---|---|
| F-025 | MAJOR | Whole kit | ABSENT: no tests of any kind | Nothing establishes that any command works | gdUnit4 + pytest (§7.3) |
| F-026 | MAJOR | Whole kit | ABSENT: no CI | No gate prevents any finding in this ledger from recurring | Pipeline (§7.2) |
| F-027 | MAJOR | Whole kit | ABSENT: no versioning of the wire protocol | Engine addon and agent will drift and fail confusingly | Protocol version in handshake |
| F-028 | MINOR | Troubleshooting table | "Use `Marshalls` (no 'a')" | The documented failure mode is a typo, which suggests the code was never run as published | Verify all listings execute |
| F-029 | MINOR | Whole kit | ABSENT: no structured logging, metrics, or run artifacts | Failures are undiagnosable after the fact | Artifact bundle (§5.6) |
| F-030 | NIT | Web UI | No loading, empty, or error states; no keyboard navigation; no focus states | Fails the accessibility baseline | WCAG 2.2 AA pass |

## 1.5 Closest calls cleared

Three things that looked wrong and are not, recorded so the audit is not one-sided.

**The XR tracker API is not deprecated.** `XRPositionalTracker` still exists in the
current class reference and is inherited by `XRControllerTracker`, `XRHandTracker`,
`XRBodyTracker`, and `OpenXRSpatialEntityTracker`. PR #90645 (merged 22 April 2024,
milestone 4.3) reworked the hierarchy to add a common `XRTracker` ancestor but did not
remove the API. v1.0's tracker code is API-valid; it is the wrong layer (F-013) and
misnames the tracker (F-012), but it does not fail to compile. (CONFIRMED.)

**The Python dependencies are licence-clean.** websocket-client (Apache-2.0), Flask
(BSD-3), Flask-SocketIO (MIT), eventlet (MIT), python-socketio (MIT), and the socket.io
JS client (MIT) are all permissive and combine into an AGPL distribution without
conflict. The licence problem is entirely about vendor provenance, not compatibility.
(CONFIRMED.)

**The base64-PNG-over-JSON transport is not the bottleneck people assume.** It is
wasteful, but at one frame per agent step against a local model with multi-second
inference latency, transport encoding is not on the critical path. It is retained.
(INFERRED.)


# Part 2 — Target architecture

## 2.1 Design principles

**The engine is instrumented, not trusted.** Godot is the system under test. Anything the
harness needs to observe or assert must be obtainable without depending on the correctness
of the code being tested.

**Observation and actuation are tiered, and the tier is always reported.** Every capture
and every input injection carries a fidelity label in the run artifact. A test that passed
against a mirror viewport has not proven the same thing as one that passed against the
composited headset frame, and the report must say which it was.

**Nothing the model emits is trusted.** Model output is data, validated against a schema,
matched against an allowlist, and — for anything that mutates the project — presented as a
diff for human approval.

**The browser never touches the engine.** All browser-reachable surface lives in the
Python plane, where request headers are readable and Origin can be validated.

**Degradation is explicit.** When a tier is unavailable the harness says so and drops to
the next one; it does not silently produce a black image and call it a screenshot.

## 2.2 Three planes

```
  +-------------------------------------------------------------+
  |  CONTROL PLANE  (Python, AGPL-3.0-or-later)                  |
  |                                                              |
  |   flow runner  --  driver interface  --  artifact writer     |
  |   agent loop   --  action validator  --  approval gate       |
  |   web UI (127.0.0.1, Origin-validated, token-gated)          |
  +----------+---------------------+---------------------+-------+
             |                     |                     |
   token-auth|            env-scoped|          loopback   |
   loopback  |            layer     |          HTTP       |
             v                     v                     v
  +----------------------+  +------------------+  +---------------------+
  | INSTRUMENTATION      |  | OPENXR API LAYER |  | MODEL PLANE         |
  | Godot addon (MIT)    |  | C++ (MIT)        |  | ModelBackend        |
  |                      |  |                  |  |   protocol          |
  | scene tree read      |  | xrReleaseSwap-   |  |                     |
  | property get/set     |  |   chainImage ->  |  | 12 adapters:        |
  | mirror capture       |  |   frame capture  |  |  4 local (default)  |
  | tracker inject (T3)  |  | pose inject (T2) |  |  8 hosted (opt-in)  |
  | editor bridge        |  | call trace       |  | capability-         |
  |                      |  |                  |  |  negotiated         |
  +----------------------+  +------------------+  +---------------------+
             |
             | EngineDebugger capture channel
             v
  +----------------------+
  | GODOT EDITOR         |
  | filesystem rescan    |
  | script assignment    |
  +----------------------+
```

Every arrow is loopback or in-process **except one**: when a hosted model adapter is
explicitly configured, the model plane reaches exactly one allowlisted provider domain and
nothing else. That exception is the only outbound path in the system, it is off by default,
and it is enforced outside the process (§3.6).

## 2.3 The observation problem

This is the single hardest constraint in the project and the reason v1.0's architecture
cannot be patched into correctness.

**The problem.** With `Viewport.use_xr = true` and an OpenXR session running, the OpenXR
compositor takes the render target through output override. `get_viewport().get_texture()
.get_image()` then yields black. Reported by Bastiaan Olij as issue #100004 on 4 December
2024; still open on 8 August 2026, labels bug / topic:rendering / topic:xr, one linked
unmerged PR (#109955), not fixed in 4.7. Reproduces on both Vulkan and OpenGL.
(CONFIRMED.)

Separately, and independently of XR: Godot's own documentation requires awaiting
`RenderingServer.frame_post_draw` before reading a viewport texture back. v1.0 reads
synchronously inside a command handler, so even in the non-XR case it can return a stale
or blank frame. (CONFIRMED — viewport documentation.)

**Three capture tiers.** The harness declares which it used on every frame it produces.

| Tier | Mechanism | Fidelity | Cost | Availability |
|---|---|---|---|---|
| T1 | OpenXR API layer intercepting `xrReleaseSwapchainImage` | Exact composited frame submitted to the runtime, per eye | High: C++, per-graphics-API interop | Requires building the layer |
| T2 | Non-XR mirror `SubViewport` with a spectator camera, captured after `frame_post_draw` | Approximates the scene; not the composited stereo output; no distortion, no runtime post-processing | Low: pure GDScript | Always |
| T3 | Run with `use_xr = false` in a desktop harness mode | Full scene fidelity, zero XR fidelity | Lowest | Always |

**Recommendation.** Ship T2 and T3 in v1 and treat T1 as the v2 objective (decision
D-04). T2 is sufficient for the majority of the agent's actual work — scene composition,
node placement, UI layout, material and lighting checks — and none of that depends on
seeing lens distortion. T1 becomes necessary when the assertion is about what the user
genuinely perceives in the headset: stereo convergence, foveation artifacts, compositor
layer ordering, or runtime-applied post-processing.

**Why the API layer is the right T1 and not a hack.** The layer sits below the
application and above the runtime, so the render-target ownership question that causes
#100004 does not arise: the layer sees the images the application handed over.
`xrReleaseSwapchainImage` is the confirmed interception point — OpenXR-Toolkit performs
its entire upscaling, post-processing, and variable-rate-shading pipeline there, and
composites its menu at `xrEndFrame`. It has a working screenshot feature writing to
`%LocalAppData%\OpenXR-Toolkit\screenshots`, with release 1.2.0 adding overlay inclusion
in screenshots — demonstrating that capture of the real submitted frame from a layer is
proven, not theoretical. (CONFIRMED.)

**The counter-argument, and why it does not apply here.** OpenXR-Toolkit was discontinued
in 2024. Its author's stated reason is a direct argument against layer-based injection:
the model of a universal injector that takes over application code is not sustainable
given the growing complexity and variety of VR applications, and the correct place to
implement these features is in each game by its developers. That is the most credible
available judgement against this architecture and it should not be waved away.

It does not transfer, for a specific reason. He was shipping a *system-wide implicit*
layer to *end users* across *arbitrary unknown applications* to deliver *product
features*. This kit ships an *explicit* layer to *developers*, scoped to *one known
engine*, for *test instrumentation*, activated per-launch. The OpenXR loader supports
exactly this: setting `XR_API_LAYER_PATH` and `XR_ENABLE_API_LAYERS` on a single process
loads the layer for that process only — no registry writes, no installer, no effect on any
other application, nothing left behind. That removes the failure mode he describes and the
"implicit injector is a security liability" objection at the same time. (CONFIRMED — the
loader specification documents both the manifest-discovery paths and the environment-
variable override.)

**Therefore, a hard constraint on the implementation:** the layer must never install a
system-wide implicit manifest. Explicit and environment-scoped only. This is a build gate
in §7.1, not a convention.

**Graphics API priority.** For realistic Godot XR use, ranked: Vulkan first (Forward+ and
Mobile renderers, desktop and Android/Quest); OpenGL second (Compatibility renderer,
low-end Android and Quest); Direct3D 12 third (Windows-only, opt-in, added by PR #104207
in Godot 4.5, authored by the OpenXR-Toolkit developer). Implement Vulkan swapchain
handling first. (Backend support CONFIRMED; the ranking is INFERRED from it.)

**Prior art for the graphics interop, since no layer template provides it.** Neither the
Ybalrid nor mbucchia layer templates demonstrate swapchain image access — both only show
call logging. Working references that do handle swapchain images: LunarG GFXReconstruct's
OpenXR capture layer, `mbucchia/OpenXR-Vk-D3D12` (real cross-API swapchain interop,
tested against Godot 4 among others), and `Jabbah/OpenXR-Layer-OBSMirror` (mirrors the
composited swapchain to OBS). Budget genuine engineering here; it is the one part of the
layer that is not boilerplate. (CONFIRMED.)

**What GFXReconstruct is and is not for.** It captures OpenXR and Vulkan call streams to
a single `.gfxr` file and `gfxrecon-convert` emits them as JSON Lines, which is a
genuinely useful offline trace. It is not a frame-capture or input-replay solution:
OpenXR support requires the Vulkan layer concurrently, desktop Linux OpenXR is
unsupported, it does not dump per-frame images, and its own documentation states that
replayed OpenXR frames are displayed at the captured head-relative position and are
insensitive to replay-time head tracking — recorded XR input is largely ignored on
replay. Use it for debugging, not for the observe loop. (CONFIRMED.)

## 2.4 The actuation problem

| Tier | Mechanism | Fidelity | Availability |
|---|---|---|---|
| A1 | `XR_EXT_conformance_automation` via `OpenXRAPIExtension` | Exercises the full action-binding pipeline exactly as production | Only where the runtime implements the extension; Monado does, most consumer runtimes do not |
| A2 | API layer intercepting pose and action-state calls | Full pipeline below the application; works regardless of runtime extension support | Requires the layer |
| A3 | In-engine `XRControllerTracker` fabrication | Exercises Godot node glue only; bypasses interaction profiles and action sets | Always |

**On A1.** The extension exposes `xrSetInputDeviceActiveEXT`,
`xrSetInputDeviceStateBoolEXT`, `xrSetInputDeviceStateFloatEXT`,
`xrSetInputDeviceStateVector2fEXT`, and `xrSetInputDeviceLocationEXT`. The specification
is explicit that it is not intended for non-conformance-test applications and that a
runtime may gate it behind a developer mode. It is the mechanism the OpenXR CTS itself
uses. Godot does not expose it directly, but `OpenXRAPIExtension` gives access to the raw
instance and `get_instance_proc_addr`, so the functions are reachable from a GDExtension.
No worked example was found, so treat this as original integration work. (Extension
CONFIRMED; reachability via `OpenXRAPIExtension` INFERRED from the exposed API surface.)

**On A2, and the strongest single finding in the research.** `OpenXR-MotionCompensation`
proves that layer-level pose injection works with no VR hardware present. Two independent
paths: `[debug] testrotation=1` runs motion compensation generating rotation internally
without any tracker input from motion controllers at all; and virtual trackers
(`srs`, `flypt`, `yaw`, `rotovr`) source all data from a Windows memory-mapped file with
`physical_enabled=0` skipping physical-tracker initialisation entirely. That is a working,
maintained demonstration of exactly the mechanism this kit needs. (CONFIRMED.)

Caveats to carry forward. It is Windows-only, so Linux equivalents are your own work. It
is LGPL-2.1 — loading a separately-built layer binary is compatible with an AGPL
application, but do not vendor its source into an MIT or Apache tree. Its recording
(`toggle_recording` writing `recording_XXX.csv` with input, filtered, modified, reference,
and delta poses) is one-way logging for analysis; there is no documented replay path, so
deterministic replay is yours to build. And its exact hooked-function set could not be
read: GitHub returned ROBOTS_DISALLOWED on the source tree and PERMISSIONS_ERROR on the
blobs, so `xrLocateSpace`, `xrSyncActions`, and
`xrSuggestInteractionProfileBindings` are inferred from its changelog and manual rather
than quoted from source. Clone the repository to confirm before implementing. (BLOCKED —
see Part 10.)

**On A3.** Retained as the always-available floor, with F-012 fixed: tracker names
constrained to `left_hand` / `right_hand`, pose name `default`, and a post-injection
assertion that an `XRController3D` actually bound. Without that assertion the injection
fails silently, which is worse than not having it.

## 2.5 The control channel

Two channels, for two different jobs.

**Game process — authenticated loopback WebSocket.** Retained from v1.0 because it is
simple and the agent needs a low-latency bidirectional channel to a running game. Hardened
per §3.2. Carries: scene tree reads, property get and set, mirror capture, tier-A3
injection, scene restart, settle sampling.

**Editor process — `EngineDebugger` capture channel.** This is the supported mechanism and
it is how Godot's own remote scene tree and profilers work. The running game calls
`EngineDebugger.send_message("openxr_operator:rescan", [])`; an `EditorDebuggerPlugin` in
the editor implements `_has_capture` and `_capture` and performs the editor-side work.
Message names are namespaced: registering capture `openxr_operator` routes every message
prefixed `openxr_operator:`. Carries: filesystem rescan, script assignment, anything else
requiring `EditorInterface`. This is the fix for F-011. (CONFIRMED — `EngineDebugger` and
`EditorDebuggerPlugin` class references; mechanism established by PR #39440.)

**Limits to design around.** The debugger channel exists only when a debugger is attached
— editor-launched and debug builds, not release exports. Payload size has no documented
cap but large binary payloads are impractical and undocumented, so frames go to disk and
the channel carries a path, never a base64 PNG. (Availability INFERRED from "active in the
running game" plus the profiler design; payload behaviour NOT VERIFIED.)

## 2.6 Repository layout

```
openxr-operator/
  LICENSE                      AGPL-3.0-or-later (repository default)
  LICENSES/
    MIT.txt                    for addon/ and layer/
    AGPL-3.0-or-later.txt
  NOTICE                       third-party attributions
  README.md
  CHANGELOG.md

  addon/                       MIT. Ships into user projects.
    openxr_operator/
      plugin.cfg
      plugin.gd                EditorPlugin: autoload + debugger plugin
      debugger_plugin.gd       EditorDebuggerPlugin: editor-side handlers
      server.gd                authenticated loopback command server
      capture.gd               mirror-viewport capture, frame_post_draw gated
      inject.gd                tier A3 tracker injection with binding assertion
      protocol.gd              wire protocol constants and version
      LICENSE                  MIT

  layer/                       MIT. Optional, built separately.
    CMakeLists.txt
    src/dispatch.cpp
    src/layer.cpp
    src/capture_vulkan.cpp
    manifest/XR_APILAYER_OPENXROP_operator.json.in
    scripts/run-with-layer.sh
    LICENSE                    MIT

  operator/                    AGPL-3.0-or-later. Never ships into user projects.
    pyproject.toml
    uv.lock
    src/openxr_operator/
      __init__.py
      driver.py                Driver protocol (the Maestro boundary)
      godot_driver.py          concrete driver over the loopback socket
      settle.py                frame-stability settle detector
      selectors.py             selector grammar and resolution
      flow.py                  YAML flow parser and runner
      schema.py                action schema, single source of truth
      model.py                 ModelBackend protocol, registry, resolution
      backends/                12 adapters, one file each
        __init__.py            registry and capability negotiation
        local_ollama.py        local, default
        local_llamacpp.py      local
        local_vllm.py          local
        local_lmstudio.py      local
        hosted_google.py       hosted, opt-in
        hosted_mistral.py      hosted, opt-in
        hosted_anthropic.py    hosted, opt-in
        hosted_cohere.py       hosted, opt-in
        hosted_deepseek.py     hosted, opt-in
        hosted_alibaba.py      hosted, opt-in
        hosted_together.py     hosted, opt-in
        hosted_groq.py         hosted, opt-in
      approval.py              diff-then-approve gate
      fsguard.py               path containment
      artifacts.py             run bundle writer, JUnit emitter
      auditlog.py              append-only action log
      ui/                      Flask app, Origin-validated
    tests/

  flows/                       example declarative flows
  tools/
    docdrift.py                documentation provenance checker
    vendorscan.py              vendor-gate enforcement
  .github/workflows/ci.yml
```

## 2.7 One agent step, in sequence

```
 1. runner    -> driver.settle(timeout=5s)          wait for frame stability
 2. driver    -> engine: capture(tier=best_available)
 3. engine    -> await RenderingServer.frame_post_draw
 4. engine    -> writes PNG to run dir, returns {path, tier, size, frame_id}
 5. driver    -> engine: scene_tree(root=..., depth=6, filter=...)
 6. runner    -> artifacts.record_observation(frame, tree, tier)
 7. runner    -> model.act(frame, tree, task, schema=ACTION_SCHEMA)
 8. model     -> resolved backend adapter, schema constraint if supported,
                temperature=0; adapter reports constrained=true|false
 9. runner    -> schema.validate(response)          reject on failure, retry once
10. runner    -> allowlist check; if mutating -> approval.request(diff)
11. human     -> approve / reject / edit
12. runner    -> driver.execute(action)
13. runner    -> auditlog.append(action, frame_hash, tree_hash, decision)
14. goto 1
```

Steps 9 through 11 are the entire difference between this and v1.0's loop, which went
directly from step 8 to step 12.

## 2.8 Failure modes

| Failure | Detection | Behaviour |
|---|---|---|
| Engine disconnects mid-flow | Socket read error or heartbeat timeout | Abort flow, write partial artifact bundle, exit non-zero |
| Capture returns black | Mean luminance below threshold and variance near zero | Log the tier, attempt next tier down, mark the step degraded in the report |
| Model returns unparseable output twice | Schema validation fails on both attempts | Abort the step, record the raw output in the bundle, do not retry a third time |
| Settle never reached | Timeout elapsed | Configurable per flow: `proceed` (Maestro's default) or `fail`. Always logged. |
| Approval denied | Human rejects the diff | Record the rejection with the proposed diff, continue to the next step |
| Layer fails to load | Loader debug output absent from process log | Fall back to T2, mark all frames in the run as T2, warn once |
| Tracker injection binds to nothing | Post-injection assertion finds no bound `XRController3D` | Hard error. Silent no-op injection is the worst outcome available. |

---

# Part 3 — Security architecture

## 3.1 Threat model

Trust boundaries, in decreasing order of trust: the human operator; the local agent
process; the Godot editor and game process; the local model server; **the model's output**;
**any web page open in the user's browser**; the network. The last three are untrusted.

The single most important observation is that model output sits on the untrusted side of
the boundary even though it originates locally. It is derived from a screenshot and a
scene tree, both of which can contain adversary-controlled content — a texture with text
in it, a node named to look like an instruction. This is OWASP LLM01 prompt injection
chained with LLM05 improper output handling and LLM06 excessive agency.

| STRIDE | Threat | Control |
|---|---|---|
| Spoofing | Web page opens a socket to the engine port and impersonates the agent | Token-first auth (§3.2) |
| Tampering | Model output rewrites project files outside the project | Containment (§3.3) plus approval (§3.4) |
| Repudiation | No record of what the agent changed | Append-only audit log (§3.7) |
| Information disclosure | Prompt-injected agent exfiltrates project source | Egress allowlist (§3.6) |
| Denial of service | Unbounded message floods the editor process | Size, rate, and connection limits (§3.2) |
| Elevation of privilege | Model-proposed script assigned and executed in-engine | Allowlist plus approval plus sandbox (§3.4) |

## 3.2 Control-channel hardening

**The constraint that shapes the design.** `WebSocketPeer.accept_stream()` performs the
HTTP upgrade internally. On the server side the peer exposes `get_requested_url()` and
`get_selected_protocol()`, but there is no getter returning the inbound `Origin` header;
`handshake_headers` and `supported_protocols` are outbound and server-advertised
configuration respectively. Consuming the request bytes from the `StreamPeerTCP` first to
read `Origin` makes the stream unusable by `accept_stream()`, which expects to read the
full request — so Origin validation in GDScript means hand-implementing RFC 6455 framing.
Godot also has no Unix-domain-socket or named-pipe IPC. (CONFIRMED.)

**The resolution.** Do not try to validate Origin in the engine. Make the engine port
unreachable by browsers in the way that matters, and put the browser-facing surface where
headers are readable.

1. **Bind loopback only.** `127.0.0.1`, never `0.0.0.0`.
2. **Token-first authentication.** At startup the addon generates 32 bytes from
   `Crypto.generate_random_bytes()`, writes them hex-encoded to
   `user://openxr_operator.token` with restrictive permissions, and requires the first
   frame on every connection to be `{"cmd":"auth","token":"..."}`. This is the actual
   defence: a cross-origin page can open the socket, but it cannot read the token file, so
   it cannot authenticate. Compare in constant time. One attempt per connection, 2-second
   deadline, close with code 1008 on failure.
3. **Reject everything pre-auth.** No command dispatches before authentication, including
   error messages that would confirm command names.
4. **Limits.** Maximum inbound frame 1 MiB; maximum 4 concurrent peers; maximum 50
   messages per second per peer; idle timeout 120 seconds.
5. **Browser-facing surface lives in Python.** The web UI's own WebSocket validates
   `Origin` against an exact allowlist, because in Python the header is readable. The
   browser never opens a socket to the engine.
6. **Protocol version in the auth frame.** Mismatch closes the connection with a clear
   message rather than failing later in a confusing way (F-027).

**On browser Local Network Access.** Chrome gated local-network requests behind a
permission prompt in Chrome 142 (28 October 2025) and extended enforcement to WebSockets
and WebTransport in Chrome 147 (stable, around April 2026). Firefox has deliberately left
WebSocket LNA unblocked for now, and Safari has not shipped the prompt. So LNA raises the
bar in Chromium only, and is not a control this design may depend on. (CONFIRMED.)

## 3.3 Filesystem containment

`pathlib` join semantics are the vulnerability: `Path('/proj') / '/etc/passwd'` yields
`Path('/etc/passwd')`, discarding the base entirely, and `..` segments are not normalised
by the join. Both must be handled. The containment function additionally resolves symlinks
(via `resolve()`), enforces an extension allowlist, and caps file size. Implementation in
§6.4.

## 3.4 Agent containment

Four layers, all required.

**Capability allowlist.** Read-only commands — scene tree, property get, capture, settle —
are unrestricted. Mutating commands — property set, script assignment, file write, input
injection, scene restart — are individually enabled per flow and default to disabled.

**Diff-then-approve.** No file write or script assignment applies without the human seeing
a unified diff and approving it. This is not configurable off in v1 (decision D-06). The
approval record, including rejections and the rejected diff, goes into the audit log.

**Filesystem jail.** The agent process runs with a writable mount covering only the target
project directory. On Linux use `bubblewrap`; elsewhere use a container. Wasmtime is the
stronger option if model-proposed code ever needs to execute rather than merely be written
— it is the mechanism Sneeze uses for per-service isolation with instruction-set-level
separation, and it is cross-platform, which `bwrap` is not. (Decision D-05.)

**Schema-constrained output.** §3.5.

## 3.5 Constraining model output

Constrained decoding narrows what the model can emit to strings matching a schema. It does
not guarantee semantic validity, so the parsed object is validated against the same schema
afterwards regardless. One retry on failure, then abort the step.

The mechanism differs per backend, which is why it is a negotiated capability on the
`ModelBackend` protocol rather than an assumption. Each adapter reports
`supports_constrained_output` and the harness records the answer on every model call.

| Backend | Constraint mechanism |
|---|---|
| Ollama | `format` parameter taking a JSON Schema |
| llama.cpp / llama-server | GBNF grammar, or `json_schema` on newer builds |
| vLLM | `guided_json` (outlines or xgrammar backend) |
| LM Studio | `response_format` with `json_schema` |
| Google, Mistral, Anthropic, Cohere, DeepSeek, Alibaba, Together, Groq | provider-native structured-output or tool-schema mechanism; see each adapter |

**When a backend cannot constrain, the security posture changes and must be reported.**
Without constrained decoding the only defence against malformed or hostile output is
validate-and-reject after the fact, which is strictly weaker. An adapter reporting
`supports_constrained_output = False` causes the run manifest to mark every step
`constrained: false`, and the run report to carry a degraded-posture banner. It does not
silently proceed as if nothing changed.

## 3.6 Network egress

Default: the agent may reach `127.0.0.1` on the configured model port and `127.0.0.1:9099`
(engine). Nothing else.

When a hosted adapter is explicitly configured, egress opens to **exactly one allowlisted
provider domain** — the one belonging to the configured adapter — and nothing else. There
is no wildcard, no "any HTTPS", and no automatic fallback that could open the hole without
a human editing configuration (§4.4).

Enforce outside the process — network namespace, firewall rule, or container network
policy — because an in-process allowlist is bypassed by the same code execution it is
meant to contain. This is what converts a successful prompt injection from a data breach
into a local nuisance, and it is why the hosted exception is a single domain rather than a
general permission.

**Permanent denylist.** `api.openai.com` and every other OpenAI-operated endpoint are
denied unconditionally. This is not a configuration default that a user or a flow can
override; it is a hardcoded denial applied after the allowlist is resolved, plus a CI grep
(§7.1). A hosted adapter that resolves to an OpenAI-operated host fails closed.

**The trade-off, stated plainly.** Every hosted adapter you enable is a path by which a
screenshot of your project and its scene tree leave the machine. That is the point of the
feature and it is not a defect, but it means the egress allowlist is the control that
decides how far a successful prompt injection travels. Enable hosted adapters per project,
not globally.

## 3.7 Audit log

Append-only JSON Lines, one record per attempted action, written before execution:
timestamp, flow and step id, action type and full parameters, SHA-256 of the observation
frame and of the serialised scene tree, capture tier, approval decision and approver,
execution result, and the diff for mutating actions. Written to the run bundle and to a
durable per-project log. This is what makes "what did the agent do to my project last
Tuesday" an answerable question.


# Part 4 — Licensing and the vendor gate

## 4.1 The split-licence decision

**The problem.** The audit posture calls for AGPL-3.0-or-later end to end. Applied
literally, that licenses the in-engine GDScript addon under AGPL. A GDScript addon is
loaded into the user's Godot project, runs in the same process, extends engine and project
classes, and calls into them intimately. Under FSF guidance on plug-ins and combined
works, plug-ins loaded into and run in the same process, sharing data structures and
making intimate function calls, are generally treated as part of one combined program.
A developer who installs the addon and ships their game would therefore face a serious
argument that the entire game is a combined work subject to AGPL, obliging them to release
the whole game's source. The MIT engine underneath does not help — MIT is AGPL-compatible,
which makes the combination *cleaner*, not more separable.

That outcome would make the addon unusable by exactly the audience it is for, and it is
why godot-xr-tools chose MIT.

**The decision.**

| Component | Licence | Rationale |
|---|---|---|
| `addon/` — in-engine GDScript | **MIT** (D-03) | Loaded in-process into user projects. Must not impose copyleft on games. |
| `layer/` — OpenXR API layer | **MIT** | Loaded into arbitrary XR applications by the loader. Same reasoning. |
| `operator/` — Python agent, flow runner, web UI | **AGPL-3.0-or-later** | Separate process, arm's-length socket communication. Copyleft applies without reaching user projects. |
| Repository default | AGPL-3.0-or-later | With `addon/LICENSE` and `layer/LICENSE` overriding for their subtrees. |

**On AGPL section 13.** The network clause obliges you to offer source to users
interacting with the software remotely over a network. When the only surface is loopback
on the operator's own machine, the remote user and the operator are the same person and
the obligation is inert. It becomes live the moment the service binds a routable interface
— which is precisely what v1.0's `host='0.0.0.0'` does (F-002). Another reason to bind
loopback. (Analysis grounded in the AGPL-3.0 text; the precise FSF FAQ wording was NOT
VERIFIED and should be checked before this reasoning appears in a legal notice.)

**On building on MIT-licensed code.** v1.0 is MIT. You may incorporate it into a work
distributed under AGPL-3.0-or-later provided the MIT copyright notice and permission text
are retained for the MIT-origin portions. You cannot revoke MIT for those portions —
anyone may still extract them under MIT — and you cannot relicense third-party MIT code
under other terms. Keep `LICENSES/` and `NOTICE` accurate.

## 4.2 Dependency register

Every dependency, its licence, and its gate status. This table is the input to the CI
vendor scan (§7.1) and to the SBOM.

| Dependency | Version | Licence | AGPL-compatible | Vendor gate |
|---|---|---|---|---|
| Godot Engine | 4.7.x | MIT | Yes | Pass (see 4.5) |
| httpx | current | BSD-3-Clause | Yes | Pass |
| pydantic | v2 | MIT | Yes | Pass |
| PyYAML | current | MIT | Yes | Pass |
| Pillow | current | MIT-CMU | Yes | Pass |
| numpy | current | BSD-3-Clause | Yes | Pass |
| Flask | current | BSD-3-Clause | Yes | Pass |
| websockets | current | BSD-3-Clause | Yes | Pass |
| jsonschema | current | MIT | Yes | Pass |
| gdUnit4 | v6.x | MIT | Yes | Pass |
| gdtoolkit | 4.5.0 | MIT | Yes | Pass |
| osv-scanner | v2.x | Apache-2.0 | Yes (tool) | Pass |
| gitleaks | 8.30.1 | MIT | Yes (tool) | Pass |
| OpenXR-SDK | 1.1.x | Apache-2.0 | Yes | Pass |
| **openai (Python SDK)** | — | Apache-2.0 | Yes | **FAIL — removed (F-019)** |
| **eventlet** | — | MIT | Yes | Removed: maintenance-only, Flask-SocketIO advises against it |
| **Flask-SocketIO** | — | MIT | Yes | Removed: replaced by plain `websockets` |
| **socket.io JS from CDN** | 4.5.4 | MIT | Yes | **FAIL — offline claim (F-005)**; vendored or removed |

Two notes. `gitleaks` is feature-complete and receiving security patches only; its author
has moved to a successor project, so pin it and plan a review. `trufflehog` is an
alternative but is AGPL-3.0 — fine as a CI tool, do not bundle it into a distributed
artifact.

**On Trivy.** The prompt's ban on Trivy is not merely a preference. GitHub advisory
GHSA-69fq-xp46-6x23 records that on 19 March 2026 a threat actor used compromised
credentials to publish a malicious Trivy v0.69.4 release, force-pushed 76 of 77 version
tags in `aquasecurity/trivy-action` to credential-stealing malware, and replaced all 7
tags in `aquasecurity/setup-trivy`, followed by malicious container images on 22 March
2026 (CVE-2026-33634). Safe versions: trivy at or below v0.69.3, trivy-action v0.35.0,
setup-trivy v0.2.6. Beyond justifying the ban, this is the argument for pinning every
GitHub Action by commit digest rather than by tag. (CONFIRMED.)

## 4.3 Model selection

v1.0's recommendations fail the gate. Replacements, with the reasoning.

| Model | Provenance | Licence | Gate | Verdict |
|---|---|---|---|---|
| **Qwen2.5-VL-7B** | Alibaba | Apache-2.0 (7B specifically) | Pass | **Default.** Strong UI, OCR, and grounding; ~6–8 GB at Q4; `qwen2.5vl` in Ollama. Note the 3B and 72B are under the custom Qwen licence, not Apache — use the 7B. |
| **Gemma 3 (12B)** | Google | Gemma licence | Pass (Google permitted) | **Alternate.** Multimodal, ~8–12 GB at Q4, `gemma3` in Ollama. |
| Phi-3.5-Vision / Phi-4-multimodal | Microsoft | MIT | Pass | Viable; lighter. |
| Moondream | — | Apache-2.0 | Pass | ~1.9B. Fast cheap checks only. |
| Pixtral 12B | Mistral | Apache-2.0 | Pass | Viable; heavier. |
| MiniCPM-V 4.6 | OpenBMB | Apache-2.0 plus MiniCPM Community Licence | Pass | Viable. Backbone varies by version — 2.6 is Qwen2-based. Verify the specific tag. |
| DeepSeek-VL2 | DeepSeek | Code MIT; weights custom DeepSeek Model Licence | Pass | Viable. Declare the model licence. |
| **LLaVA 13B** | Vicuna → Llama-2 | Llama-2 Community Licence | **FAIL** | Meta lineage. Also not OSI-approved and adds field-of-use terms incompatible with AGPL redistribution. |
| **BakLLaVA** | Mistral base, LLaVA corpus | card tagged `llama2` | **FAIL** | Base is clean but training data is OpenAI-generated and the card carries a Llama tag. |

Qwen3-VL exists in Ollama but has known vision-detection integration issues (issue #50569,
March 2026); verify vision actually works on your exact tag before adopting it.

The table above covers **open-weight models you run yourself**, which is the local-first
default. The eight hosted adapters in §4.4 serve their own proprietary models — Gemini,
Mistral Large, Claude, Command, DeepSeek, Qwen, and whatever Together and Groq are serving
— and those are not enumerated here because the list changes monthly and any version
number written down now will be wrong. Two standing constraints apply to every hosted
model regardless: it must be vision-capable, and its provider must not be Meta, OpenAI, or
xAI. Note that some hosted catalogues include Llama-derived models; selecting one would
fail the gate even though the provider passes it, so the adapter validates the configured
model identifier against a Meta-lineage denylist at startup.

## 4.4 Backend policy and register

### What the gate actually covers

The gate excludes **what OpenAI makes and runs**: their servers (`api.openai.com`), their
SDK (the `openai` package), and their models. It does **not** cover the request format
OpenAI popularised. That JSON shape — `{"model": ..., "messages": [{"role", "content"}]}`
— is now a de facto interface standard spoken by llama.cpp, vLLM, LM Studio, and most
hosted providers. Sending it to a server on your own machine involves no OpenAI code,
service, or model, and is permitted. (Decision D-10.)

The absolute rule stands regardless: **nothing talks to OpenAI servers, ever.** §3.6
implements this as an unconditional denial applied after allowlist resolution, not as a
configurable default.

### Policy

**Local first, not local only.** Local backends are the default and require no network
permission. Hosted backends are available, permitted providers only, and off until a human
edits configuration.

**Manual configuration only — no automatic fallback.** If the configured local backend is
unreachable, the run fails with a clear error naming the backend and the port. It does not
silently switch to a hosted provider. Automatic fallback would mean a screenshot of the
project leaving the machine at a moment nobody chose, which is exactly the property this
project exists to avoid. (Decision: manual config only.)

**Twelve bespoke adapters, not one generic client.** Five of the twelve speak the
OpenAI-compatible format and could share a single adapter, but each provider is
implemented natively so that provider-specific structured-output mechanisms, error
taxonomies, rate-limit headers, and multimodal encodings are handled properly rather than
lowest-common-denominator. The cost is more code and more test surface; the benefit is
that a provider's failure modes surface as themselves instead of as a generic 400.
(Decision D-09, option b.)

### Backend register

`Locality` is `local` or `hosted`. `Constrain` is the structured-output mechanism the
adapter uses (§3.5). `Egress` is the single domain the allowlist opens when the adapter is
configured; local adapters open none.

| Adapter | Locality | Vendor | Constrain | Egress domain |
|---|---|---|---|---|
| `local_ollama` | local | Ollama | `format` = JSON Schema | none (loopback) |
| `local_llamacpp` | local | llama.cpp | GBNF grammar / `json_schema` | none (loopback) |
| `local_vllm` | local | vLLM | `guided_json` | none (loopback) |
| `local_lmstudio` | local | LM Studio | `response_format` json_schema | none (loopback) |
| `hosted_google` | hosted | Google | native structured output | Google API domain |
| `hosted_mistral` | hosted | Mistral | native structured output | Mistral API domain |
| `hosted_anthropic` | hosted | Anthropic | tool-schema | Anthropic API domain |
| `hosted_cohere` | hosted | Cohere | native structured output | Cohere API domain |
| `hosted_deepseek` | hosted | DeepSeek | OpenAI-compatible `response_format` | DeepSeek API domain |
| `hosted_alibaba` | hosted | Alibaba | OpenAI-compatible `response_format` | Alibaba API domain |
| `hosted_together` | hosted | Together | OpenAI-compatible `response_format` | Together API domain |
| `hosted_groq` | hosted | Groq | OpenAI-compatible `response_format` | Groq API domain |

All twelve vendors pass the exclusion gate: none is Meta, OpenAI, or xAI. Google is
explicitly permitted.

**Exact endpoint hostnames, request paths, current model identifiers, and structured-output
field names for the eight hosted providers were NOT VERIFIED in this pass.** The register
above records the design decision and the shape of each adapter, not verified API detail.
Confirm each against the provider's current documentation at implementation time — this is
precisely the kind of detail that goes stale, and eight providers is eight chances to ship
a wrong endpoint. Adapter implementation is gated on that verification (§7.1).

### Selecting a backend

```toml
# operator/openxr-operator.toml
[model]
backend = "local_ollama"        # any adapter id from the register
model   = "qwen2.5vl:7b"
# host is optional; local adapters default to loopback on their usual port

[model.egress]
# Empty for local adapters. A hosted adapter requires exactly one domain here,
# and it must match that adapter's registered domain, or startup fails.
allow = []
```

A hosted adapter configured with an empty or mismatched `egress.allow` fails at startup
rather than at first request, so the network permission is a visible, deliberate act.

## 4.5 The one honest complication in the gate

Your own engine has funding proximity to an excluded vendor. Meta funds W4 Games — a
partnership announced 14 March 2024 covering Godot on the Quest platform; W4 was
co-founded by Godot's creators. Separately, the Khronos Group funds the Godot OpenXR
Integration Project led by Bastiaan Olij, which shipped Render Models in 4.5 and Spatial
Entities in 4.6. Neither is a code, SDK, model, or infrastructure dependency. Both are
funding and governance proximity to the engine at the centre of the project. (CONFIRMED.)

This is decision D-02, and it should be made explicitly rather than discovered later. The
kit's position is that the gate is about dependency, not about who funds whom — but the
decision belongs to you, and the fact belongs in the record either way.

For contrast, and because it came up during research: Sneeze and the Open Metaverse
Browser Initiative are clean on this test. Sneeze's full dependency set — ANARI, Halogen,
Filament, Vox, Wasmtime, OpenXR-SDK, curl, RmlUi, BoringSSL, jwt-cpp, SPIRV tooling,
nlohmann/json — contains no Meta, OpenAI, or xAI code. Google appears twice (Filament,
BoringSSL) and is permitted. Meta and Google are both Metaverse Standards Forum members,
but MSF operates with no IP framework, so membership creates no licence or patent hook
into Sneeze. That is governance proximity, not dependency. (CONFIRMED.)

---

# Part 5 — The flow runner

This part specifies the declarative test layer, derived from Maestro's design and
re-implemented for Godot. Nothing here is copied code; Maestro is Apache-2.0, so even
direct reuse would be permitted, but these are patterns, not source.

## 5.1 What transfers, and what it becomes

| Maestro mechanism | What it actually does | Godot equivalent |
|---|---|---|
| `waitForAnimationToEnd` | Takes successive screenshots and compares them; when the screen is sufficiently static the animation is considered ended. Default timeout 15000 ms; **on timeout it succeeds and execution continues**. | Frame-stability settle detector (§5.2) with the same succeed-on-timeout default, configurable to fail |
| Implicit waits on assertions | `assertVisible` and `tapOn` poll until a per-command timeout rather than failing immediately; documentation directs users to assertions instead of explicit waits | Every assertion and every interaction polls; `sleep` is not in the command vocabulary |
| `retryTapIfNoChange` | Re-taps if the screen does not change after a tap — screen-change detection as an implicit post-action check | Post-action settle check with optional re-issue |
| `extendedWaitUntil` | Explicit long wait with a stated timeout, returns as soon as the condition holds | `wait_until` with an explicit condition and timeout |
| Normalised view hierarchy | Platform drivers produce one tree IR; element bounds to tap-centre computation happens in the platform-agnostic layer | Normalised node tree from the Godot driver; screen-space projection for spatial targeting |
| Relational selectors | `below`, `above`, `leftOf`, `rightOf`, `containsChild`, plus regex and `index` | Same, extended for 3D (§5.3) |
| `Driver` interface | A narrow typed boundary; everything above it has no idea which driver is running | `Driver` protocol (§5.5) — the seam that makes T1/T2/T3 and A1/A2/A3 interchangeable |
| YAML flows, no compile step | `appId` header, `---`, ordered command list; `runFlow`, `when`, `repeat`, `retry`, subflows | §5.4 |
| Watch mode | Continuously monitors test files and re-runs on change | `--watch` |
| `maestro studio` and artifact bundles | Inspector plus per-run screenshots, hierarchy dumps, command log; `--format junit` | §5.6 |

Two Maestro details worth carrying deliberately. Its `waitForAnimationToEnd` had a
documented bug (#2843) where the timeout was not respected — a warning that the settle
detector's timeout must be tested, not assumed. And Maestro moved its scripting engine
from Rhino to GraalJS in v2.0.0, removing Rhino entirely by v2.6.0, with no `async/await`
and no `fetch` available in flow scripts. If this kit ever adds scripting, keep it
deliberately small; that migration is what happens when it grows.

## 5.2 Settle detection

The mechanism that replaces every `time.sleep(2)` in v1.0 (F-014).

```
INPUT   capture()        -> grayscale frame, downscaled to 160x90
        interval         default 100 ms
        threshold        default 0.002 (mean absolute normalised difference)
        stable_samples   default 3 consecutive samples below threshold
        timeout          default 5000 ms
        on_timeout       'proceed' (default, matches Maestro) | 'fail'

ALGORITHM
  prev <- capture(); stable <- 0; t0 <- now()
  loop:
    sleep(interval)
    cur <- capture()
    d <- mean(abs(cur - prev)) / 255.0
    if d < threshold: stable <- stable + 1
    else:             stable <- 0
    prev <- cur
    if stable >= stable_samples: return SETTLED, elapsed
    if now() - t0 > timeout:
        if on_timeout == 'fail': return TIMEOUT_FAIL, elapsed
        else:                    return TIMEOUT_PROCEED, elapsed
```

Notes that matter in practice. Downscale before comparison or noise and dither dominate
the metric. Grayscale, because hue changes that do not alter structure should not defeat
settling. The threshold is scene-dependent: a scene with an idle animation or a particle
system never fully settles, which is why `stable_samples` and the timeout both exist, and
why the outcome — SETTLED versus TIMEOUT_PROCEED — is recorded per step in the artifact
bundle. A flow whose steps are all TIMEOUT_PROCEED is not a passing flow; it is a flow that
is not actually synchronising, and the report should make that visible.

## 5.3 Selector grammar

Selectors resolve against the normalised node tree. Attributes:

```
name:        exact or /regex/ match on Node.name
class:       Node.get_class(), including inherited match
path:        exact NodePath
text:        Control text properties (Label.text, Button.text, RichTextLabel)
group:       membership in a Godot node group
visible:     boolean
index:       disambiguator among otherwise-equal matches, 0-based
```

Relational operators, evaluated in screen space after projection so that 3D and 2D nodes
compose:

```
below: <selector>        above: <selector>
left_of: <selector>      right_of: <selector>
child_of: <selector>     contains: <selector>
near: <selector>         with max_distance in pixels, or metres for 3D
```

Resolution rules. Zero matches is an error unless the selector is marked `optional`.
Multiple matches without an `index` is an error — silently taking the first is how tests
become non-deterministic. Every resolution is logged with the candidate set, so a failure
report shows what else was on screen.

Deliberately excluded: absolute screen coordinates as a primary selector. They are
available as `point:` for the escape hatch, and flagged in the report as brittle.

**On the Scene Object Model.** OMBI's SOM is the obvious long-term target for a selector
grammar that outlives the engine binding. It is not one yet. Research found no retrievable
normative specification with defined object types, schema, versioning, or conformance
language — the architecture document explicitly presents concepts "for rigorous debate"
and invites challenge, which is a design discussion, not a ratified spec. Attempts to read
`omb.wiki/sneeze` and `omb.wiki/standards` returned only page metadata because the site is
a client-rendered SPA. Revisit at v2 (decision D-08). (BLOCKED — see Part 10.)

## 5.4 Flow format

```yaml
# flows/grab_and_throw.yaml
project: ../demo_project
scene: res://scenes/main.tscn
capture_tier: auto          # auto | t1 | t2 | t3
inject_tier: auto           # auto | a1 | a2 | a3
capabilities:               # everything not listed is denied
  - property_set
  - input_inject
env:
  CUBE: Main/GrabbableCube
---
- launch:
    clean: true
- settle: { timeout: 8000 }
- assert_visible:
    selector: { name: "${CUBE}", class: RigidBody3D }
- move_controller:
    hand: right
    position: [0.2, 1.2, -0.4]
    rotation: [0, 0, 0, 1]
- settle: {}
- press:
    hand: right
    action: grab
    value: 1.0
- settle: {}
- assert_property:
    selector: { name: "${CUBE}" }
    property: freeze
    equals: false
- capture: { label: "after-grab" }
- run_flow:
    file: subflows/verify_throw.yaml
    when: { platform: linux }
- repeat:
    times: 3
    commands:
      - press: { hand: right, action: trigger, value: 1.0 }
      - settle: {}
```

Rules. `settle` with no arguments uses defaults. There is no `sleep` command; its absence
is the point. `capabilities` defaults to empty, so a flow that does not declare
`property_set` cannot set properties regardless of what the model proposes. Flows are
validated against a JSON Schema before any step executes, so a typo fails in
milliseconds rather than at step 40.

## 5.5 The Driver boundary

The seam that makes capture and injection tiers interchangeable, and that would let a
second engine be added without touching the runner.

```python
from typing import Protocol, Literal, Any

CaptureTier = Literal["t1", "t2", "t3"]
InjectTier = Literal["a1", "a2", "a3"]

class Driver(Protocol):
    def launch(self, scene: str, clean: bool = False) -> None: ...
    def shutdown(self) -> None: ...

    def capture(self, tier: CaptureTier | None = None) -> "Frame": ...
    def scene_tree(self, root: str = "/root", depth: int = 6,
                   include: list[str] | None = None) -> "TreeNode": ...
    def get_property(self, path: str, prop: str) -> Any: ...

    def set_property(self, path: str, prop: str, value: Any) -> None: ...
    def move_controller(self, hand: Literal["left", "right"],
                        position: tuple[float, float, float],
                        rotation: tuple[float, float, float, float],
                        tier: InjectTier | None = None) -> None: ...
    def press(self, hand: Literal["left", "right"], action: str,
              value: float, tier: InjectTier | None = None) -> None: ...
    def restart_scene(self) -> None: ...

    @property
    def available_capture_tiers(self) -> list[CaptureTier]: ...
    @property
    def available_inject_tiers(self) -> list[InjectTier]: ...
```

Everything above this protocol is engine-agnostic. `Frame` carries the image bytes, the
tier actually used, a frame id, and a SHA-256 — the tier travels with the data so a report
can never claim a fidelity it did not have.

## 5.6 Run artifacts

Every run writes a directory, whether it passed or failed:

```
runs/2026-08-08T14-22-31Z/
  manifest.json        flow, git SHA, engine version, tiers used, environment
  commands.jsonl       one record per step: command, resolution, timing, outcome
  audit.jsonl          the §3.7 action log for this run
  frames/
    0001-launch.png
    0002-after-grab.png
  trees/
    0001.json
  model/
    0003-request.json  prompt, schema, and the images referenced by hash
    0003-response.json raw model output before validation
  junit.xml
  report.html
```

JUnit XML because it is what CI consumes. The raw model request and response are kept
because when an agent step goes wrong the interesting question is almost always what the
model actually saw and said, and reconstructing that after the fact is impossible.


# Part 6 — Reference implementations

Every listing is complete. Prerequisites are stated inline. Code targets Godot 4.7.x and
Python 3.11+.

## 6.1 Authenticated command server (GDScript)

Replaces v1.0 `server.gd`. Fixes F-001, F-006, F-009, F-027.

```gdscript
# addon/openxr_operator/server.gd
extends Node

const PROTOCOL_VERSION := 2
const PORT := 9099
const MAX_FRAME_BYTES := 1048576      # 1 MiB
const MAX_PEERS := 4
const MAX_MSGS_PER_SEC := 50
const AUTH_DEADLINE_MS := 2000
const IDLE_TIMEOUT_MS := 120000
const TOKEN_PATH := "user://openxr_operator.token"

var _server := TCPServer.new()
var _peers: Array = []               # Array[Dictionary]
var _token := ""

func _ready() -> void:
    _token = _load_or_create_token()
    if _server.listen(PORT, "127.0.0.1") != OK:
        push_error("openxr_operator: cannot listen on 127.0.0.1:%d" % PORT)
        return
    print("openxr_operator: listening on 127.0.0.1:%d (protocol %d)"
        % [PORT, PROTOCOL_VERSION])

func _exit_tree() -> void:
    for p in _peers:
        p.peer.close()
    _server.stop()

func _load_or_create_token() -> String:
    if FileAccess.file_exists(TOKEN_PATH):
        var rf := FileAccess.open(TOKEN_PATH, FileAccess.READ)
        if rf:
            var existing := rf.get_as_text().strip_edges()
            rf.close()
            if existing.length() == 64:
                return existing
    var raw := Crypto.new().generate_random_bytes(32)
    var hex := raw.hex_encode()
    var wf := FileAccess.open(TOKEN_PATH, FileAccess.WRITE)
    if wf == null:
        push_error("openxr_operator: cannot write token file")
        return hex
    wf.store_string(hex)
    wf.close()
    return hex

func _process(_delta: float) -> void:
    _accept_new()
    _pump_peers()

func _accept_new() -> void:
    if not _server.is_connection_available():
        return
    var conn := _server.take_connection()
    if _peers.size() >= MAX_PEERS:
        conn.disconnect_from_host()
        return
    var peer := WebSocketPeer.new()
    peer.max_queued_packets = 64
    peer.inbound_buffer_size = MAX_FRAME_BYTES
    if peer.accept_stream(conn) != OK:
        conn.disconnect_from_host()
        return
    _peers.append({
        "peer": peer,
        "authed": false,
        "opened_ms": Time.get_ticks_msec(),
        "last_seen_ms": Time.get_ticks_msec(),
        "window_start_ms": Time.get_ticks_msec(),
        "msgs_in_window": 0,
        "auth_attempted": false,
    })

func _pump_peers() -> void:
    var now := Time.get_ticks_msec()
    for i in range(_peers.size() - 1, -1, -1):
        var s: Dictionary = _peers[i]
        var peer: WebSocketPeer = s.peer
        peer.poll()
        var state := peer.get_ready_state()

        if state == WebSocketPeer.STATE_CLOSED:
            _peers.remove_at(i)
            continue
        if state != WebSocketPeer.STATE_OPEN:
            continue

        if not s.authed and now - s.opened_ms > AUTH_DEADLINE_MS:
            peer.close(1008, "auth timeout")
            continue
        if now - s.last_seen_ms > IDLE_TIMEOUT_MS:
            peer.close(1001, "idle")
            continue

        while peer.get_available_packet_count() > 0:
            var pkt := peer.get_packet()
            s.last_seen_ms = now
            if pkt.size() > MAX_FRAME_BYTES:
                peer.close(1009, "frame too large")
                break
            if not _rate_ok(s, now):
                peer.close(1008, "rate limit")
                break
            _on_packet(s, peer, pkt.get_string_from_utf8())

func _rate_ok(s: Dictionary, now: int) -> bool:
    if now - s.window_start_ms >= 1000:
        s.window_start_ms = now
        s.msgs_in_window = 0
    s.msgs_in_window += 1
    return s.msgs_in_window <= MAX_MSGS_PER_SEC

func _on_packet(s: Dictionary, peer: WebSocketPeer, text: String) -> void:
    var json := JSON.new()
    if json.parse(text) != OK:
        _reply(peer, {"error": "invalid json"})
        return
    var msg = json.data
    if typeof(msg) != TYPE_DICTIONARY or not msg.has("cmd"):
        _reply(peer, {"error": "missing cmd"})
        return

    var cmd := String(msg["cmd"])
    var rid = msg.get("id", null)

    if not s.authed:
        if cmd != "auth" or s.auth_attempted:
            peer.close(1008, "unauthenticated")
            return
        s.auth_attempted = true
        var supplied := String(msg.get("token", ""))
        var ver := int(msg.get("protocol", -1))
        if ver != PROTOCOL_VERSION:
            _reply(peer, {"id": rid, "error":
                "protocol mismatch: server %d" % PROTOCOL_VERSION})
            peer.close(1008, "protocol mismatch")
            return
        if not _constant_time_equals(supplied, _token):
            _reply(peer, {"id": rid, "error": "bad token"})
            peer.close(1008, "bad token")
            return
        s.authed = true
        _reply(peer, {"id": rid, "ok": true, "protocol": PROTOCOL_VERSION})
        return

    _dispatch(peer, cmd, msg, rid)

func _constant_time_equals(a: String, b: String) -> bool:
    if a.length() != b.length():
        return false
    var diff := 0
    for i in range(a.length()):
        diff |= a.unicode_at(i) ^ b.unicode_at(i)
    return diff == 0

func _dispatch(peer: WebSocketPeer, cmd: String, msg: Dictionary, rid) -> void:
    match cmd:
        "ping":
            _reply(peer, {"id": rid, "ok": true})
        "scene_tree":
            var root := String(msg.get("root", "/root"))
            var depth := clampi(int(msg.get("depth", 6)), 1, 32)
            _reply(peer, {"id": rid, "tree": _tree(root, depth)})
        "capture":
            var label := String(msg.get("label", "frame"))
            Capture.capture_async(label, func(result: Dictionary) -> void:
                _reply(peer, {"id": rid, "frame": result}))
        "get_property":
            var n := get_node_or_null(NodePath(String(msg.get("path", ""))))
            if n == null:
                _reply(peer, {"id": rid, "error": "node not found"})
            else:
                _reply(peer, {"id": rid,
                    "value": n.get(String(msg.get("property", "")))})
        "set_property":
            var n2 := get_node_or_null(NodePath(String(msg.get("path", ""))))
            if n2 == null:
                _reply(peer, {"id": rid, "error": "node not found"})
            else:
                n2.set(String(msg.get("property", "")), msg.get("value"))
                _reply(peer, {"id": rid, "ok": true})
        "inject":
            var res := Inject.apply(msg)
            _reply(peer, {"id": rid, "ok": res.ok, "tier": res.tier,
                "error": res.get("error", null)})
        "restart_scene":
            get_tree().reload_current_scene()
            _reply(peer, {"id": rid, "ok": true})
        "editor_rescan":
            # Cannot touch EditorInterface here (F-011). Ask the editor.
            if EngineDebugger.is_active():
                EngineDebugger.send_message("openxr_operator:rescan", [])
                _reply(peer, {"id": rid, "ok": true, "via": "debugger"})
            else:
                _reply(peer, {"id": rid, "error": "no debugger attached"})
        _:
            _reply(peer, {"id": rid, "error": "unknown cmd: " + cmd})

func _tree(root_path: String, max_depth: int) -> Dictionary:
    var root := get_node_or_null(NodePath(root_path))
    if root == null:
        return {}
    return _node_to_dict(root, max_depth)

func _node_to_dict(node: Node, depth_left: int) -> Dictionary:
    var out := {
        "name": String(node.name),
        "class": node.get_class(),
        "path": String(node.get_path()),   # F-015: cast NodePath to String
        "visible": (node.visible if node is CanvasItem or node is Node3D else true),
        "groups": node.get_groups(),
    }
    if node is Control and "text" in node:
        out["text"] = String(node.text)
    if depth_left <= 1:
        out["children_truncated"] = node.get_child_count()
        return out
    var kids := []
    for c in node.get_children():
        kids.append(_node_to_dict(c, depth_left - 1))
    out["children"] = kids
    return out

func _reply(peer: WebSocketPeer, data: Dictionary) -> void:
    peer.send_text(JSON.stringify(data))
```

## 6.2 Model backend protocol and adapters (Python)

Fixes F-019 and replaces the single hardcoded client. The protocol mirrors `Driver`
(§5.5): everything above it is backend-agnostic, and the adapter reports what it can do
rather than the harness assuming.

### 6.2.1 The protocol

```python
# operator/src/openxr_operator/model.py
"""ModelBackend protocol and registry. No vendor SDKs anywhere."""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

# Hosts that are denied unconditionally, after allowlist resolution.
# Not configurable. Not overridable by a flow, a config file, or an env var.
FORBIDDEN_HOSTS: frozenset[str] = frozenset({
    "api.openai.com", "openai.com", "www.openai.com",
    "oai.azure.com",              # OpenAI models via Azure
    "api.x.ai", "x.ai",           # xAI
    "llama.meta.com", "llama-api.meta.com",  # Meta
})

# Model identifiers whose lineage fails the vendor gate, checked at startup.
FORBIDDEN_MODEL_SUBSTRINGS: tuple[str, ...] = (
    "llama", "llava", "bakllava", "vicuna",
    "gpt-3", "gpt-4", "gpt-5", "o1-", "o3-", "o4-",
    "grok",
)


class ModelError(RuntimeError):
    pass


class BackendRejected(ValueError):
    """Raised at startup for a configuration that fails the gate."""


@dataclass(frozen=True)
class Capabilities:
    supports_constrained_output: bool
    supports_images: bool
    max_images_per_request: int
    locality: str                      # "local" | "hosted"
    egress_domain: str | None          # None for local


@dataclass(frozen=True)
class ModelResponse:
    raw: str
    parsed: dict[str, Any]
    model: str
    backend_id: str
    constrained: bool                  # was decoding actually constrained
    duration_ns: int
    usage: dict[str, int] = field(default_factory=dict)


@runtime_checkable
class ModelBackend(Protocol):
    """Implemented once per provider. Twelve implementations ship."""

    backend_id: str

    def capabilities(self) -> Capabilities: ...

    def health(self) -> bool:
        """True if the backend is reachable and the model is available."""
        ...

    def act(self, system: str, task: str, scene_tree: dict[str, Any],
            image_paths: list[Path],
            schema: dict[str, Any]) -> ModelResponse:
        """Send observation plus task, return a validated-shape response.

        Adapters that support constrained decoding must apply `schema` at the
        provider level and set ModelResponse.constrained = True. Adapters that
        cannot must set it False; the harness records the degraded posture
        (section 3.5) rather than pretending the constraint applied.
        """
        ...


def encode_images(paths: list[Path]) -> list[str]:
    return [base64.b64encode(p.read_bytes()).decode("ascii") for p in paths]


def assert_host_allowed(host: str, allowlist: list[str]) -> None:
    """Allowlist first, then unconditional denial. Denial always wins."""
    h = host.lower().strip().rstrip(".")
    if h not in {a.lower() for a in allowlist}:
        raise BackendRejected(f"host {h!r} not in egress allowlist")
    for bad in FORBIDDEN_HOSTS:
        if h == bad or h.endswith("." + bad):
            raise BackendRejected(f"host {h!r} is permanently denied")


def assert_model_allowed(model_id: str) -> None:
    m = model_id.lower()
    for bad in FORBIDDEN_MODEL_SUBSTRINGS:
        if bad in m:
            raise BackendRejected(
                f"model {model_id!r} matches excluded lineage {bad!r}")
```

### 6.2.2 Registry and resolution

```python
# operator/src/openxr_operator/backends/__init__.py
"""Adapter registry. Resolution fails closed."""
from __future__ import annotations

from typing import Callable

from ..model import BackendRejected, ModelBackend, assert_model_allowed

_REGISTRY: dict[str, Callable[..., ModelBackend]] = {}

LOCAL_IDS = (
    "local_ollama", "local_llamacpp", "local_vllm", "local_lmstudio",
)
HOSTED_IDS = (
    "hosted_google", "hosted_mistral", "hosted_anthropic", "hosted_cohere",
    "hosted_deepseek", "hosted_alibaba", "hosted_together", "hosted_groq",
)
ALL_IDS = LOCAL_IDS + HOSTED_IDS


def register(backend_id: str):
    def deco(factory: Callable[..., ModelBackend]):
        _REGISTRY[backend_id] = factory
        return factory
    return deco


def resolve(cfg: dict) -> ModelBackend:
    """Build the configured backend or refuse to start.

    No fallback. If the configured backend is unreachable the run fails with
    a named error; it does not silently switch to another backend, hosted or
    otherwise (section 4.4, manual configuration only).
    """
    backend_id = cfg.get("backend")
    if backend_id not in _REGISTRY:
        raise BackendRejected(
            f"unknown backend {backend_id!r}; known: {sorted(_REGISTRY)}")

    model_id = cfg.get("model", "")
    assert_model_allowed(model_id)

    allow = list(cfg.get("egress", {}).get("allow", []))
    backend = _REGISTRY[backend_id](cfg)
    caps = backend.capabilities()

    if caps.locality == "local":
        if allow:
            raise BackendRejected(
                f"{backend_id} is local; egress.allow must be empty")
    else:
        if len(allow) != 1 or allow[0] != caps.egress_domain:
            raise BackendRejected(
                f"{backend_id} requires egress.allow == "
                f"['{caps.egress_domain}']; got {allow}")

    if not backend.health():
        raise ModelUnreachable(
            f"backend {backend_id!r} unreachable; fix configuration. "
            "No automatic fallback is performed.")
    return backend


class ModelUnreachable(RuntimeError):
    pass
```

### 6.2.3 Local adapter — Ollama

```python
# operator/src/openxr_operator/backends/local_ollama.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from ..model import (Capabilities, ModelError, ModelResponse,
                     encode_images)
from . import register

DEFAULT_HOST = "http://127.0.0.1:11434"


@register("local_ollama")
class OllamaBackend:
    backend_id = "local_ollama"

    def __init__(self, cfg: dict) -> None:
        self._host = str(cfg.get("host", DEFAULT_HOST)).rstrip("/")
        self._model = str(cfg.get("model", "qwen2.5vl:7b"))
        self._client = httpx.Client(timeout=float(cfg.get("timeout_s", 180)))

    def capabilities(self) -> Capabilities:
        return Capabilities(
            supports_constrained_output=True,
            supports_images=True,
            max_images_per_request=8,
            locality="local",
            egress_domain=None,
        )

    def health(self) -> bool:
        try:
            return self._client.get(f"{self._host}/api/tags",
                                    timeout=5.0).status_code == 200
        except httpx.HTTPError:
            return False

    def act(self, system: str, task: str, scene_tree: dict[str, Any],
            image_paths: list[Path],
            schema: dict[str, Any]) -> ModelResponse:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",
                 "content": _user_text(task, scene_tree),
                 "images": encode_images(image_paths)},
            ],
            "stream": False,
            "format": schema,                      # constrained decoding
            "options": {"temperature": 0, "num_ctx": 8192},
        }
        try:
            r = self._client.post(f"{self._host}/api/chat", json=payload)
        except httpx.HTTPError as exc:
            raise ModelError(f"ollama unreachable: {exc}") from exc
        if r.status_code != 200:
            raise ModelError(f"ollama {r.status_code}: {r.text[:400]}")
        body = r.json()
        content = (body.get("message") or {}).get("content", "")
        return _finish(content, body.get("model", self._model),
                       self.backend_id, True,
                       int(body.get("total_duration", 0)))


def _user_text(task: str, scene_tree: dict[str, Any]) -> str:
    return (f"Task: {task}\n\n"
            f"Scene tree (JSON):\n{json.dumps(scene_tree, indent=2)}\n\n"
            "Reply with a single JSON object matching the required schema.")


def _finish(content: str, model: str, backend_id: str, constrained: bool,
            duration_ns: int) -> ModelResponse:
    if not content:
        raise ModelError("empty content from model")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ModelError(f"non-JSON from model: {content[:400]}") from exc
    if not isinstance(parsed, dict):
        raise ModelError("model returned JSON that is not an object")
    return ModelResponse(raw=content, parsed=parsed, model=model,
                         backend_id=backend_id, constrained=constrained,
                         duration_ns=duration_ns)
```

### 6.2.4 Local adapter — llama.cpp

Different constraint mechanism, different image encoding. This is why the twelve are
bespoke rather than one generic client.

```python
# operator/src/openxr_operator/backends/local_llamacpp.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from ..model import Capabilities, ModelError, ModelResponse, encode_images
from . import register
from .local_ollama import _finish, _user_text

DEFAULT_HOST = "http://127.0.0.1:8080"


@register("local_llamacpp")
class LlamaCppBackend:
    backend_id = "local_llamacpp"

    def __init__(self, cfg: dict) -> None:
        self._host = str(cfg.get("host", DEFAULT_HOST)).rstrip("/")
        self._model = str(cfg.get("model", "local"))
        self._client = httpx.Client(timeout=float(cfg.get("timeout_s", 180)))

    def capabilities(self) -> Capabilities:
        return Capabilities(
            supports_constrained_output=True,   # json_schema or GBNF
            supports_images=True,               # requires an mmproj build
            max_images_per_request=4,
            locality="local",
            egress_domain=None,
        )

    def health(self) -> bool:
        try:
            return self._client.get(f"{self._host}/health",
                                    timeout=5.0).status_code == 200
        except httpx.HTTPError:
            return False

    def act(self, system: str, task: str, scene_tree: dict[str, Any],
            image_paths: list[Path],
            schema: dict[str, Any]) -> ModelResponse:
        # llama-server speaks the OpenAI-compatible shape, which the gate
        # permits (section 4.4, D-10). Images are content parts, not a
        # top-level array as in Ollama.
        parts: list[dict[str, Any]] = [
            {"type": "text", "text": _user_text(task, scene_tree)}]
        for b64 in encode_images(image_paths):
            parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            })
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": parts},
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "action", "schema": schema,
                                "strict": True},
            },
        }
        try:
            r = self._client.post(f"{self._host}/v1/chat/completions",
                                  json=payload)
        except httpx.HTTPError as exc:
            raise ModelError(f"llama-server unreachable: {exc}") from exc
        if r.status_code != 200:
            raise ModelError(f"llama-server {r.status_code}: {r.text[:400]}")
        body = r.json()
        content = body["choices"][0]["message"]["content"]
        return _finish(content, self._model, self.backend_id, True, 0)
```

### 6.2.5 Hosted adapter — shape

The remaining ten follow the same shape. A hosted adapter differs in three ways only: it
declares `locality="hosted"` with its `egress_domain`, it reads its credential from the
environment rather than accepting it in config, and it uses the provider's own
structured-output mechanism.

```python
# operator/src/openxr_operator/backends/hosted_google.py  (representative)
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from ..model import (BackendRejected, Capabilities, ModelError,
                     ModelResponse, assert_host_allowed, encode_images)
from . import register
from .local_ollama import _finish, _user_text

# NOT VERIFIED: confirm host, path, model ids, and the structured-output
# field name against current provider documentation before shipping.
HOST = "generativelanguage.googleapis.com"


@register("hosted_google")
class GoogleBackend:
    backend_id = "hosted_google"

    def __init__(self, cfg: dict) -> None:
        assert_host_allowed(HOST, cfg.get("egress", {}).get("allow", []))
        self._key = os.environ.get("OPENXROP_GOOGLE_API_KEY")
        if not self._key:
            raise BackendRejected(
                "OPENXROP_GOOGLE_API_KEY not set; credentials are read from "
                "the environment, never from the config file")
        self._model = str(cfg.get("model", ""))
        self._client = httpx.Client(timeout=float(cfg.get("timeout_s", 180)))

    def capabilities(self) -> Capabilities:
        return Capabilities(
            supports_constrained_output=True,
            supports_images=True,
            max_images_per_request=8,
            locality="hosted",
            egress_domain=HOST,
        )

    def health(self) -> bool:
        # A cheap authenticated call against the provider's model listing.
        raise NotImplementedError("verify endpoint before implementing")

    def act(self, system: str, task: str, scene_tree: dict[str, Any],
            image_paths: list[Path],
            schema: dict[str, Any]) -> ModelResponse:
        raise NotImplementedError("verify endpoint before implementing")
```

Deliberately left `NotImplementedError`. The endpoint paths, current model identifiers,
and structured-output field names for all eight hosted providers were **NOT VERIFIED** in
this research pass. Writing plausible-looking calls here would be exactly the fabrication
this kit's own rules forbid. Each adapter is unblocked by one documentation check, and
§7.1 gates adapter merge on that check being recorded.
## 6.3 Action schema and validation

Fixes F-004. This schema is passed to the model as `format` *and* used to validate the
result. One definition, two uses — they cannot drift.

```python
# operator/src/openxr_operator/schema.py
"""Single source of truth for the action contract."""
from __future__ import annotations

from typing import Any

READ_ONLY_ACTIONS = frozenset({"observe", "assert_property", "finish"})
MUTATING_ACTIONS = frozenset({
    "set_property", "write_code", "assign_script",
    "move_controller", "press", "restart_scene",
})
ALL_ACTIONS = READ_ONLY_ACTIONS | MUTATING_ACTIONS

ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["action", "rationale"],
    "properties": {
        "action": {"type": "string", "enum": sorted(ALL_ACTIONS)},
        "rationale": {"type": "string", "maxLength": 500},
        "path": {"type": "string", "maxLength": 512},
        "property": {"type": "string", "maxLength": 128},
        "value": {},
        "file_path": {"type": "string", "maxLength": 512},
        "code": {"type": "string", "maxLength": 65536},
        "script_path": {"type": "string", "maxLength": 512},
        "hand": {"type": "string", "enum": ["left", "right"]},
        "action_name": {"type": "string", "maxLength": 64},
        "position": {
            "type": "array", "items": {"type": "number"},
            "minItems": 3, "maxItems": 3,
        },
        "rotation": {
            "type": "array", "items": {"type": "number"},
            "minItems": 4, "maxItems": 4,
        },
        "float_value": {"type": "number", "minimum": -1.0, "maximum": 1.0},
        "summary": {"type": "string", "maxLength": 1000},
    },
}

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "set_property": ("path", "property", "value"),
    "write_code": ("file_path", "code"),
    "assign_script": ("path", "script_path"),
    "move_controller": ("hand", "position", "rotation"),
    "press": ("hand", "action_name", "float_value"),
    "assert_property": ("path", "property", "value"),
    "restart_scene": (),
    "observe": (),
    "finish": ("summary",),
}


class ActionRejected(ValueError):
    pass


def validate_action(obj: dict[str, Any],
                    capabilities: frozenset[str]) -> dict[str, Any]:
    """Validate shape, then capability. Raises ActionRejected."""
    import jsonschema

    try:
        jsonschema.validate(obj, ACTION_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise ActionRejected(f"schema: {exc.message}") from exc

    action = obj["action"]
    for field in _REQUIRED_FIELDS[action]:
        if field not in obj:
            raise ActionRejected(f"{action} requires '{field}'")

    if action in MUTATING_ACTIONS and action not in capabilities:
        raise ActionRejected(
            f"'{action}' not granted by flow capabilities {sorted(capabilities)}"
        )
    return obj


def is_mutating(action: str) -> bool:
    return action in MUTATING_ACTIONS
```

## 6.4 Path containment

Fixes F-003.

```python
# operator/src/openxr_operator/fsguard.py
"""Contain model-supplied paths inside the project root."""
from __future__ import annotations

from pathlib import Path

ALLOWED_SUFFIXES = frozenset({".gd", ".tres", ".tscn", ".json", ".cfg", ".md"})
MAX_BYTES = 256 * 1024


class PathRejected(ValueError):
    pass


def safe_target(project_root: str | Path, relative_path: str) -> Path:
    """Resolve relative_path under project_root or raise.

    Handles the two pathlib traps: an absolute right-hand operand discards the
    base entirely, and '..' segments are not normalised by the join.
    """
    if not relative_path or relative_path.strip() != relative_path:
        raise PathRejected("empty or padded path")

    candidate = Path(relative_path)
    if candidate.is_absolute() or candidate.drive or candidate.root:
        raise PathRejected(f"absolute path rejected: {relative_path!r}")
    if any(part == ".." for part in candidate.parts):
        raise PathRejected(f"parent traversal rejected: {relative_path!r}")

    base = Path(project_root).resolve(strict=True)
    target = (base / candidate).resolve()

    if not target.is_relative_to(base):        # Python 3.9+
        raise PathRejected(f"escapes project root: {relative_path!r}")
    if target.suffix.lower() not in ALLOWED_SUFFIXES:
        raise PathRejected(f"suffix not allowed: {target.suffix!r}")
    if target.is_symlink():
        raise PathRejected("symlink target rejected")
    return target


def safe_write(project_root: str | Path, relative_path: str,
               content: str) -> Path:
    data = content.encode("utf-8")
    if len(data) > MAX_BYTES:
        raise PathRejected(f"content too large: {len(data)} bytes")
    target = safe_target(project_root, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target
```

## 6.5 Settle detector

Implements §5.2. Fixes F-014.

```python
# operator/src/openxr_operator/settle.py
"""Frame-stability settle detection. Replaces every sleep() in the loop."""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

import numpy as np
from PIL import Image


class SettleOutcome(str, Enum):
    SETTLED = "settled"
    TIMEOUT_PROCEED = "timeout_proceed"
    TIMEOUT_FAIL = "timeout_fail"


@dataclass(frozen=True)
class SettleResult:
    outcome: SettleOutcome
    elapsed_ms: int
    samples: int
    last_delta: float


def _fingerprint(png_bytes: bytes, size: tuple[int, int] = (160, 90)):
    img = Image.open(__import__("io").BytesIO(png_bytes))
    img = img.convert("L").resize(size, Image.BILINEAR)
    return np.asarray(img, dtype=np.float32)


def wait_for_settle(
    capture: Callable[[], bytes],
    interval_ms: int = 100,
    threshold: float = 0.002,
    stable_samples: int = 3,
    timeout_ms: int = 5000,
    on_timeout: str = "proceed",
) -> SettleResult:
    """Poll capture() until consecutive frames stop changing.

    on_timeout='proceed' matches Maestro's waitForAnimationToEnd, which
    succeeds and continues when the timeout is reached. Use 'fail' when the
    flow genuinely requires a quiescent scene.
    """
    t0 = time.monotonic()
    prev = _fingerprint(capture())
    stable = 0
    samples = 1
    delta = 1.0

    while True:
        time.sleep(interval_ms / 1000.0)
        cur = _fingerprint(capture())
        samples += 1
        delta = float(np.mean(np.abs(cur - prev))) / 255.0
        stable = stable + 1 if delta < threshold else 0
        prev = cur

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        if stable >= stable_samples:
            return SettleResult(SettleOutcome.SETTLED, elapsed_ms, samples, delta)
        if elapsed_ms > timeout_ms:
            outcome = (SettleOutcome.TIMEOUT_FAIL if on_timeout == "fail"
                       else SettleOutcome.TIMEOUT_PROCEED)
            return SettleResult(outcome, elapsed_ms, samples, delta)
```

## 6.6 Frame-synchronised capture (GDScript)

Fixes the synchronisation half of F-010. The XR half is unfixable in-engine; this is
tier T2.

```gdscript
# addon/openxr_operator/capture.gd
extends Node
class_name OperatorCapture

## Mirror-viewport capture (tier T2). Godot issue #100004 means capturing a
## use_xr viewport returns black, so we render a dedicated non-XR mirror.

@export var mirror_size := Vector2i(1280, 720)

var _mirror: SubViewport
var _mirror_cam: Camera3D
var _out_dir := "user://operator_frames"

func _ready() -> void:
    DirAccess.make_dir_recursive_absolute(ProjectSettings
        .globalize_path(_out_dir))
    _build_mirror()

func _build_mirror() -> void:
    _mirror = SubViewport.new()
    _mirror.size = mirror_size
    _mirror.use_xr = false                       # critical: not an XR viewport
    _mirror.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    _mirror.transparent_bg = false
    add_child(_mirror)

    _mirror_cam = Camera3D.new()
    _mirror_cam.current = true
    _mirror.add_child(_mirror_cam)

func _process(_delta: float) -> void:
    # Track the XR camera so the mirror shows what the user is looking at.
    var xr_cam := _find_xr_camera()
    if xr_cam and _mirror_cam:
        _mirror_cam.global_transform = xr_cam.global_transform
        _mirror_cam.fov = xr_cam.fov

func _find_xr_camera() -> Camera3D:
    var origins := get_tree().get_nodes_in_group("xr_origin")
    if origins.is_empty():
        var root := get_tree().current_scene
        return root.find_child("XRCamera3D", true, false) as Camera3D
    return (origins[0] as Node).find_child("XRCamera3D", true, false) as Camera3D

## Captures after the frame is actually drawn, then invokes cb with a dict.
func capture_async(label: String, cb: Callable) -> void:
    await RenderingServer.frame_post_draw          # required before readback
    var tex := _mirror.get_texture()
    if tex == null:
        cb.call({"error": "no mirror texture", "tier": "t2"})
        return
    var img := tex.get_image()
    if img == null or img.is_empty():
        cb.call({"error": "empty image", "tier": "t2"})
        return

    var png := img.save_png_to_buffer()
    var ts := Time.get_datetime_string_from_system(true).replace(":", "-")
    var path := "%s/%s-%s.png" % [_out_dir, ts, label]
    var f := FileAccess.open(path, FileAccess.WRITE)
    if f == null:
        cb.call({"error": "cannot write frame", "tier": "t2"})
        return
    f.store_buffer(png)
    f.close()

    cb.call({
        "path": ProjectSettings.globalize_path(path),
        "tier": "t2",
        "width": img.get_width(),
        "height": img.get_height(),
        "bytes": png.size(),
        "sha256": _sha256_hex(png),
        "black": _looks_black(img),
    })

func _sha256_hex(buf: PackedByteArray) -> String:
    var ctx := HashingContext.new()
    ctx.start(HashingContext.HASH_SHA256)
    ctx.update(buf)
    return ctx.finish().hex_encode()

## Cheap guard so we never silently report a black frame as a screenshot.
func _looks_black(img: Image) -> bool:
    var small := img.duplicate() as Image
    small.resize(32, 18, Image.INTERPOLATE_BILINEAR)
    var total := 0.0
    for y in range(small.get_height()):
        for x in range(small.get_width()):
            var c := small.get_pixel(x, y)
            total += (c.r + c.g + c.b) / 3.0
    return (total / float(small.get_width() * small.get_height())) < 0.01
```

## 6.7 Editor bridge over the debugger channel

Fixes F-011. Two halves: game side (already shown in 6.1 `editor_rescan`) and editor side.

```gdscript
# addon/openxr_operator/debugger_plugin.gd
@tool
extends EditorDebuggerPlugin

const CAPTURE := "openxr_operator"

func _has_capture(capture: String) -> bool:
    return capture == CAPTURE

func _capture(message: String, data: Array, session_id: int) -> bool:
    # message arrives as "openxr_operator:rescan"
    match message:
        CAPTURE + ":rescan":
            EditorInterface.get_resource_filesystem().scan()
            return true
        CAPTURE + ":assign_script":
            if data.size() >= 2:
                _assign(String(data[0]), String(data[1]))
            return true
        _:
            return false

func _assign(node_path: String, script_path: String) -> void:
    var fs := EditorInterface.get_resource_filesystem()
    fs.update_file(script_path)
    var res := ResourceLoader.load(script_path, "Script",
        ResourceLoader.CACHE_MODE_REPLACE)
    if res == null:
        push_error("openxr_operator: cannot load %s" % script_path)
        return
    # Editor-side assignment happens against the edited scene, not the
    # running game; the running game reloads the scene afterwards.
    var root := EditorInterface.get_edited_scene_root()
    if root == null:
        push_error("openxr_operator: no edited scene")
        return
    var node := root.get_node_or_null(NodePath(node_path))
    if node == null:
        push_error("openxr_operator: node not found in edited scene: %s"
            % node_path)
        return
    node.set_script(res)
    EditorInterface.save_scene()
```

```gdscript
# addon/openxr_operator/plugin.gd
@tool
extends EditorPlugin

const AUTOLOAD := "OpenXROperatorServer"
const SERVER := "res://addons/openxr_operator/server.gd"

var _dbg: EditorDebuggerPlugin

func _enter_tree() -> void:
    add_autoload_singleton(AUTOLOAD, SERVER)
    _dbg = preload("res://addons/openxr_operator/debugger_plugin.gd").new()
    add_debugger_plugin(_dbg)

func _exit_tree() -> void:
    if _dbg:
        remove_debugger_plugin(_dbg)
        _dbg = null
    remove_autoload_singleton(AUTOLOAD)
```

## 6.8 OpenXR API layer skeleton (tier T1)

Minimal but complete: negotiation, dispatch, and the two hooks that matter. The Vulkan
swapchain copy is the part you must write; its shape is indicated and the working
references are named in §2.3.

```cpp
// layer/src/layer.cpp  --  XR_APILAYER_OPENXROP_operator
#include <openxr/openxr.h>
#include <openxr/loader_interfaces.h>
#include <cstring>
#include <string>
#include <unordered_map>
#include <mutex>

namespace {

struct Dispatch {
    PFN_xrGetInstanceProcAddr   GetInstanceProcAddr = nullptr;
    PFN_xrDestroyInstance       DestroyInstance     = nullptr;
    PFN_xrEndFrame              EndFrame            = nullptr;
    PFN_xrReleaseSwapchainImage ReleaseSwapchainImage = nullptr;
};

std::mutex g_mutex;
std::unordered_map<XrInstance, Dispatch> g_dispatch;

Dispatch* lookup(XrInstance instance) {
    std::lock_guard<std::mutex> lock(g_mutex);
    auto it = g_dispatch.find(instance);
    return it == g_dispatch.end() ? nullptr : &it->second;
}

// ---- hooks ---------------------------------------------------------------

XRAPI_ATTR XrResult XRAPI_CALL
layer_xrReleaseSwapchainImage(XrSwapchain swapchain,
                              const XrSwapchainImageReleaseInfo* info) {
    // The frame is complete here and still owned by the application.
    // Capture point for tier T1: copy the image for the swapchain being
    // released into a staging buffer and write it out of band.
    // See capture_vulkan.cpp; references in section 2.3.
    CaptureIfArmed(swapchain);

    Dispatch* d = CurrentDispatch();
    return d->ReleaseSwapchainImage(swapchain, info);
}

XRAPI_ATTR XrResult XRAPI_CALL
layer_xrEndFrame(XrSession session, const XrFrameEndInfo* frameEndInfo) {
    RecordFrameStats(frameEndInfo->displayTime,
                     frameEndInfo->layerCount);
    Dispatch* d = CurrentDispatchForSession(session);
    return d->EndFrame(session, frameEndInfo);
}

XRAPI_ATTR XrResult XRAPI_CALL
layer_xrDestroyInstance(XrInstance instance) {
    Dispatch* d = lookup(instance);
    if (!d) return XR_ERROR_HANDLE_INVALID;
    PFN_xrDestroyInstance down = d->DestroyInstance;
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        g_dispatch.erase(instance);
    }
    return down(instance);
}

XRAPI_ATTR XrResult XRAPI_CALL
layer_xrGetInstanceProcAddr(XrInstance instance, const char* name,
                            PFN_xrVoidFunction* function) {
    if (std::strcmp(name, "xrEndFrame") == 0) {
        *function = reinterpret_cast<PFN_xrVoidFunction>(layer_xrEndFrame);
        return XR_SUCCESS;
    }
    if (std::strcmp(name, "xrReleaseSwapchainImage") == 0) {
        *function = reinterpret_cast<PFN_xrVoidFunction>(
            layer_xrReleaseSwapchainImage);
        return XR_SUCCESS;
    }
    if (std::strcmp(name, "xrDestroyInstance") == 0) {
        *function = reinterpret_cast<PFN_xrVoidFunction>(
            layer_xrDestroyInstance);
        return XR_SUCCESS;
    }
    Dispatch* d = lookup(instance);
    if (!d) return XR_ERROR_HANDLE_INVALID;
    return d->GetInstanceProcAddr(instance, name, function);
}

XRAPI_ATTR XrResult XRAPI_CALL
layer_xrCreateApiLayerInstance(const XrInstanceCreateInfo* info,
                               const XrApiLayerCreateInfo* layerInfo,
                               XrInstance* instance) {
    XrApiLayerCreateInfo next = *layerInfo;
    next.nextInfo = layerInfo->nextInfo->next;

    XrResult res = layerInfo->nextInfo->nextCreateApiLayerInstance(
        info, &next, instance);
    if (XR_FAILED(res)) return res;

    Dispatch d{};
    d.GetInstanceProcAddr = layerInfo->nextInfo->nextGetInstanceProcAddr;
    d.GetInstanceProcAddr(*instance, "xrDestroyInstance",
        reinterpret_cast<PFN_xrVoidFunction*>(&d.DestroyInstance));
    d.GetInstanceProcAddr(*instance, "xrEndFrame",
        reinterpret_cast<PFN_xrVoidFunction*>(&d.EndFrame));
    d.GetInstanceProcAddr(*instance, "xrReleaseSwapchainImage",
        reinterpret_cast<PFN_xrVoidFunction*>(&d.ReleaseSwapchainImage));

    std::lock_guard<std::mutex> lock(g_mutex);
    g_dispatch[*instance] = d;
    return XR_SUCCESS;
}

}  // namespace

extern "C" XRAPI_ATTR XrResult XRAPI_CALL
xrNegotiateLoaderApiLayerInterface(const XrNegotiateLoaderInfo* loaderInfo,
                                   const char* /*layerName*/,
                                   XrNegotiateApiLayerRequest* request) {
    if (!loaderInfo || !request) return XR_ERROR_INITIALIZATION_FAILED;
    if (loaderInfo->structType != XR_LOADER_INTERFACE_STRUCT_LOADER_INFO ||
        request->structType != XR_LOADER_INTERFACE_STRUCT_API_LAYER_REQUEST) {
        return XR_ERROR_INITIALIZATION_FAILED;
    }
    request->layerInterfaceVersion = XR_CURRENT_LOADER_API_LAYER_VERSION;
    request->layerApiVersion       = XR_CURRENT_API_VERSION;
    request->getInstanceProcAddr   = layer_xrGetInstanceProcAddr;
    request->createApiLayerInstance = layer_xrCreateApiLayerInstance;
    return XR_SUCCESS;
}
```

Manifest. Note the path: `explicit.d`, never `implicit.d` (§2.3 hard constraint).

```json
{
  "file_format_version": "1.0.0",
  "api_layer": {
    "name": "XR_APILAYER_OPENXROP_operator",
    "library_path": "./libXR_APILAYER_OPENXROP_operator.so",
    "api_version": "1.0",
    "implementation_version": "1",
    "description": "OpenXR Operator test instrumentation (explicit layer)"
  }
}
```

Launch script. This is the whole activation story — no installer, nothing persistent.

```bash
#!/usr/bin/env bash
# layer/scripts/run-with-layer.sh
# Activates the layer for ONE process only. Never installs system-wide.
set -euo pipefail

LAYER_DIR="${LAYER_DIR:-$(cd "$(dirname "$0")/../build" && pwd)}"
GODOT_BIN="${GODOT_BIN:-godot}"
PROJECT="${1:?usage: run-with-layer.sh <project-path> [godot args...]}"
shift || true

if [[ ! -f "$LAYER_DIR/XR_APILAYER_OPENXROP_operator.json" ]]; then
  echo "layer manifest not found in $LAYER_DIR" >&2
  exit 1
fi

export XR_API_LAYER_PATH="$LAYER_DIR"
export XR_ENABLE_API_LAYERS="XR_APILAYER_OPENXROP_operator"
export XR_LOADER_DEBUG="${XR_LOADER_DEBUG:-error}"
export OPENXROP_CAPTURE_DIR="${OPENXROP_CAPTURE_DIR:-$PWD/runs/frames}"
mkdir -p "$OPENXROP_CAPTURE_DIR"

exec "$GODOT_BIN" --path "$PROJECT" "$@"
```

```cmake
# layer/CMakeLists.txt
cmake_minimum_required(VERSION 3.20)
project(openxrop_layer LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(LAYER_NAME "XR_APILAYER_OPENXROP_operator")

find_package(Vulkan REQUIRED)

include(FetchContent)
FetchContent_Declare(OpenXR
  GIT_REPOSITORY https://github.com/KhronosGroup/OpenXR-SDK.git
  GIT_TAG        release-1.1.58)
FetchContent_MakeAvailable(OpenXR)

add_library(${LAYER_NAME} SHARED
  src/layer.cpp
  src/capture_vulkan.cpp)

target_link_libraries(${LAYER_NAME} PRIVATE OpenXR::headers Vulkan::Vulkan)
set_target_properties(${LAYER_NAME} PROPERTIES PREFIX "lib")

configure_file(
  ${CMAKE_SOURCE_DIR}/manifest/${LAYER_NAME}.json.in
  ${CMAKE_BINARY_DIR}/${LAYER_NAME}.json @ONLY)
```


# Part 7 — Pipeline, tests, provenance

## 7.1 Gates

Every gate is blocking unless marked otherwise. Each maps to findings it prevents from
recurring.

| Gate | Tool | Blocks on | Prevents |
|---|---|---|---|
| Format | `gdformat --check`, `ruff format --check` | Any diff | — |
| Lint | `gdlint`, `ruff check` | Any error | — |
| GDScript parse | `godot --headless --check-only --script` per file | Parse failure | F-028 |
| Python types | `mypy --strict` on `operator/` | Any error | — |
| Unit tests | `pytest`, `gdunit4` | Any failure | F-025 |
| Flow smoke test | runner against the demo project, headless | Any failure | F-025 |
| Vulnerabilities | `osv-scanner` on `uv.lock` and the SBOM | Any unignored finding | F-023 |
| Secrets | `gitleaks git -s . --log-opts=--all` | Any finding | — |
| **Vendor gate** | `tools/vendorscan.py` | Any Meta / OpenAI / xAI match | F-019, F-020, F-021 |
| **Licence gate** | `tools/vendorscan.py --licences` | Any dependency not on the allowlist | F-022, F-024 |
| **Implicit-layer gate** | `grep` for `implicit.d` and registry writes in `layer/` | Any match | §2.3 constraint |
| **Bind gate** | `grep` for `0.0.0.0` in `operator/`, `addon/` | Any match | F-002 |
| **OpenAI-host gate** | `grep` for `openai.com`, `oai.azure.com`, `api.x.ai`, Meta model hosts outside the denylist constant | Any match | Absolute rule |
| **Egress-pairing gate** | `tools/backendcheck.py` — every hosted adapter declares exactly one `egress_domain`, and no adapter's domain is on `FORBIDDEN_HOSTS` | Any mismatch | §3.6 |
| **Adapter-verification gate** | `tools/backendcheck.py --verified` — every non-`NotImplementedError` adapter has a dated documentation-check record in `backends/VERIFIED.md` | Any unverified adapter shipping live code | Fabricated endpoints |
| **No-fallback gate** | `grep` in `backends/` for fallback or retry-with-different-backend logic | Any match | §4.4 manual config only |
| SBOM | `cyclonedx-py` (or equivalent) | Generation failure | F-023 |
| Doc provenance | `tools/docdrift.py` | Warn only (non-blocking) | — |
| Provenance attestation | `actions/attest-build-provenance` | Failure on release only | — |

Three gates deserve comment. The vendor gate exists because a policy that lives only in a
document gets violated on the first convenient afternoon; as a grep over the lockfile and
the source tree it cannot be. The implicit-layer gate encodes the one architectural
constraint that separates this design from the tool whose author declared the approach
unsustainable. The bind gate is three characters of grep that would have prevented F-002.

Pin every action by commit digest, not tag — the Trivy tag-hijack of March 2026 (§4.2) is
the reason.

## 7.2 Workflow

```yaml
# .github/workflows/ci.yml
name: ci
on:
  push: { branches: [main] }
  pull_request:
permissions:
  contents: read

env:
  GODOT_VERSION: "4.7.1"

jobs:
  static:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with: { enable-cache: true }

      - name: Sync (frozen)
        run: uv sync --frozen --project operator

      - name: Format
        run: |
          uv run --project operator ruff format --check operator/
          uv run --project operator gdformat --check addon/

      - name: Lint
        run: |
          uv run --project operator ruff check operator/
          uv run --project operator gdlint addon/

      - name: Types
        run: uv run --project operator mypy --strict operator/src

      - name: Vendor gate
        run: uv run --project operator python tools/vendorscan.py --strict

      - name: Bind gate
        run: |
          if grep -rn --include='*.py' --include='*.gd' "0\.0\.0\.0" \
               operator/ addon/; then
            echo "::error::service bound to 0.0.0.0 (finding F-002)"
            exit 1
          fi

      - name: Implicit-layer gate
        run: |
          if grep -rn -e "implicit\.d" -e "ApiLayers\\\\Implicit" layer/ ; then
            echo "::error::implicit layer installation is forbidden"
            exit 1
          fi

      - name: OpenAI-host gate
        run: |
          # The denylist constant in model.py is the one legitimate mention.
          if grep -rn --include='*.py' --include='*.gd' --include='*.toml' \
               -e "openai\.com" -e "oai\.azure\.com" -e "api\.x\.ai" \
               operator/ addon/ | grep -v "src/openxr_operator/model.py"; then
            echo "::error::reference to a forbidden vendor host"
            exit 1
          fi

      - name: Backend gates
        run: |
          uv run --project operator python tools/backendcheck.py --verified

      - name: No-fallback gate
        run: |
          if grep -rniE "fallback|try_next_backend|switch_backend" \
               operator/src/openxr_operator/backends/ ; then
            echo "::error::automatic backend fallback is forbidden (4.4)"
            exit 1
          fi

      - name: Secrets
        run: |
          curl -sSfL -o gitleaks.tar.gz \
            https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz
          tar xzf gitleaks.tar.gz gitleaks
          ./gitleaks git -s . --log-opts=--all --redact --exit-code 1

      - name: SBOM
        run: uv run --project operator cyclonedx-py environment -o sbom.json

      - name: Vulnerabilities
        uses: google/osv-scanner-action/.github/workflows/osv-scanner-reusable.yml@v2.3.8
        with:
          scan-args: |-
            --lockfile=operator/uv.lock
            --sbom=sbom.json

      - name: Doc provenance (warn only)
        continue-on-error: true
        run: uv run --project operator python tools/docdrift.py

  test:
    runs-on: ubuntu-24.04
    needs: static
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --frozen --project operator
      - run: uv run --project operator pytest -q

      - name: Fetch Godot
        run: |
          curl -sSfL -o godot.zip \
            "https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}-stable/Godot_v${GODOT_VERSION}-stable_linux.x86_64.zip"
          unzip -q godot.zip && mv Godot_v*_linux.x86_64 /usr/local/bin/godot
          chmod +x /usr/local/bin/godot

      - name: GDScript parse check
        run: |
          find addon -name '*.gd' -print0 | while IFS= read -r -d '' f; do
            godot --headless --check-only --script "$f" \
              || { echo "::error file=$f::parse failed"; exit 1; }
          done

      - name: gdUnit4
        run: |
          godot --headless --path demo_project \
            -s addons/gdUnit4/bin/GdUnitCmdTool.gd \
            -a addon/tests -rd reports
      - uses: actions/upload-artifact@v4
        if: always()
        with: { name: test-reports, path: reports/ }

  flow-smoke:
    runs-on: ubuntu-24.04
    needs: test
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --frozen --project operator
      - name: Run demo flow headless (T3 capture, no model)
        run: |
          xvfb-run -a uv run --project operator \
            openxr-operator run flows/smoke.yaml \
            --capture-tier t3 --no-model --junit reports/flows.xml
      - uses: actions/upload-artifact@v4
        if: always()
        with: { name: flow-run, path: runs/ }
```

Note what the smoke job does not do: it does not call a model. The flow runner must be
usable as a deterministic test harness with the agent turned off, because a test suite
whose outcomes depend on a language model is not a test suite. The model is a client of
the runner, not a component of it.

## 7.3 Test strategy

| Level | Scope | Tool | Runs |
|---|---|---|---|
| Unit (Python) | selectors, settle maths, path guard, schema validation, flow parsing | pytest | Every push |
| Unit (GDScript) | tree serialisation, protocol framing, injection binding assertion | gdUnit4 | Every push |
| Contract | wire protocol round-trip against a fake engine and a fake agent | pytest | Every push |
| Integration | real Godot headless, demo project, T3 capture | gdUnit4 + runner | Every push |
| Flow | declarative flows against the demo project | runner | Every push |
| Model-in-loop | full agent loop against a pinned local model | runner | Nightly, non-blocking |
| XR | Monado simulated device, layer loaded | runner | Manual until D-04 |

Model-in-loop is non-blocking on purpose. Model output varies; gating merges on it makes
the pipeline a coin toss. It runs nightly and its failures open issues rather than
blocking work.

Specific tests that must exist, because they map to findings that were only findable by
reading carefully:

- Auth: unauthenticated command is rejected and the connection closes (F-001).
- Auth: wrong protocol version closes with a clear message (F-027).
- Path guard: absolute path, `..` traversal, symlink, and oversize all raise (F-003).
- Schema: an action not in the flow's capabilities is rejected even if well-formed (F-004).
- Capture: a black frame is detected and reported as such, not returned as a screenshot
  (F-010).
- Injection: an injection that binds no `XRController3D` raises rather than no-ops (F-012).
- Settle: the timeout is actually honoured — Maestro shipped a bug where it was not.

## 7.4 Documentation provenance

Adopted from Sneeze's DocDrift, which is a Python script using git log path filtering, and
whose front matter records the source files a page documents and the short commit SHA the
page was last verified against. Ships under Apache-2.0; reusable in an AGPL project with
attribution. (CONFIRMED.)

Every document in this kit that describes code carries:

```yaml
---
sources:
  - addon/openxr_operator/server.gd
  - operator/src/openxr_operator/godot_driver.py
verified: a1b2c3d
---
```

The checker runs `git log <verified>..HEAD -- <sources>` and flags any page whose sources
moved. It is warn-only in CI, which is the right default: blocking merges on documentation
drift trains people to lie in the front matter. If you want it blocking, Fiberplane's
`drift` does exactly that and is the more mature option.

The reason this matters for this project specifically: the audit posture demands that
nothing be asserted without evidence, and that unverified claims be labelled. That
requirement decays the moment code changes underneath a written finding. Front-matter
provenance turns a standing instruction into a mechanical check.

Known limitations, inherited: the `sources` list is hand-maintained, so it catches changes
to files a page lists, not coverage a page forgot to list. Renames appear as a change on
the old path and require manual fix-up.

## 7.5 Supply chain

Lockfile `uv.lock` committed; CI uses `uv sync --frozen`. SBOM in CycloneDX (current spec
1.7, adopted as ECMA-424 2nd edition December 2025) or SPDX (current 3.0.1) — osv-scanner
consumes either via Package URLs. Godot addons have no package ecosystem, so vendored
addons are pinned by commit and enumerated in the SBOM by hand; osv-scanner does not cover
GDScript. Release artifacts get provenance via `actions/attest-build-provenance` (GA since
25 June 2024; current major v3, with GitHub steering new users to `actions/attest@v4`).
SLSA v1.2 is the current approved specification, approved 24 November 2025 and backwards
compatible with v1.1 — target Build L2 initially, L3 when releases are automated.
(All CONFIRMED.)

---

# Part 8 — Build plan

RPI applies: research, then plan, then implement. No code before `AUDIT.md` and `PLAN.md`
exist on disk. Rule 9 applies: nothing destructive or irreversible without listing it first
and getting explicit approval.

## Milestones

**M0 — Repository and gates.** Repo layout per §2.6, split licences in place, `uv` project
with committed lockfile, all §7.1 gates wired and passing on an empty codebase. Nothing
else. *Acceptance:* CI green; vendor gate demonstrably fails when `openai` is added to the
lockfile, and passes when removed. Resolves F-023, F-026.

**M1 — Authenticated transport.** `server.gd` per §6.1; Python client; contract tests.
*Acceptance:* unauthenticated command closes the connection; wrong protocol version
reports clearly; 1 MiB frame rejected; 51st message in a second closes the peer. Resolves
F-001, F-006, F-009, F-027.

**M2 — Observation.** Scene tree with depth limiting and filtering; T2 mirror capture with
`frame_post_draw` gating and black-frame detection; T3 desktop mode. *Acceptance:* capture
against an XR-enabled demo project returns a non-black frame at a declared tier; the black
detector trips when the mirror camera is deliberately pointed into a void. Resolves F-010
(T2/T3 scope), F-015, F-016.

**M3 — Actuation, tier A3.** Tracker injection constrained to `left_hand` / `right_hand`
with pose `default`, plus a binding assertion. Editor bridge over the debugger channel.
*Acceptance:* injection moves a bound `XRController3D`; injection with a bogus tracker name
raises rather than silently doing nothing; `editor_rescan` completes and a newly written
script is loadable. Resolves F-011, F-012.

**M4 — Flow runner.** Settle detector, selector resolution, YAML flows with schema
validation, driver protocol, artifact bundle, JUnit output. *Acceptance:* the demo flow
runs headless in CI with the model disabled and produces a complete run bundle; no `sleep`
appears anywhere in the runner. Resolves F-014, F-029.

**M5 — Agent loop, local backends.** `ModelBackend` protocol, registry, and the four local
adapters (Ollama, llama.cpp, vLLM, LM Studio). Schema-constrained decoding with capability
negotiation, action validation, capability allowlist, diff-then-approve gate, audit log,
egress restriction, filesystem jail. *Acceptance:* a mutating action cannot execute without
an approval record; a model response violating the schema is rejected, retried once, then
aborted; path traversal attempts are rejected with the attempt logged; an unreachable
backend fails with a named error and does not switch to another; a backend reporting
`supports_constrained_output = False` marks every step degraded in the run report.
Resolves F-003, F-004, F-007, F-008, F-019.

**M5b — Hosted backends.** The eight hosted adapters (Google, Mistral, Anthropic, Cohere,
DeepSeek, Alibaba, Together, Groq), each implemented natively, each gated on a dated
documentation-check record in `backends/VERIFIED.md`. *Acceptance:* every hosted adapter
refuses to start without its single matching egress domain and its environment credential;
the OpenAI-host denial cannot be overridden by config, flow, or environment variable; a
model identifier matching excluded lineage is rejected at startup even when the provider
passes the gate; no fallback path exists between any two adapters.

**M6 — Web UI.** Loopback bind, Origin allowlist, token gate, vendored assets, CSP,
loading and empty and error states, keyboard navigation and visible focus. *Acceptance:*
WCAG 2.2 AA baseline pass; no third-party origin in any response; page functions with the
network cable unplugged. Resolves F-002, F-005, F-030.

**M7 — Tier T1 and A2 (gated on D-04).** OpenXR API layer, Vulkan swapchain capture,
layer-level pose injection, Monado simulated-device CI job. *Acceptance:* a frame captured
through the layer differs measurably from the T2 mirror frame under stereo rendering,
demonstrating that it is genuinely the composited output; the implicit-layer gate still
passes. Resolves F-010 fully, F-013.

## Definition of done

- Fresh clone builds and runs with the documented commands; zero lint, type, or parse
  errors, or documented suppressions with justification.
- Every flow in `flows/` completes end to end with no unhandled exception, on two
  consecutive full runs from a clean state.
- Every async surface has loading, empty, and error states; failures degrade to a lower
  tier or a clear error, never a silent black frame.
- `osv-scanner` clean or accepted risks recorded in `osv-scanner.toml` with a reason and
  an expiry; repository and full git history scanned for secrets, none present.
- Vendor gate and licence gate pass; SBOM generated and committed for the release.
- All model output validated against the schema before use; no unaudited dynamic execution.
- Loopback binding everywhere; token auth on the engine port; Origin allowlist on the UI
  port; CSP set with no third-party origins.
- Accessibility baseline: keyboard-navigable, visible focus, semantic markup, alt text,
  contrast checked.
- `README.md` covers setup, build, run, and the tier model; `CHANGELOG.md` records the
  v1.0 to v2.0 deltas.
- Every claim in `SHIP.md` is either verified with evidence or marked UNTESTED.

## Non-goals for v1

Unity or Unreal support. Cloud inference of any kind. Multi-agent orchestration. Voice
input. Model fine-tuning. Publishing to the Godot Asset Store. Any feature of v1.0's
"Extending the Kit" section. Targeting the OMBI Scene Object Model (D-08).

---

# Part 9 — Agent prompts

Two prompts, both self-contained, both ready to paste.

## 9.1 Adversarial audit prompt

Paste as the first message in a project whose knowledge base contains the artifacts under
audit.

```text
# Adversarial QA and Production-Readiness Audit — OpenXR Operator

PROJECT: OpenXR Operator — local, privacy-first AI agent for Godot XR development
INTENT: An agent observes a running Godot XR app, reads its scene tree, and acts on it
        via a declarative flow runner, using a locally-hosted vision-language model
DEPLOY TARGET: Developer workstation. Godot addon (MIT) + Python CLI/UI (AGPL-3.0+)
        + optional OpenXR API layer (MIT). No hosted component.

## Mission

You are the adversarial auditor. The knowledge base is the artifact under audit — treat
every document in it as claims to test, not context to trust. Prior model outputs in the
KB carry no authority. Find every reason this fails before code is written, then produce
numbered amendments and a go/no-go verdict.

## Posture

Audit, do not assist. Improve the spec, not morale. Burden of proof is on the KB. A
positive verdict carries the same evidentiary burden as a teardown: "looks solid" is not
a finding — show the closest calls you cleared. If the project as specified should not be
built, say so and say why.

## Operating rules

Zero fabrication. Every external factual claim gets a primary source with a date, or an
UNVERIFIED tag. Never fill a gap with plausible detail.

Four epistemic states, and you must use all four honestly:
  CONFIRMED    — primary source, cited, dated
  INFERRED     — reasoned from primary evidence; show the reasoning
  BLOCKED      — you tried to retrieve it and failed; say what you tried and how it failed
  NOT ATTEMPTED — you did not spend a retrieval on it; say so plainly
Never present NOT ATTEMPTED as BLOCKED. Collapsing "I did not look" into "I could not
confirm" is itself a finding against you.

Evidence or it did not happen. Every finding quotes the KB (file and section) or states
ABSENT explicitly.

Licensing gate: the in-engine addon must be permissive (MIT/BSD/Apache) because a
copyleft GDScript addon loaded in-process risks reaching users' games; out-of-process
components should be AGPL-3.0-or-later. Verify the split holds end to end, including
dependencies.

Vendor gate: no Meta, OpenAI, or xAI anywhere — direct or transitive, SDKs, models, APIs,
infrastructure. Google is permitted. Distinguish (a) technical dependency, (b) governance
or funding proximity, (c) no relationship. Only (a) is a Blocker; (b) is a finding
requiring an explicit human decision.

Rule 9: amendments are proposals until approved. Recommend nothing destructive or
irreversible for execution without explicit go-ahead.

Web research is expected wherever the KB is unverifiable or thin. Primary sources,
publication dates, per-phase source ledger.

Terse. No hyperbole, no praise, no restating the KB back to me.

One phase per response. End each phase with its ledger and STOP. Wait for GO.

## Finding format

F-### | Severity | Category | Location | Evidence (quote or ABSENT) | Why it matters |
Recommended fix | Confidence (H/M/L)

BLOCKER: build fails, product is wrong, legal/security/licensing breach, or a
cheap-to-avoid irreversible decision. MAJOR: significant rework or risk if unfixed
pre-build. MINOR: fix during build. NIT: polish.
IDs stable for the whole audit. Amendments are A-##. Human decisions are D-##.

## Phases

Phase 0 — Inventory and scope contract. Enumerate every KB file: purpose, freshness,
inter-document dependencies. State what the KB claims the project is, in five lines, from
evidence. Name the documents you expected and did not find. Declare the committed stack.
State what this audit will and will not cover. STOP.

Phase 1 — Claims, sources, epistemic audit. Extract every load-bearing factual claim.
Verify against primary sources or mark UNVERIFIED / FALSE / STALE with dates. Flag
citations that do not say what the KB says they say. Pay specific attention to: the
current Godot stable version; whether the described engine APIs exist and are callable
from the process the KB says calls them; whether the recommended models have the licence
and lineage the KB implies. Produce a source ledger. STOP.

Phase 2 — Logic, models, assumptions. Contradiction hunt across all documents. Surface
hidden assumptions; rank the five most load-bearing and stress-test each: what breaks if
false, how we would detect it, cost of being wrong. Every "we will X" must have a stated
mechanism; missing mechanism is a finding. STOP.

Phase 3 — Architecture, security, infra, SDLC. Data flows, trust boundaries, authn/authz,
failure modes, degraded behaviour. Threat model, STRIDE-lite acceptable. Secrets, supply
chain, SBOM stance, dependency policy. Repo layout, CI gates, test pyramid, release,
observability. Verify the licensing and vendor gates concretely against the dependency
list, not in the abstract. Pay specific attention to any locally-bound network service:
who can reach it, how it authenticates, and what a web page the user visits can do to it.
STOP.

Phase 4 — Product and UX. Reconstruct the users and their jobs from evidence; unsupported
persona claims are findings. Walk each primary flow end to end. Audit information
architecture, empty/error/loading states, accessibility to WCAG 2.2 AA intent, first five
minutes. Anything the UI promises that the architecture cannot deliver is a Blocker. STOP.

Phase 5 — Unknown unknowns. Premortem: twelve months post-launch the project is dead;
write the three most probable obituaries from evidence. Red-team personas: hostile power
user, abuse actor, exhausted first-time user, future maintainer inheriting the repo,
hostile platform. Comparables scan: three to five nearest projects, living and dead; what
killed the dead ones, what the living ones all do that this KB ignores. Expert-question
test: the five questions a domain expert asks in ten minutes that the KB cannot answer.
Checklist delta against a standard production-readiness checklist. STOP.

Phase 6 — Build strategy and kickoff prompt. Audit phasing, milestone acceptance criteria,
definition of done, dependency ordering, what is deferred and why. Spec completeness test:
could a competent stranger build this without asking questions? Every question they would
ask is a finding. Then rewrite the implementation kickoff prompt as a standalone block.
STOP.

Phase 7 — Synthesis and verdict. Consolidated deduplicated ledger. Numbered amendments
A-01..A-N: exact document, exact change, findings resolved, ordered by dependency then
severity. Remediation backlog for anything not fixable by amendment, with human decisions
listed separately as D-01..D-N. Verdict: READY / READY WITH AMENDMENTS (name the gating
ones) / NOT READY (state the kill criteria). Close with the one sentence you would put at
the top of the repo README.
```

## 9.2 Implementation kickoff prompt

Paste into Claude Code at the repository root.

```text
# Mission

Build the OpenXR Operator to a production-ready, shippable state, following the build kit
in docs/BUILD_KIT.pdf and its source markdown in docs/kit/. The architecture, tier model,
security design, and licence split in that kit are canonical — refine execution, do not
redesign. Where intent is ambiguous, follow the dominant pattern already in the kit and
log the ambiguity in AUDIT.md; do not invent a new direction.

# Operating rules

1. RPI: Research, then Plan, then Implement. No code changes until AUDIT.md and PLAN.md
   exist on disk.
2. Rule 9: no destructive or irreversible action — force-push, history rewrite, file or
   branch deletion, dependency removal — without listing it first and getting explicit
   approval.
3. Zero fabrication. Every claim in every report is backed by something you ran, read, or
   can cite from a primary source. Use four labels and use them honestly: CONFIRMED,
   INFERRED, BLOCKED (say what you tried and how it failed), NOT ATTEMPTED (say so
   plainly). Never write "could not confirm" for something you did not attempt.
4. Preserve the licence split: addon/ and layer/ are MIT, operator/ is AGPL-3.0-or-later,
   repository default AGPL-3.0-or-later. Keep LICENSES/ and NOTICE accurate.
5. Vulnerability scanning: osv-scanner. Never Trivy — its action tags were hijacked in
   March 2026 (GHSA-69fq-xp46-6x23). Pin every GitHub Action by commit digest.
6. Vendor gate: no Meta, OpenAI, or xAI dependency, direct or transitive. Google is
   permitted. tools/vendorscan.py enforces this and must stay green.
7. The OpenXR layer is explicit and environment-scoped only. Never write an implicit
   layer manifest, never write to the Khronos registry keys. This is a CI gate.
8. No service binds anything but 127.0.0.1. This is a CI gate.
9. Terse output. Findings over narration. No hyperbole.

# Phase 1 — Research (read-only)

- Map the repository: stack, entry points, build and run commands, every user-facing flow.
- Build and run it. Document actual behaviour per flow against intended behaviour.
- Verify current best practice for Godot 4.7.x, the OpenXR loader, uv, gdUnit4, and
  osv-scanner against primary sources current as of today. Flag anything the kit specifies
  that is now deprecated, changed, or known-vulnerable.
- Confirm or refute, from primary sources, the three claims the whole architecture rests
  on: (a) Godot issue #100004 is still open and viewport capture under use_xr returns
  black; (b) EditorInterface is unavailable in the running game process; (c)
  WebSocketPeer.accept_stream exposes no inbound Origin header. If any has changed, stop
  and report before proceeding — the architecture would need revisiting.
- Write AUDIT.md: findings ranked P0 (security or broken) / P1 (correctness or UX) /
  P2 (polish), each with file:line and evidence.

# Phase 2 — Plan

Write PLAN.md: ordered fixes mapped to audit findings and to the kit's F-### ledger,
acceptance criteria per item, explicit non-goals. Follow the kit's milestone order M0
through M6; M7 only if explicitly approved. Then proceed — no approval gate unless Rule 9
triggers.

# Phase 3 — Implement

Work PLAN.md in priority order. One logical change per commit, clear messages referencing
the finding id. No scope creep. Every document describing code carries the front matter
`sources:` and `verified:` per the kit section 7.4.

# Phase 4 — Verification loop

Repeat:
1. Build from clean state.
2. Run every flow in flows/ end to end with the model disabled, then with it enabled.
3. Log pass/fail per flow with evidence in VERIFICATION.md, including the capture tier and
   settle outcome for every step.
4. Fix failures.

Exit when every Definition of Done item in the kit passes on two consecutive full runs.
If the same failure survives three fix attempts, stop and write BLOCKERS.md with
root-cause analysis instead of thrashing.

# Definition of done

Use the kit's Part 8 Definition of Done verbatim. It is the contract.

# Final report

SHIP.md: what changed, what was tested with evidence, known limitations, residual risks,
deploy and install steps. Every claim verified or marked UNTESTED. Include a table of the
kit's F-### findings and their disposition.
```

---

# Part 10 — Source ledger and open items

## 10.1 Source ledger

| Source | Date / version | Supports | Tier |
|---|---|---|---|
| github.com/godotengine/godot/issues/100004 | Open, checked 8 Aug 2026 | Black viewport under XR output override | Primary |
| Godot class reference, `XRPositionalTracker`, `XRServer`, `XRController3D` | 4.7 stable docs | Tracker API present, not deprecated | Primary |
| Godot PR #90645 | Merged 22 Apr 2024, milestone 4.3 | XR tracker hierarchy rework | Primary |
| Godot PR #104207 | Godot 4.5 | D3D12 OpenXR backend | Primary |
| Godot viewport documentation | 4.x | `await RenderingServer.frame_post_draw` before readback | Primary |
| Godot `EngineDebugger`, `EditorDebuggerPlugin` class refs; PR #39440 | Current | Debugger capture channel mechanism | Primary |
| Godot `WebSocketPeer` class reference and `modules/websocket/` | Current | `accept_stream` internalises handshake; no Origin getter | Primary |
| godotengine.org/releases/4.7 | 18–19 Jun 2026 | 4.7 "Director's Cut" is current stable | Primary |
| Khronos OpenXR loader specification, `api_layer.adoc` | OpenXR 1.1 | Layer discovery, `XR_API_LAYER_PATH`, `XR_ENABLE_API_LAYERS`, explicit vs implicit | Primary |
| Khronos registry, `xrSetInputDeviceLocationEXT` man page | OpenXR 1.1 | `XR_EXT_conformance_automation` function set and intended use | Primary |
| github.com/mbucchia/OpenXR-Toolkit + mbucchia.github.io/OpenXR-Toolkit | v1.3.2; discontinued 2024 | MIT; hook points; screenshot and stats paths; no Vulkan; author's retrospective | Primary |
| deepwiki.com/mbucchia/OpenXR-Toolkit/3.1 | Jun 2025 | Intercepted-function table, dispatch structure | Secondary (code-derived) |
| github.com/BuzzteeBear/OpenXR-MotionCompensation | v0.3.10.0-beta, 8 Jun 2025 | LGPL-2.1; Windows-only; hardware-free operation via `testrotation` and MMF virtual trackers; one-way CSV recording | Primary (docs) |
| github.com/Ybalrid/OpenXR-API-Layer-Template | MIT, REUSE 3.0 | Layer scaffolding; negotiate/dispatch; env-var activation; Linux and Windows | Primary |
| github.com/LunarG/gfxreconstruct + USAGE_desktop_OpenXR.md | MIT; OpenXR experimental | Requires Vulkan layer concurrently; no desktop Linux OpenXR; JSONL convert; replay ignores recorded XR input | Primary |
| docs.maestro.dev + mobile-dev-inc/maestro CHANGELOG | v2.x | `waitForAnimationToEnd` screenshot-stability with 15 s default, succeeds on timeout; implicit waits; GraalJS migration; issue #2843 | Primary |
| ollama.com/blog/structured-outputs; docs.ollama.com | Current | `format` accepts JSON Schema; works with vision; `images` array | Primary |
| github.com/MetaversalCorp/Sneeze | 363 commits, Apache-2.0 | Canonical upstream; dependency set; platforms; `tools/DocDrift` | Primary |
| Sneeze `tools/DocDrift/README.md` | Current | `sources` / `verified` front matter; `git log <verified>..HEAD -- <sources>`; exit codes; warn-only intent | Primary |
| metaverse-standards.org FAQ, members, board | Current | MSF has no IP framework; Meta and Google are members | Primary |
| businesswire.com RP1 Artemis release | 6 Jul 2026 | Artemis, Sneeze, OMBI, SOM framing | Primary |
| GHSA-69fq-xp46-6x23 | Mar 2026 | Trivy release and action-tag compromise; safe versions | Primary |
| OWASP LLM Top 10 (2025); OWASP WebSocket Security Cheat Sheet; OWASP ASVS 13.5.2 | 2024–2025 | LLM01/05/06; Origin allowlist and auth for CSWSH | Primary |
| developer.chrome.com/blog/local-network-access; Chrome 147 notes | Oct 2025 / Apr 2026 | LNA prompt in 142; WebSocket enforcement in 147; Firefox and Safari have not | Primary |
| Hugging Face model cards: Qwen2.5-VL, LLaVA-1.6-vicuna-13b, BakLLaVA, MiniCPM-V, DeepSeek-VL2 | Current | Licences and base-model lineage | Primary |
| slsa.dev; github.com/actions/attest-build-provenance; spdx.dev; CycloneDX 1.7 / ECMA-424 | 2025–2026 | SLSA v1.2 approved 24 Nov 2025; attestation GA 25 Jun 2024; SPDX 3.0.1; CycloneDX 1.7 | Primary |
| docs.astral.sh/uv; google.github.io/osv-scanner; github.com/gitleaks/gitleaks | Current | Lockfile and frozen sync; SBOM input and `osv-scanner.toml`; gitleaks 8.30.1 MIT, feature-complete | Primary |
| BusinessWire, 14 Mar 2024 (Meta and W4 Games); Godot OpenXR Integration Project | 2024–2026 | Funding proximity in the Godot XR toolchain | Primary |

## 10.2 Blocked — retrieval attempted and failed

| Item | What was tried | How it failed |
|---|---|---|
| OMBI Scene Object Model normative specification | Fetched `omb.wiki/`, `omb.wiki/sneeze`, `omb.wiki/sneeze/architecture/sneeze-architecture` | Client-rendered SPA; returned page metadata and a tag-manager noscript URL only. Partial content recovered via search snippets. |
| `OpenXR-MotionCompensation` hooked-function list | Requested the layer source tree and `layer.cpp` / `framework/layer_apis.py` blobs | GitHub returned ROBOTS_DISALLOWED on the tree and PERMISSIONS_ERROR on the blobs. Function list inferred from changelog and manual. Clone the repository to confirm. |
| Sneeze raw `LICENSE` and `NOTICE` bytes | Repository root listing retrieved | Files listed but raw contents not opened; Apache-2.0 confirmed from README text only. No CLA or DCO visible. |
| Godot 4.7 `XRPositionalTracker` member table | Fetched the class reference page | Page loaded; the rendered method table did not extract. `set_pose` and `set_input` signatures remain inferred from PRs #90645, #71830, #81239 and prior-version docs. |
| rp1.com/artemis platform and download details | Fetched the page | Client-rendered SPA; metadata only. |

## 10.3 Not attempted — stated plainly

No retrieval was spent on any of the following. They are not "uncertain"; they are
unexamined, and should be closed before the corresponding design decision is finalised.

- Sneeze most-recent-commit date and exact contributor count.
- A dedicated definition of "RMAP", which appeared in OMBI press-release tags.
- omb.wiki changelog or edit history.
- The Sneeze `.github/workflows` YAML confirming how DocDrift is actually wired.
- GFXReconstruct issue #2145, which holds the list of known-working OpenXR applications.
- Producing or inspecting an actual converted OpenXR JSONL trace record.
- Licence, stars, and last-commit dates for `sigr3s/Recording-OpenXR-API-Layer` and
  `mbucchia/OpenXR-Layer-Template`.
- Exhaustive current MSF roster to fix Meta's present tier, and definitive confirmation
  that OpenAI and xAI are absent; full board roster by name.
- Current GUT version and its Godot 4.7 compatibility statement.
- The specific "Godot VR Simulator" addon credited to Aerton Oliveira: repository, licence,
  version, maintenance status.
- Exact licence strings on the Ollama `gemma3` and `moondream` model cards.
- **Every API detail for all eight hosted providers** — Google, Mistral, Anthropic, Cohere,
  DeepSeek, Alibaba, Together, Groq. Endpoint hostnames, request paths, current
  vision-capable model identifiers, structured-output field names, credential header
  formats, rate-limit semantics, and image-encoding conventions. §4.4 and §6.2.5 record the
  design decision and adapter shape only. The hosted adapter listing deliberately raises
  `NotImplementedError` rather than showing plausible-looking calls. Eight providers is
  eight chances to ship a wrong endpoint, so §7.1's adapter-verification gate blocks merge
  until each is checked and dated in `backends/VERIFIED.md`.
- Whether llama.cpp, vLLM, and LM Studio's current builds accept the exact
  `response_format` / `guided_json` shapes written in §6.2.4 and the register, and whether
  each requires a specific multimodal build for image input.
- Exact current `uv` and `osv-scanner` patch versions, and confirmation that `uv.lock` is
  on the osv-scanner supported-lockfile list at the version you pin.
- Live re-confirmation from w3.org that WCAG 2.2 remains the current Recommendation and of
  XAUR's current status.
- Whether an official JSON Schema for Maestro flow YAML exists; whether the Go
  "maestro-runner" rewrite has shipped; Maestro's exact LICENSE file.
- Precise FSF AGPL FAQ wording on section 13 and on plug-ins as combined works. The
  reasoning in Part 4 is sound but the quotations should be verified before appearing in a
  legal notice.
- A documented headless-null compositor environment variable for Monado.
- LICENSE files and current activity for the five candidate Godot MCP servers, which bears
  on decision D-07.

## 10.4 Decision register

Carried forward from §0.4 for tracking. None of these has been made.

| ID | Decision | Owner | Status |
|---|---|---|---|
| D-01 | Primary platform for the API layer | Human | Open |
| D-02 | Accept Meta funding proximity in the Godot XR toolchain | Human | Open |
| D-03 | In-engine addon licence | Human | Open |
| D-04 | Build the API layer in v1 or defer to v2 | Human | Open |
| D-05 | Agent sandbox mechanism | Human | Open |
| D-06 | Whether destructive actions ever auto-apply | Human | Open |
| D-07 | Reuse an existing Godot MCP server or build the bridge | Human | Open, blocked on licence audit |
| D-08 | Target the OMBI Scene Object Model in the selector grammar | Human | Open |
| D-09 | Model backend policy | Human | **DECIDED** — swappable adapters; any provider except Meta, OpenAI, xAI; twelve bespoke adapters, not one generic client |
| D-10 | Does the gate cover the OpenAI request format | Human | **DECIDED** — no. The gate covers OpenAI's servers, SDK, and models only |
| D-11 | Inference locality | Human | **DECIDED** — local first, not local only. Hosted permitted, opt-in |
| D-12 | Local-first fallback behaviour | Human | **DECIDED** — manual configuration only. No automatic switch to hosted |
| D-13 | Egress containment with hosted backends | Human | **DECIDED** — allowlist of specific provider domains, one per configured adapter |

Earlier drafts of this register carried a "default if unanswered" column in which every row
was pre-filled with an answer. That column was removed. Pre-filling a decision and calling
it a default is deciding it; the rows above are either DECIDED by the human or Open.


