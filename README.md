# brmangue-dissmodel 🌊

> **Coastal flood and mangrove migration models (Raster version) built on top of [DisSModel](https://github.com/LambdaGeo/dissmodel).**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![DisSModel](https://img.shields.io/badge/DisSModel-%3E%3D0.4.0-orange.svg)](https://github.com/LambdaGeo)
[![LambdaGeo](https://img.shields.io/badge/LambdaGeo-Research-green.svg)](https://github.com/LambdaGeo)

---

## 📖 About

**brmangue-dissmodel** implements spatially explicit models of coastal ecosystem
processes using the **[DisSModel](https://github.com/LambdaGeo/dissmodel)** framework.
Two coupled processes are modelled:

1. **Flood Dynamics** — sea-level rise propagation and terrain elevation adjustments.
2. **Mangrove Migration** — ecosystem response to rising sea levels, soil transitions,
   and sediment accretion.

This implementation is a Python/NumPy port of the original BR-MANGUE cellular
automata model (Bezerra et al., 2014), focused entirely on the **Raster substrate**
for high-performance vectorized simulations.

---

## 🚀 Quick Start

### CLI local (development)

```bash
# BR-MANGUE simulation (NumPy-based, fast)
python examples/main.py run \
  --input  examples/data/input/synthetic_grid_60x60_tiff.zip \
  --output examples/data/output/saida.tiff \
  --param  interactive=true \
  --param  end_time=20

# Load calibrated parameters from TOML
python examples/main.py run \
  --input  examples/data/input/synthetic_grid_60x60_tiff.zip \
  --toml   examples/model.toml

# Validate executor data contract without running
python examples/main.py validate \
  --input examples/data/input/synthetic_grid_60x60_tiff.zip

# Prepare raster from vector
python examples/prepare_raster.py data/input.shp --output data/input.tif

# Run Validation against TerraME golden CSVs
python brmangue/executor/validation_executor.py run \
  --input  examples/data/input/elevacao_pol.zip \
  --param  golden_dir=tests/fixtures/golden \
  --param  end_time=20 \
  --param  taxa_elevacao=0.05 \
  --param  altura_mare=6.0 \
  --param  checkpoints=[1,5,10,15,20]
```

### Platform API (production / reproducibility)

```bash
# Submit job
curl -X POST http://localhost:8000/submit_job \
  -H "X-API-Key: chave-sergio" \
  -H "Content-Type: application/json" \
  -d '{
    "model_name":    "brmangue",
    "input_dataset": "s3://dissmodel-inputs/mangue_grid.tif",
    "parameters":    {"end_time": 88, "taxa_elevacao": 0.011}
  }'
```

---

## 🧩 Model Processes

### 🌊 Flood Dynamics (`flood_model.py`)

Sea-level rise propagates across the landscape using a push-based neighbourhood
algorithm faithful to the original TerraME implementation (Bezerra et al., 2014).

### 🌿 Mangrove Migration (`mangrove_model.py`)

Ecosystem transitions driven by tidal influence and flooding thresholds, including
soil migration and optional sediment accretion (Alongi, 2008).

---

## 🗂️ Executor Architecture

The project follows the DisSModel `ModelExecutor` pattern — each executor separates
science from infrastructure.

### Executors available

| name | Substrate | Input → Output | Description |
|------|-----------|----------------|-------------|
| `brmangue` | RasterBackend / NumPy | Shapefile / GeoTIFF → GeoTIFF | Production simulation |
| `validation` | RasterBackend | Shapefile → MD + PNG | Validation against golden CSVs (TerraME) |

---

## 📦 Installation

```bash
# From source
git clone https://github.com/lambdageo/brmangue-dissmodel.git
cd brmangue-dissmodel
pip install -e .
```

---

## 🗂️ Project Structure

```
brmangue-dissmodel/
├── brmangue/
│   ├── __init__.py
│   ├── executor/                         # ModelExecutor implementations
│   │   ├── __init__.py                   # imports executors → auto-registration
│   │   ├── brmangue_executor.py          # Production simulation
│   │   └── validation_executor.py        # Validation against TerraME
│   ├── models/                           # NumPy-based models
│   │   ├── flood_model.py
│   │   └── mangrove_model.py
│   └── common/
│       └── constants.py                  # TIFF_BANDS, CRS, USO_COLORS, ...
├── examples/
│   ├── main.py                           # BrmangueExecutor via CLI
│   ├── prepare_raster.py                 # Vector to GeoTIFF converter
│   ├── model.toml                        # Simulation parameters
│   └── data/
└── pyproject.toml
```

---

## 📚 References

Bezerra, D. da S., Amaral, S., & Kampel, M. (2014). Impactos da Elevação do Nível
Médio do Mar sobre o Ecossistema Manguezal: A Contribuição do Sensoriamento Remoto
e Modelos Computacionais. *Ciência e Natura*, *35*(2), 152–162.
https://doi.org/10.5902/2179460X12569

---

Developed by the **[LambdaGeo](https://lambdageo.github.io)** research group.
