#!/usr/bin/env bash
# scripts/pi_zero2w/run_demo_smoke_test.sh
#
# Pre-demo smoke test. Runs ON the target device, from the repository root.
#
# Confirms the parts of the demo path that can be checked without a human:
# bind-host resolution, WebUI startup, access-token publication, the `/unlock`
# page-session flow introduced in 0.3.0, and the Silent Standby state machine.
# It then prints the steps that must be walked by hand, because a camera and a
# projector cannot be asserted from a shell.
#
# Usage:
#   bash scripts/pi_zero2w/run_demo_smoke_test.sh [results_dir]
#
# Environment:
#   PHASMID_PORT   defaults to 8099, deliberately not 8000, so a running
#                  operator WebUI is left alone.
#   PHASMID_WEBUI_EXPOSE_GADGET=1
#                  additionally assert the USB gadget path resolves to a gadget
#                  address rather than to all interfaces.
#
# State is redirected to a scratch directory; the operator profile and the real
# state directory are not touched. Exit status is 0 only when every automated
# check passes.

set -uo pipefail

RESULTS_DIR="${1:-_pi_field_test/results}"
mkdir -p "$RESULTS_DIR"

PORT="${PHASMID_PORT:-8099}"
BASE_URL="http://127.0.0.1:${PORT}"
SCRATCH="$(mktemp -d)"
STATE_DIR="$SCRATCH/state"
WEBUI_LOG="$RESULTS_DIR/demo-smoke-webui.log"
MAX_WAIT_S=45
WEBUI_PID=""

mkdir -p "$STATE_DIR"

if [[ -x .venv/bin/python ]]; then
    PY=".venv/bin/python"
else
    PY="python3"
fi

PASS=0
FAIL=0

ok() {
    printf '[smoke] PASS  %s\n' "$1"
    PASS=$(( PASS + 1 ))
}

bad() {
    printf '[smoke] FAIL  %s\n' "$1" >&2
    FAIL=$(( FAIL + 1 ))
}

cleanup() {
    if [[ -n "$WEBUI_PID" ]] && kill -0 "$WEBUI_PID" 2>/dev/null; then
        kill "$WEBUI_PID" 2>/dev/null || true
        sleep 2
        kill -9 "$WEBUI_PID" 2>/dev/null || true
    fi
    rm -rf "$SCRATCH"
}
trap cleanup EXIT

export PHASMID_STATE_DIR="$STATE_DIR"

# ── 1. Import ────────────────────────────────────────────────────────────────

if PYTHONPATH=src "$PY" -c 'import phasmid' 2>/dev/null; then
    ok "phasmid imports"
else
    bad "phasmid does not import — run ./phasmid once to build the venv"
    printf '[smoke] Cannot continue.\n' >&2
    exit 1
fi

# ── 2. Bind host resolution ──────────────────────────────────────────────────
# The demo depends on this: without the opt-in the WebUI is loopback-only and a
# browser on the attached laptop cannot reach it.

BIND_HOST="$(PYTHONPATH=src "$PY" -c '
from phasmid.services.webui_service import WebUIService
print(WebUIService().resolve_bind_host())
' 2>/dev/null)"

if [[ "${PHASMID_WEBUI_EXPOSE_GADGET:-0}" == "1" ]]; then
    case "$BIND_HOST" in
        127.0.0.1)
            bad "gadget exposure requested but resolved to loopback — no usb0/enx* address found; the laptop browser will not reach the WebUI"
            ;;
        0.0.0.0)
            bad "resolved to 0.0.0.0 (all interfaces) — must never happen on the gadget path"
            ;;
        *)
            ok "gadget exposure resolves to a single address: $BIND_HOST"
            ;;
    esac
else
    if [[ "$BIND_HOST" == "127.0.0.1" ]]; then
        ok "default bind is loopback ($BIND_HOST)"
    else
        bad "default bind is $BIND_HOST, expected 127.0.0.1"
    fi
fi

# ── 3. WebUI startup ─────────────────────────────────────────────────────────
# Bound to loopback for the probe regardless of the gadget setting, so this
# check never opens a port on a network.

PHASMID_HOST=127.0.0.1 \
PHASMID_PORT="$PORT" \
PHASMID_STATE_DIR="$STATE_DIR" \
PYTHONPATH=src \
"$PY" -m phasmid.web_server > "$WEBUI_LOG" 2>&1 &
WEBUI_PID=$!
# Detach so the shell does not print its own "Terminated" notice over the
# pass/fail output when the probe stops the server.
disown "$WEBUI_PID" 2>/dev/null || true

STARTED=0
for _ in $(seq 1 "$MAX_WAIT_S"); do
    if ! kill -0 "$WEBUI_PID" 2>/dev/null; then
        break
    fi
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "$BASE_URL/" 2>/dev/null)"
    if [[ "$code" == "200" ]]; then
        STARTED=1
        break
    fi
    sleep 1
done

if [[ "$STARTED" -eq 1 ]]; then
    ok "WebUI answers 200 on loopback"
else
    bad "WebUI did not answer 200 within ${MAX_WAIT_S}s"
    tail -20 "$WEBUI_LOG" >&2
    printf '[smoke] Cannot continue.\n' >&2
    exit 1
fi

# ── 4. Access token ──────────────────────────────────────────────────────────

