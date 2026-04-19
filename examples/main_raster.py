from brmangue_dissmodel.executor.coastal_raster_executor import CoastalRasterExecutor

import matplotlib
matplotlib.use('tkagg')

from dissmodel.executor.cli import run_cli

if __name__ == "__main__":
    run_cli(CoastalRasterExecutor)