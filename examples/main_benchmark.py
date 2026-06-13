# examples/main_benchmark.py
from __future__ import annotations

from dissmodel.executor.cli import run_cli
# the benchmark executor forces the non-interactive Agg backend on import
from brmangue.executors.benchmark_executor import BrmangueBenchmarkExecutor

if __name__ == "__main__":
    run_cli(BrmangueBenchmarkExecutor)
