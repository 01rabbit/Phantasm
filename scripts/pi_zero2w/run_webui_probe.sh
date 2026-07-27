#!/usr/bin/env bash
# scripts/pi_zero2w/run_webui_probe.sh
#
# WebUI viability probe. Runs ON the Raspberry Pi (called via SSH from
# run_remote_perf.sh). Must be executed from PHASMID_PI_REMOTE_DIR.
#
# Usage:
#   bash scripts/pi_zero2w/run_webui_probe.sh <results_dir>
#
# Expected environment (set by run_remote_perf.sh before SSH):
#   PHASMID_HOST=127.0.0.1
#   PHASMID_PORT=8001          (use 8001 not 8000 to avoid clashing with dev)
#   PHASMID_FIELD_MODE=1
#   PHASMID_AUDIT=0
#   PHASMID_DEBUG=0
#
# PHASMID_TMPFS_STATE must NOT be set. run_remote_perf.sh strips it.
#
# PHASMID_HOST must stay loopback. Since 0.3.0 the WebUI requires a page session
# for non-loopback peers, so pointing this probe at a routable address measures
# redirects to /unlock rather than the home page.

set -uo pipefail

RESULTS_DIR="${1:-_pi_field_test/results}"
mkdir -p "$RESULTS_DIR"

HOST="${PHASMID_HOST:-127.0.0.1}"
PORT="${PHASMID_PORT:-8001}"
BASE_URL="http://${HOST}:${PORT}"
MAX_WAIT_S=45
WEBUI_PID=""

WEBUI_LOG="$RESULTS_DIR/webui.log"

cleanup() {
    if [[ -n "$WEBUI_PID" ]] && kill -0 "$WEBUI_PID" 2>/dev/null; then
        printf '[webui] Killing WebUI pid %d ...\n' "$WEBUI_PID"
        kill "$WEBUI_PID" 2>/dev/null || true
        sleep 2
        kill -9 "$WEBUI_PID" 2>/dev/null || true
    fi
    if pgrep -f "phasmid.web_server" > /dev/null 2>&1; then
        printf '[webui] WARNING: phasmid.web_server process still running after cleanup\n' >&2
    fi
}
trap cleanup EXIT

# ── Start WebUI ───────────────────────────────────────────────────────────────

printf '[webui] Starting WebUI on %s ...\n' "$BASE_URL"

PHASMID_HOST="$HOST" \
PHASMID_PORT="$PORT" \
PHASMID_FIELD_MODE="${PHASMID_FIELD_MODE:-1}" \
PHASMID_AUDIT="${PHASMID_AUDIT:-0}" \
PHASMID_DEBUG="${PHASMID_DEBUG:-0}" \
.venv/bin/python -m phasmid.web_server > "$WEBUI_LOG" 2>&1 &

WEBUI_PID=$!
printf '[webui] WebUI PID: %d\n' "$WEBUI_PID"

# ── Wait for startup ──────────────────────────────────────────────────────────

STARTUP_T0="$(date +%s)"
STARTED=0
for i in $(seq 1 $MAX_WAIT_S); do
    if ! kill -0 "$WEBUI_PID" 2>/dev/null; then
        printf '[webui] ERROR: WebUI process exited during startup\n' >&2
        printf '[webui] Last log output:\n' >&2
        tail -20 "$WEBUI_LOG" >&2
        exit 1
    fi
    # Assert 200 rather than "curl did not fail". Since 0.3.0 a non-loopback
    # peer without a page session is redirected to /unlock, and `curl -sf`
    # treats that 303 as success — the probe would then time an empty redirect
    # instead of the home page and report latency that means nothing.
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "$BASE_URL/" 2>/dev/null)"
    if [[ "$code" == "200" ]]; then
        STARTED=1
        break
    fi
    if [[ "$code" == "302" || "$code" == "303" ]]; then
        printf '[webui] ERROR: %s redirected to the unlock page (HTTP %s).\n' "$BASE_URL/" "$code" >&2
        printf '[webui] Page access requires a session for non-loopback peers since 0.3.0.\n' >&2
        printf '[webui] Run this probe on the device against 127.0.0.1, which is exempt.\n' >&2
        exit 1
    fi
    sleep 1
