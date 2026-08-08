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
    "EXECUTOR_REGISTRY", # Exportando o registro também
]

# BÔNUS PARA A API/WORKER:
# Um dicionário que mapeia a string do request (JSON) para a Classe real
EXECUTOR_REGISTRY = {
    BrmangueRasterExecutor.name: BrmangueRasterExecutor,
    BrmangueVectorExecutor.name: BrmangueVectorExecutor,
    BrmangueBenchmarkExecutor.name: BrmangueBenchmarkExecutor,
    ValidationExecutor.name: ValidationExecutor,
}
