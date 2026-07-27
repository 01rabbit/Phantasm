# Phasmid Pi Zero 2W Remote Field Test — Quickstart

Run from macOS. All test phases execute on the Raspberry Pi via SSH.

## Prerequisites

**On macOS (host):**

- Git repository checked out
- `ssh` available (`rsync` is preferred; fallback exists if missing)
- SSH key configured for the Pi (or ssh-agent running)

**On the Raspberry Pi:**

- **64-bit Raspberry Pi OS Lite** (aarch64) — 32-bit is not supported
- SSH enabled (`sudo systemctl enable ssh && sudo systemctl start ssh`)
- Python 3 available (`python3 --version`)
- Required OS packages:

```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip libopenblas-dev
```

## Setup

```bash
export PHASMID_PI_HOST=phasmid-pi.local   # or IP address
export PHASMID_PI_USER=pi
export PHASMID_PI_REMOTE_DIR=/home/pi/Phasmid
export PHASMID_PI_SSH_PORT=22
export PHASMID_PI_SSH_KEY=~/.ssh/id_ed25519   # optional if ssh-agent is running
```

## Run

```bash
./scripts/pi_zero2w/run_remote_perf.sh
```

The script will:

1. Validate environment variables and abort if any are missing
2. Check that the Pi is 64-bit (aarch64) — fails immediately if not
3. Collect system info (CPU, memory, swap, temperature)
4. Sync the repository to the Pi via rsync
5. Create a `.venv` on the Pi and run `pip install -e .`
6. Verify that the `phasmid` CLI entry point exists
7. Run performance and timing measurements on the Pi
8. Probe the WebUI startup, response latency, and shutdown
9. Copy results back to `release/pi-zero2w/` on the Mac

## Pre-demo smoke test

Separate from the performance run. Run it on the device, from the repository
root, before a demonstration:

```bash
bash scripts/pi_zero2w/run_demo_smoke_test.sh
```

It asserts what a shell can assert — bind-host resolution, WebUI startup, access
token publication and permissions, the `/unlock` page-session flow, the Silent
Standby transitions, and clean shutdown — then prints the steps that need a
human, because a camera and a projector cannot be checked from a script. It
exits non-zero if any automated check fails.

State is redirected to a scratch directory and the port defaults to 8099, so a
running operator WebUI and the real state directory are left alone.

Add `PHASMID_WEBUI_EXPOSE_GADGET=1` to additionally assert that the USB gadget
path resolves to a single gadget address rather than to all interfaces. Without
a `usb0`/`enx*` address present the check fails by design: that is exactly the
condition in which a browser on the attached laptop cannot reach the WebUI.

## Results

| File | Contents |
|---|---|
| `release/pi-zero2w/run.log` | Full run log |
| `release/pi-zero2w/install.log` | pip install output |
| `release/pi-zero2w/sysinfo.txt` | Target hardware summary |
| `release/pi-zero2w/perf-results.json` | Structured JSON results |
| `release/pi-zero2w/perf-report.md` | Human-readable summary report |
| `release/pi-zero2w/webui-probe.json` | WebUI timing results |

## Key result fields

```json
{
  "overall_status": "pass",
  "coercion_path_timing": {
    "gate_passed": true,
    "max_timing_delta_ms": 0.42,
    "kdf_wall_time_ms": 1234.5,
    "gate_threshold_ms": 61.7
  },
  "swap_enabled": false,
  "vault_operations": {
    "roundtrip_ok": true,
    "store_s": 1.23,
    "retrieve_s": 1.19
  }
}
```

If `coercion_path_timing.gate_passed` is `false`, the timing delta between
the FAILED and RESTRICTED code paths exceeds 5% of Argon2id wall time.
This is a significant finding that must be documented before field use.

## Sync Fallback

If `rsync` is unavailable on the macOS host, the harness falls back to a
bounded `tar` stream over SSH with the same exclude rules (`.git`, `.venv`,
`.state`, `vault.bin`, `release/`, caches, and `_pi_field_test/`).

## Cleanup (remote test artifacts only)

```bash
ssh $PHASMID_PI_USER@$PHASMID_PI_HOST \
    "rm -rf $PHASMID_PI_REMOTE_DIR/_pi_field_test"
```

This removes only the dedicated test directory. It does not touch other files.

## Troubleshooting

**"Target reports architecture 'armv7l'"**
Flash 64-bit Raspberry Pi OS Lite. 32-bit is not supported.

**"phasmid CLI not found after install"**
Check `release/pi-zero2w/install.log`. A dependency may have failed.
Run `sudo apt-get install python3-dev build-essential` on the Pi and retry.

**"WebUI process exited during startup"**
Check `release/pi-zero2w/webui.log`. The most common cause is a missing
`_pi_field_test/.state` directory or a port conflict on 8001.

**opencv or numpy build triggered (slow)**
This script uses `pip install -e .` which should install pre-built
`manylinux_2_17_aarch64` wheels on 64-bit Pi OS. If a source build is
triggered, ensure you are running 64-bit OS (`uname -m` → `aarch64`).
