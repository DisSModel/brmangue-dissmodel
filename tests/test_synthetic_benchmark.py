"""
Vector and raster substrates on the 60x60 synthetic grid (3,600 cells, 10 steps),
the case in README.md ("BrmangueBenchmarkExecutor"). Runtime is not asserted.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
import pytest
from brmangue.common.constants import ALTITUDE, LAND_USE, SOIL

ROOT = Path(__file__).resolve().parent.parent


def test_vector_and_raster_agree_on_synthetic_grid(tmp_path):
    subprocess.run(
        [sys.executable, str(ROOT / "examples" / "main_benchmark.py"), "run",
         "--input", str(ROOT / "examples" / "data" / "input" / "synthetic_grid_60x60_shp.zip"),
         "--output", str(tmp_path / "bench.out"),
         "--param", "end_time=10", "--param", "sea_level_rise_rate=0.011",
         "--param", "tide_height=6.0", "--param", "tolerance=0.05"],
        check=True, capture_output=True, text=True, cwd=ROOT,
    )
    (report,) = tmp_path.glob("bench_*.out/report.md")
    rows = {}
    for line in report.read_text().splitlines():
        bands = "|".join(map(re.escape, (ALTITUDE, SOIL, LAND_USE)))
        m = re.match(rf"\|\s*({bands})\s*\|\s*([\d.]+)%\s*\|\s*([\d.]+)\s*\|[^|]*\|\s*([\d.]+)\s*\|\s*(\d+)", line)
        if m:
            rows[m[1]] = (float(m[2]), float(m[3]), float(m[4]), int(m[5]))
    assert set(rows) == {ALTITUDE, SOIL, LAND_USE}
    for band, (match, _mae, _max, n) in rows.items():
        assert n == 3600
        assert match == 100.0, band
    assert rows[SOIL][1] == 0.0 and rows[LAND_USE][1] == 0.0
    assert rows[ALTITUDE][1] < 2e-3          # 0.001131 as of this writing
    assert rows[ALTITUDE][2] < 0.03          # 0.0243


# ── parameter names before 0.5.0 are rejected, not silently ignored ───────────

@pytest.mark.parametrize("old, new", [
    ("taxa_elevacao", "sea_level_rise_rate"),
    ("altura_mare", "tide_height"),
    ("acrecao_ativa", "accretion_enabled"),
])
def test_renamed_parameters_are_rejected(old, new):
    from brmangue.common.utils import reject_renamed_parameters

    with pytest.raises(ValueError, match=f"'{old}' → '{new}'"):
        reject_renamed_parameters({old: 1, "end_time": 5})
    reject_renamed_parameters({new: 1, "end_time": 5})   # current names pass


def test_executors_reject_renamed_parameters():
    from dissmodel.executor import ExperimentRecord
    from dissmodel.executor.schemas import DataSource

    from brmangue.executors import EXECUTOR_REGISTRY

    for name, cls in EXECUTOR_REGISTRY.items():
        record = ExperimentRecord(
            source=DataSource(type="local", uri="in.zip"),
            parameters={"taxa_elevacao": 0.5, "golden_dir": "x"},
        )
        with pytest.raises(ValueError, match="sea_level_rise_rate"):
            cls().validate(record)
