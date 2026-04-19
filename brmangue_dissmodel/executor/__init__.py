# brmangue_dissmodel/executor/__init__.py

from .coastal_raster_executor import CoastalRasterExecutor
from .coastal_raster_validation_executor import CoastalRasterValidationExecutor

# A variável mágica __all__ define exatamente o que é exportado
# quando alguém faz `from brmangue_dissmodel.executor import *`
__all__ = [
    "CoastalRasterExecutor",
    "CoastalRasterValidationExecutor",
    "EXECUTOR_REGISTRY", # Exportando o registro também
]

# BÔNUS PARA A API/WORKER:
# Um dicionário que mapeia a string do request (JSON) para a Classe real
EXECUTOR_REGISTRY = {
    CoastalRasterExecutor.name: CoastalRasterExecutor,
    CoastalRasterValidationExecutor.name: CoastalRasterValidationExecutor,
}