done

STARTUP_S=$(( $(date +%s) - STARTUP_T0 ))

if [[ "$STARTED" -eq 0 ]]; then
    printf '[webui] ERROR: WebUI did not respond within %ds\n' "$MAX_WAIT_S" >&2
    tail -20 "$WEBUI_LOG" >&2
    exit 1
fi
printf '[webui] Startup time: %ds\n' "$STARTUP_S"

# ── HTTP response measurements ────────────────────────────────────────────────
# curl -w '%{time_total}' works on Linux (Pi) for float seconds.

first_response_ms="$(curl -sf --max-time 10 -o /dev/null \
    -w '%{time_total}' "$BASE_URL/" 2>/dev/null \
    | awk '{printf "%d", $1 * 1000}')"
printf '[webui] First HTTP response: %sms\n' "$first_response_ms"

# Five repeated requests for average latency.
total_ms=0
req_count=5
for i in $(seq 1 $req_count); do
    ms="$(curl -sf --max-time 10 -o /dev/null \
        -w '%{time_total}' "$BASE_URL/" 2>/dev/null \
        | awk '{printf "%d", $1 * 1000}')"
    total_ms=$(( total_ms + ms ))
done
avg_ms=$(( total_ms / req_count ))
printf '[webui] Average HTTP latency (%d req): %dms\n' "$req_count" "$avg_ms"

# ── Memory usage ──────────────────────────────────────────────────────────────

rss_kb="null"
if command -v ps > /dev/null 2>&1; then
    rss_raw="$(ps -o rss= -p "$WEBUI_PID" 2>/dev/null | tr -d ' ' || true)"
    if [[ -n "$rss_raw" ]]; then
        rss_kb="$rss_raw"
        printf '[webui] WebUI RSS: %s kB\n' "$rss_kb"
    fi
fi

# ── Graceful shutdown ──────────────────────────────────────────────────────────

printf '[webui] Sending SIGTERM ...\n'
kill "$WEBUI_PID" 2>/dev/null || true
SHUTDOWN_T0="$(date +%s)"
for i in $(seq 1 15); do
    if ! kill -0 "$WEBUI_PID" 2>/dev/null; then
        break
    fi
    sleep 1
done
SHUTDOWN_S=$(( $(date +%s) - SHUTDOWN_T0 ))

if kill -0 "$WEBUI_PID" 2>/dev/null; then
    printf '[webui] WARNING: graceful shutdown timed out; forcing kill\n' >&2
    kill -9 "$WEBUI_PID" 2>/dev/null || true
fi
WEBUI_PID=""

printf '[webui] Shutdown time: %ds\n' "$SHUTDOWN_S"

# ── Orphan check ──────────────────────────────────────────────────────────────

ORPHAN=false
if pgrep -f "phasmid.web_server" > /dev/null 2>&1; then
    printf '[webui] WARNING: phasmid.web_server process still running (orphan)\n' >&2
    ORPHAN=true
fi

# ── Write JSON result ─────────────────────────────────────────────────────────

cat > "$RESULTS_DIR/webui-probe.json" << JSONEOF
{
  "status": "ok",
  "startup_s": ${STARTUP_S},
  "first_response_ms": ${first_response_ms:-0},
  "avg_latency_ms": ${avg_ms},
  "rss_kb": ${rss_kb},
  "shutdown_s": ${SHUTDOWN_S},
  "orphan_detected": ${ORPHAN}
}
JSONEOF

printf '[webui] Probe complete. Results: %s/webui-probe.json\n' "$RESULTS_DIR"
