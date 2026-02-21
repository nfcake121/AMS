from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS_DIR = ROOT / "src" / "builders" / "blender" / "components"


def test_components_have_no_print_calls() -> None:
    offenders: list[str] = []
    for path in sorted(COMPONENTS_DIR.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "print":
                rel = path.relative_to(ROOT)
                offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, f"print() is forbidden in components: {', '.join(offenders)}"
