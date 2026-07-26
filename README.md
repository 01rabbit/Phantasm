# Phasmid

![Phasmid logo](images/Phasmid_banner.jpg)

[![CI](https://github.com/01rabbit/Phasmid/actions/workflows/ci.yml/badge.svg)](https://github.com/01rabbit/Phasmid/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![status: research prototype](https://img.shields.io/badge/status-research%20prototype-orange)](docs/CLAIMS.md)
[![local-only](https://img.shields.io/badge/operation-local--only-lightgrey)](docs/THREAT_MODEL.md)
[![Security Policy](https://img.shields.io/badge/security-policy-informational)](SECURITY.md)

> When encryption is strong enough, attackers may stop attacking the cipher and start attacking the human.

Phasmid is a field-evaluation prototype for local-only coercion-aware deniable storage.

It is designed for situations where an attacker may not break the cipher, but may seize a device, inspect it, or compel a person to disclose access.

Phasmid is the reference implementation of the Janus Eidolon System, a two-slot local storage architecture designed to separate visible disclosure from protected local state under practical risks such as device seizure, compelled access, and over-disclosure.

## Why Phasmid exists

Most encryption tools assume the user can safely refuse disclosure. In field conditions, that assumption may fail.

Phasmid treats coercion, inspection, and over-disclosure as first-class design constraints. It does not try to defeat all forensic analysis; it explores controlled disclosure behavior on local-only constrained devices under documented limits.

## Arsenal Demo Summary

Phasmid is a local-only coercion-aware disclosure-control prototype for constrained devices.

In an Arsenal demo, Phasmid demonstrates how encrypted local storage can separate coerced disclosure from true disclosure without claiming forensic invisibility or anti-forensic evasion.

The demo flow shows creation of an encrypted local Vessel, selection of a context-consistent Disclosure Face, generation and evaluation of a plausible disclosure dataset, Silent Standby transition that removes sensitive UI state, coercion-safe fallback toward controlled disclosure, and explicit claims and non-claims.

## Not Anti-Forensics

Phasmid is research software. It is not a replacement for full-disk encryption, hardware-backed key storage, an audited classified-data handling system, or a complete solution to compelled disclosure.

Phasmid is not an anti-forensics tool. It does not bypass forensic tools, forge timestamps, fabricate kernel logs, hide processes, hide like malware, claim forensic invisibility, claim guaranteed secure deletion on flash media, or claim permanent secrecy against unlimited analysis.

The goal is to separate coerced disclosure from true disclosure and reduce unsafe fail-closed behavior under compelled-access conditions.

**Who this is for:** security researchers, field-risk evaluators, and local-only disclosure-control experiments. It is not for casual file encryption.

## Concept Track Baseline

Phasmid's fixed core message:

Phasmid is a coercion-aware local storage prototype for constrained devices.  
It asks whether encryption can protect not only data, but also the person who may be forced to disclose it.

For internal concept work, use two tracks without changing the technical core:

- `privacy-and-research track`: emphasizes privacy-preserving disclosure, compelled-access safety, and explicit claims/non-claims transparency.
- `field-operations track`: emphasizes constrained-device readiness, operational resilience, and safer disclosure behavior under inspection pressure.

Internal draft assets: [`docs/CONCEPT_TRACKS.md`](docs/CONCEPT_TRACKS.md), [`docs/submissions/README.md`](docs/submissions/README.md), and the Europe submission-prep note [`docs/BLACKHAT_EUROPE_ARSENAL_DEMO.md`](docs/BLACKHAT_EUROPE_ARSENAL_DEMO.md).

## Implementation Status

Current implementation status and evidence paths are tracked in [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md).

## Requirements

| Requirement | Detail |
|---|---|
| Python | 3.10 or later |
| OS | Linux, macOS (development); Raspberry Pi OS Bookworm/Bullseye (deployment) |
| Hardware | x86-64 laptop/desktop for development; Raspberry Pi Zero 2 W for field deployment |
| Camera (optional) | Picamera2 / libcamera — required only for object-cue matching on Pi |
| WebUI (optional) | Any modern browser; binds `127.0.0.1` by default. USB gadget Ethernet access is opt-in — see [WebUI access](#webui-access) |
| LUKS (optional) | Linux kernel with dm-crypt — required for the optional LUKS2 storage layer |

For Raspberry Pi deployment, `python3-picamera2` and `python3-libcamera` must be installed via apt before running the bootstrap script.

## Hardware Snapshot

![Phasmid hardware main tripod](./images/phasmid-hardware-main-tripod.jpg)
![Phasmid hardware RPi Zero 2 W](./images/phasmid-hardware-rpi-zero2w.jpg)

## Quick Start in 60 seconds

```bash
git clone https://github.com/01rabbit/Phasmid.git
cd Phasmid
./phasmid
```

What `./phasmid` does on first run:

- creates `.venv` if needed
- installs project dependencies
- opens the TUI Operator Console

Success check:

- you see the Simple Operator screen
- press `n` to create protected storage
- press `g` for a guided walkthrough

If the TUI does not open, run `phasmid doctor`.

## Architecture Overview

![Phasmid Architecture Overview](images/architecture_overview.png)

> Quick legend:
> - **Vessel**: local container carrying multiple Disclosure Faces
> - **Object cue**: operational access gate, not cryptographic key material
> - **Restricted slot**: triggers irreversible local-state destruction on access
>
> Full cryptographic parameters and storage layout:
> [docs/PHASMID_ARCHITECTURE.md](docs/PHASMID_ARCHITECTURE.md)

Access flow, two-slot storage, coercion defense, and local-only boundary are documented in [`docs/PHASMID_ARCHITECTURE.md`](docs/PHASMID_ARCHITECTURE.md).

## What Phasmid does

- creates and operates encrypted local containers (`vault.bin`)
- uses Argon2id-derived keys and AES-GCM authenticated encryption
- mixes local key material into recovery so `vault.bin` alone is insufficient
- supports local CLI, TUI Operator Console, and optional local WebUI
- enforces restricted local actions with explicit confirmation
- provides metadata-risk review and metadata-reduction workflows (best effort)

## Security boundary summary

Phasmid claims:

- local-only operation by default
- controlled disclosure behavior under documented conditions
- reduced dependence on `vault.bin` alone through mixed local key material

Phasmid does not claim:

- perfect deniability
- guaranteed secure deletion
- protection against compromised hosts, keyloggers, or live memory capture
- covert communication, censorship bypass, remote wipe, or remote unlock

For complete claims and non-claims, see [`docs/CLAIMS.md`](docs/CLAIMS.md), [`docs/NON_CLAIMS.md`](docs/NON_CLAIMS.md), and [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md).

## WebUI access

The WebUI binds `127.0.0.1:8000` by default, so pressing `w` in the TUI keeps it
reachable only from the device itself. Reaching it from another machine is an
explicit opt-in:

```bash
# Reach the WebUI from a laptop over the USB Ethernet gadget link.
# Binds the gadget interface address (usb0 / enx*) only — never all interfaces.
PHASMID_WEBUI_EXPOSE_GADGET=1 phasmid
```

If you skip this, the WebUI starts successfully but a browser on the attached
laptop cannot reach it. The TUI notification and exposure banner always show the
address actually bound, so check there first when a browser cannot connect.

`PHASMID_HOST` overrides the bind address directly and takes precedence over the
gadget opt-in. Setting `PHASMID_HOST=0.0.0.0` exposes the WebUI on every
interface; because WebUI pages, the embedded mutation token, and `/video_feed`
are served without authentication, treat that as unsafe on any untrusted
network. See [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) and
[`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md).

## Install and run details

For normal repository-local use:

```bash
./phasmid
```

If you need a manual environment setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Raspberry Pi bootstrap:

```bash
./scripts/bootstrap_pi.sh
source .venv/bin/activate
./scripts/validate_pi_environment.sh
```

## Common commands

```bash
phasmid                # open TUI Operator Console
phasmid create ~/Documents/travel.vessel --no-tui --size 512M
phasmid store ~/Documents/travel.vessel --input note.txt
phasmid retrieve ~/Documents/travel.vessel --out recovered.bin
phasmid doctor         # local environment checks
phasmid guided         # guided workflows
phasmid audit          # audit view
python3 -m unittest discover -s tests
```

## Documentation map

Primary entry points:

- Documentation index (full map): [`docs/README_INDEX.md`](docs/README_INDEX.md)
- WebUI normal-use manual: [`docs/WEBUI_OPERATOR_GUIDE.md`](docs/WEBUI_OPERATOR_GUIDE.md)
- Threat model authority: [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md)
- Behavioral specification: [`docs/SPECIFICATION.md`](docs/SPECIFICATION.md)
- Architecture overview: [`docs/PHASMID_ARCHITECTURE.md`](docs/PHASMID_ARCHITECTURE.md)
- Black Hat Europe Arsenal submission-prep note: [`docs/BLACKHAT_EUROPE_ARSENAL_DEMO.md`](docs/BLACKHAT_EUROPE_ARSENAL_DEMO.md)

## Repository layout

```text
.
├── main.py                  # Local CLI launcher
├── src/phasmid/            # Application package
│   ├── cli.py              # CLI entry point
│   ├── vault_core.py
│   ├── ai_gate.py
│   ├── web_server.py
│   ├── tui/                # TUI Operator Console (textual)
│   ├── services/           # Service layer
│   ├── models/             # Data models
│   └── templates/
├── docs/                   # Specification and threat model
├── scripts/                # Utility scripts
├── tests/                  # Unit tests
└── requirements.txt
```

Runtime files such as `vault.bin`, `.state/`, and audit logs are intentionally ignored by Git.