TOKEN_FILE="$STATE_DIR/webui_token"
if [[ -f "$TOKEN_FILE" ]]; then
    ok "access token published"
    perms="$(stat -c '%a' "$TOKEN_FILE" 2>/dev/null || stat -f '%Lp' "$TOKEN_FILE" 2>/dev/null)"
    if [[ "$perms" == "600" ]]; then
        ok "access token is 0600"
    else
        bad "access token is $perms, expected 600"
    fi
else
    bad "no access token at $TOKEN_FILE — the laptop browser cannot unlock"
fi
TOKEN="$(cat "$TOKEN_FILE" 2>/dev/null || true)"

# ── 5. Unlock flow ───────────────────────────────────────────────────────────
# Loopback peers are exempt from unlock, so these assertions cover the
# mechanism itself: a wrong token must not mint a session, a correct one must.

BAD_JAR="$SCRATCH/bad.jar"
GOOD_JAR="$SCRATCH/good.jar"

curl -s -c "$BAD_JAR" -o /dev/null --max-time 5 \
    -X POST -d 'token=DEFINITELY-NOT-THE-TOKEN' "$BASE_URL/unlock" 2>/dev/null
if grep -q 'phasmid_ui_session' "$BAD_JAR" 2>/dev/null; then
    bad "a wrong access token minted a page session"
else
    ok "wrong access token is rejected"
fi

if [[ -n "$TOKEN" ]]; then
    curl -s -c "$GOOD_JAR" -o /dev/null --max-time 5 \
        -X POST -d "token=$TOKEN" "$BASE_URL/unlock" 2>/dev/null
    if grep -q 'phasmid_ui_session' "$GOOD_JAR" 2>/dev/null; then
        ok "correct access token opens a page session"
        if grep -q '^#HttpOnly_' "$GOOD_JAR"; then
            ok "page session cookie is HttpOnly"
        else
            bad "page session cookie is not HttpOnly"
        fi
    else
        bad "correct access token did not open a page session"
    fi
fi

# ── 6. Silent Standby ────────────────────────────────────────────────────────
# The demo climax. It exists only in the TUI, so assert the state machine
# rather than the screen.

if PYTHONPATH=src "$PY" -c '
from phasmid.standby_state import StandbyStateMachine, StandbyState
m = StandbyStateMachine()
assert m.state is StandbyState.ACTIVE, m.state
m.trigger_standby()
assert m.state is StandbyState.SEALED, m.state
m.enter_dummy_disclosure()
assert m.state is StandbyState.DUMMY_DISCLOSURE, m.state
m.seal_dummy()
assert m.state is StandbyState.SEALED, m.state
m.recover()
assert m.state is StandbyState.ACTIVE, m.state
' 2>/dev/null; then
    ok "standby active -> sealed -> dummy_disclosure -> sealed -> active"
else
    bad "standby state machine did not walk the demo path"
fi

# ── 7. Shutdown ──────────────────────────────────────────────────────────────

kill "$WEBUI_PID" 2>/dev/null || true
for _ in $(seq 1 15); do
    kill -0 "$WEBUI_PID" 2>/dev/null || break
    sleep 1
done

if kill -0 "$WEBUI_PID" 2>/dev/null; then
    bad "WebUI did not shut down on SIGTERM"
    kill -9 "$WEBUI_PID" 2>/dev/null || true
else
    ok "WebUI shuts down on SIGTERM"
fi
WEBUI_PID=""

if [[ -f "$TOKEN_FILE" ]]; then
    bad "access token survived shutdown at $TOKEN_FILE"
else
    ok "access token removed on shutdown"
fi

# ── Result ───────────────────────────────────────────────────────────────────

cat > "$RESULTS_DIR/demo-smoke-test.json" << JSONEOF
{
  "checks_passed": ${PASS},
  "checks_failed": ${FAIL},
  "bind_host": "${BIND_HOST}",
  "gadget_exposure_requested": ${PHASMID_WEBUI_EXPOSE_GADGET:-0}
}
JSONEOF

printf '\n[smoke] %d passed, %d failed. Results: %s/demo-smoke-test.json\n' \
    "$PASS" "$FAIL" "$RESULTS_DIR"

cat <<'MANUAL'

[smoke] Automated checks cannot cover the following. Walk them by hand.

  1. Object cue, on the camera
     WebUI -> Protect a File -> step 3 -> present the object -> Capture.
     Watch for the camera frame locking onto a stable match. This is the
     cue-not-key beat and it has no TUI equivalent.

  2. Laptop reachability over the USB gadget link
     With PHASMID_WEBUI_EXPOSE_GADGET=1 on the device, open the gadget address
     from the laptop browser and complete /unlock. Loopback is exempt from
     unlock, so testing on the device alone does not prove this path.

  3. Access token handling on stage
     Pressing `w` prints the legacy shared WEB_TOKEN into the TUI notification
     for 30 seconds. It no longer unlocks anything once PHASMID_STORE_TOKEN /
     PHASMID_RECOVER_TOKEN are pinned (see run_demo_console.sh), but it is
     still a credential-shaped string - switch the projector to the laptop
     before pressing `w`, or wait out the 30 seconds off-camera.

  4. Silent Standby on the real screen
     Press the standby hotkey and confirm the sensitive surface actually
     clears. The state machine check above proves the transitions, not the
     rendering.

  5. Projector switching
     Rehearse device -> laptop -> device. The demo crosses surfaces twice.

MANUAL

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
