---
sources: docs/BUILD_KIT_v3.pdf (v3.2, 10 Aug 2026); repo state as executed
verified: 2026-08-11 (UTC) — W0 preflight executed on the build host
---

# AUDIT.md — OpenXR Operator

Orchestrator ledger. Epistemic labels per kit §0.2: CONFIRMED / INFERRED /
BLOCKED / NOT ATTEMPTED / UNTESTED. Findings use W0-## IDs to avoid collision
with kit F-001…F-030 and v3.0-audit F-1## namespaces.

## 1. Scope & inputs

1. `docs/BUILD_KIT_v3.pdf` v3.2 — canonical design. Ingested in full (CONFIRMED).
2. Audit ledgers — v3.0 suspect dispositions S-01…S-16 carried by kit Part 4;
   decisions D-10…D-14 recorded in `swarm/decisions/`.
3. Repo as it exists — prior session produced partial W1 (licences, contracts,
   CI, decisions D-10…D-14) before any W0 record. Logged as disagreement D-log-1.

Kit F-001…F-030 full text lives in build kit **v2.0**, which is not in this
repo (only the v3.2 PDF is). Mapping in PLAN.md uses the v3.2 references to
those findings. Label: BLOCKED (v2.0 document absent; only v3.2 present).

## 2. W0 preflight report (executed 2026-08-11 UTC, host: Windows 11 + WSL2 Ubuntu)

### 2.1 Toolchain

| Tool | Required | Found | Verdict |
|---|---|---|---|
| Godot | 4.7.1 | absent on PATH → provisioned `.tools/godot/Godot_v4.7.1-stable_linux.x86_64`, sha512-verified vs official `SHA512-SUMS.txt`; `--version` → `4.7.1.stable.official.a13da4feb` (executed in WSL) | CONFIRMED (was P0, resolved) |
| Python | ≥3.11 | 3.13.14 (Windows), 3.14.4 (WSL) | CONFIRMED |
| uv | any | 0.12.2 | CONFIRMED |
| CMake + C++17 compiler | cmake + compiler | cmake 4.4.2; **no g++/cl/clang++ on host or WSL** | P0 for W6 only (W0-02) |
| Ollama | any | 0.32.6; `GET /api/tags` → `{"models":[]}` (no model pulled — W4 task) | CONFIRMED |
| git | any | 2.54.0 | CONFIRMED |

### 2.2 Sandbox preflight (D-05 — answered by human: WSL2 Ubuntu, bubblewrap 0.11.1)

Executed in WSL2 Ubuntu (kernel `6.18.33.2-microsoft-standard-WSL2`):

```
$ bwrap --unshare-user --ro-bind / / --proc /proc --dev /dev true
rc=0
```

