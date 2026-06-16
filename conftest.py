from __future__ import annotations

import sys
from pathlib import Path

# Ensure pytest collection can resolve repository-root imports such as
# ``src.phasmid`` and ``tests.scenarios`` without requiring manual PYTHONPATH.
_REPO_ROOT = Path(__file__).resolve().parent
_repo_root_str = str(_REPO_ROOT)
if _repo_root_str not in sys.path:
    sys.path.insert(0, _repo_root_str)
