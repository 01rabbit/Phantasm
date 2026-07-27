#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

HOST="${PHASMID_WEBUI_HOST:-127.0.0.1}"
PORT="${PHASMID_WEBUI_PORT:-8000}"
STATUS_URL="http://127.0.0.1:${PORT}/status"
FEED_URL="http://127.0.0.1:${PORT}/video_feed"
TMP_FEED="/tmp/phasmid-feed.bin"
WEBUI_PID=""

PASS_ITEMS=()
FAIL_ITEMS=()
WARN_ITEMS=()

log() { printf '[validate] %s\n' "$*"; }
warn() { printf '[validate][warn] %s\n' "$*" >&2; }

record_pass() { PASS_ITEMS+=("$1"); log "PASS: $1"; }
record_fail() { FAIL_ITEMS+=("$1"); warn "FAIL: $1"; }
record_warn() { WARN_ITEMS+=("$1"); warn "WARNING: $1"; }

cleanup() {
  if [[ -n "$WEBUI_PID" ]] && kill -0 "$WEBUI_PID" 2>/dev/null; then
    log "Stopping validation WebUI process (pid=$WEBUI_PID)"
    kill -TERM "-$WEBUI_PID" 2>/dev/null || kill -TERM "$WEBUI_PID" 2>/dev/null || true
    sleep 2
    if kill -0 "$WEBUI_PID" 2>/dev/null; then
      warn "Graceful stop timed out, sending SIGKILL"
      kill -KILL "-$WEBUI_PID" 2>/dev/null || kill -KILL "$WEBUI_PID" 2>/dev/null || true
      sleep 1
    fi
  fi
}
trap cleanup EXIT

activate_venv_if_present() {
  cd "$REPO_ROOT"
  if [[ -f .venv/bin/activate ]]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
    log "Activated .venv"
  else
    record_warn "No .venv found. Running with system python."
  fi
}

stage_a_imports() {
  log "Stage A: Python imports"
  if python - <<'PY'
import importlib.util
mods = ["picamera2", "cv2", "numpy"]
missing = [m for m in mods if importlib.util.find_spec(m) is None]
if missing:
    raise SystemExit("missing imports: " + ",".join(missing))
print("ok")
PY
  then
    record_pass "Python imports (picamera2/cv2/numpy)"
  else
    record_fail "Python imports (picamera2/cv2/numpy)"
  fi
}

stage_b_picamera_capture() {
  log "Stage B: Picamera2 frame capture"
  if python - <<'PY'
from picamera2 import Picamera2
picam2 = Picamera2()
config = picam2.create_preview_configuration(main={"size": (320, 240), "format": "RGB888"})
picam2.configure(config)
picam2.start()
frame = picam2.capture_array("main")
print(frame.shape, frame.dtype)
picam2.stop()
picam2.close()
if tuple(frame.shape) != (240, 320, 3):
    raise SystemExit("unexpected shape")
if str(frame.dtype) != "uint8":
    raise SystemExit("unexpected dtype")
PY
  then
    record_pass "Picamera2 capture (RGB888 320x240 uint8)"
  else
    record_fail "Picamera2 capture (RGB888 320x240 uint8)"
  fi
}

