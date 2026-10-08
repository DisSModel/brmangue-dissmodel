# BR-MANGUE DisSModel 🌊

> **A Python re-implementation of the BR-MANGUE coastal flood and mangrove migration model (Bezerra et al., 2013), built on top of [DisSModel](https://github.com/DisSModel/dissmodel) and compared against the original [TerraME version](https://github.com/LambdaGeo/brmangue-terrame).**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![DisSModel](https://img.shields.io/badge/DisSModel-%3E%3D0.4.0-orange.svg)](https://github.com/DisSModel)
[![LambdaGeo](https://img.shields.io/badge/LambdaGeo-Research-green.svg)](https://github.com/DisSModel)

---

## 📖 About

This repository was created with a modest, specific goal: to **replicate the
BR-MANGUE model originally written in TerraME/Lua**
([LambdaGeo/brmangue-terrame](https://github.com/LambdaGeo/brmangue-terrame))
using the **[DisSModel](https://github.com/DisSModel/dissmodel)** framework, so
that the two implementations can be compared side by side.

Two coupled processes are modelled, following Bezerra et al. (2013):

1. **Flood Dynamics** — sea-level rise propagation and terrain elevation adjustments.
2. **Mangrove Migration** — ecosystem response to rising sea levels, soil transitions,
   and sediment accretion.

As an additional experiment, the model is implemented on **two spatial
substrates** offered by DisSModel, which lets us also compare how they behave
and what each costs in computing time:

- **Raster** (`brmangue.models.raster`) — NumPy/RasterBackend, vectorized. This is
  the implementation we use as the reference for the comparison with TerraME.
- **Vector** (`brmangue.models.vector`) — GeoDataFrame/libpysal, cell-by-cell over
  real polygon geometry. It is written to follow the same rules as the raster
  version, and a benchmark executor checks how closely the two agree.

> ⚠️ **Status:** this is work in progress. The comparison with TerraME covers two
> reference scenarios, a baseline and a flooding one (see
> [Testing & Validation](#-testing--validation)); the model still needs to be
> validated against more scenarios before it should be relied upon for scientific
> conclusions.

---

## 🚀 Quick Start

### CLI local (development)

```bash
# Raster simulation (NumPy-based)
python examples/main_raster.py run \
  --input  examples/data/input/synthetic_grid_60x60_tiff.zip \
  --output examples/data/output/saida.tiff \
  --param  interactive=true \
  --param  end_time=20

# Vector simulation (GeoDataFrame-based)
python examples/main_vector.py run \
  --input  examples/data/input/synthetic_grid_60x60_shp.zip \
  --output examples/data/output/saida.gpkg \
  --param  end_time=20

# Load calibrated parameters from TOML (works for both substrates)
python examples/main_raster.py run \
  --input  examples/data/input/synthetic_grid_60x60_tiff.zip \
  --toml   examples/model.toml

# Vector vs Raster comparison (agreement and runtime)
python examples/main_benchmark.py run \
  --input  examples/data/input/synthetic_grid_60x60_shp.zip \
  --param  end_time=10 \
  --param  taxa_elevacao=0.011 \
  --param  tolerance=0.05

# Validate executor data contract without running
python examples/main_raster.py validate \
  --input examples/data/input/synthetic_grid_60x60_tiff.zip

# Prepare raster from vector
python examples/prepare_raster.py data/input.shp --output data/input.tif

# Compare against TerraME golden CSVs
python src/brmangue/executors/validation_executor.py run \
  --input  examples/data/input/elevacao_pol.zip \
  --param  golden_dir=tests/fixtures/golden \
  --param  end_time=19 \
  --param  taxa_elevacao=0.05 \
  --param  altura_mare=6.0 \
  --param  checkpoints=[1,5,10,15,20]
```

### Platform API (reproducible runs)

```bash
# Submit job
curl -X POST http://localhost:8000/submit_job \
  -H "X-API-Key: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model_name":    "brmangue_raster",
    "input_dataset": "s3://dissmodel-inputs/ilha_maranhao_epsg31983.tif",
    "parameters":    {"end_time": 88, "taxa_elevacao": 0.011}
  }'
```

---

## 🧩 Model Processes

### 🌊 Flood Dynamics (`flood_model.py`)

Sea-level rise propagates across the landscape using a push-based neighbourhood
algorithm that we tried to keep faithful to the original TerraME implementation
(Bezerra et al., 2013).

### 🌿 Mangrove Migration (`mangrove_model.py`)

Ecosystem transitions driven by tidal influence and flooding thresholds, including
soil migration and optional sediment accretion (Alongi, 2008).

Both processes exist in raster and vector form, using the same equations,
thresholds, parameter names, and update ordering.

---

## 🗂️ Executor Architecture

The project follows the DisSModel `ModelExecutor` pattern — each executor separates
science from infrastructure.

### Executors available

| name | Substrate | Input → Output | Description |
|------|-----------|----------------|-------------|
| `brmangue_raster` | RasterBackend / NumPy | Shapefile / GeoTIFF → GeoTIFF | Raster simulation, used as the reference for comparison with TerraME |
| `brmangue_vector` | GeoDataFrame / libpysal | Shapefile / ZIP → GeoPackage | Cell-by-cell vector simulation over real polygon geometry |
| `brmangue_benchmark` | raster + vector | Shapefile / ZIP → scatter.png + report.md | Runs both substrates on the same input and reports match %/MAE/RMSE per band, plus runtime |
| `validation` | RasterBackend | Shapefile / ZIP → scatter.png + report.md | Compares raster output against TerraME golden CSVs at configurable checkpoints |

#### BrmangueVectorExecutor — usage example

```bash
# Vector simulation over real geometry (GeoDataFrame / libpysal)
python examples/main_vector.py run \
  --input  examples/data/input/synthetic_grid_60x60_shp.zip \
  --output examples/data/output/saida.gpkg \
  --param  end_time=88 \
  --param  taxa_elevacao=0.5 \
  --param  altura_mare=6.0

# With column remapping (source uses non-canonical names)
python examples/main_vector.py run \
  --input      examples/data/input/synthetic_grid_60x60_shp.zip \
  --column-map uso=land_use alt=elevation solo=soil
```

#### BrmangueBenchmarkExecutor — usage example

```bash
# Runs both Vector and Raster models on the same input; reports match per band
python examples/main_benchmark.py run \
  --input  examples/data/input/synthetic_grid_60x60_shp.zip \
  --param  end_time=10 \
  --param  taxa_elevacao=0.011 \
  --param  altura_mare=6.0 \
  --param  tolerance=0.05

# Output artifacts written to outputs/experiments/<id>/benchmark/
#   scatter.png — per-band Vector vs Raster scatter plots
#   report.md   — runtime (ms/step) and accuracy table
```

On `synthetic_grid_60x60_shp.zip` with the parameters above (3,600 cells, 10 steps)
the two substrates agree on every cell of `uso` and `solo`, and `alt` agrees with
MAE 0.0011 and a maximum error of 0.024 m; `tests/test_synthetic_benchmark.py`
checks this. The runtime columns depend on the machine.

The runtime figures in `report.md` are what we use to compare the efficiency of
the raster and vector substrates. They depend on the machine and the input, so
we recommend running the benchmark on your own data rather than taking any
single number as general.

---

## 📦 Installation

```bash
# From source
git clone https://github.com/DisSModel/brmangue-dissmodel.git
cd brmangue-dissmodel
pip install -e .
```

---

## 🗂️ Project Structure

```
brmangue-dissmodel/
├── src/
│   └── brmangue/
│       ├── __init__.py
│       ├── common/
│       │   ├── constants.py              # TIFF_BANDS, CRS, USO_COLORS, ...
│       │   └── utils.py                  # default_output_uri helper
│       ├── executors/                    # ModelExecutor implementations
│       │   ├── __init__.py               # imports executors → auto-registration
│       │   ├── raster_executor.py        # Raster simulation
│       │   ├── vector_executor.py        # Vector simulation over real geometry
│       │   ├── benchmark_executor.py     # Vector vs raster comparison
│       │   └── validation_executor.py    # Comparison against TerraME golden CSVs
│       └── models/
│           ├── raster/                   # NumPy-based models
│           │   ├── flood_model.py
│           │   └── mangrove_model.py
│           └── vector/                   # GeoDataFrame-based models
│               ├── flood_model.py
│               └── mangrove_model.py
├── tests/
│   ├── fixtures/golden/                  # TerraME reference CSVs (step_01..step_20)
│   ├── test_transition_rules.py
│   └── test_model_invariants.py
├── examples/
│   ├── main_raster.py                    # BrmangueRasterExecutor via CLI
│   ├── main_vector.py                    # BrmangueVectorExecutor via CLI
│   ├── main_benchmark.py                 # BrmangueBenchmarkExecutor via CLI
│   ├── prepare_raster.py                 # Vector to GeoTIFF converter
│   ├── model.toml                        # Simulation parameters
│   └── data/
└── pyproject.toml
```

---

## 🧪 Testing & Validation

### Unit & invariant tests

Two test modules cover basic model correctness without external data:

- **`tests/test_transition_rules.py`** — analytical tests on 3×3 synthetic grids
  with hand-calculated expected values (flood propagation, mangrove soil/use
  migration, altitude blocking).
- **`tests/test_model_invariants.py`** — structural invariants on a 5×5 real grid
  (flooded cells monotonically non-decreasing, `SOLO_MANGUE_MIGRADO` never
  reverts, masked cells never change, etc.).

```bash
pytest tests/ -v
```

### Comparison against TerraME

`ValidationExecutor` (`src/brmangue/executors/validation_executor.py`,
`name="validation"`) runs the raster model and compares its output step-by-step
against reference CSVs generated by the original TerraME/Lua model
(Bezerra et al., 2013), located in `tests/fixtures/golden/step_NN.csv`
(currently step_01 … step_20).

Metrics reported per band (`uso`, `solo`, `alt`) at each checkpoint:
match %, MAE, RMSE, max_err.

#### Golden indexing convention

The golden CSVs are indexed on **state**, not on number of executions:
`step_01.csv` is the *initial* state, before the model has run once (verified:
zero cells differ from the input shapefile). Simulation step *N* therefore maps
to `step_{N+1}.csv`, applied via `GOLDEN_STEP_OFFSET` in the executor.

With 20 golden files, the highest comparable simulation step is **19**.

#### Results so far (Maranhão Island, 50,496 cells, `taxa_elevacao=0.05`)

| Step | `uso` | `solo` | `alt` (1 mm tol) | `alt` MAE |
|-----:|------:|-------:|-----------------:|----------:|
| 1  | 100.0% | 100.0% | 100.0% | 0.00000 |
| 5  | 100.0% | 100.0% | 99.6% | 0.00002 |
| 10 | 100.0% | 100.0% | 98.6% | 0.00017 |
| 19 | 100.0% | 100.0% | 97.4% | 0.00038 |

In this scenario, the categorical bands (`uso`, `solo`) agree with TerraME cell
for cell at every checkpoint. Only `alt` diverges slightly (maximum absolute
error 0.10 m after 19 steps, against elevations of 1–58 m). The residual is
floating-point tie-breaking, not a rule difference: the flux rule compares
accumulated elevations with `<=`, and ~57% of neighbour pairs hold *exactly*
equal elevations, so a ~1e-16 difference in summation order (TerraME visits
cells sequentially, NumPy adds neighbour contributions per direction) flips an
occasional comparison. Fed the exact TerraME state (17 significant digits), the
elevation rule reproduces the next TerraME step to 1e-14 at most steps.

#### Flood scenario (`taxa_elevacao=0.5`, `FINAL_TIME=11`)

Same dataset, with the laboratory parameters of `lab1.lua`, where flooding does
occur (TerraME flood golden regenerated with TerraME 2.0.1; 2,469 flooded cells
at step 11). Python vs TerraME:

| Step | `uso` | `solo` | `alt` (1 mm tol) | `alt` MAE |
|-----:|------:|-------:|-----------------:|----------:|
| 1  | 100.0% | 100.0% | 100.0% | 0.00000 |
| 3  | 100.0% | 100.0% | 98.8% | 0.00063 |
| 5  | 100.0% | 100.0% | 97.8% | 0.00200 |
| 10 | 100.0% | 100.0% | 94.9% | 0.00708 |
| 11 | 99.99% | 100.0% | 94.4% | 0.00801 |

`solo` is exact at every step and `uso` differs in <0.05% of cells (4 cells at
step 11, frontier cells whose flooding flips on the same elevation ties); the
maximum `alt` error at step 11 is 1.01 m. The golden files for this scenario are
in `tests/fixtures/golden_flood/` (only the steps the checkpoints need) and
`tests/test_flood_validation.py` checks the comparison; to regenerate them, run
`make golden TAXA=0.5 FINAL=11 OUT=golden_flood` in
[`brmangue-terrame`](https://github.com/LambdaGeo/brmangue-terrame). Because the
flooding threshold is discontinuous, the tie noise grows with the number of
steps; this scenario should be read as "same dynamics, not bit-identical".

#### Limitations and scenario coverage

These results should be read with care, because **the model has been validated
on two scenarios so far**, and the baseline one is a limited test:

- At `taxa_elevacao=0.05` the flood component **never triggers a land-use
  transition**: the lowest cell adjacent to a source sits at 1.0 m and the sea only
  reaches 1.0 m at step 20, by which point flux diffusion has raised it further.
  The golden CSVs show TerraME behaving the same way (zero newly flooded cells
  across all 20 steps), so the two implementations agree — but this scenario
  leaves the flood component essentially unexercised, and the agreement above
  mostly reflects the mangrove migration component.
- The original laboratory script (`lab1.lua`) uses `TAXA_ELEVACAO_MAR = 0.5` with
  `FINAL_TIME = 11`, under which flooding does occur (2,469 cells by step 11 in
  TerraME). The "Flood scenario" table above compares that run step by step with
  TerraME, and
  `tests/test_model_invariants.py::test_flood_model_floods_with_laboratory_parameters`
  checks that flooding happens under those parameters.
- The vector/raster comparison and the runtime measurements have likewise been
  run on a limited set of inputs.

**Next steps** are to validate the model against additional scenarios —
especially ones in which flooding actually occurs — and to extend the
raster/vector comparison to more datasets. Feedback, issues and suggestions are
very welcome.

```bash
# See Quick Start above for the full CLI invocation:
python src/brmangue/executors/validation_executor.py run \
  --input  examples/data/input/elevacao_pol.zip \
  --param  golden_dir=tests/fixtures/golden \
  --param  end_time=19 \
  --param  'checkpoints=[1,5,10,19]'
```

---

## 📚 References

Bezerra, D. da S., Amaral, S., & Kampel, M. (2013). Impactos da Elevação do Nível
Médio do Mar sobre o Ecossistema Manguezal: A Contribuição do Sensoriamento Remoto
e Modelos Computacionais. *Ciência e Natura*, *35*(2), 152–162.
https://doi.org/10.5902/2179460X12569

Original TerraME implementation: [LambdaGeo/brmangue-terrame](https://github.com/LambdaGeo/brmangue-terrame)

---

## 🤝 Credits

This port builds on the reference implementation and design ideas of
**Felipe Martins Sousa** (UFMA), co-author of the BR-MANGUE application to the
Baixada Maranhense (Bezerra et al., 2025, https://doi.org/10.5772/intechopen.1012210).

---

Developed by the **[LambdaGeo](https://lambdageo.github.io)** research group.
