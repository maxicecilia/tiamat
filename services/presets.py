"""Deploy presets (environment -> workflow file, inputs, branch), read from a JSON file.

Your own presets live in `presets.json` at the repo root (not tracked), or in the file
named by TIAMAT_PRESETS_FILE. Without one, the generic `presets.example.json` is used.
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_FILE = ROOT / "presets.example.json"


def presets_file() -> Path:
    if path := os.getenv("TIAMAT_PRESETS_FILE"):
        return Path(path)
    own = ROOT / "presets.json"
    return own if own.exists() else EXAMPLE_FILE


def load_deploy_presets() -> dict[str, dict]:
    """Environment name -> preset. Keys starting with '_' (comments) are skipped."""
    data = json.loads(presets_file().read_text())
    return {env: cfg for env, cfg in data.items() if not env.startswith("_")}
