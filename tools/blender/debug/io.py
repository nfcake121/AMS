"""JSON I/O helpers for debug runs."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def ir_sha256(ir: Mapping[str, Any]) -> str:
    """Return SHA256 of canonical IR JSON."""
    payload = json.dumps(ir, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_run_id(short_len: int = 8) -> str:
    """Return run id as run_YYYYmmdd_HHMMSS_<shortid>."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short_id = uuid.uuid4().hex[: max(4, int(short_len))]
    return f"run_{timestamp}_{short_id}"


def save_json(path: str | os.PathLike[str], payload: Mapping[str, Any]) -> str:
    """Save JSON payload to path, creating parent directories."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output_path)


def load_json(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load JSON object from path."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}, got {type(data).__name__}")
    return data


def save_run_log(
    payload: Mapping[str, Any],
    out_dir: str | os.PathLike[str] = "out/logs/runs",
    run_id: str | None = None,
) -> str:
    """Save debug run payload as out/logs/runs/run_<timestamp>_<shortid>.json."""
    resolved_run_id = run_id or make_run_id()
    file_path = Path(out_dir) / f"{resolved_run_id}.json"
    return save_json(file_path, payload)


def load_run_log(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load a previously saved debug run log."""
    return load_json(path)

def ensure_dir(path: str | os.PathLike[str]) -> str:
    """Create directory if it doesn't exist. Returns normalized string path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return str(p)
def ensure_parent(path: str | os.PathLike[str]) -> str:
    """Ensure parent directory for a file path exists. Returns normalized string path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)
def ensure_dir(path: str | os.PathLike[str]) -> str:
    """Create directory if it doesn't exist. Returns normalized string path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def make_run_tag(*, run_id: str) -> str:
    """Return a stable tag for artifacts based on run_id."""
    # debug_run ожидает, что run_tag используется в именах файлов: <run_tag>.json / .metrics.json / .ir_in.json ...
    return str(run_id)


def sha256_file(path: str | os.PathLike[str]) -> str:
    """Compute SHA256 hex digest of a file."""
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(payload: Mapping[str, Any]) -> str:
    """Compute SHA256 of canonical JSON (stable across key order)."""
    s = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
