# brmangue/executor/__init__.py

from .brmangue_executor import BrmangueExecutor
from .validation_executor import ValidationExecutor

# A variável mágica __all__ define exatamente o que é exportado
# quando alguém faz `from brmangue.executor import *`
__all__ = [
    "BrmangueExecutor",
    "ValidationExecutor",
    "EXECUTOR_REGISTRY", # Exportando o registro também
]

# BÔNUS PARA A API/WORKER:
# Um dicionário que mapeia a string do request (JSON) para a Classe real
EXECUTOR_REGISTRY = {
    BrmangueExecutor.name: BrmangueExecutor,
    ValidationExecutor.name: ValidationExecutor,
}
