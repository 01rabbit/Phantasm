# Phasmid TUI Operator Console

## Overview

Phasmid provides a terminal user interface as its primary operator console.

Running `phasmid` with no arguments opens the Simple Operator screen. Long
command-line argument chains are not required for normal operation. The
default screen provides only Open, New, Guided, Expert, and Quit. Detailed
operator screens remain available through Expert.

Phasmid is a research-grade prototype for studying and operating deniable
storage under coerced disclosure scenarios. The TUI reflects that position: it
is visually distinctive enough for hacker and security-research audiences, and
structured enough to be discussed with institutional and government-adjacent
reviewers.

## Product Position

Phasmid is presented throughout the UI as:

```text
A coercion-aware deniable-storage system.
```

Expanded:

```text
A research-grade prototype for studying and operating deniable storage
under coerced disclosure scenarios.
```

Phasmid does not claim to be production-grade, military-grade, forensic-proof,
coercion-proof, undetectable, or unbreakable. These claims are explicitly
excluded from all UI text, help output, and documentation.

## Core Terminology

### Vessel

A Vessel is a headerless deniable container file. It carries one or more
disclosure faces without exposing metadata, magic bytes, or an obvious vault
structure.

Primary UI labels:

```text
Vessels
Deniable container files
```

`Vault` is not used as the primary UI term. `Vault` implies an obvious
protected-storage object. Phasmid emphasises that the storage object does not
assert a conventional vault structure.

### Face

A Face (or Disclosure Face) is a disclosure surface within a Vessel. A Vessel
may carry multiple disclosure faces. The UI uses neutral labels and does not
identify which face is primary.

Allowed labels in the UI:

```text
Face
Disclosure Face
Face Label
Disclosure Face 1
Disclosure Face 2
```

The following terms are excluded from ordinary operation:

```text
real  /  fake  /  true  /  decoy  /  hidden truth
```

## Architecture

```text
src/phasmid/
  cli.py                    CLI entry point — routes to TUI by default

  tui/
    app.py                  PhasmidApp (Textual App subclass)
    banner.py               FULL_BANNER, COMPACT_BANNER, get_banner()
    theme.py                phasmid-dark and phasmid-light themes

    screens/
      simple_home.py        Simple Operator screen (default)
      home.py               Expert operator console
      about.py              About / splash screen with full banner
      audit.py              Audit View
      doctor.py             Doctor View
      guided.py             Guided Workflows
      inspect_vessel.py     Vessel inspection
      create_vessel.py      Vessel creation workflow
      open_vessel.py        Vessel open workflow
      face_manager.py       Disclosure face label management
      settings.py           Non-secret settings

    widgets/
      status_panel.py       VesselSummaryPanel
      vessel_table.py       VesselTable (DataTable wrapper)
      event_log.py          EventLog (RichLog wrapper)
      warning_box.py        WarningBox

  services/
    vessel_service.py       Vessel registration, listing, path redaction
    vessel_workflow_service.py shared Vessel create/store/recover operations
    profile_service.py      platformdirs config paths, TOML save/load
    inspection_service.py   Entropy estimation, magic-byte detection
    doctor_service.py       Structured local environment checks
    audit_service.py        Audit report generation
    guided_service.py       Guided workflow definitions

  models/
    vessel.py               VesselMeta, VesselPosture
    profile.py              Profile (non-secret fields only)
    inspection.py           InspectionResult, InspectionField
    doctor.py               DoctorResult, DoctorCheck, DoctorLevel
    audit.py                AuditReport, AuditSection, AuditEntry
```

Separation of concerns is enforced:

- The TUI layer handles rendering, navigation, prompts, and confirmations.
- The service layer handles use-case orchestration.
- The core layer handles cryptographic and container internals.
- The model layer holds structured data passed between services and UI.

The TUI does not implement cryptographic operations directly.

## Commands

```bash
phasmid                    Open the Simple Operator screen
phasmid open <vessel>      Open a Vessel in the TUI
phasmid open <vessel> --no-tui --face face_a
                           Mark a Vessel open directly from the CLI
phasmid close <vessel>     Close a Vessel and preserve local metadata
phasmid face create <vessel> --face face_b --label travel
                           Create or update a local Face record
phasmid file add <vessel> --face face_a --input note.txt
                           Add a file to the selected Face
phasmid file list <vessel> --face face_a
                           List files in the selected Face
phasmid file remove <vessel> --face face_a --name note.txt
                           Remove a file from the selected Face
phasmid create <vessel>    Open Vessel creation in the TUI
phasmid create <vessel> --no-tui --size 512M
                           Create a Vessel directly from the CLI
phasmid store <vessel> --input path/to/file
                           Store a local file in a Vessel
phasmid retrieve <vessel> --out output.bin
                           Recover a local file from a Vessel
phasmid inspect <vessel>   Inspect a Vessel
phasmid guided             Open Guided Workflows
phasmid audit              Open Audit View
phasmid doctor             Open Doctor View
phasmid doctor --no-tui    Print doctor output without opening the TUI
phasmid about              Open the About screen
```