wait_for_webui() {
  local deadline=$((SECONDS + 15))
  while (( SECONDS < deadline )); do
    if curl -fsS "$STATUS_URL" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

stage_c_webui_start() {
  log "Stage C: WebUI startup"
  if ss -ltn 2>/dev/null | grep -q ":${PORT} "; then
    record_fail "WebUI startup (port ${PORT} already in use)"
    return
  fi

  PHASMID_HOST="$HOST" PHASMID_PORT="$PORT" python -m uvicorn phasmid.web_server:app --host "$HOST" --port "$PORT" >/tmp/phasmid-validate-webui.log 2>&1 &
  WEBUI_PID="$!"
  sleep 1

  if ! wait_for_webui; then
    record_fail "WebUI startup (status endpoint not ready)"
    return
  fi

  if ss -ltnp 2>/dev/null | grep -q "${HOST}:${PORT}"; then
    record_pass "WebUI listener on ${HOST}:${PORT}"
  else
    record_fail "WebUI listener on ${HOST}:${PORT}"
  fi

  if [ "$HOST" != "0.0.0.0" ] && ss -ltnp 2>/dev/null | grep -q "0.0.0.0:${PORT}"; then
    record_fail "WebUI must not listen on all interfaces (0.0.0.0:${PORT})"
  fi
}

stage_d_status_validation() {
  log "Stage D: /status validation"
  # Warm up camera/status coupling with a short feed read.
  python - <<PY
import contextlib
import urllib.request
with contextlib.suppress(Exception):
    urllib.request.urlopen("$FEED_URL", timeout=2).read(1024)
PY

  if python - <<PY
import json
import urllib.request
u = urllib.request.urlopen("$STATUS_URL", timeout=5)
obj = json.loads(u.read().decode("utf-8"))
ready = bool(obj.get("camera_ready"))
backend = str(obj.get("camera_backend") or "").strip().lower()
last_error = obj.get("last_camera_error")
ok_backend = backend not in {"", "none", "unavailable"}
ok_error = (last_error is None) or (str(last_error).strip() == "")
if not (ready and ok_backend and ok_error):
    raise SystemExit(f"status invalid: ready={ready} backend={backend!r} last_error={last_error!r}")
print("ok")
PY
  then
    record_pass "/status camera fields (ready/backend/error)"
  else
    record_fail "/status camera fields (ready/backend/error)"
  fi
}

stage_e_mjpeg_validation() {
  log "Stage E: MJPEG validation"
  rm -f "$TMP_FEED"
  if curl -fsS "$FEED_URL" --max-time 5 -o "$TMP_FEED"; then
    :
  else
    # timeout is expected for continuous MJPEG streams; continue to file-size check
    true
  fi

  if [[ -s "$TMP_FEED" ]]; then
    record_pass "/video_feed returns non-zero bytes"
  else
    record_fail "/video_feed returns non-zero bytes"
  fi
}

stage_f_cleanup_validation() {
  log "Stage F: cleanup and camera release"
  cleanup
  WEBUI_PID=""

  if pgrep -f "uvicorn phasmid.web_server:app --host ${HOST} --port ${PORT}" >/dev/null 2>&1; then
    record_fail "WebUI process exit after validation"
  else
    record_pass "WebUI process exit after validation"
  fi

  if python - <<'PY'
from picamera2 import Picamera2
picam2 = Picamera2()
config = picam2.create_preview_configuration(main={"size": (320, 240), "format": "RGB888"})
picam2.configure(config)
picam2.start()
frame = picam2.capture_array("main")
print(frame.shape, frame.dtype)
picam2.stop()
picam2.close()
PY
  then
    record_pass "Camera resource released after shutdown"
  else
    record_fail "Camera resource released after shutdown"
  fi
}

print_summary() {
  printf '\n=== Raspberry Pi Validation Summary ===\n'
  printf 'PASS:\n'
  for item in "${PASS_ITEMS[@]:-}"; do
    printf '  - %s\n' "$item"
  done
  printf 'FAIL:\n'
  for item in "${FAIL_ITEMS[@]:-}"; do
    printf '  - %s\n' "$item"
  done
  printf 'WARNING:\n'
  for item in "${WARN_ITEMS[@]:-}"; do
    printf '  - %s\n' "$item"
  done

  if (( ${#FAIL_ITEMS[@]} > 0 )); then
    exit 1
  fi
}

main() {
  activate_venv_if_present
  stage_a_imports
  stage_b_picamera_capture
  stage_c_webui_start
  stage_d_status_validation
  stage_e_mjpeg_validation
  stage_f_cleanup_validation
  print_summary
}

main "$@"
