from __future__ import annotations

import logging
from pathlib import Path

import platformdirs

try:
    import tomllib  # type: ignore[import-not-found]
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

import tomli_w

from ..models.profile import Profile  # noqa: F401 (re-exported)

APP_NAME = "phasmid"
APP_AUTHOR = "phasmid"
LOG = logging.getLogger(__name__)


def config_dir() -> Path:
    return Path(platformdirs.user_config_dir(APP_NAME, APP_AUTHOR))


def _profile_path(name: str) -> Path:
    return config_dir() / "profiles" / f"{name}.toml"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError as exc:
        LOG.debug("profile directory permission update failed: %s", exc)


def load_profile(name: str = "default") -> Profile:
    path = _profile_path(name)
    if not path.exists():
        return Profile(name=name)
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return Profile.from_dict(data)
    except Exception as exc:
        LOG.debug("profile load failed: %s", exc)
        return Profile(name=name)


def save_profile(profile: Profile) -> None:
    if profile.has_secrets():
        raise ValueError("Profile must not contain secret fields.")
    path = _profile_path(profile.name)
    _ensure_dir(path.parent)
    data = profile.to_dict()
    with open(path, "wb") as f:
        tomli_w.dump(data, f)
    try:
        path.chmod(0o600)
    except OSError as exc:
        LOG.debug("profile permission update failed: %s", exc)


def list_profiles() -> list[str]:
    profiles_dir = config_dir() / "profiles"
    if not profiles_dir.exists():
        return ["default"]
    names = sorted(p.stem for p in profiles_dir.glob("*.toml"))
    return names if names else ["default"]


def delete_profile(name: str) -> bool:
    if name == "default":
        return False
    path = _profile_path(name)
    if path.exists():
        path.unlink()
        return True
    return False


class ProfileService:
    def load(self, name: str = "default") -> "Profile":
        return load_profile(name)

    def save(self, profile: "Profile") -> None:
        save_profile(profile)

    def list(self) -> list[str]:
        return list_profiles()

    def delete(self, name: str) -> bool:
        return delete_profile(name)
