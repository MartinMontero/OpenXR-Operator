# Wire protocol v2 (FROZEN after W1 — orchestrator-owned)

Game process <-> agent. Loopback WebSocket on 127.0.0.1:9099.

- First frame on every connection MUST be {"cmd":"auth","token":"<64 hex>","protocol":2}.
  One attempt, 2-second deadline, close 1008 on failure. Constant-time compare.
- Nothing dispatches pre-auth, including error messages confirming command names.
- Protocol mismatch closes with a clear message (F-027).
- Limits: 1 MiB max inbound frame (close 1009), 4 concurrent peers,
  50 msgs/s/peer (close 1008), 120 s idle timeout (close 1001).
- Commands: ping, scene_tree, capture, get_property, set_property, inject,
  restart_scene, editor_rescan. Every request carries "id"; every reply
  echoes it (F-017).
- Frames go to disk; the channel carries {path, tier, sha256, ...},
  never base64 (v2.0 section 2.5).
- Editor-side work goes over the EngineDebugger capture channel
  ("openxr_operator:*"), never EditorInterface from the game process (F-011).

Changes bump PROTOCOL_VERSION and land both ends in one commit (orchestrator only).
