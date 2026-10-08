# brmangue/executors/__init__.py

from .raster_executor import BrmangueRasterExecutor
from .vector_executor import BrmangueVectorExecutor
from .benchmark_executor import BrmangueBenchmarkExecutor
from .validation_executor import ValidationExecutor

# The __all__ magic variable defines exactly what gets exported
# when someone does `from brmangue.executor import *`
__all__ = [
    "BrmangueRasterExecutor",
    "BrmangueVectorExecutor",
    "BrmangueBenchmarkExecutor",
    "ValidationExecutor",
    "EXECUTOR_REGISTRY", # the registry is exported too
]

# For the API/worker: maps the executor name in a (JSON) request to its class
EXECUTOR_REGISTRY = {
    BrmangueRasterExecutor.name: BrmangueRasterExecutor,
    BrmangueVectorExecutor.name: BrmangueVectorExecutor,
    BrmangueBenchmarkExecutor.name: BrmangueBenchmarkExecutor,
    ValidationExecutor.name: ValidationExecutor,
}
