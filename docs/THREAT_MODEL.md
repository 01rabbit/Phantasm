# Phasmid Threat Model

## Scope

Phasmid is a field-evaluation prototype for local-only coercion-aware storage. It protects payloads in `vault.bin` with password-based cryptographic recovery, a camera-matched physical object cue, a local access key, and authenticated encryption.

It is not a substitute for audited full-disk encryption, hardware-backed key storage, classified-data handling procedures, or a complete answer to compelled disclosure.

A structured STRIDE analysis mapping this model to the six threat categories is in
`docs/THREAT_ANALYSIS_STRIDE.md`.

---

## Security Claims and Non-Claims

Phasmid does not claim to conceal the existence of encryption or coercion-aware storage software from a capable examiner. If the project files, binaries, or deployment traces are discovered, software existence is observable.

The project distinguishes:

- Software existence concealment: out of scope.
- Data-existence deniability: partial and adversary-dependent.
- Controlled disclosure: in scope and central to the design.
- Coercion-aware fallback behavior: in scope as an operational objective.

Discovery of Phasmid can weaken operational deniability, but software discovery alone does not prove the existence of additional undisclosed protected data.

Non-claims are explicit:

- no perfect deniability;
- no guaranteed secure deletion on flash media;
- no protection against compromised hosts, keyloggers, or live memory capture;
- no forensic immunity.

For the full non-claim inventory and rationale, see `docs/NON_CLAIMS.md`.

---

## In-Scope Adversaries

| Adversary | Capability | Goal |
|---|---|---|
| **Physical captor** | Physical possession of device at rest (powered off or locked) | Recover vault payload or confirm existence of restricted state |
| **Local passive observer** | Can view screen, read shell history, inspect filesystem without active access | Extract operational context, identify Phasmid installation, learn slot count or mode |
| **Local active attacker** | OS-level access to project directory and state directory | Copy `vault.bin` and state for offline cracking; replace access key; tamper with audit log |
| **Remote attacker (local-network)** | Network access to the WebUI over localhost or USB gadget interface | Replay web token; brute-force passphrase via WebUI; exploit WebUI endpoint |
| **Coercing authority** | Legal or physical coercion of operator | Compel disclosure of normal or restricted passphrase; compel confirmation of vault contents |

---

## Out-of-Scope Adversaries

| Adversary | Reason for Exclusion |
|---|---|
| **Compromised host kernel or hypervisor** | Assumed trusted; kernel-level access defeats all software controls |
| **Hardware implant or side-channel attacker** | Beyond prototype scope; requires hardware security module or certified enclave |
| **Remote attacker over untrusted network** | WebUI is designed for localhost / USB gadget only; external exposure is an operational misconfiguration |
| **Supply-chain attacker** | Package integrity is out of scope for this prototype; see `SH-22` (dependency pinning) |
| **Cryptographic breaks against AES-GCM or Argon2id** | Assumed computationally secure under current parameters |

---

## Trust Assumptions

> **Note:** This section was previously titled "Assumptions" (anchor `#assumptions`). The old anchor is preserved via this note.

- The host operating system account is trusted while Phasmid is running.
- Attackers may obtain a copy of `vault.bin`.
- Attackers may observe or copy files in the project directory if OS permissions are weak.
- The Web UI is intended for local use through `127.0.0.1` or USB gadget networking. Any party able to reach the bind address is treated as an operator: page HTML is served unauthenticated, the mutation token is embedded in it, and restricted-action confirmation phrases are public constants. Reachability, not in-app authentication, is what bounds the WebUI.
- Camera matching is an operational gate, not a cryptographic biometric factor.
- Experimental object-model output, if enabled, is an operational cue only and must never influence key derivation or container layout.
- Device capture is realistic, so rendered UI and documentation should avoid explaining the internal disclosure model during normal use.
- The device hardware (e.g., CPU serial, hardware revision) is relatively static and can be used as a source of device-binding entropy.
- Field Mode reduces normal information exposure, but it is not a security boundary.
- Hidden restricted routes reduce casual exposure, but they are not security boundaries.
- Hidden routes are not access control by themselves; server-side token checks, restricted confirmation, and typed confirmation remain required.

---

## Hardware Form Factor Considerations

Phasmid currently targets a transparent evaluation prototype form factor (for example, Raspberry Pi Zero 2 W with visible camera hardware) to support reproducible testing and operator evaluation.

This prototype form factor is not designed to appear benign under hostile physical inspection. Hardware recognition by technically informed examiners, visible camera modules, and conspicuous enclosure/wiring choices are operational threat vectors separate from software security properties.

The current codebase does not claim to solve possession plausibility or hostile-inspection-safe industrial design. Those are separate engineering and deployment problems.

---

## Assets

