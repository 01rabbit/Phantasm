# Phasmid Threat Analysis — STRIDE Framework

## Scope and Caveats

This document maps the Phasmid threat model to the STRIDE framework.  It covers the
WebUI, CLI, metadata workflow, object cue matching, local state, restricted actions,
audit logging, and deployment posture.

**This document does not claim that Phasmid is field-proven, certified, approved for
classified-data handling, or guaranteed to resist compelled disclosure.**  It records
known risks and current mitigations to support structured review.

See `docs/THREAT_MODEL.md` for the base model, `docs/SPECIFICATION.md` for the full
system description, and `docs/SEIZURE_REVIEW_CHECKLIST.md` for the pre-field review.

---

## STRIDE Summary Table

| Category | Key Risks | Primary Controls |
|---|---|---|
| Spoofing | Web token replay, restricted session fixation | Per-session token, session TTL, client binding |
| Tampering | Vault ciphertext modification, state directory manipulation | AES-GCM authentication, key-material separation |
| Repudiation | Missing audit trail | Optional HMAC-chained audit log |
| Information Disclosure | Response headers, download filename, CLI output, browser cache | Neutral filenames, security headers, Field Mode |
| Denial of Service | Repeated access failures, rate limit bypass | Per-client limiter, access lockout |
| Elevation of Privilege | Restricted confirmation bypass, unrestricted action access | Server-side session check, typed confirmation |

---

## S — Spoofing

### Assets at Risk

- WebUI mutation token (`X-Phasmid-Token`)
- Restricted confirmation session cookie
- Object cue match state

### Attack Vectors and Controls

**Web token replay**: An attacker who obtains `PHASMID_WEB_TOKEN` or observes a
request containing `X-Phasmid-Token` can replay it until the process restarts.

*Controls*: Token is per-process by default.  `PHASMID_WEB_TOKEN` can be rotated via
the restricted action endpoint.  WebUI binds to `127.0.0.1` by default, limiting
token exposure to local sessions.

**Restricted session fixation**: The restricted confirmation cookie binds to the
originating client IP but not to a cryptographic session.  An attacker with local
network access and knowledge of the cookie value could attempt replay.

*Controls*: Cookie is `HttpOnly`, short TTL (120 s default), bound to client IP.
Field Mode limits restricted action pages until a fresh restricted session is active.

presenting a photo or screen.

*Controls*: Face lock is a UI gate only, not vault encryption.  A compromised face
lock does not expose vault contents without the correct passphrase and object cue.
The enrolled template is AES-GCM encrypted at rest.

**Object cue spoofing**: An attacker who knows the reference object can present it to
the camera to match the cue.

*Controls*: Object matching is an operational access cue, not cryptographic material.
The vault requires the correct passphrase in addition to the object match.

### Residual Risks

- Web token has process-lifetime validity; restart or explicit rotation required to
  invalidate a captured token.
- Face lock does not protect against a determined attacker with a physical copy of the
  enrollment reference and the ability to present it to the camera.

---

## T — Tampering

### Assets at Risk

- `vault.bin` ciphertext
- `.state/` directory (access key, state blob, audit log)
- Phasmid source files and configuration

### Attack Vectors and Controls

**Vault ciphertext modification**: An attacker with filesystem access can modify
`vault.bin` bytes.

*Controls*: Each slot uses AES-GCM with a fresh random nonce and per-record AAD
`phasmid-record-v3:<mode>:<role>:<size>`.  Bit flips in the ciphertext produce an
`InvalidTag` exception; the slot returns `(None, None)` rather than modified
plaintext.

**Access key replacement**: Replacing `.state/access.bin` with a known value would
allow an attacker to attempt brute-force derivation without the original key.

*Controls*: Access key is mixed into Argon2id as a key-material input.  Without
the original key, the derived AES-GCM key differs; decryption fails.  The state
directory should be mode 0700 and on encrypted storage.

