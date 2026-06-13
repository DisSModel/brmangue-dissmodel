from brmangue.executors.raster_executor import BrmangueRasterExecutor

import os
import matplotlib
# Use interactive backend only when a display is available (e.g. local Linux desktop);
# fall back to non-interactive Agg in headless environments (CI, SSH, containers).
matplotlib.use("tkagg" if os.environ.get("DISPLAY") else "Agg")

from dissmodel.executor.cli import run_cli

if __name__ == "__main__":
    run_cli(BrmangueRasterExecutor)