- Payload bytes and encrypted payload metadata.
- Separation between visible recovery outcomes and protected local state.
- Encrypted camera reference state blob in the configured state directory.
- Local vault access key in the configured state directory.
- Panic token in the configured state directory.
- Web UI mutation token created at process start or supplied through `PHASMID_WEB_TOKEN`.
- Encrypted store/recover access-token hash map in the configured state directory (see [WebUI Access Roles](#webui-access-roles)).
- Browser-visible surfaces such as rendered HTML, console output, response headers, filenames, and cached pages.
- CLI output, shell history, application stdout/stderr, and systemd logs.
- camera overlay text and Maintenance diagnostics output.
- Source identity, notes, evidence metadata, temporary field data, and local operational context.

---

## Attack Surfaces

> **Note:** This section was previously titled "Capture-Visible Surfaces" (anchor `#capture-visible-surfaces`). The old anchor is preserved via this note.

Capture-visible surfaces include the WebUI, rendered HTML, browser history, browser cache, JavaScript console, response headers, download filenames, CLI output, shell history, systemd stdout/stderr, audit logs, state-directory filenames, screenshots, and documentation copied to the device.

These surfaces should not reveal the internal disclosure model, internal trial order, slot purpose, restricted recovery side effects, or the existence of an alternate protected state.

### WebUI Surface

- HTTP endpoints served on `127.0.0.1` (default) or a configured bind address. See [WebUI Bind Address](#webui-bind-address) for the resolution order.
- Page, status, and camera-stream endpoints require a live page session for any peer that is not on loopback. See [WebUI Page Session](#webui-page-session).
- Requests carrying a DNS-name `Host` header are rejected. See [Host Header Validation](#host-header-validation).
- Mutation endpoints require `X-Phasmid-Token`; restricted action endpoints additionally require a live restricted confirmation session.
- Restricted-action confirmation phrases are public constants in `src/phasmid/restricted_actions.py`. They are typo guards against operator mistakes and carry no authorization weight.
- Response headers, `Content-Disposition` filename, and HTTP status codes are normalized to avoid leaking slot or mode information.

### WebUI Bind Address

The bind address is the WebUI's primary containment boundary, so it is resolved
by one documented order in `WebUIService.resolve_bind_host()`. Every start path,
including the TUI `w` key, uses it.

1. If `PHASMID_HOST` is set to a non-empty value, that value is used. This is the
   only way to reach a wildcard bind such as `0.0.0.0`, and it is an explicit
   operator decision.
2. Otherwise, if `PHASMID_WEBUI_EXPOSE_GADGET` is enabled, the WebUI binds to the
   address of the USB Ethernet gadget interface (`usb0`, or an `enx*` interface).
   It binds to that one address, not to all interfaces. If no gadget address is
   detected, it falls back to loopback and logs a warning.
3. Otherwise, the WebUI binds to `127.0.0.1`.

The bind address is a containment boundary, not the only one. Once the WebUI is
reachable from another machine, that peer must authenticate before it is served
operator pages, the mutation token, or the camera stream — see
[WebUI Page Session](#webui-page-session).

Treat `PHASMID_WEBUI_EXPOSE_GADGET` as extending network reachability to whatever
is on the other end of the USB cable, and `PHASMID_HOST=0.0.0.0` as extending it
to every network the device is attached to. Reachability still matters: it
exposes the unlock endpoint to online token guessing, and it widens the blast
radius of any future authentication defect.

### WebUI Page Session

These WebUI surfaces reveal operator state:

- Page HTML for `/`, `/store`, `/retrieve`, `/maintenance`, `/maintenance/entries`,
  `/emergency`, and `/operator/*`.
- `/status`, the object-cue and camera state poll.
- `/video_feed`, the live object-cue camera stream.

**A loopback peer is served them directly.** It is on the device itself,
alongside a TUI that already has full local control, so a token prompt there
costs the operator a step per session and adds no boundary. This is decided
per request from the peer address, never from configuration, so a server started
straight through uvicorn without `PHASMID_HOST` cannot fail open.

**Any other peer must present the access token at `/unlock` first.** That covers
a USB-tethered host, a gadget-interface neighbour, and anything reached through
an explicit `PHASMID_HOST`. The server then issues an `HttpOnly`,
`SameSite=Strict` session cookie bound to the client address, expiring after
`PHASMID_UI_SESSION_SECONDS` (default 1800). Unlock attempts are rate limited and
locked out by `AttemptLimiter` on the same local policy as vault access attempts.

The mutation token is rendered into page HTML only for a request that already
satisfies this gate, so for a remote peer it is a CSRF token for an unlocked
session rather than the credential that establishes one. `_ui_unlocked()` is the
single check behind all of this; it must never be reduced to an unconditional
`True`.

The access token is published to `<state dir>/webui_token` (mode `0600`) while
the WebUI runs and removed at shutdown, because the WebUI is normally started as
a subprocess and the operator has no other way to learn a per-process token. The
state directory already holds the local access key, so this does not widen the
file-system trust boundary.

**Residual risk:** a process running as the same user can read `webui_token`, or
the token out of the WebUI process environment when `PHASMID_WEB_TOKEN` is set,
and a loopback peer needs neither. The page session gate is a boundary against a
network or USB-gadget peer, not against same-user code execution on the device.

### WebUI Access Roles

An unlocked WebUI page session carries one of two roles, decided by which
credential was presented at `/unlock`, not by anything the operator picks
after unlocking:

- **Store role** - reaches `/store`, `/maintenance`, `/maintenance/entries`,
  and `/operator/*` (Diagnostics, Audit, Workflows, Inspect), in addition to
  everything the recover role reaches. This is the only role from which a
  Face can be selected or a restricted (destroy) passphrase entered, in
  either the TUI's Open Vessel screen or the WebUI's Store page.
- **Recover role** - reaches `/`, `/retrieve`, `/status`, `/video_feed`, and
  the destroy routes under `/emergency`. It has no Face selector anywhere,
  and no field named as a restricted or destroy passphrase; which face
  answers is resolved from the passphrase and the object cue, the same way
  `retrieve_file(selector=None)` resolves it at the service layer. A
  store-only route reached by a recover-role session returns a 404
  byte-identical to a route that does not exist, rather than a redirect or a
  distinct error - the same "wrong credential looks like no such route"
  pattern `web_panic_trigger` already uses, so guessing at the URL bar
  cannot confirm that a higher-privileged tier exists.

**The legacy shared `WEB_TOKEN` still grants the store role, but only until a
role token has been issued.** `WEB_TOKEN` is embedded as the CSRF mutation
guard in every unlocked page's HTML, recover-role sessions included - it is
the only thing `require_web_token` has ever checked, and the server never
learns which specific session read it back. If it kept working at `/unlock`
after a role token exists, reading a recover-role session's page source would
be enough to open an independent, full store-role session through that
endpoint, which would defeat the entire reason a narrower role exists.
`/unlock` therefore stops accepting `WEB_TOKEN` on its own the moment any role
token has been issued for either role; a device that has not adopted role
tokens yet has nothing narrower to defeat, so it is unaffected.

A **role token** is issued from the TUI (never from the WebUI), persisted
only as a salted hash, and requires a live USB gadget connection to issue or
reissue - granting either role is meant to require the operator's hands on
the device over USB, not reachability from the same Wi-Fi network or across a
room. Only one token per role may exist at a time; issuing a second requires
revoking the first.

`PHASMID_STORE_TOKEN`/`PHASMID_RECOVER_TOKEN` pin either role to a fixed
value at process startup instead, for a reproducible demo run where a token
the TUI shows exactly once is impractical. An env-pinned role always wins
over any persisted hash for that role, counts as "issued" for the `WEB_TOKEN`
fallback rule above, and cannot be issued or revoked from the TUI while the
variable is set - the environment is the only thing that can change it.

**Residual risk this does not close:** `WEB_TOKEN` is still embedded in a
recover-role session's own page HTML as its CSRF guard, and remains valid
proof of *that* session for as long as it is unlocked - `require_store_role`
is what keeps it from mutating store-only routes, not the absence of the
token. Closing this fully would mean deriving the CSRF guard from a value scoped to
the individual session instead of the one static `WEB_TOKEN`, which is a
larger change than this pass makes; what is closed here is specifically the
ability to mint a *new, independent* store-role session from a leaked
recover-role page.

**Assumption this role split depends on:** encrypting or storing new material
(the store role's surface) is assumed to happen outside any coercive event.
Nothing enforces that assumption technically - if an operator were compelled
to unlock with a store-role credential, the same disclosure the recover role
exists to prevent would still occur. The role split's guarantee is narrower
and unconditional: an operator who was only ever handed a recover-role
credential has no UI path in either interface to reveal that a second face or
a second credential category exists, regardless of what they are compelled to
do with it.

### Host Header Validation

The WebUI rejects any request whose `Host` header is a DNS name rather than an
address literal, `localhost`, or a name listed in `PHASMID_ALLOWED_HOSTS`.

This closes DNS rebinding, which is the attack that makes a USB-gadget-only
deployment reachable in practice: the operator's tethered laptop browses an
attacker page, that page re-resolves its own domain to the gadget address, and
the browser then treats the WebUI as same-origin. Rebinding requires a name,
because a name is the only thing DNS can repoint; an address literal cannot be
rebound. The check costs the operator nothing, so it applies to loopback peers
too, where the page-session gate deliberately does not.

Set `PHASMID_ALLOWED_HOSTS` only when the WebUI is genuinely reached by name,
for example `phasmid.local` over mDNS. Doing so reopens rebinding for that name.

### CLI Surface

- Passphrase arguments are not passed on the command line; the TUI reads them interactively.
- Shell history and terminal scrollback may retain operation output.
- The Doctor page warns when shell history is active.

### State Directory Surface

- `access.bin`, `store.bin`, `lock.bin` — fixed filenames recognizable to an informed examiner.
- The ORB state blob (`store.bin`) encrypts reference templates under AES-GCM; raw templates are not stored.
- `webui_token`, `webui.pid`, `webui.log` — present only while the WebUI runs. `webui_token` holds the plaintext WebUI access token at mode `0600` and is removed at shutdown.

### Configuration Directory Surface

- `vessel_registry.json` — cleartext JSON at mode `0600` in the config directory, holding only the Vessel *discovery* index: `path`, the operator's non-sensitive Vessel label, Vessel-level open bookkeeping, and each Face's fixed `face_id`/`created_at`/`selector`. Vessel paths are already discoverable from the filesystem and the two-Face model is documented, so this does not disclose more than the specification does.
- `vessel_registry.bin` — the sealed sidecar in the state directory, AES-GCM under the local state key via `LocalStateCipher` with its own AAD, the same primitive as the ORB reference blob and the access-token store. It holds everything that describes or authenticates a Face's contents: `label`, `last_accessed`, `status`, `file_count`, `occupancy`, `credentials_initialized`, `object_binding_initialized`, `dummy_profile`, the `object_binding` perceptual fingerprints of the bound access object, `emergency_auth`, and the Vessel-level `active_face_id`.
- **This was previously a gap, and the split is what closes it.** Before it, all of the above sat in cleartext at `0600`, readable as the logged-in user with no passphrase and without launching Phasmid — against the in-scope physical-captor and coercing-authority adversaries, who by definition hold the device, and requiring no out-of-scope compromised-host assumption. What that disclosed: the two-Face structure and each Face's volume; which Face carried generated filler, via `dummy_profile`; a characterisation of the access object, via its fingerprints; and an offline oracle for whether a passphrase offered under coercion was the destroy credential, via `emergency_auth`.
- **A purge no longer leaves a signature in cleartext.** `forget_face_contents()` still resets content bookkeeping while preserving `object_binding` and `emergency_auth` as credentials, but since all three are now sealed, a purged Face (bound, credentialed, zero files) and a never-used one (unbound, uncredentialed, zero files) are indistinguishable in the cleartext index. Both read as `face_id`/`created_at`/`selector` and nothing else. A party who recovers the local state key can still tell them apart.
- The destroy-passphrase verifier has to exist rather than being replaced by a check against the container: `destroy_face` and `destroy_vessel` overwrite raw bytes via `purge_mode`/`silent_brick` and must work on a container that cannot be decrypted, so coupling destruction to a successful decrypt would leave a damaged container undestroyable. Its cost was therefore raised from the interactive tier (`n=2**14`, 16 MiB) to `n=2**15` — `128*r*n` = 32 MiB, matching `ARGON2_MEMORY_COST` — and the KDF parameters are now recorded with the hash so the cost can be raised again without invalidating passphrases already set. Records written before that fall back to the legacy parameters.
- Migration overwrites the old cleartext bytes before rewriting the file without them. On flash media, prior plaintext may still persist in unlinked blocks; this document does not claim secure deletion there.
- Residual: losing the state key costs Face detail, not Vessel access — a missing, truncated, or wrong-key sidecar degrades to "no Face detail known". Under `PHASMID_TMPFS_STATE` that detail is volatile, consistent with the object-cue references that already live in a volatile state directory.

### Filesystem and Log Surface

- `vault.bin` contains no plaintext header or format marker (v3 format).
- Optional audit log (`events.log`) records operation type, timestamp, and length only — not passwords, payload bytes, or plaintext filenames.

---

## Threat Scenarios

Each scenario is tagged with applicable [STRIDE](https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats) and [LINDDUN](https://linddun.org/) categories.

> STRIDE: **S**poofing · **T**ampering · **R**epudiation · **I**nformation Disclosure · **D**enial of Service · **E**levation of Privilege  
> LINDDUN: **Li**nkability · **Id**entifiability · **N**on-repudiation · **De**tectability · **Di**sclosure · **U**nawareness · **N**on-compliance

---

### TS-01: Vault Copy + Offline Cracking

**Tags:** T, Di

**Scenario:** Attacker copies `vault.bin` from captured or accessible device and attempts offline passphrase brute-force.

**Mitigation:** Local access key is mixed into Argon2id derivation; `vault.bin` alone is insufficient. Default Argon2id parameters (`memory_cost=32768`, `iterations=2`, `lanes=1`) are tuned to impose meaningful cost on Raspberry Pi Zero 2 W class hardware. Each slot uses a fresh random salt and nonce.

---

### TS-02: State Directory Copy

**Tags:** T, Di

**Scenario:** Attacker copies both `vault.bin` and the state directory (including `access.bin`), removing the access-key separation benefit.

**Mitigation:** State directory should be on encrypted storage (separate from `vault.bin` where operationally feasible). `PHASMID_HARDWARE_SECRET_FILE` or `PHASMID_HARDWARE_SECRET_PROMPT=1` adds a third factor requiring knowledge of an external value.

**Residual risk:** If `vault.bin`, state directory, and external key material are all on one medium, separation benefits are eliminated.

---

### TS-03: Web Token Replay

**Tags:** S, I

**Scenario:** Attacker observes or captures `X-Phasmid-Token` from a local session and replays it to perform vault operations.

**Mitigation:** Token is per-process; rotation available via restricted action endpoint. WebUI binds to `127.0.0.1` by default, limiting token exposure to the local session. For a peer that is not on loopback, the mutation token is rendered only into pages served to a request that already holds a valid page session, so reaching the bind address does not disclose it; establishing a session requires presenting the token at `/unlock`, which is rate limited and attempt limited.

**Residual risk:** Token is valid for the process lifetime; a compromised local session can replay it until process restart or explicit rotation. Anything on the device itself — a same-user process reading `<state dir>/webui_token` or the WebUI process environment, or simply a loopback HTTP client — can obtain it.

---

### TS-03a: DNS Rebinding from a Tethered or Local Browser

**Tags:** S, T, E, Di

**Scenario:** The operator browses an attacker-controlled page from a USB-tethered laptop, or from a browser on the device. The page re-resolves its own domain to the WebUI bind address, so the browser treats the WebUI as same-origin, and its JavaScript reads operator pages, harvests the mutation token, and drives state-changing endpoints. This does not require the attacker to be on the network path or to know the bind address in advance.

**Mitigation:** Requests whose `Host` header is a DNS name are rejected; see [Host Header Validation](#host-header-validation). Rebinding needs a name, and an address literal cannot be rebound. Independently, a rebound origin cannot present the page-session cookie, because that cookie belongs to the address the operator actually opened.

**Residual risk:** Setting `PHASMID_ALLOWED_HOSTS` reopens rebinding for the names listed there.

---

### TS-04: Restricted Session Fixation or Replay

**Tags:** S, E

**Scenario:** Attacker who knows the restricted session cookie value replays it to access restricted action endpoints without re-confirmation.

**Mitigation:** Cookie is `HttpOnly`, short TTL (120 s default), bound to client IP, and validated server-side against an in-memory session store (not a static value). Restricted actions additionally require typed confirmation phrases.

**Residual risk:** Session state is in-process and clears on restart; no persistent invalidation mechanism.

---

### TS-05: Vault Ciphertext Tampering

**Tags:** T

**Scenario:** Attacker with filesystem access modifies bytes in `vault.bin` to corrupt or inject data.

**Mitigation:** Each slot uses AES-GCM with per-record AAD `phasmid-record-v3:<mode>:<role>:<size>`. Bit flips produce `InvalidTag`; the slot returns `(None, None)` instead of modified plaintext.

---

### TS-06: Access Key Replacement

**Tags:** T, E

**Scenario:** Attacker replaces `.state/access.bin` with a known value to enable brute-force with a controlled key.

**Mitigation:** Without the original `access.bin`, the Argon2id-derived AES-GCM key differs and decryption fails. State directory should be mode `0700` on encrypted storage.

**Residual risk:** An attacker who replaces `access.bin` before re-provisioning may introduce a known key if the operator re-stores data.

---

### TS-07: Audit Log Truncation or Deletion

**Tags:** R, T

**Scenario:** Attacker with filesystem access truncates or deletes `events.log` to erase evidence of operations.

**Mitigation:** Log integrity verification uses HMAC-SHA-256 chaining; gaps or hash mismatches are reported. Audit logging is opt-in (`PHASMID_AUDIT=1`).

**Residual risk:** Tampering is detectable after the fact but not preventable. Off-device log shipping is out of scope.

---

### TS-08: Response Header / Filename Leakage

**Tags:** I, Di, De

**Scenario:** HTTP response headers or `Content-Disposition` filename reveal slot labels, restricted action outcomes, or stored filenames to an observer.

**Mitigation:** `create_file_response()` always returns `retrieved_payload.bin` regardless of original filename. `purge_applied` flag is not exposed in any response header. Security headers include `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and a `Content-Security-Policy` with `frame-ancestors 'none'`. All responses include `Cache-Control: no-store, no-cache`.

---

### TS-09: Browser Cache Leakage

**Tags:** Di, De

**Scenario:** Cached browser responses reveal payload content, filenames, or slot information to a later visitor.

**Mitigation:** All responses include `Cache-Control: no-store, no-cache` and `Pragma: no-cache`.

**Residual risk:** Browser behavior varies; some browsers or proxies may not honor cache headers in all circumstances.

---

### TS-10: CLI Output or Shell History Leakage

**Tags:** Di, Id

**Scenario:** Shell history or terminal scrollback records passphrase arguments or operation results, exposing operational context.

**Mitigation:** TUI reads passphrases interactively; they are not passed as CLI arguments. Doctor page warns when shell history is active. Field Mode suppresses diagnostic detail until restricted confirmation is active.

---

### TS-11: Metadata Leakage in Stored Files

**Tags:** Di, Id, Li

**Scenario:** Stored files (JPEG, Office, PDF) contain embedded metadata (EXIF, authorship, location) that reveals source identity or operational context.

**Mitigation:** Store flow warns on metadata risk detection; best-effort scrubbing is available for supported file types. Unsupported types fail safely.

**Residual risk:** Metadata checks are best-effort. They can miss embedded identifiers, thumbnails, histories, and application-specific fields.

---

### TS-12: Repeated Access Failure / Lockout Bypass

**Tags:** D

**Scenario:** Attacker submits repeated incorrect passwords to exhaust the attempt counter, or restarts the process to reset the in-memory limiter.

**Mitigation:** `AttemptLimiter` applies per-client lockout after configurable failure threshold (`PHASMID_ACCESS_MAX_FAILURES`, default 5) for a configurable period (`PHASMID_ACCESS_LOCKOUT_SECONDS`, default 60 s). WebUI rate limiter (`enforce_rate_limit()`) limits 20 requests/60 s per client; exceeded rate returns HTTP 429.

**Residual risk:** In-process limiters reset on restart. Process-level restart clears the counter; this does not stop offline guessing against copied data.

---

### TS-13: Timing Side-Channel on Recovery Path

**Tags:** I, De

**Scenario:** Adversary with kernel-level or process-level tracing distinguishes the RESTRICTED recovery path from the FAILED path by observing timing differences (RESTRICTED path includes additional filesystem writes).

**Mitigation:** Argon2id KDF cost dominates end-to-end latency. NORMAL and RESTRICTED paths share the same HTTP response structure, `Content-Disposition` filename (`retrieved_payload.bin`), and media type. `purge_applied` flag does not appear in any response.

**Residual risk (unmitigated for kernel-level tracing):** The additional filesystem write on the RESTRICTED path is measurable with kernel-level process instrumentation. This difference cannot be eliminated without removing the local-state update itself. An adversary with such access is outside the in-scope adversary model.

---

### TS-14: Secure Deletion Failure on Flash Media

**Tags:** Di

**Scenario:** Deleted or overwritten payload bytes are retained in flash media wear-leveling sectors, SSD remapped blocks, backups, or filesystem journals, and recovered after device seizure.

**Mitigation (unmitigated):** Secure deletion of flash media is not reliably achievable through software alone. Key-material destruction (wiping `access.bin` or the LUKS container) renders retained ciphertext unrecoverable without the key. The seizure review checklist covers this risk.

**Claim boundary:** Brick and restricted-clear paths are logical access-destruction mechanisms. They are not physical media sanitization and must not be described as guaranteed secure deletion.

**Residual risk:** Physical recovery of flash chips may yield retained data. This threat is in-scope for awareness but not mitigated by Phasmid software controls alone.

---

### TS-15: State Directory Filename Detectability

**Tags:** De, Id

**Scenario:** Files named `access.bin`, `store.bin`, `lock.bin` in the state directory reveal to an examiner that a Phasmid-style installation is or was present.

**Mitigation:** Field Mode and LUKS layer reduce casual exposure. The seizure review checklist covers state directory inspection. The v3 vault format avoids a plaintext format marker in `vault.bin`.

**Residual risk:** File names are fixed by the current format version and are recognizable to an informed examiner.

---

### TS-16: Object Cue Spoofing

**Tags:** S

**Scenario:** Attacker who knows the reference object presents it to the camera to satisfy the object cue gate without authorization.

**Mitigation:** Object matching is an operational access cue, not cryptographic material. The vault requires the correct passphrase in addition to the object match. The cue is a layered operational control, not a single authentication factor.

---

### TS-17: Experimental Object Model Misclassification

**Tags:** S, D, Di

**Scenario:** A lightweight local object model returns an overconfident result under low light, blur, printed spoof, partial occlusion, or poor camera quality.

**Mitigation:** The model path is disabled by default, bounded by frame and time limits, and combined with neutral policy rather than trusted directly. ORB remains the baseline path unless target-hardware validation proves otherwise.

**Residual risk:** False accepts, false rejects, timing differences, and operator retry pressure remain possible until Raspberry Pi Zero 2 W validation is complete.

---

### TS-18: Coerced Disclosure

**Tags:** Di, U

**Scenario:** Operator is compelled by legal or physical coercion to reveal passphrase, confirm vault contents, or hand over device.

**Mitigation:** Restricted recovery path provides a plausible-deniability operational option (design intent). Protected entries use distinct normal and restricted passphrases sharing the same object cue. `PHASMID_PURGE_CONFIRMATION=1` requires explicit confirmation before irreversible local-state updates.

**Residual risk (partially unmitigated):** Phasmid does not claim to defeat compelled disclosure. The design provides operational friction and deniability tooling, not a legal or physical guarantee. See `docs/SPECIFICATION.md` Non-Claims section.

---

## Non-Goals

Phasmid explicitly does not aim to provide:

- **Certified cryptographic module compliance** (FIPS 140, Common Criteria) — Phasmid is a prototype; cryptographic primitives are standard but not validated.
- **Protection against a compromised host OS or kernel** — A trusted host is a foundational assumption.
- **Hardware-backed key storage or secure enclave isolation** — Key material resides in the filesystem under OS access controls.
- **Guaranteed resistance to compelled disclosure** — Restricted recovery provides operational deniability tooling, not a legal defense.
- **Reliable secure deletion on flash media** — Wear leveling and journaling prevent software-only guarantees.
- **Full audit trail by default** — Audit logging is opt-in to minimize local metadata; it is not tamper-proof against filesystem access.
- **Multi-user access control** — Phasmid is designed for single-operator local use.
- **Remote or network-accessible deployment** — WebUI is designed for localhost or USB gadget; remote deployment is a misconfiguration.
- **Protection against supply-chain compromise of dependencies** — Package integrity is operational responsibility; see `SH-22`.

---

## Current Defenses

- New stores use JES v3 records: random per-record Argon2id salt, random per-record AES-GCM nonce, no plaintext magic/header, and AEAD-authenticated encrypted metadata.
- Startup self-tests check local AES-GCM, HMAC-SHA-256, and random byte generation behavior before normal CLI/WebUI operation.
- The local access key is mixed into Argon2id by default, so copying `vault.bin` alone is insufficient for recovery.
- Hardware-specific identifiers (e.g., CPU serial, revision) are incorporated into the KDF derivation pipeline, providing basic device-binding for the vault container.
- Protected entries can be stored with normal access and restricted recovery passwords that share the same object cue.
- Store flows reject empty, duplicate, short, or highly repetitive passphrases to reduce accidental weak input.
- `PHASMID_HARDWARE_SECRET_FILE`, `PHASMID_HARDWARE_SECRET`, or `PHASMID_HARDWARE_SECRET_PROMPT=1` can add an external value to Argon2id derivation. Data stored with any of these values requires the same value for retrieval.
- Default Argon2id parameters are tuned for Raspberry Pi Zero 2 W class hardware: `memory_cost=32768`, `iterations=2`, `lanes=1`.
- Restricted recovery behavior and explicit restricted actions can update unmatched local state. These paths can cause irreversible data loss.
- Reference keys are stored together in a single AES-GCM encrypted ORB state blob under the configured state directory, not as raw reference photos or semantic per-entry template filenames.
- Image-key matching requires stable results across a short frame window rather than accepting a single-frame match.
- Web mutation endpoints require `X-Phasmid-Token`, apply a simple per-client rate limit, and enforce upload size limits.
- Access recovery flows count repeated local failures and apply a bounded temporary lockout. WebUI limiting is process-local; CLI limiting is stored in local state.
- Web responses include no-store cache headers, frame denial, MIME-sniffing protection, no-referrer policy, constrained browser permissions, and a local-only content security policy. These reduce browser residue and common Web embedding risks but do not make the WebUI safe for untrusted networks.
- Sensitive Web actions require a fresh restricted confirmation session in addition to the Web token. Restricted action pages and entry maintenance details are withheld until that confirmation is active.
- The Web server binds to `127.0.0.1` by default, including when started from the TUI with `w`. See [WebUI Bind Address](#webui-bind-address).
- **Inactivity Auto-Kill**: When managed via the TUI, the WebUI server is
  automatically terminated after 30 minutes of operator inactivity to minimize
  exposure time and return the system to a stealth state.
- **Exposure Visualization**: The TUI Home Screen displays a high-visibility
  warning banner while the WebUI port is open, preventing accidental long-term
  exposure.
- Audit logging is disabled by default. If `PHASMID_AUDIT=1` is set, security-relevant operations append minimal versioned JSONL records to the state directory's event log without recording passwords, payload bytes, plaintext filenames, or internal slot labels. New records include local integrity fields for review.
- Field Mode (`PHASMID_FIELD_MODE=1`) hides Maintenance paths, audit export, token rotation, and detailed diagnostics until restricted confirmation is active.
- Store includes a local metadata risk check and limited best-effort metadata reduction for supported file types.
- Documentation includes seizure review, source-safe storage separation, field testing, and Raspberry Pi Zero 2 W appliance deployment guidance.

---

## Residual Risks

- A compromised host can read passwords, process memory, camera frames, Web tokens, and decrypted output.
- ORB feature templates are not high-entropy cryptographic material. If the local state lock key is copied with the state blob, the local template encryption does not protect them.
- If the local access key is copied with `vault.bin`, the local access-key protection does not raise attacker cost.
- If `vault.bin`, the configured state directory, and external key material are carried together on one medium, separation benefits are reduced.
- Secure deletion is best-effort only. SSD wear leveling, backups, snapshots, and journaling filesystems may retain previous data.
- Startup self-tests detect some local primitive failures but are not cryptographic certification and do not prove the host is uncompromised.
- On flash media, recovery resistance depends primarily on key-material destruction or removal, not overwrite guarantees.
- The v3 format avoids a plaintext format marker, but surrounding tool files can still reveal that a Phasmid-style container may be in use.
- Dual password slots duplicate encrypted payload material within the selected internal storage span. This improves operational control but reduces maximum payload size.
- Multi-object cues and visual sequence cues can increase ambiguity risk and operator retry burden if relation checks are unstable under lighting, angle, or motion changes.
- The in-memory Web rate limiter and restricted confirmation state reset on process restart and are not substitutes for a full access-control layer.
- Access-attempt limiting slows repeated local failures but does not stop offline guessing against copied data, compromised hosts, or deliberate state rollback.
- UI tokens can be read from a compromised browser or host session.
- Passphrase policy cannot compensate for observed input, reused passwords, coercion, compromised hosts, or poor operational separation.
- Metadata checks and metadata reduction are best-effort. They can miss embedded identifiers, thumbnails, histories, and application-specific fields.
- Optional audit logs can support local review, including tamper detection for versioned records, but they also create local metadata.
- Browser history, cache, shell history, systemd logs, environment variables, and temporary files can leak operational context if the appliance is not configured carefully.
- Legacy v1/v2 retrieval has been removed. Old containers must be migrated by retrieving with an older build and storing again with this build.
- Timing normalization between the NORMAL, FAILED, and RESTRICTED recovery paths is best-effort only. The Argon2id KDF cost dominates end-to-end latency, but the RESTRICTED path includes additional filesystem writes for local-state updates that are measurable with process-level instrumentation. This difference cannot be eliminated without removing the local-state update itself. An adversary with kernel-level tracing tools can distinguish the RESTRICTED path from the FAILED path. The NORMAL and RESTRICTED paths share the same HTTP response structure and file download format; they are not distinguishable from the WebUI client's perspective.
- The access-token store records which of the store/recover roles currently have an issued token as separate encrypted map entries (see [WebUI Access Roles](#webui-access-roles)). A party who recovers the local state key can decrypt this map and learn which roles exist, even though the tokens themselves remain unrecoverable from it. This is a narrower leak than the Face or credential-category disclosure the role split exists to prevent - it reveals that a role tier exists, not which Face was accessed or what either passphrase is - but it is not nothing, and is accepted as a residual risk rather than solved.
- Response headers and download filenames for the NORMAL and RESTRICTED paths are structurally identical. Both return `retrieved_payload.bin` in `Content-Disposition` and the same media type. The `purge_applied` internal flag does not appear in any response header.
- The Vessel registry's Face detail is sealed in `vessel_registry.bin` under the local state key, leaving only a discovery index in cleartext (see [Configuration Directory Surface](#configuration-directory-surface)). The residual is now the same one the access-token store carries: a party who recovers the local state key can decrypt the sidecar and learn each Face's volume, which Face holds generated filler, the bound object's fingerprints, and the destroy-passphrase verifier. That is a materially narrower exposure than the cleartext it replaced — it no longer reaches an adversary who merely holds the device — but it is not nothing, and is accepted as a residual risk rather than solved.

---

## Coercion-Safe Delaying Architecture

Phasmid implements a coercion-safe delaying architecture to increase uncertainty,
delay confident conclusions, and route disclosure toward material the operator
prepared and stored ahead of time.

### Security Claims

- Separates coerced disclosure path from true disclosure path: the coerced path opens
  a file the operator prepared and stored ahead of time in a Face separate from the
  protected Face. Phasmid never fabricates that material.
- Avoids immediate proof by ensuring no single observation confirms or denies
  the existence of protected content.
- Increases adversarial analysis cost because distinguishing the disclosed Face from
  the protected Face takes investigation time.
- Silent Standby removes sensitive UI state on a configurable hotkey trigger.
- Coercion-safe recognition mode routes low-confidence recognition to the
  controlled-disclosure path rather than an obvious access-denied response.

### Non-Claims

- Phasmid does not guarantee permanent secrecy against unlimited forensic analysis.
- Phasmid does not forge or tamper with filesystem metadata, kernel logs, or timestamps.
- Phasmid does not conceal the existence of the software itself.
- Silent Standby does not erase key material from process memory.
- Operator-supplied disclosure material is not guaranteed to be indistinguishable
  from the protected content under expert forensic analysis, and Phasmid does not judge
  whether it is convincing — that is the operator's responsibility.

### Assumptions

- The operator has stored disclosure material they prepared themselves in the
  disclosure Face before any coercive event, and optionally filled free space so the
  container does not read as empty.
- That material's plausibility comes from the operator having prepared it themselves;
  Phasmid does not fabricate it or vouch for it.
- The operator activates standby before a coercive party reaches the active UI state.
- The host operating system is not compromised at the time of standby activation.

### Known Limitations

- Standby is a UI-layer operation; it does not erase in-memory key material.
- The credibility of the disclosed material depends entirely on the operator's own
  preparation; Phasmid does not assess it.
- Recognition confidence routing does not verify physical coercion context.
- Free-space occupancy warnings are advisory and measure volume only; they do not
  verify adversarial perception or judge believability.

### Allowed Behaviors

- Disclosure of operator-supplied material stored ahead of any coercive event.
- Privacy-preserving standby transitions that remove sensitive UI state.
- Ambiguity-preserving workflows.
- Configurable hotkey-triggered standby.
- Operational context template-guided free-space filler structure.
- Local free-space occupancy reports.

### Disallowed Behaviors

- Rootkits or kernel-level hiding.
- Hidden process persistence.
- Anti-forensic data destruction.
- Forensic tool bypass or interference.
- Malware-like concealment.
- False system event fabrication.
- Timestamp forgery.
- Anti-forensic metadata tampering.

For full architectural documentation see `docs/COERCION_SAFE_DELAYING.md`.

---

## Operational Guidance

- Keep `PHASMID_HOST` at the default `127.0.0.1` unless the host is otherwise protected.
- Use `PHASMID_WEBUI_EXPOSE_GADGET=1` rather than `PHASMID_HOST=0.0.0.0` when the operator interface must be reachable over the USB gadget link; it binds the gadget address only.
- Do not expose the WebUI to an untrusted network.
- Set `PHASMID_WEB_TOKEN` explicitly for repeatable controlled sessions.
- Prefer `PHASMID_HARDWARE_SECRET_FILE` or `PHASMID_HARDWARE_SECRET_PROMPT=1` over long-lived environment variables when adding an external device value.
- Set `PHASMID_STATE_SECRET` from removable media, a password manager, or a device value if encrypted reference templates must survive project-directory disclosure.
- Enable `PHASMID_AUDIT=1` only when an audit trail is more important than minimizing local metadata.
- Keep the configured state directory and `vault.bin` on encrypted local storage.
- For high-risk deployments, separate `vault.bin`, local state, memorized password, object cue, and optional external key material across different control conditions.
- Use `PHASMID_FIELD_MODE=1` for appliance-style deployments.
- Treat WebUI exposure control as an operational measure built from TUI-managed start/stop, default localhost binding, page-session authentication, and inactivity auto-kill. It is not a substitute for passwords, object cues, or external values.
- Lock the WebUI (`POST /lock`) or stop it from the TUI when stepping away; the page session otherwise survives for `PHASMID_UI_SESSION_SECONDS`.
- Use distinct high-entropy values for normal access and restricted recovery passwords.
- Keep `PHASMID_PURGE_CONFIRMATION=1` unless the deployment explicitly accepts the data-loss risk of automatic local-state updates.
- Reinitialize the container after a panic event.
- Run the seizure review checklist before field evaluation.
- Review metadata before storing source, evidence, notes, or travel material.
- Keep only necessary data on the device and remove stale entries after the task or trip.
- Run tests before changing cryptographic or Web boundary behavior.
- If evaluating multi-object or sequence cues, require bounded runtime windows and neutral reject behavior before enabling any experimental gate by default.
