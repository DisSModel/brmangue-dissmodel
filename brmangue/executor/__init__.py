# brmangue/executor/__init__.py

from .brmangue_executor import BrmangueExecutor
from .validation_executor import ValidationExecutor
from .vector_executor import BrmangueVectorExecutor
from .benchmark_executor import BrmangueBenchmarkExecutor

# A variável mágica __all__ define exatamente o que é exportado
# quando alguém faz `from brmangue.executor import *`
__all__ = [
    "BrmangueExecutor",
    "ValidationExecutor",
    "BrmangueVectorExecutor",
    "BrmangueBenchmarkExecutor",
    "EXECUTOR_REGISTRY", # Exportando o registro também
]

# BÔNUS PARA A API/WORKER:
# Um dicionário que mapeia a string do request (JSON) para a Classe real
EXECUTOR_REGISTRY = {
    BrmangueExecutor.name: BrmangueExecutor,
    ValidationExecutor.name: ValidationExecutor,
    BrmangueVectorExecutor.name: BrmangueVectorExecutor,
    BrmangueBenchmarkExecutor.name: BrmangueBenchmarkExecutor,
}
