from __future__ import annotations

import os
from pathlib import Path


def _parse_value(raw: str) -> str:
    value = raw.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def load_env_file(env_path: Path | None = None) -> None:
    """Load .env entries into os.environ without overriding existing variables."""
    if env_path is None:
        env_path = Path(__file__).resolve().parents[2] / ".env"

    if not env_path.exists() or not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        os.environ.setdefault(key, _parse_value(value))
