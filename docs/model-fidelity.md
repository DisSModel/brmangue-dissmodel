# Fidelity to the published BR-MANGUE model

**Reference:** Bezerra, D. S. (2014). *Modelagem espacialmente explícita da
resposta do ecossistema manguezal à elevação do nível do mar* (INPE thesis),
§3.6 "Experimento de Modelagem (BR-MANGUE)", equations (3.1)–(3.3) and
transition rules I–XII.

This repository is validated against TerraME golden CSVs
(`tests/fixtures/golden`, see README). Those goldens come from an *adaptation*
of the model to TerraME 2.0 (`LambdaGeo/brmangue-terrame`), not from the
published scripts. Agreement with them shows that the Python code reproduces
that adaptation; **it does not by itself show agreement with the thesis**. This
page records, rule by rule, how the implementation relates to the thesis.
Status: ✅ implemented as published · ⚠️ implemented differently ·
⛔ not implemented. Entries marked *(to confirm)* are our reading and have not
been checked with the model's author.

| Thesis | Published rule | This implementation | Status |
|---|---|---|---|
| Eq. 3.1 | Water column of each sea cell rises by `r` (0.011 m) per event; 88 events (2012–2100) | Global sea level `nivel_mar = t · taxa_elevacao`; each source cell's elevation grows by the flux of the step (`taxa_elevacao / n`) | ⚠️ *(to confirm)* |
| Eq. 3.2 / rule I | `Fluxo = Elevação / nº de vizinhas` with altitude lower than the water column | `fluxo = taxa / (1 + nº vizinhos reais com alt ≤ alt da fonte)`; applied to the source and those neighbours. Only real neighbours count (off-grid / off-mask positions do not) | ⚠️ (lower than the *source cell altitude*, not the column; `+1` for the cell itself) |
| Rules II–III | Neighbours of water cells become flooded when `fluxo + altitude ≤ coluna d'água` | Neighbour of a flooded/sea cell floods when `alt ≤ nivel_mar` (absolute level) | ⚠️ |
| Rule IV | Mangrove cell resists flooding if vertical accretion + altitude ≥ water column | Not applied: mangrove cells flood by the same rule as the others | ⛔ |
| Eq. 3.3 / rule XII | Vertical accretion `y = 1.693 + 0.939 x` (mm; Alongi 2008) raises mud banks | Implemented (`acrecao_ativa`), **off by default**; also commented out in the TerraME adaptation | ⚠️ opt-in |
| Rules V–VI | Intertidal zone (AIM) set by tidal amplitude and shifted with sea-level rise | `zona de influência = altura_mare + nivel_mar` (`altura_mare` 6 m) | ✅ |
| Rules VII, X, XI | Mangrove migrates only inside the AIM, onto cells whose soil is mangrove mud | Land use → `MANGUE_MIGRADO` for dry targets with mangrove soil and `alt ≤ zona de influência`, adjacent to a mangrove cell | ✅ |
| Rule XII | New mud banks form when the AIM moves (longitudinal accretion) | Soil → `SOLO_MANGUE_MIGRADO` for adjacent targets with `alt ≤ zona de influência` | ✅ |
| Rules VIII–IX | Barriers: anthropic use, beach, unsuitable soil, altitude above the AIM | Only `VEGETACAO_TERRESTRE` and `SOLO_DESCOBERTO` can be targets; everything else is a barrier | ✅ |
| Neighbourhood | Moore, up to 8 neighbours | Moore (8); border cells have fewer | ✅ |
| Update scheme | In-place, cell by cell (TerraME `forEachCell`) | Synchronous, with one start-of-step snapshot shared by both models (TerraME `cell.past` semantics) | ⚠️ differences below |

## Known consequences

* **Order and ties.** The published scripts update cells in place in visiting
  order; this code is synchronous. Because the flux rule compares accumulated
  elevations with `≤` and many neighbours hold exactly equal values, results
  can differ from a sequential run by tie-breaking on ~1e-16 differences.
  Expect "same dynamics", not bit-identical `alt` after many flooding steps
  (README, *Flood scenario*).
* **Sea-level formula.** The thesis adds an increment to each sea cell's own
  water column; the code uses a single global level. In the published scripts
  the increment is `cell.Alt2 · Tx_elev`, which differs again. Which one is
  intended is not settled here.
* **Land-use / soil codes** follow the TerraME adaptation
  (`src/brmangue/common/constants.py`), not the codes of the 2013 script.
* **Rule IV is missing**, so mangrove loss under flooding is probably
  overestimated relative to the thesis whenever accretion would have allowed
  resistance.

Contributions that align a rule with the thesis are welcome; please cite the
page/equation and add a test in `tests/test_transition_rules.py`.
