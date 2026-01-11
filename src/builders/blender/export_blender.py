"""Runner that triggers Blender build from an IR JSON path."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


DEFAULT_GLB_PATH = Path("out/glb/sofa.glb")
DEFAULT_LOG_PATH = Path("out/logs/build.log")
DEFAULT_BLEND_PATH = Path("out/logs/sofa.blend")


def _blender_executable() -> str:
    """Resolve Blender executable path."""
    return os.environ.get("BLENDER_EXE", "blender")


def _run_blender(args: list[str], log_path: Path, env: dict[str, str] | None = None) -> None:
    """Run a Blender command and write output to log."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        subprocess.run(args, stdout=handle, stderr=subprocess.STDOUT, check=True, env=env)


def run_blender_build(ir_json_path: str, glb_path: str | None = None) -> Path:
    """Run Blender build for the given IR JSON path."""
    ir_path = Path(ir_json_path)
    out_path = Path(glb_path) if glb_path else DEFAULT_GLB_PATH
    blender = _blender_executable()
    blend_path = DEFAULT_BLEND_PATH

    builder_script = Path("tools/blender/run_builder_v01.py")
    export_script = Path("tools/blender/run_export_glb.py")

    builder_env = os.environ.copy()
    builder_env["IR_PATH"] = str(ir_path)
    builder_env["BLEND_PATH"] = str(blend_path)

    _run_blender(
        [
            blender,
            "--background",
            "--python",
            str(builder_script),
            "--",
            str(ir_path),
        ],
        DEFAULT_LOG_PATH,
        env=builder_env,
    )

    export_env = os.environ.copy()
    export_env["GLB_PATH"] = str(out_path)

    _run_blender(
        [
            blender,
            "--background",
            str(blend_path),
            "--python",
            str(export_script),
            "--",
            str(out_path),
        ],
        DEFAULT_LOG_PATH,
        env=export_env,
    )

    return out_path


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run Blender builder and export GLB.")
    parser.add_argument("ir_json_path", help="Path to resolved IR JSON.")
    parser.add_argument("glb_path", nargs="?", default=str(DEFAULT_GLB_PATH), help="Output GLB path.")
    args = parser.parse_args()

    run_blender_build(args.ir_json_path, args.glb_path)


if __name__ == "__main__":
    main()
