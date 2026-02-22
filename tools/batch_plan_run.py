from __future__ import annotations

import argparse
import io
import json
import os
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import Any, Iterable

from src.builders.blender.builder_v01 import build_plan_from_ir
from src.builders.blender.diagnostics import Severity
from src.builders.blender.plan_snapshot import plan_to_snapshot


def _load_ir(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _discover_ir_paths(inputs: Iterable[str | Path]) -> list[Path]:
    paths: list[Path] = []
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            paths.extend(sorted(item for item in path.glob("*.json") if item.is_file()))
            continue
        if path.is_file():
            paths.append(path)
    deduped = sorted(set(paths))
    return deduped


def _load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        events.append(json.loads(stripped))
    return events


@contextmanager
def _temporary_env(name: str, value: str | None):
    old_value = os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    try:
        yield
    finally:
        if old_value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = old_value


def run_batch(
    inputs: Iterable[str | Path],
    *,
    outdir: str | Path,
    preset_id: str | None = None,
    diag_dir: str | Path | None = None,
) -> dict[str, Any]:
    out_path = Path(outdir)
    out_path.mkdir(parents=True, exist_ok=True)
    diag_path = Path(diag_dir) if diag_dir is not None else out_path
    diag_path.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    ir_paths = _discover_ir_paths(inputs)
    for ir_path in ir_paths:
        ir = _load_ir(ir_path)
        if preset_id:
            ir["preset_id"] = preset_id

        events_file = diag_path / f"{ir_path.stem}.events.jsonl"
        if events_file.exists():
            events_file.unlink()

        with _temporary_env("AMS_DIAG_JSONL", str(events_file)):
            with redirect_stdout(io.StringIO()):
                plan = build_plan_from_ir(ir)

        snapshot = plan_to_snapshot(plan)
        snapshot_file = out_path / f"{ir_path.stem}.plan.json"
        _write_json(snapshot_file, snapshot)

        events = _load_events(events_file)
        warning_count = sum(int(event.get("severity", 0)) >= int(Severity.WARN) for event in events)
        error_count = sum(int(event.get("severity", 0)) >= int(Severity.ERROR) for event in events)

        results.append(
            {
                "ir_path": str(ir_path),
                "snapshot_path": str(snapshot_file),
                "events_path": str(events_file),
                "primitives_count": len(plan.primitives),
                "anchors_count": len(plan.anchors),
                "events_count": len(events),
                "warnings_count": warning_count,
                "errors_count": error_count,
            }
        )

    summary = {
        "runs": results,
        "total_runs": len(results),
        "total_primitives": sum(item["primitives_count"] for item in results),
        "total_anchors": sum(item["anchors_count"] for item in results),
        "total_events": sum(item["events_count"] for item in results),
        "total_warnings": sum(item["warnings_count"] for item in results),
        "total_errors": sum(item["errors_count"] for item in results),
    }
    _write_json(out_path / "summary.json", summary)
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run batch plan generation without Blender runtime.")
    parser.add_argument("inputs", nargs="+", help="IR json files or directories containing json files")
    parser.add_argument("--outdir", default="out/reports/plan_runs", help="Output directory for snapshots")
    parser.add_argument("--preset-id", default="", help="Optional preset_id override")
    parser.add_argument(
        "--diag-dir",
        default="",
        help="Optional directory for per-IR diagnostics JSONL files (defaults to outdir)",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    diag_dir = args.diag_dir.strip() if isinstance(args.diag_dir, str) else ""
    summary = run_batch(
        inputs=args.inputs,
        outdir=args.outdir,
        preset_id=(args.preset_id.strip() or None),
        diag_dir=(diag_dir or args.outdir),
    )
    print(f"BATCH_DONE runs={summary['total_runs']} outdir={args.outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