Legacy commands (`init`, `brick`, `verify-state`, `verify-audit-log`,
`export-redacted-log`) remain available for compatibility and advanced use.

## Simple Operator Screen

The Simple Operator screen is the default TUI entry point. It shows protected
storage and keeps normal actions short and visible. The current profile's
default Vessel directory and selected Vessel context are preserved.

### Keyboard Shortcuts

| Key | Action |
|---|---|
| `o` | Open selected Vessel |
| `n` | Create protected storage |
| `g` | Guided Help |
| `e` | Open Expert controls |
| `q` | Quit |
| `r` | Refresh Vessel list (not shown in footer) |

## Expert Controls

Press `e` from the Simple Operator screen to open the detailed operator
console. It retains the selected Vessel and provides the previous detailed
actions: Close, Create, Inspect, Face management, Audit, Doctor, Settings,
LUKS, and Help. Expert controls are for diagnostic and maintenance work, not
the normal Protect/Open flow.

## WebUI Integration (Exposed Mode)

Phasmid provides a local WebUI for operators who require a graphical interface
for certain tasks. This interface is considered "exposed" as it opens a network
port. The default bind address is `127.0.0.1:8000`, and `w` uses that default;
deployment configuration may set a different host only when the access path is
otherwise protected. Set `PHASMID_WEBUI_EXPOSE_GADGET=1` to bind the USB gadget
interface address instead, or `PHASMID_HOST` to choose a bind address directly.
The exposure banner and the start notification show the address actually bound.

### WebUI Control

The WebUI can be started and stopped directly from the TUI using the `w` key.
Starting the WebUI launches a background process managed by the TUI.

### Safety Features

- **Auto-Kill Timer**: If the TUI detects no operator input for 10 minutes while
  the WebUI is active, it will automatically terminate the WebUI server to
  return the system to a stealth state.
- **Exposure Warning**: When the WebUI is active, a high-visibility warning
  banner (`⚠️ WEBUI ACTIVE (EXPOSED)`) is displayed at the top of the Home
  screen.
- **Uptime Tracking**: The Vessel Summary panel displays the current WebUI
  status and uptime when active.

### Operational Guidance

The WebUI should only be active during active use. Operators are encouraged to
use the TUI (`w`) to manually retract the WebUI as soon as the graphical task
is complete.

## ASCII Banner

`src/phasmid/tui/banner.py` provides centralised banner support.

```python
FULL_BANNER: str      # full multi-line ASCII art banner
COMPACT_BANNER: str   # compact text fallback
BANNER_FULL_MIN_WIDTH = 90

def get_banner(width: int, compact: bool = False) -> str:
    ...
```

Behaviour:

- Terminal width ≥ 90 and `compact=False`: returns `FULL_BANNER`.
- Terminal width < 90 or `compact=True`: returns `COMPACT_BANNER`.
- The full banner is shown only on the About / splash screen.
- It is not shown on every workflow screen.

Full banner:

```text
██████╗ ██╗  ██╗ █████╗ ███████╗███╗   ███╗██╗██████╗
██╔══██╗██║  ██║██╔══██╗██╔════╝████╗ ████║██║██╔══██╗
██████╔╝███████║███████║███████╗██╔████╔██║██║██║  ██║
██╔═══╝ ██╔══██║██╔══██║╚════██║██║╚██╔╝██║██║██║  ██║
██║     ██║  ██║██║  ██║███████║██║ ╚═╝ ██║██║██████╔╝
╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚═╝╚═════╝

Janus Eidolon System
LOCAL DISCLOSURE CONTROL
```

Compact banner:

```text
PHASMID
Janus Eidolon System
LOCAL DISCLOSURE CONTROL
```

## Vessel Discovery and Registration

Known Vessels are sourced from:

- registered Vessel paths (stored in `vessel_registry.json` in the config dir)
- the default Vessel directory configured in settings
- manually selected files

The registry stores only non-secret metadata (file paths). It never stores
passphrases, derived keys, raw keys, object keys, recovery secrets, or file
contents.

Paths in the UI may be redacted. A long path such as:

```text
/Users/alice/Documents/travel/notes/field.vessel
```

is displayed as:

```text
~/Documents/.../field.vessel
```

## Inspection

The inspection service (`services/inspection_service.py`) analyses a file
without decrypting it.

Output fields:

```text
File              path to the file
Size              human-readable size
Header            no recognized header detected
Magic Bytes       no obvious magic bytes detected  (or detected type)
Entropy           high / random-like  (with bits/byte value)
Recognized Type   unknown  (or identified type)
Vessel Claim      not asserted
```

Cautious language is used throughout. The inspection result never asserts that
a file is deniable or undetectable. It reports what was observed.

## Doctor View

The doctor service (`services/doctor_service.py`) runs structured local
environment checks and returns a `DoctorResult` with a list of `DoctorCheck`
entries, each with a level of `OK`, `WARN`, `FAIL`, or `INFO`.

Checks performed:

