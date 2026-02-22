from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.batch_plan_run import run_batch


def test_batch_plan_run_smoke(tmp_path) -> None:
    outdir = tmp_path / "plan_runs"
    buf = io.StringIO()
    with redirect_stdout(buf):
        summary = run_batch(
            ["data/examples/sofa_ir.json"],
            outdir=outdir,
            diag_dir=outdir,
        )
    assert buf.getvalue() == ""

    assert summary["total_runs"] == 1
    assert summary["total_primitives"] > 0
    assert summary["total_anchors"] > 0
    assert summary["total_events"] >= 2

    snapshot_path = outdir / "sofa_ir.plan.json"
    events_path = outdir / "sofa_ir.events.jsonl"
    summary_path = outdir / "summary.json"
    assert snapshot_path.exists()
    assert events_path.exists()
    assert summary_path.exists()

    snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert isinstance(snapshot_payload.get("primitives"), list)
    assert isinstance(snapshot_payload.get("anchors"), list)
    assert snapshot_payload["primitives"]

    event_codes = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event_codes.append(json.loads(line).get("code"))
    assert "BUILD_START" in event_codes
    assert "BUILD_DONE" in event_codes

