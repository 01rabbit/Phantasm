#!/usr/bin/env bash
# scripts/pi_zero2w/run_demo_console.sh
#
# Launches the operator console with the environment the live demo needs.
# Runs ON the target device, from the repository root.
#
# Every variable set here was established by rehearsing on real hardware; the
# console starts without them, but each omission costs something on stage:
#
#   LIBCAMERA_LOG_LEVELS
#       libcamera logs to stderr, which is the same terminal Textual is
#       drawing on. Left at its default the INFO/WARN stream overwrites the
#       TUI for the whole time the camera is open - which is exactly the
#       object-cue step, the centrepiece of the talk. Silencing it below
#       ERROR keeps the screen intact.
#
#   PHASMID_WEBUI_EXPOSE_GADGET
#       The WebUI binds loopback-only by default, so a tethered laptop cannot
#       reach it at all. Opting in binds the USB gadget address (never all
#       interfaces), which is what makes the browser view projectable.
#
#   PHASMID_WEB_TOKEN
#       Off-device access requires a token at /unlock. Without a fixed value
#       one is generated per start, meaning a long random string has to be
#       typed by hand on stage. Pin it so the browser tab can be staged in
#       advance.
#
#   PHASMID_RECOGNITION_MODE
#       There is no UI for this; it is environment-only. `demo` keeps object
#       recognition deterministic under stage lighting.
#
# Usage:
#   bash scripts/pi_zero2w/run_demo_console.sh
#
# Override any value by exporting it before calling, e.g.
#   PHASMID_RECOGNITION_MODE=coercion_safe bash scripts/pi_zero2w/run_demo_console.sh

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

VENV_PHASMID="$REPO_ROOT/.venv/bin/phasmid"
if [[ ! -x "$VENV_PHASMID" ]]; then
    echo "error: $VENV_PHASMID not found or not executable." >&2
    echo "Run the environment bootstrap before the demo." >&2
    exit 1
fi

export LIBCAMERA_LOG_LEVELS="${LIBCAMERA_LOG_LEVELS:-*:ERROR}"
export PHASMID_WEBUI_EXPOSE_GADGET="${PHASMID_WEBUI_EXPOSE_GADGET:-1}"
export PHASMID_WEB_TOKEN="${PHASMID_WEB_TOKEN:-phasmid-demo-token}"
export PHASMID_RECOGNITION_MODE="${PHASMID_RECOGNITION_MODE:-demo}"

# Ctrl+S is the Silent Standby hotkey. It is also the terminal's traditional
# XOFF, and a terminal with flow control enabled swallows it before the app
# ever sees it - the hotkey would simply appear dead on stage. Disable flow
# control for this terminal when we have one.
if [[ -t 0 ]]; then
    stty -ixon 2>/dev/null || true
fi

echo "Phasmid demo console"
echo "  recognition mode : $PHASMID_RECOGNITION_MODE"
echo "  webui gadget     : $PHASMID_WEBUI_EXPOSE_GADGET (press w to expose)"
echo "  webui token      : $PHASMID_WEB_TOKEN"
echo "  libcamera logs   : $LIBCAMERA_LOG_LEVELS"
echo
echo "Operate by keyboard. Mouse clicks do not reach the app over SSH:"
echo "  Tab / Shift+Tab to move focus, Enter to activate a button."
echo

exec "$VENV_PHASMID" "$@"