**State blob manipulation**: The ORB reference template is
both AES-GCM encrypted in the state directory.

*Controls*: Corruption or replacement produces decryption failure at load time.

**Source code modification**: An attacker with write access to the project directory
can alter behavior.

*Controls*: The optional release manifest (Ed25519-signed) covers source files.
The CI pipeline runs `ruff`, `mypy`, and the full test suite on each commit.

### Residual Risks

- Vault ciphertext authentication protects against passive modification, not against
  an attacker who can observe the AES-GCM key (e.g., from a compromised process).
- The state directory is not cryptographically sealed; an attacker who can delete
  or replace `access.bin` before re-provisioning may be able to introduce a known key.

---

## R — Repudiation

### Assets at Risk

- Evidence that a retrieve, store, or restricted action occurred
- Tamper-detection evidence for the audit log

### Attack Vectors and Controls

**Denial of a retrieve event**: A user may claim they never retrieved a protected
entry.

*Controls*: Audit logging is opt-in (`PHASMID_AUDIT=1`).  When enabled, versioned
JSONL records include an HMAC-SHA-256 chain so that record insertion, deletion, or
modification is locally detectable.  Audit events do not record passwords, payload
bytes, plaintext filenames, or internal slot labels.

**Audit log truncation**: An attacker with filesystem access can truncate or delete
the audit log.

*Controls*: Log integrity verification checks the chain; gaps or hash mismatches are
reported.  This detects tampering after the fact but does not prevent it.

### Residual Risks

- Audit logging is disabled by default to minimize local metadata.  Deployers who
  require accountability must enable it explicitly.
- An attacker who can delete `events.log` removes all local accountability evidence.
  Off-device log shipping is out of scope for the current prototype.

---

## I — Information Disclosure

### Assets at Risk

- Payload content and metadata
- Existence of restricted recovery configuration
- Internal slot structure and mode labels
- Operator identity or workflow context

### Attack Vectors and Controls

**Response header leakage**: HTTP responses could expose slot labels, restricted
action outcomes, or stored filenames.

*Controls*: `create_file_response()` always uses `retrieved_payload.bin` regardless
of the original stored filename.  The `purge_applied` internal flag does not appear in
any response header.  Security headers include `X-Content-Type-Options`, `X-Frame-Options`,
`Referrer-Policy`, and a `Content-Security-Policy` with `frame-ancestors 'none'`.

**Browser cache leakage**: Responses cached by the browser could reveal payload
content or filenames to a later visitor.

*Controls*: All responses include `Cache-Control: no-store, no-cache` and
`Pragma: no-cache`.

**CLI output leakage**: Shell history or terminal scrollback may record passphrase
arguments or operation results.

*Controls*: The TUI avoids passing passphrases as command-line arguments.  The Doctor
page warns when shell history is active.  Field Mode suppresses diagnostic detail until
restricted confirmation is active.

**Metadata leakage**: Stored files may contain EXIF, Office, or PDF metadata that
reveals authorship, device, or location information.

*Controls*: The metadata risk check warns on store; best-effort scrubbing is available
for supported file types (JPEG, PNG, Office ZIP).  Unsupported types fail safely.

**State directory filename leakage**: Files named `access.bin`, `store.bin`, `lock.bin`
in the state directory reveal the presence of a Phasmid installation.

*Controls*: Field Mode (and LUKS layer) reduce casual exposure.  File names cannot be
changed without a format version bump.  The seizure review checklist covers state
directory inspection.

**Audit log leakage**: Enabled audit logs create local metadata about operations.

*Controls*: Events record only operation type, timestamp, source, and length — not
passwords, payload bytes, plaintext filenames, or internal slot labels.

### Residual Risks

- Browser cache, shell history, systemd logs, and temporary files are all potential
  disclosure surfaces that depend on careful operational configuration.
- The state directory filename set (`access.bin`, `store.bin`, `lock.bin`) is
  consistent across deployments and recognisable to an informed examiner.

