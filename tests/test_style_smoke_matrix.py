from __future__ import annotations

import copy
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.builders.blender.builder_v01 import build_plan_from_ir
from src.builders.blender.plan_snapshot import plan_to_snapshot


GOLDEN_DIR = Path("tests/golden")
BASE_IR = "data/examples/sofa_ir.json"


class ListDiagnosticsSink:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> None:
        self.events.append(event)


def _load_ir(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _golden_path(ir_path: str) -> Path:
    return GOLDEN_DIR / f"{Path(ir_path).stem}.plan.json"


def _make_matrix_case(
    *,
    style: str,
    preset_id: str,
    arms_type: str,
    arms_profile: str,
    back_mode: str,
) -> dict:
    ir = copy.deepcopy(_load_ir(BASE_IR))
    ir["style"] = style
    ir["preset_id"] = preset_id
    ir.setdefault("arms", {})
    ir["arms"]["type"] = arms_type
    ir["arms"]["profile"] = arms_profile
    ir.setdefault("back_support", {})
    ir["back_support"]["mode"] = back_mode
    return ir


def _assert_expected_groups(plan) -> None:
    names = [primitive.name for primitive in plan.primitives]
    assert names
    assert any(name.startswith("beam_") for name in names)
    assert any(name.startswith("leg_") for name in names)
    assert any(name.startswith("back_") for name in names)
    assert any(name.startswith("arm_") for name in names)
    assert any(anchor.name == "seat_zone" for anchor in plan.anchors)


def _assert_build_events(sink: ListDiagnosticsSink) -> None:
    build_events = [event for event in sink.events if event.stage == "build" and event.component == "builder"]
    build_codes = [event.code for event in build_events]
    assert build_codes.count("BUILD_START") == 1
    assert build_codes.count("BUILD_DONE") == 1


def test_style_smoke_matrix(monkeypatch):
    import src.builders.blender.builder_v01 as builder_mod

    cases: list[tuple[str, dict, str | None]] = [
        ("baseline_sofa_ir", _load_ir("data/examples/sofa_ir.json"), "data/examples/sofa_ir.json"),
        (
            "baseline_scandi_v03",
            _load_ir("data/examples/sofa_ir_scandi_back_split2_hslats_v03_armframe.json"),
            "data/examples/sofa_ir_scandi_back_split2_hslats_v03_armframe.json",
        ),
        (
            "baseline_scandi_v04",
            _load_ir("data/examples/sofa_ir_scandi_back_split2_hslats_v04.json"),
            "data/examples/sofa_ir_scandi_back_split2_hslats_v04.json",
        ),
        (
            "modern_boxy_v1_panel_box",
            _make_matrix_case(
                style="modern",
                preset_id="modern_boxy_v1",
                arms_type="both",
                arms_profile="box",
                back_mode="panel",
            ),
            None,
        ),
        (
            "modern_boxy_v1_slats_open",
            _make_matrix_case(
                style="modern",
                preset_id="modern_boxy_v1",
                arms_type="both",
                arms_profile="frame_box_open",
                back_mode="slats",
            ),
            None,
        ),
        (
            "modern_boxy_compact_panel_box",
            _make_matrix_case(
                style="modern",
                preset_id="modern_boxy_compact_v1",
                arms_type="both",
                arms_profile="box",
                back_mode="panel",
            ),
            None,
        ),
        (
            "scandi_straight_straps",
            _make_matrix_case(
                style="scandi",
                preset_id="scandi_straight_v1",
                arms_type="both",
                arms_profile="frame_box_open",
                back_mode="straps",
            ),
            None,
        ),
    ]

    for case_name, ir, golden_ir_path in cases:
        sink = ListDiagnosticsSink()
        monkeypatch.setattr(builder_mod, "_diag_sink_from_env", lambda sink=sink: sink)

        out = io.StringIO()
        with redirect_stdout(out):
            plan = build_plan_from_ir(ir)
        assert out.getvalue() == "", f"stdout should stay silent for {case_name}"

        _assert_expected_groups(plan)
        _assert_build_events(sink)

        if golden_ir_path is None:
            continue
        golden_path = _golden_path(golden_ir_path)
        assert golden_path.exists(), f"golden snapshot missing for {case_name}: {golden_path}"
        expected_snapshot = json.loads(golden_path.read_text(encoding="utf-8"))
        actual_snapshot = plan_to_snapshot(plan)
        assert actual_snapshot == expected_snapshot, f"snapshot drift for {case_name}"