| Check | Notes |
|---|---|
| Configuration directory permissions | Warns if accessible to other users |
| Profile directory permissions | Warns if accessible to other users |
| Temporary directory policy | Warns if world-writable |
| Output directory permissions | Checked when an output dir is configured |
| Secure randomness | Verifies `secrets.token_bytes` is available |
| Shell history | Warns if `HISTFILE` is set |
| Swap status | Best effort; Linux only |
| Terminal scrollback | Info notice only |
| Debug logging | Warns if `PHASMID_DEBUG` is set |

Required disclaimer shown at the end of every Doctor run:

```text
This check reduces obvious mistakes. It does not certify the host as secure.
```

## Audit View

The audit service (`services/audit_service.py`) generates a static
`AuditReport` with the following sections:

- **System Position** — status, purpose, scope, non-claims
- **Cryptographic Controls** — AEAD, KDF, header, magic bytes, metadata
- **Operational Controls** — config secrets, passphrase logging, destructive confirm
- **Logging Policy** — what is and is not logged, path redaction
- **Known Limitations** — host compromise, OS artifacts, coercion resistance
- **Non-Claims** — explicit list of things Phasmid does not claim

The Audit View is intended to make Phasmid credible to security researchers,
government-adjacent evaluators, and institutional reviewers.

## Guided Workflows

Guided Workflows are step-by-step interactive explanations built into the same
operator console. They are not a separate demo mode.

The first two workflows support normal use:

| ID | Title |
|---|---|
| `quick_protect` | Protect a File |
| `quick_open` | Open a Protected File |
| `coerced_disclosure` | Coerced Disclosure Walkthrough |
| `headerless_inspection` | Headerless Vessel Inspection |
| `multiple_faces` | Multiple Disclosure Faces |
| `safety_checklist` | Operator Safety Checklist |

Each workflow shows a description and numbered steps. Steps use only permitted
terminology and avoid forbidden terms.

## Configuration and Profiles

Configuration is stored in the OS-native user config directory, resolved
through `platformdirs.user_config_dir("phasmid")`.

Typical locations:

```text
macOS:  ~/Library/Application Support/phasmid/
Linux:  ~/.config/phasmid/
```

Profiles are stored as TOML files under `profiles/`. Profile files are
created with mode `0600`. The config directory is created with mode `0700`.

Allowed profile fields:

```text
name                  profile name
container_size        default container size (e.g. "512M")
default_vessel_dir    default Vessel directory
default_output        default output directory
recent_tracking       whether to track recently opened Vessels
kdf_profile           KDF preset name (e.g. "interactive")
theme                 UI theme ("dark" or "light")
compact_banner        force compact banner regardless of terminal width
```

Profiles must not contain passphrases, derived keys, raw key material, object
keys, or recovery secrets. The `Profile` model enforces this with a
`FORBIDDEN_KEYS` check and a `has_secrets()` guard. Attempting to save a
profile with a forbidden field raises a `ValueError`.

## Logging and Redaction

The following are never logged:

- passphrases
- derived keys
- raw key material
- object keys
- recovery phrases
- file contents

`vessel_service.redact_path()` reduces full paths before they appear in log
output or UI notifications. Paths with more than three components relative to
the home directory are shortened to `~/first/.../filename`.

## Confirmation Rules

The following actions require explicit confirmation before proceeding:

```text
Overwrite an existing Vessel file
Overwrite extracted output
Delete a Vessel registration
Remove a Face label
Clear recent history
Reset local generated assets
```

High-impact actions require the user to type `CONFIRM` before proceeding. The
confirmation prompt is plain and professional. Theatrical phrases are not used
for safety-critical operations.

## Error Handling

Errors are actionable. Example format:

```text
Could not open Vessel.
Reason: file does not exist.
Next step: choose another path or create a new Vessel.
```

Python tracebacks are not shown in normal TUI usage. They are visible only when
`PHASMID_DEBUG=1` is set.

## Terminal Requirements

Minimum supported terminal size: 100 columns × 30 rows.

Required navigation:

```text
Arrow keys   selection
Enter        activate
Esc          go back / dismiss
q            quit
?            help
```

Mouse support is optional.

## Security Claim Discipline

Allowed wording in all UI text, help output, and documentation:

```text
headerless
deniable
random-like
no obvious metadata
no recognized header detected
plausible disclosure
coerced disclosure
research-grade prototype
coercion-aware
```

Excluded wording:

```text
undetectable
unbreakable
forensic-proof
coercion-proof
military-grade
guaranteed safe
impossible to discover
production-grade
```

## Known Limitations

- Host compromise may defeat confidentiality.
- OS artifacts (swap, logs, filesystem metadata) may reveal usage.
- Coercion resistance is procedural, not absolute.
- Deniability depends on operational context, not only on technical design.
- Side channels are not systematically addressed.
- Memory forensics is not addressed.

These limitations are displayed verbatim in the Audit View.

## Intended Balance

Phasmid is designed to be:

```text
Distinctive enough to attract hackers.
Practical enough to operate.
Careful enough to avoid false security claims.
Structured enough for serious institutional review.
```
