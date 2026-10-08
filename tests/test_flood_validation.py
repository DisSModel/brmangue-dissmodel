"""
Flooding scenario (laboratory parameters of lab1.lua: sea_level_rise_rate=0.5, 11 steps)
against the TerraME 2.0.1 golden CSVs in tests/fixtures/golden_flood/ (only the
files the checkpoints need: step_NN.csv holds the state after NN-1 steps).

Soil is exact and land use differs in a handful of cells; elevation differs by
floating-point ties in the flux rule, so it is checked with bounds, not equality.
See README.md ("Flood scenario").
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from brmangue.common.constants import ALTITUDE, LAND_USE, SOIL

ROOT = Path(__file__).resolve().parent.parent


def test_flood_scenario_matches_terrame(tmp_path):
    out = subprocess.run(
        [sys.executable, str(ROOT / "src" / "brmangue" / "executors" / "validation_executor.py"), "run",
         "--input", str(ROOT / "examples" / "data" / "input" / "elevacao_pol.zip"),
         "--output", str(tmp_path / "flood.out"),
         "--param", f"golden_dir={ROOT / 'tests' / 'fixtures' / 'golden_flood'}",
         "--param", "end_time=11", "--param", "sea_level_rise_rate=0.5",
         "--param", "tide_height=6.0", "--param", "checkpoints=[1,3,5,10,11]"],
        check=True, capture_output=True, text=True, cwd=ROOT,
    ).stdout
    last = {}
    bands = "|".join(map(re.escape, (LAND_USE, SOIL, ALTITUDE)))
    for m in re.finditer(rf"step=11\s+({bands}): match=([\d.]+)%\s+MAE=([\d.]+)\s+max_err=([\d.]+)", out):
        last[m[1]] = (float(m[2]), float(m[3]), float(m[4]))
    assert set(last) == {LAND_USE, SOIL, ALTITUDE}, out[-500:]
    assert last[SOIL][0] == 100.0 and last[SOIL][1] == 0.0
    assert last[LAND_USE][0] >= 99.9                 # 4 of 50,496 cells differ
    assert last[ALTITUDE][0] > 93.0                  # 94.4% within 1 mm
    assert last[ALTITUDE][1] < 0.02                  # MAE 0.0080 m
    assert last[ALTITUDE][2] < 1.5                   # max 1.0129 m
