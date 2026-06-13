# brmangue/executor/__init__.py

from .raster_executor import BrmangueRasterExecutor
from .vector_executor import BrmangueVectorExecutor
from .benchmark_executor import BrmangueBenchmarkExecutor
from .validation_executor import ValidationExecutor

# A variável mágica __all__ define exatamente o que é exportado
# quando alguém faz `from brmangue.executor import *`
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
