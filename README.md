# OpenXR Operator

**Build XR experiences by describing them.**

OpenXR Operator is an AI agent that watches your running Godot XR application, understands what's in it, and acts on it — moving controllers, navigating menus, writing and fixing code — while you stay in charge. You describe what you want in plain language. It proposes every change in plain language. Nothing happens until you approve it (D-14).

This is an open-source, vendor-clean alternative to Meta's XR Operator, built for the Godot engine. No coding required to use it. No cloud service required to run it. No data leaves your machine unless you explicitly configure it to.

## Why this exists

Meta's XR Operator demonstrated that an AI agent can meaningfully help build and test XR experiences. But it's locked to Meta's hardware, Meta's AI services, and Meta's ecosystem. OpenXR Operator takes the same core idea — an agent that sees your XR app and acts on your instructions — and builds it open, private, and independent:

- **Open source.** The in-engine plugin is MIT-licensed (use it however you want). The agent is AGPL-3.0-or-later (modifications must stay open).
- **Privacy-first.** The AI runs on your own machine by default. Your project's screenshots and scene data never leave your computer unless you explicitly opt in to a hosted AI provider — and even then, it connects to exactly one provider you choose, never silently (D-12).
- **No vendor lock-in.** Meta, OpenAI, and xAI are permanently blocked at the code level — not by policy, by architecture (D-11). The system is built for the open ecosystem, not to feed another platform's moat.
- **Godot-native.** Built for Godot 4.7+, the open-source game engine. No Unity. No Unreal. No proprietary runtime.

## Who this is for

- **Creators (no code):** Tell it what to build or fix. It sees your running app, proposes each action in plain English, and executes only what you approve — step by step.
- **XR developers:** The same approval loop, plus a declarative flow runner for repeatable, version-controlled test sessions you can script in YAML and run without any AI model involved.

## How it works

The system has two main pieces that talk to each other through a secure local-only connection:

**The Godot addon** (runs inside your project). A small plugin that instruments your running app — it can see the scene tree (the hierarchy of every object in your project), capture what's on screen, and carry out approved actions like moving objects, injecting scripts, or restarting scenes. It only accepts connections from your own machine (localhost / 127.0.0.1), and every connection requires a security token before anything else happens — not even an error message goes back without it.

**The local agent** (runs alongside your project). A Python program on your computer that connects to the addon, observes what's happening in your app, and decides what to do based on your instructions. It sends the AI model a screenshot and the scene structure, gets back a proposed action, validates that action against a strict schema, and presents it to you in plain language for approval. Nothing executes without your yes.

The AI model runs locally by default using Ollama (D-12). It does not contact any cloud service unless you manually configure a hosted provider — and it will never silently fall back to a cloud service if the local model is slow or unavailable (D-13). Every model, local or hosted, connects through the same standardized interface called the ModelBackend contract (D-10), so you can swap models without changing anything else in the system.

### The approval loop (D-14)

When the agent wants to do something that changes your project — set a property, inject a script, restart a scene — it generates a plain-language card describing what it intends to do and why. That card appears in the web interface. You read it and click approve or reject. If you reject it, the rejection is logged and the agent moves on. If you approve, the action executes and the result is recorded. There is no auto-approve mode. Every mutation requires an explicit human decision.

### Deterministic flows (no AI involved)

You can also write flows in YAML that script a sequence of actions — useful for repeatable test runs. These execute against the same addon and driver but skip the AI model entirely. The flow runner validates the YAML at parse time, executes each step, records timing (measured to within ±50 ms), and produces a results bundle with a JUnit report you can check into version control. Hand-writing these files is never required; the system can generate them.

**Canonical design document:** `docs/BUILD_KIT_v3.pdf` (Kimi Code Swarm Edition).
**Build coordination:** see `swarm/STATUS.md` and `docs/prompts/`.

## Current status

The MVP implementation is complete and unit-tested: 123 Python tests passing (2 marked skips), plus the Godot-side test suites (85 tests across server, rendering, injection, and editor bridge). What's built and verified:

- Authenticated addon with connection limits and token-first security
- Driver — the bridge between the agent and the addon, with id-matching, capability checks, and tier/hash verification
- Flow runner for scripted, model-free test sessions
- Agent loop with plain-language approval cards (approve executes; reject and capability violations never reach the wire)
- Hash-chained, tamper-evident audit log with automatic secret redaction
- File-system guard that blocks path traversal, absolute paths, symlinks, and oversized writes
- Loopback web UI with CSP headers, origin allowlisting, and token-required access

