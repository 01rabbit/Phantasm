from __future__ import annotations

import sys
from pathlib import Path

# Ensure pytest collection can resolve repository-root imports such as
# ``src.phasmid`` and ``tests.scenarios`` without requiring manual PYTHONPATH.
_REPO_ROOT = Path(__file__).resolve().parent
_repo_root_str = str(_REPO_ROOT)
if _repo_root_str not in sys.path:
    sys.path.insert(0, _repo_root_str)


# The WebUI resolves its target Vessel from the operator registry, which is
# real, global, and outlives any single test. A Vessel left registered by an
# earlier run therefore silently changes which container the WebUI acts on,
# and tests written against the legacy fallback start failing for reasons
# that have nothing to do with the code under test.
#
# Point the override at a path that cannot exist, which resolve_web_vessel()
# treats as "nothing registered". Tests that want a real target set the
# variable themselves; tests that want the registry branch pop it.
import os  # noqa: E402

import pytest  # noqa: E402

_NO_WEB_VESSEL = "/nonexistent/phasmid-test-no-vessel.vessel"


@pytest.fixture(autouse=True)
def _isolate_web_vessel_target():
    previous = os.environ.get("PHASMID_WEB_VESSEL")
    os.environ["PHASMID_WEB_VESSEL"] = _NO_WEB_VESSEL
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("PHASMID_WEB_VESSEL", None)
        else:
            os.environ["PHASMID_WEB_VESSEL"] = previous
