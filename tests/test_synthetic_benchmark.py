"""
Vector and raster substrates on the 60x60 synthetic grid (3,600 cells, 10 steps),
the case in README.md ("BrmangueBenchmarkExecutor"). Runtime is not asserted.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_vector_and_raster_agree_on_synthetic_grid(tmp_path):
    subprocess.run(
        [sys.executable, str(ROOT / "examples" / "main_benchmark.py"), "run",
         "--input", str(ROOT / "examples" / "data" / "input" / "synthetic_grid_60x60_shp.zip"),
         "--output", str(tmp_path / "bench.out"),
         "--param", "end_time=10", "--param", "taxa_elevacao=0.011",
         "--param", "altura_mare=6.0", "--param", "tolerance=0.05"],
        check=True, capture_output=True, text=True, cwd=ROOT,
    )
    (report,) = tmp_path.glob("bench_*.out/report.md")
    rows = {}
    for line in report.read_text().splitlines():
        m = re.match(r"\|\s*(alt|solo|uso)\s*\|\s*([\d.]+)%\s*\|\s*([\d.]+)\s*\|[^|]*\|\s*([\d.]+)\s*\|\s*(\d+)", line)
        if m:
            rows[m[1]] = (float(m[2]), float(m[3]), float(m[4]), int(m[5]))
    assert set(rows) == {"alt", "solo", "uso"}
    for band, (match, _mae, _max, n) in rows.items():
        assert n == 3600
        assert match == 100.0, band
    assert rows["solo"][1] == 0.0 and rows["uso"][1] == 0.0
    assert rows["alt"][1] < 2e-3          # 0.001131 as of this writing
    assert rows["alt"][2] < 0.03          # 0.0243
