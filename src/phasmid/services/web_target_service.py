"""Resolves which container the WebUI acts on.

The WebUI and the TUI used to work on different storage: the TUI on Vessels,
the WebUI straight through ``PhasmidVault("vault.bin")``. Two operator
surfaces on one device therefore disagreed about what was stored - a file
saved from a browser never appeared in any Vessel, in Audit, or in VESSEL
STATUS.

Both go through the same Vessel now. The selection lives here rather than in
``web_server`` because it has to consult the operator profile and the face
vocabulary, and ``web_server`` is a boundary module whose text is audited for
exactly those terms.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..vault_core import PhasmidVault

WEB_VESSEL_ENV = "PHASMID_WEB_VESSEL"
LEGACY_CONTAINER_PATH = "vault.bin"


def resolve_web_vessel() -> Path | None:
    """Vessel the WebUI stores into and retrieves from.

    The WebUI has no Vessel picker, so the target is resolved rather than
    chosen: an explicit override first, then the registry the TUI writes to,
    so both surfaces land on the same container without the operator having
    to keep them in step by hand.

    Returns None when nothing is registered, leaving callers to fall back to
    the legacy container so a device that has never created a Vessel keeps
    working. Pointing the override at a path that does not exist also returns
    None, which is the deterministic way to exercise that fallback without
    depending on whatever Vessels happen to be registered on the machine.
    """
    override = os.environ.get(WEB_VESSEL_ENV, "").strip()
    if override:
        candidate = Path(override).expanduser()
        return candidate if candidate.exists() else None

    try:
        from .profile_service import load_profile
        from .vessel_service import VesselService

        settings = load_profile()
        known = VesselService().list_all(settings.default_vessel_dir or None)
    except Exception:
        return None

    existing = [item for item in known if Path(item.path).exists()]
    if not existing:
        return None
    # Most recently opened wins, so the interface follows whichever Vessel the
    # operator is actually working in rather than whichever sorts first.
    existing.sort(key=lambda item: (item.last_opened_at or "", str(item.path)))
    return Path(existing[-1].path)


def resolve_web_container(fallback: PhasmidVault) -> PhasmidVault:
    """Container the destructive operations act on.

    Purge, clear and re-initialise have to reach the same container that store
    and retrieve use. Otherwise the emergency controls would wipe the legacy
    file while leaving the Vessel the operator actually filled untouched -
    the operator would believe the device had been cleared when it had not.
    """
    vessel_path = resolve_web_vessel()
    if vessel_path is None:
        return fallback
    try:
        size_mb = vessel_path.stat().st_size / (1024 * 1024)
        return PhasmidVault(str(vessel_path), size_mb=size_mb)
    except OSError:
        return fallback


def forget_face_contents(mode: str | None = None) -> None:
    """Reset the stored-content bookkeeping for a face after a purge.

    A purge rewrites raw container bytes and knows nothing about the
    registry, which keeps file counts, occupancy and the plausibility profile
    per face. Left untouched those figures survive the data they describe, so
    the console would go on reporting stored files and a high-plausibility
    profile for a face whose bytes are gone.

    Only content bookkeeping is reset. The object binding and the
    destroy-password hash are credentials, not content: clearing one face's
    files must not quietly remove the physical-object requirement or
    invalidate the destroy passphrase for it. Whole-container wipes use
    :func:`forget_container_contents` instead.
    """
    _reset_faces(
        ["face_a", "face_b"] if mode is None else [face_for_mode(mode)],
        credentials=False,
    )


def forget_container_contents() -> None:
    """Reset everything after a whole-container wipe.

    Re-initialise and clear destroy the container outright, so the
    credentials go with it. Carrying a destroy-password hash across a
    re-initialise would leave a passphrase compromised beforehand still able
    to authorise destruction of whatever is stored afterwards, which is the
    situation the re-initialise exists to end.
    """
    _reset_faces(["face_a", "face_b"], credentials=True)


def _reset_faces(faces: list[str], *, credentials: bool) -> None:
    vessel_path = resolve_web_vessel()
    if vessel_path is None:
        return
    try:
        from .vessel_service import VesselService

        registry = VesselService()
        for face in faces:
            if credentials:
                registry.touch_face(
                    vessel_path,
                    _FACE_IDS[face],
                    status="available",
                    occupancy=0,
                    file_count=0,
                    dummy_profile={},
                    object_binding={},
                    emergency_auth={},
                    credentials_initialized=False,
                    object_binding_initialized=False,
                )
            else:
                registry.touch_face(
                    vessel_path,
                    _FACE_IDS[face],
                    occupancy=0,
                    file_count=0,
                    dummy_profile={},
                )
    except Exception:
        # Best effort: the destructive operation itself already succeeded and
        # must not be reported as failed because bookkeeping could not follow.
        return


_FACE_IDS = {
    "dummy": "face_a",
    "secret": "face_b",
    "face_a": "face_a",
    "face_b": "face_b",
}


def face_for_mode(mode: str) -> str:
    """Face selector matching an access mode.

    The two selector vocabularies already agree on the mode axis, and
    ``_FACE_ALIASES`` in the workflow service accepts a mode name directly,
    so this is a rename rather than a mapping decision. Kept explicit so the
    correspondence is stated somewhere rather than relied on implicitly.
    """
    return str(mode)
