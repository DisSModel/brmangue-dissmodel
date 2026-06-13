from brmangue.executor.raster_executor import BrmangueRasterExecutor

import matplotlib
matplotlib.use('tkagg')

from dissmodel.executor.cli import run_cli

if __name__ == "__main__":
    run_cli(BrmangueRasterExecutor)
