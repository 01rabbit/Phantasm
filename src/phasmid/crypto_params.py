"""Centralized cryptographic parameter definitions for Phasmid.

All primitive parameters are defined here so they have a single source of truth
and can be cross-referenced against docs/CRYPTO_INVENTORY.md.

Rationale for each parameter is documented inline.  These values must not be
changed without a corresponding format-version bump and migration path, because
vaults created under one parameter set cannot be opened with a different set.
"""

# ---------------------------------------------------------------------------
# Argon2id — vault key derivation
# ---------------------------------------------------------------------------

# Target hardware: Raspberry Pi Zero 2 W (ARMv7, 512 MB LPDDR2).
# Benchmark at 2025-01: ~1.0 s wall-clock at these settings.
# OWASP minimum (2023): m=19456 KiB, t=2, p=1.  We exceed memory by ~67 %.
# Increasing memory_cost is the preferred upgrade path; bump FORMAT_VERSION.
ARGON2_ITERATIONS: int = 2
ARGON2_LANES: int = 1
ARGON2_MEMORY_COST: int = 32768  # KiB — 32 MiB

# Output length matches AES-256 key requirement.
ARGON2_KEY_LENGTH: int = 32  # bytes

# ---------------------------------------------------------------------------
# scrypt — destroy-passphrase verifier for a Face
# ---------------------------------------------------------------------------

# The destroy paths (`destroy_face`, `destroy_vessel`) authenticate against a
# stored verifier rather than by opening the container, because they overwrite
# raw bytes: `purge_mode` and `silent_brick` must work on a container that
# cannot be decrypted, so coupling destruction to a successful decrypt would
# make a damaged container undestroyable. The verifier therefore has to exist,
# which makes its cost the thing that matters.
#
# 128 * r * n = 32 MiB, matching the Argon2id memory tier above rather than the
# interactive-login tier this previously used (n=2**14, 16 MiB). Destroy is a
# rare, deliberate operation already gated behind a typed confirmation and a
# 10-second object-cue wait, so a KDF in the Argon2 range costs nothing
# operationally. maxmem is set explicitly because OpenSSL's default cap is
# itself 32 MiB and would reject these parameters at the boundary.
SCRYPT_DESTROY_N: int = 2**15
SCRYPT_DESTROY_R: int = 8
SCRYPT_DESTROY_P: int = 1
SCRYPT_DESTROY_MAXMEM: int = 64 * 1024 * 1024  # bytes — headroom over 128*r*n
SCRYPT_DESTROY_KEY_LENGTH: int = 32  # bytes

# Records written before the parameters were recorded alongside the hash used
# these. Verification falls back to them when a stored record names no
# parameters, so existing destroy passphrases keep working.
SCRYPT_DESTROY_LEGACY_N: int = 2**14
SCRYPT_DESTROY_LEGACY_R: int = 8
SCRYPT_DESTROY_LEGACY_P: int = 1

# ---------------------------------------------------------------------------
# AES-GCM — authenticated encryption
# ---------------------------------------------------------------------------

# NIST SP 800-38D recommends 96-bit (12-byte) nonces with random generation.
# Each nonce is generated via os.urandom(AESGCM_NONCE_SIZE) — never reused.
AESGCM_NONCE_SIZE: int = 12  # bytes (96 bits)

# AES-256 key size.
AESGCM_KEY_SIZE: int = 32  # bytes (256 bits)

# GCM authentication tag size (full 128-bit tag; no truncation).
AESGCM_TAG_SIZE: int = 16  # bytes (128 bits)

# ---------------------------------------------------------------------------
# Record format — vault container
# ---------------------------------------------------------------------------

# Per-record Argon2id salt (random, stored in plaintext alongside ciphertext).
RECORD_SALT_SIZE: int = 16  # bytes (128 bits)
SALT_SIZE: int = RECORD_SALT_SIZE
NONCE_SIZE: int = AESGCM_NONCE_SIZE
TAG_SIZE: int = AESGCM_TAG_SIZE
RECORD_OVERHEAD: int = SALT_SIZE + NONCE_SIZE + TAG_SIZE
FORMAT_MARKER: str = "jes-v3"
OPEN_ROLE: str = "open"
PURGE_ROLE: str = "purge"
SLOT_ROLES: tuple[str, str] = (OPEN_ROLE, PURGE_ROLE)

# ---------------------------------------------------------------------------
# Access key — local key material mixed into Argon2id secret
# ---------------------------------------------------------------------------

ACCESS_KEY_SIZE: int = 32  # bytes (256 bits)

# ---------------------------------------------------------------------------
# PBKDF2-HMAC-SHA-256 — supervisor role passphrase storage
# ---------------------------------------------------------------------------

# NIST SP 800-132 minimum: 1000 iterations.  We use 100 000 (100×) with a
# 32-byte random salt.  This role is not performance-critical.
PBKDF2_ITERATIONS: int = 100_000
PBKDF2_DKLEN: int = 32  # bytes
PBKDF2_SALT_SIZE: int = 32  # bytes

# ---------------------------------------------------------------------------
# Vault format version
# ---------------------------------------------------------------------------

# Increment when any parameter above changes or the on-disk layout changes.
# Old vaults at FORMAT_VERSION N cannot be opened by code expecting N+1.
VAULT_FORMAT_VERSION: int = 3
FORMAT_VERSION: int = VAULT_FORMAT_VERSION
