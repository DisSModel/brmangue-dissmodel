from brmangue.executor.brmangue_executor import BrmangueExecutor

import matplotlib
matplotlib.use('tkagg')

from dissmodel.executor.cli import run_cli

if __name__ == "__main__":
    run_cli(BrmangueExecutor)