- `bwrap --version` → 0.11.1 (`/usr/bin/bwrap`) — CONFIRMED by execution.
- `kernel.unprivileged_userns_clone`: sysctl absent on this kernel (no restriction).
- `/proc/sys/kernel/apparmor_restrict_unprivileged_userns`: absent (WSL2 kernel
  does not carry Ubuntu's AppArmor userns restriction).
- Verdict: sandbox available; no EPERM. D-05 resolved — bubblewrap in WSL2.
  CONFIRMED by execution.

### 2.3 Hardware envelope (S-11, measured)

| Item | Measured |
|---|---|
| CPU | AMD Ryzen 5 7530U (Zen 3 mobile, 6c/12t) |
| RAM | 16,535,863,296 B ≈ 15.4 GiB total |
| GPU | AMD Radeon integrated (Ryzen APU), 512 MiB dedicated + shared; no discrete GPU, no `nvidia-smi` |

Against kit model table (Qwen2.5-VL-7B ≈ 6–8 GB at Q4; Gemma 3 12B ≈ 8–12 GB):
7B Q4 is feasible only from system RAM on CPU/iGPU — expect high per-step
latency; 12B is not viable on this host. Provisional floor (to be measured, not
estimated, in W4): 16 GiB RAM class host, Qwen2.5-VL-7B Q4 via Ollama; GPU
contention with an XR runtime is untested here (no XR runtime on this host).
Label: CONFIRMED (inventory measured); latency UNTESTED.

### 2.4 CI command dry-run (every command in `.github/workflows/ci.yml`, executed locally)

| CI step | Result |
|---|---|
| `uv sync --frozen --project operator` | OK (lockfile frozen) |
| `ruff format --check operator/` | 9 files already formatted |
| `ruff check operator/` | All checks passed |
| `mypy --strict operator/src` | no issues in 7 source files |
| `gdformat --check addon/` | 1 file unchanged, rc=0 |
| `gdlint addon/` | no problems, rc=0 |
| `python3 tools/vendorscan.py` | vendor gate: clean, rc=0 |
| `bash tools/check-action-pins.sh` | digest gate: all pinned, rc=0 |
| bind gate grep (`0\.0\.0\.0` in operator/, addon/) | clean |
| implicit-layer gate grep (`implicit\.d`, `ApiLayers\Implicit` in layer/) | clean |
| Secrets: gitleaks 8.30.1 tarball downloaded, `sha256sum -c tools/gitleaks.sha256` OK; `gitleaks git . --log-opts=--all --redact --exit-code 1` → 23 commits, no leaks, rc=0 | OK |
| SBOM: `cyclonedx-py environment` | `.tools/sbom.json` generated (91,360 B) |
| `pytest -q` | 10 passed |
| GDScript parse: `timeout 60 godot --headless --check-only --script <f>` (in WSL) | `PARSE OK: addon/openxr_operator/protocol.gd` — timeout wrapper works |
| gdUnit4 headless invocation + `--import` pass | NOT ATTEMPTED — no `demo_project/` in repo (lands W2); ci.yml has no gdUnit4 step yet |
| osv-scanner | NOT ATTEMPTED — step ABSENT from ci.yml (W0-03) |

## 3. Findings

- **W0-01 | P0 → resolved | toolchain** — Godot absent on host. Resolved:
  provisioned 4.7.1 under `.tools/`, sha512-verified (standing rule:
  downloaded binaries checksum-verified). CONFIRMED.
- **W0-02 | P0 (W6 scope only) | toolchain** — No C++17 compiler on host or
  WSL (cmake 4.4.2 present). Blocks the layer wave (W6); W6 is gated on D-04
  regardless. Record before W6 planning. CONFIRMED.
- **W0-03 | P1 | CI** — osv-scanner gate ABSENT from `.github/workflows/ci.yml`.
  Kit mandates osv-scanner (never Trivy) and the DoD requires an osv-scanner
  result. Cross-ref: supply-chain standing rule. Fix in W1. CONFIRMED (absent).
- **W0-04 | P1 | CI** — `ci.yml` "Fetch Godot" step downloads the Godot zip
  with no checksum verification (`.github/workflows/ci.yml:71-76`). Same class
  as S-10; violates the downloaded-binaries standing rule. Fix in W1 (pin
  digest + verify against official `SHA512-SUMS.txt`). CONFIRMED.
- **W0-05 | P1 | hardware (S-11)** — Envelope measured (§2.3): 15.4 GiB RAM,
  iGPU only. Host fits Qwen2.5-VL-7B Q4 on CPU/RAM with high latency; Gemma 3
  12B not viable. Final floor must be measured (not estimated) at W4 and
  published in README. CONFIRMED (measured); latency UNTESTED.
- **W0-06 | P2 | CI** — gdUnit4 headless dry-run NOT ATTEMPTED: no
  `demo_project/` (QA skeleton lands W2) and no gdUnit4 step in ci.yml. Schedule
  with the W2 demo-project card. NOT ATTEMPTED.
- **W0-07 | P2 | docs** — Kit F-001…F-030 full text unavailable (v2.0 kit not
  in repo). PLAN.md maps them via v3.2 references. BLOCKED (document absent).

## 4. Decision register status (ingest; none assumed)

| ID | Status at W0 |
|---|---|
| D-01 | Unexamined default: Linux first, Windows second. Blocks W6. |
| D-02 | **ANSWERED by human 2026-08-11** (examined default): Accept, documented. swarm/decisions/D-02.md. |
| D-03 | Default adopted by implementation: addon MIT (`addon/LICENSE` present). |
| D-04 | **ANSWERED by human 2026-08-11** (examined default): Defer; ship T2/T3 in v1. W6 stays gated. swarm/decisions/D-04.md. |
| D-05 | **ANSWERED by human 2026-08-11**: WSL2 Ubuntu + bubblewrap 0.11.1. Smoke test executed, rc=0 (§2.2). |
| D-06 | Unexamined default: Never auto-apply. Blocks W4. |
| D-07 | Unexamined default: Build the bridge (after licence audit of candidates). Blocks W2. |
| D-08 | Unexamined default: No OMBI Scene Object Model. Blocks W3. |
| D-09 | Unexamined default: Stay on 4.7.1 for v1. CI pins 4.7.1 (`GODOT_VERSION`). |
| D-10…D-14 | ANSWERED, recorded in `swarm/decisions/`. |

## 5. Disagreement log (repo vs kit)

- **D-log-1** — Prior session executed W1-scope work (licences, contracts, CI,
  decisions D-10…D-14, task cards) before any W0 preflight record existed.
  RPI/W0 order violated by history; outcome verified by W0 dry-run above rather
  than assumed. No action beyond recording.
- **D-log-2** — v3.2 kit §7.2-era workflow claims vs actual `ci.yml`: the
  workflow already pins Actions by digest and verifies the gitleaks checksum,
  but lacks osv-scanner (W0-03) and Godot-zip verification (W0-04). Recorded as
  findings, scheduled in W1.
