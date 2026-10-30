extends RefCounted
## Wire protocol constants (FROZEN contract — orchestrator-owned).
## See docs/contracts/wire-protocol.md. Changes bump PROTOCOL_VERSION.
const PROTOCOL_VERSION := 2
const PORT := 9099
const BIND := "127.0.0.1"
const MAX_FRAME_BYTES := 1048576
const MAX_PEERS := 4
const MAX_MSGS_PER_SEC := 50
const AUTH_DEADLINE_MS := 2000
const IDLE_TIMEOUT_MS := 120000
const TOKEN_PATH := "user://openxr_operator.token"
const DEBUGGER_CAPTURE := "openxr_operator"
