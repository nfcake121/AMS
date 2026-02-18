# Blender Debug Usage

Optional IR block for modifier expectations:

```json
"debug": {
  "expect_modifiers": {
    "slat_": ["SIMPLE_DEFORM:BEND", "SOLIDIFY", "BEVEL"],
    "back_slat_": ["SIMPLE_DEFORM:BEND"],
    "arm_": ["MIRROR"],
    "frame_": ["BEVEL"],
    "leg_": ["BEVEL"]
  }
}
```

## Color Legend

| Class | Color | Source problem codes |
|---|---|---|
| Overlap offenders | Red | `OVERLAP_*` |
| Missing expected modifiers | Blue | `MOD_EXPECTATION_MISSING` |
| Modifier no-effect offenders | Orange | `MOD_EXPECTATION_NO_EFFECT` |
| Non-offenders / other meshes | Gray | fallback |

Paint priority is fixed: `RED > BLUE > ORANGE > GRAY`.

## Highlight-Only (No Autofix)

```powershell
$env:DEBUG_VISUALIZE="1"
$env:DEBUG_AUTOFIX="0"
$env:DEBUG_ITERS="1"
$env:DEBUG_SNAPSHOT_BLEND="out/snapshots/sofa_highlight_only.blend"
$env:DEBUG_SNAPSHOT_PNG="out/snapshots/sofa_highlight_only.png"
& $env:BLENDER_EXE --background --python tools/blender/debug_run.py -- data/examples/sofa_ir.json
```

## Highlight + Autofix (Iterative)

```powershell
$env:DEBUG_VISUALIZE="1"
$env:DEBUG_AUTOFIX="1"
$env:DEBUG_ITERS="2"
$env:DEBUG_AUTOFIX_VERBOSE="1"
$env:DEBUG_AUTOFIX_SAFETY_MM="3"
$env:DEBUG_SNAPSHOT_BLEND="out/snapshots/sofa_autofix.blend"
$env:DEBUG_SNAPSHOT_PNG="out/snapshots/sofa_autofix.png"
& $env:BLENDER_EXE --background --python tools/blender/debug_run.py -- data/examples/sofa_ir.json
```

Autofix overlap safety margin:
- `DEBUG_AUTOFIX_SAFETY_MM` (default `2`) adds extra millimeters on top of bbox-derived penetration delta.

## Batch Run For Folder Of IR Files

Generates per-IR debug outputs and `summary.csv` with:
- `file_name`
- `debug_score`
- `problems_count`
- `overlaps_slats_m3`
- `overlaps_back_m3`
- `fixes_applied_count`

```powershell
$env:DEBUG_AUTOFIX="1"
$env:DEBUG_ITERS="2"
$env:DEBUG_SNAPSHOT_BLEND_DIR="out/snapshots/batch_blend"
& $env:BLENDER_EXE --background --python tools/blender/batch_debug_run.py -- data/examples out/logs/batch

Get-Item out/logs/batch/summary.csv
```
