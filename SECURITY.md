# Security Policy

## Supported Versions

Phasmid is a prototype project. Security fixes land on the latest `main` branch
and the current release line. Fixes are not backported to earlier lines.

| Version | Supported | Notes |
| --- | --- | --- |
| `0.3.x` | Yes | Current release line |
| `0.2.0` | No | Affected by [GHSA-2gm6-2phc-wv26](https://github.com/01rabbit/Phasmid/security/advisories/GHSA-2gm6-2phc-wv26) — upgrade to 0.3.0 |
| `0.1.4` | No | Affected by [GHSA-2gm6-2phc-wv26](https://github.com/01rabbit/Phasmid/security/advisories/GHSA-2gm6-2phc-wv26) — upgrade to 0.3.0 |
| `< 0.1.4` | No | Unsupported prototype snapshots |

0.1.5 was version-bumped but never tagged or published; its changes shipped in
0.2.0.

"Not supported" means no backported fix will be issued for that line. It does
not mean the line is free of known issues; check the published advisories.

## Published Advisories

Resolved issues are published at
[Security advisories](https://github.com/01rabbit/Phasmid/security/advisories).
Each names the affected range and the release that fixes it.

## Reporting a Vulnerability

**Preferred:** use GitHub's private vulnerability reporting —
[Report a vulnerability](https://github.com/01rabbit/Phasmid/security/advisories/new).
The report stays private, and it becomes the draft advisory directly, so no
separate key exchange is needed.

Alternatively, report privately by email:

- Email: `appleseedj073@gmail.com`
- PGP fingerprint: `3B25 D2EE 9084 FAF4 7525 86FA CA32 EA9B 9038 7A39`
- Public key: `docs/keys/security@phasmid.asc`

Please do not open a public issue for a suspected vulnerability.

When possible, include:

- affected commit or release
- reproducible steps
- impact assessment
- whether exploitation requires local host compromise

### Scope

Phasmid documents several accepted residual risks — for example, a process
running as the same user on the device can read WebUI access-token material.
These are stated in [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) and in
[`docs/NON_CLAIMS.md`](docs/NON_CLAIMS.md); they are known limits rather than
unreported issues. Reports are still welcome if you believe a documented limit
is stated incorrectly or is worse than described.

## Disclosure Process and Timeline

- Initial acknowledgement target: within 7 calendar days
- Triage target: within 14 calendar days
- Fix target (if accepted): best effort, usually 30–90 days depending on severity and complexity
- Coordinated disclosure publication: after fix availability or explicit maintainer statement

These windows are best-effort for a single-maintainer project and can vary.

## Single-Maintainer Risk Disclosure

Phasmid currently operates with a bus factor of 1.  
Response time can be delayed by maintainer availability. In worst-case scenarios, an explicit EOL (end-of-life) declaration may be issued if sustained maintenance is no longer feasible.
