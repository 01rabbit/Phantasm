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

## Camera tuning

How many keypoints the cue has to work with is decided by the camera, long
before any threshold is applied — by resolution, by how long the shutter is
open, by how hard the ISP denoises, and by where the lens is. Those defaults are
tuned for photographs a person will look at, which is not the same thing as an
image a corner detector can work with.

The right values depend on the room and the object. With the console stopped and
the object sitting in front of the camera, not moving:

```bash
.venv/bin/python scripts/pi_zero2w/tune_camera.py
```

It sweeps resolution, shutter ceiling, denoising and sharpening against the
object actually there, reports what each is worth in keypoints, and prints an
export line to put in front of the launcher. It writes nothing.

Read the `ms/frame` column as well as the keypoint count: past roughly 250 ms
the device will not hold four frames a second, and the match history needs
several consecutive frames before anything opens. More pixels than the Pi can
process is not more cue.

Re-bind the object after changing any of these — a template is only comparable
with frames captured the same way — then confirm with **Cue margin** below.

## Cue margin

The smoke test cannot check the camera, and the one camera question that
matters before a demonstration is not "does the object match" — the WebUI badge
already answers that — but *by how much*. An object clearing its threshold by
one point and an object clearing it threefold look identical on screen, right
up until the lighting changes.

There are two ways to see it. **Start with the overlay** — aiming a camera is
iterative, and the script cannot show you what the lens is looking at:

```bash
PHASMID_CUE_DEBUG=1 bash scripts/pi_zero2w/run_demo_console.sh
```

Then press `w`, open the Store or Retrieve page, and hold the object up. The
scores are drawn along the bottom of the live preview — keypoints, good
matches, inliers, and the bar each has to clear — so moving the object and
watching the numbers respond is one continuous action rather than a guess
followed by a separate measurement.

**Bench use only.** The preview is a capture-visible surface and these numbers
describe the mechanism, so the flag is off by default and has no UI control.

For a recorded run with statistics rather than a live readout, stop the console
and, with the object presented:

```bash
.venv/bin/python scripts/pi_zero2w/measure_cue_margin.py --frames 30
```

It reports, per bound entry, the template's keypoint count, the thresholds that
count produces, and the good matches and inliers scored over a run of live
frames — ending in a worst-case margin. **Under about x1.5, expect the stage
lighting to cross it.**

Prefer moving the object closer or choosing one with more texture over lowering
`PHASMID_CUE_GOOD_MATCH_RATIO` / `PHASMID_CUE_INLIER_RATIO`: more keypoints
raise the threshold and the score together, and the score rises faster. Below
roughly 48 keypoints the floors decide the threshold rather than the ratios, and
those environment variables will not move it at all — the script says so when
that is the case.

If the ratios are lowered, re-run with the object absent and again with an
unbound object. Confirming only the side that should match confirms nothing.

The script reads the same reference store the console uses and registers
nothing, writes nothing, and changes nothing. The camera is exclusive, so the
console has to be stopped first.

## Deploying an update to the device

The device is meant to stay off networks, which makes `git pull` on the device
the wrong tool: it needs the internet to work, and the Pi only has the USB link
to the laptop. Deployment therefore runs **from the Mac**, and carries the
dependency wheels across with the source.

With the Pi attached over USB and the operator console stopped:

```bash
export PHASMID_PI_HOST=10.12.194.1      # the address the browser uses
export PHASMID_PI_USER=pi
export PHASMID_PI_REMOTE_DIR=/home/pi/Phasmid
bash scripts/pi_zero2w/deploy_to_device.sh
```

It fast-forwards the local checkout to `origin/main`, asks the device which
Python it runs, downloads the matching aarch64 wheels **on the Mac**, syncs
both, installs with `--no-index`, and then verifies on the device rather than
trusting rsync's exit status. It refuses to run against a dirty working tree:
deploying uncommitted work puts a build on the device that exists nowhere else.

`.state`, the vault, `*.vessel` and the venv are excluded, so a deployment
cannot destroy a bound object or a stored file.

### When the Pi takes over the Mac's default route

Reported from the bench, and the reason the script checks for it before doing
anything: with the Pi attached, the Mac loses the internet. The gadget hands
out a DHCP lease that includes a router option, macOS ranks that service above
Wi-Fi, and every packet meant for the internet is sent to a device that has no
upstream. `git pull` then fails — and the failure looks like a git problem, not
a network one.

**On the Mac, once:** System Settings → Network → **⋯** → *Set Service Order*,
drag **Wi-Fi above the USB gadget service**, Apply. macOS takes the default
route from the highest-priority active service, so this survives replugging.
The Pi stays reachable at its own address; only the default route moves back.

To unblock a single session without changing anything permanent:

```bash
route -n get default | awk '/interface:/{print $2}'   # confirm which one it is
sudo route -n delete default -interface en5           # substitute the real one
```

**On the Pi, better:** stop advertising a router at all, and no laptop has the
problem — including a borrowed one at the venue. If the gadget address is
handed out by `dnsmasq`, adding these to its config and restarting it makes the
lease carry an address and nothing else:

```
dhcp-option=3       # no router
dhcp-option=6       # no DNS server
```

Check what is actually serving the lease first — this is configured on the
device by hand and is not part of this repository:

```bash
systemctl status dnsmasq
ip -4 addr show usb0
```

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