---

## D — Denial of Service

### Assets at Risk

- Availability of the WebUI retrieve endpoint
- Availability of the local access key after repeated failures

### Attack Vectors and Controls

**Repeated incorrect access attempts**: An attacker with local network access can
repeatedly submit wrong passwords to exhaust the attempt counter.

*Controls*: `AttemptLimiter` applies per-client lockout after a configurable failure
threshold (`PHASMID_ACCESS_MAX_FAILURES`, default 5) for a configurable period
(`PHASMID_ACCESS_LOCKOUT_SECONDS`, default 60 s).  The limiter is in-process and
resets on restart; it does not substitute for a hardware-backed counter.

**Rate limit exhaustion**: An attacker can send rapid requests to exhaust the rate
limiter.

*Controls*: `enforce_rate_limit()` limits requests per client per time window
(default: 20 requests per 60 s).  Exceeded rate returns HTTP 429.

**Process crash**: A panic event or deliberate process termination disrupts service.

*Controls*: The systemd unit restarts on failure (`Restart=on-failure`, `RestartSec=2`).
The TUI auto-kills the WebUI after 30 minutes of inactivity to limit exposure.

**LUKS mount unavailability**: If the optional LUKS layer or tmpfs mount is
unavailable, Phasmid refuses to start rather than falling back to unencrypted storage.

*Controls*: This is intentional fail-closed behavior.  The systemd unit uses
`Requires=` to declare the dependency.

### Residual Risks

- The in-process attempt limiter resets on restart; an attacker can restart the
  process to clear the counter.
- DoS via file descriptor exhaustion, memory pressure, or kernel-level resource limits
  is not mitigated beyond standard systemd hardening options.

---

## E — Elevation of Privilege

### Assets at Risk

- Restricted confirmation session (gates destructive local actions)
- Capability policy enforcement

### Attack Vectors and Controls

**Restricted confirmation bypass**: An attacker who can forge or replay the restricted
session cookie can access restricted action endpoints without the confirmation step.

*Controls*: The cookie is validated server-side against an in-memory session store
(not a static value).  Sessions are bound to client IP and expire after TTL.  Actions
additionally require typed confirmation phrases.

**Capability policy bypass**: Disabling a capability via the environment or policy
file should prevent the corresponding action.

*Controls*: `require_capability()` checks the active policy before allowing each
capability-gated endpoint.  Disabled capabilities return HTTP 403 with the neutral
`operation unavailable` message.

**Privilege escalation via file permission weakness**: If the state directory or vault
file has permissive permissions, another local user may read or modify them.

*Controls*: The service unit sets `UMask=0077` and `ProtectHome=true`.
`_write_new_access_key()` sets `access.bin` to mode 0600 after creation.  The Doctor
page checks directory and file permissions.

### Residual Risks

- Server-side session validation is in-process; a crash or restart clears all
  restricted sessions, requiring re-confirmation.
- `ProtectSystem=strict` limits write paths to those in `ReadWritePaths`.  Misconfigured
  `ReadWritePaths` can expand the writable surface.

---

## Follow-Up Issues

| Issue | STRIDE Category | Description |
|---|---|---|
| `#11` | D, E | Process hardening (umask, RLIMIT_CORE, prctl, mlockall) ✅ |
| `#12` | T, I | Volatile tmpfs key-material store ✅ |
| `#13` | T, I | Device binding evaluation ✅ |
| `#17` | T, I | LUKS optional storage layer ✅ |
| `#14` | I, D | Threshold split-key recovery evaluation ✅ |

---

## References

- `docs/THREAT_MODEL.md`
- `docs/SPECIFICATION.md`
- `docs/SEIZURE_REVIEW_CHECKLIST.md`
- `docs/FIELD_TEST_PROCEDURE.md`
- `docs/RPI_ZERO_APPLIANCE_DEPLOYMENT.md`