See `SHIP.md` for the full evidence list and `CHANGELOG.md` for the decision register (build kit Part 8).

**What hasn't been tested yet** (see `SHIP.md` for details):
- **Real model-in-the-loop:** The full cycle — AI model seeing your app, proposing actions, you approving them — hasn't been run end to end on actual hardware yet. The latency measurement (S-11) and model-digest pinning (S-09) are outstanding.
- **Real addon ↔ driver contract round-trip:** Unit fakes on both sides are green; the live pairing over a real WebSocket is the remaining proof.
- **XR headset:** No headset test. Current capture is screen-based (T2/T3 tiers); headset-native composited-frame capture (T1) is deferred to v2 (D-04).
- **Fresh-clone install** on a second machine, and a usability pass with a non-developer user.
- **WCAG 2.2 AA formal audit:** Keyboard, focus, empty, and error states are built in, but no formal accessibility audit has been run.

## Getting started (local, no cloud required)

Everything runs on your machine. No account to create, no service to sign up for.

### What you need installed

- **Godot 4.7.1** — the open-source game engine ([godotengine.org](https://godotengine.org)). This is where your XR project lives.
- **Python 3.11 or newer** — the language the agent runs on. Most systems have it; check with `python --version` in a terminal.
- **uv** — a fast Python package manager ([docs.astral.sh/uv](https://docs.astral.sh/uv)). Used to install the agent's dependencies with exact, locked versions.
- **Ollama** — a local AI model runner ([ollama.com](https://ollama.com)). This runs the AI on your machine instead of in the cloud. You'll need to pull the default model: `ollama pull qwen2.5vl:7b` (a 7-billion-parameter vision-language model, roughly 4–5 GB download).

### Step by step

**Step 1 — Install the addon into your Godot project.**
Copy the folder `addon/openxr_operator/` into your project's `addons/` directory (so the path looks like `<your-project>/addons/openxr_operator/`). Open your project in Godot, go to Project → Project Settings → Plugins, and enable "OpenXR Operator." Run your project once — the addon writes a security token file to your Godot user data directory at `user://openxr_operator.token`. You'll need the path to this file in step 4.

**Step 2 — Install the agent's dependencies.**
In a terminal, from the repo root:
```
uv sync --project operator
```
This installs everything the Python agent needs, locked to exact tested versions.

**Step 3 — Start Ollama.**
Make sure Ollama is running (it usually starts automatically after installation). If you haven't pulled the default model yet:
```
ollama pull qwen2.5vl:7b
```

**Step 4 — Launch the agent.**
```
uv run --project operator openxr-operator ui \
  --project <your-project> \
  --token-file <path-to-engine-token> \
  [--godot <godot-binary>]
```
Replace `<your-project>` with the path to your Godot project folder and `<path-to-engine-token>` with the path to the token file from step 1. Add `--godot <godot-binary>` if the Godot executable isn't on your system PATH.

**Step 5 — Open the web interface.**
The terminal prints a URL like `http://127.0.0.1:5000/?token=...` — open it in your browser. This is where you describe what you want and approve or reject each action card. The interface runs entirely locally; it never contacts any external server.

### Running a scripted flow (no AI model contacted)

```
uv run --project operator openxr-operator run flows/smoke.yaml \
  --token-file <path-to-engine-token>
```
This runs a scripted test flow against your project without involving any AI model — useful for repeatable, deterministic testing.

## Project structure

| Path | Licence | What it does |
|---|---|---|
| `addon/` | MIT | The in-engine Godot plugin (GDScript). Runs inside your project and gives the agent eyes and hands — scene access, screen capture, and action execution. |
| `layer/` | MIT | An optional OpenXR API layer (C++17/CMake). Only activates when explicitly enabled for a specific application — never system-wide, never automatically. Currently deferred to v2 (D-04). |
| `operator/` | AGPL-3.0-or-later | The Python agent, flow runner, and web UI. The brain that observes, plans, proposes, and — with your approval — acts. |
| `docs/contracts/` | — | Five frozen contracts defining how the pieces talk to each other: wire protocol, Driver interface, action schema, flow schema, and ModelBackend. "Frozen" means they don't change once set, which keeps the system stable and predictable. |
| `flows/` | — | Declarative test flows — scripted sequences of actions saved as YAML files. These are saved artifacts; hand-writing them is never required. |
| `tools/` | — | Automated enforcement scripts: vendor scanning, documentation-vs-code drift checking, and action-pinning verification. The machinery behind the gates described below. |
| `swarm/` | — | Build coordination: task cards, requests, decisions, and status tracking for the AI agents that built this project. The swarm builds the product; it is not part of the shipped product. |

## Automated safety checks (Gates)

Every change to the codebase must pass all of the automated checks listed below before it can be merged. Every one is blocking — if any single check fails, the change is rejected. Together, they enforce the project's security, licensing, vendor-independence, and quality commitments without relying on anyone remembering to check manually.

| Gate | What it checks |
|---|---|
| **Vendor gate** | Scans all code and dependency lock files to confirm nothing from Meta, OpenAI, or xAI is present — packages, imports, API endpoints. If someone adds an `openai` package, this fails immediately. |
| **Licence gate** | Verifies every component carries the correct open-source licence (MIT for the addon and layer, AGPL for the agent). |
| **Bind gate** | Confirms the system only listens on `127.0.0.1` (your machine only), never on `0.0.0.0` (all network interfaces, which would expose it to other devices on your network). |
| **Implicit-layer gate** | Ensures the optional OpenXR layer cannot activate itself silently — it must be explicitly enabled per application, per environment. |
| **Secrets scan** | Searches the entire Git commit history for accidentally committed passwords, API keys, or tokens (using gitleaks, a checksummed binary). |
| **SBOM + vulnerability scan** | Generates a complete inventory of every dependency (a Software Bill of Materials) and checks each one against databases of known security vulnerabilities (using osv-scanner). |
| **Format / lint / types** | Enforces consistent code style (ruff), catches common programming errors, and verifies type correctness across the Python codebase (mypy --strict). |
| **GDScript parse** | Validates that all the Godot addon code is syntactically correct and passes lint (gdformat + gdlint). |
| **pytest** | Runs the full Python test suite — 123 tests covering security boundaries, driver behaviour, approval logic, audit logging, file-system guards, and more. |
| **gdUnit4** | Runs the Godot-side test suites covering the server, rendering pipeline, script injection, and editor bridge. |
| **Flow smoke test** | Runs a test flow end to end with the AI model disabled, proving the entire pipeline — YAML parsing, driver communication, action execution, result bundling — works independently of any AI model. |

## Security model (non-negotiable)

These are architectural commitments, not configuration options. They cannot be turned off.

**Your data stays on your machine.**
The system only accepts connections from localhost — no device on your network can reach it. By default, it makes zero outbound connections. If you configure a hosted AI provider, it opens exactly one outbound connection to that provider's domain. The trade-off is explicit and documented: every hosted provider you enable is a path by which a screenshot of your project and its scene tree leave the machine (D-12).

**No connection to Meta, OpenAI, or xAI. Ever.**
These vendors' endpoints are on a permanent deny list applied after all other network resolution and cannot be overridden by configuration (D-11). Azure OpenAI and api.llama.com endpoints are also denied.

**Authentication before everything.**
The engine port requires a security token on the very first message of every connection. Nothing happens before that token is verified — not even an error message confirming what commands exist. One attempt, two-second deadline, connection closed on failure.

**The browser never touches the engine.**
The web interface talks to the agent. The agent talks to the engine. The browser has no direct connection to your running Godot project — a compromised browser tab cannot reach the engine.

**AI output is treated as untrusted data.**
Everything the AI model produces is schema-validated, checked against an allowlist of permitted actions, and presented to you as a plain-language card describing what it wants to do. If it passes validation and you approve, it executes. If it fails validation, it gets one retry, then the attempt is aborted. The model cannot bypass the schema, the allowlist, or your approval (D-14). Model observation content is explicitly delimited as untrusted in the rendering pipeline (D-17).

**Tamper-evident audit log.**
Every action — proposed, approved, rejected, executed — is recorded in a hash-chained log. Each entry's hash incorporates the previous entry's hash, forming a chain. If anyone edits, deletes, or reorders entries, the chain breaks and the tampering is detectable. The log includes a head anchor for truncation detection and automatically redacts secrets.

**OpenXR layer is explicit and scoped.**
The optional OpenXR API layer (deferred to v2, D-04) only activates when explicitly enabled for a specific application in a specific environment. It never installs system-wide and never activates on its own. No implicit manifest.
