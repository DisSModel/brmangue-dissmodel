"""
Flooding scenario (laboratory parameters of lab1.lua: taxa_elevacao=0.5, 11 steps)
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

ROOT = Path(__file__).resolve().parent.parent


def test_flood_scenario_matches_terrame(tmp_path):
    out = subprocess.run(
        [sys.executable, str(ROOT / "src" / "brmangue" / "executors" / "validation_executor.py"), "run",
         "--input", str(ROOT / "examples" / "data" / "input" / "elevacao_pol.zip"),
         "--output", str(tmp_path / "flood.out"),
         "--param", f"golden_dir={ROOT / 'tests' / 'fixtures' / 'golden_flood'}",
         "--param", "end_time=11", "--param", "taxa_elevacao=0.5",
         "--param", "altura_mare=6.0", "--param", "checkpoints=[1,3,5,10,11]"],
        check=True, capture_output=True, text=True, cwd=ROOT,
    ).stdout
    last = {}
    for m in re.finditer(r"step=11\s+(uso|solo|alt): match=([\d.]+)%\s+MAE=([\d.]+)\s+max_err=([\d.]+)", out):
        last[m[1]] = (float(m[2]), float(m[3]), float(m[4]))
    assert set(last) == {"uso", "solo", "alt"}, out[-500:]
    assert last["solo"][0] == 100.0 and last["solo"][1] == 0.0
    assert last["uso"][0] >= 99.9                 # 4 of 50,496 cells differ
    assert last["alt"][0] > 93.0                  # 94.4% within 1 mm
    assert last["alt"][1] < 0.02                  # MAE 0.0080 m
    assert last["alt"][2] < 1.5                   # max 1.0129 m
