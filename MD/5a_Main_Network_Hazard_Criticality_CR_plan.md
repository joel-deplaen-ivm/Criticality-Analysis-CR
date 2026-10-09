# Plan: `5a_Main_Network_Hazard_Criticality_CR` — criticality × CR hazard layers

Source notebook: `notebooks/5a_Main_Network_Hazard_Criticality.ipynb` (Serbia)
Target notebook: `notebooks/5a_Main_Network_Hazard_Criticality_CR.ipynb`
Upstream: [4a hazard registry](../notebooks/4a_Hazard_maps_CR.ipynb),
[2 criticality](2_Main_Network_Criticality_Analysis_CR_plan.md),
[2b socioeconomic](2b_Socioeconomic_Criticality_CR_plan.md)

Status: **built and run.** Both notebooks execute clean end to end (0 errors, 0 unexecuted cells ✅).

- `notebooks/4a_Hazard_maps_CR.ipynb` — 38 cells; carries the D1/D2/D5/D6 sampling work and writes
  `gpkg/hazard_exposure/main_network_hazard_exposure.gpkg`, 9,764 edges × 41 columns ✅.
- `notebooks/5a_Main_Network_Hazard_Criticality_CR.ipynb` — **rewritten from scratch** in 4a's
  idiom, 22 cells, replacing the byte-identical Serbia copy. Writes
  `gpkg/travel_disruptions/main_network_hazard_criticality.gpkg` with layers `physical`
  (5,012 × 45) and `directed` (9,764 × 81), EPSG:8908, no road dropped ✅.

Headline crossing results (physical-road level, 14,811 km network ✅):

| Hazard | Roads | km | % length | % VHL | Lift |
|---|---|---|---|---|---|
| Flood RP100 > 0.25 m | 378 | 2,420 | 16.3 % | 26.6 % | **1.63** |
| Landslide LHASA ≥ 4 | 1,764 | 7,972 | 53.8 % | 42.3 % | **0.79** |
| Rx1month ≥ 750 mm | 1,448 | 6,110 | 41.3 % | 33.8 % | 0.82 |
| ≥ 1 water crossing | 1,036 | 4,839 | 32.7 % | 40.1 % | 1.23 (TKL **1.98**) |

130 roads isolate when closed (578 km); 35 of them are flood-exposed, 71 landslide-exposed ✅.

**Landslide exposure has lift below 1** — landslide-prone roads carry *less* traffic than their
length share, because susceptibility concentrates on low-volume mountain roads. Flood and bridges
run the other way. This is the substantive CR finding and it inverts the intuition that the most
hazardous roads are the most critical ones.

Numbers marked ✅ were measured against the files on disk during this planning pass. Everything
else is a proposal.

---

## 1. Assumptions baked into the Serbia original

These are the things the notebook asserts rather than derives. Each one has to be either ported,
replaced or dropped, and most of them do not survive the move to Costa Rica.

### 1.1 Network and geometry

| # | Assumption | Where | Holds for CR? |
|---|---|---|---|
| A1 | The criticality result set is **incomplete**, so baseline road sections missing from it are appended with **zero-filled metrics** and still assessed for hazard exposure | `merge_baseline_roads` | **No.** CR notebook 2 returns all 9,764 directed edges and all 5,012 physical roads ✅ — nothing to backfill. Drop the step. |
| A2 | Sections outside core Serbia (Kosovo) are excluded by a Natural Earth `SOV_A3` overlay | `merge_baseline_roads` | **No.** No disputed territory; 4a already clips to the dissolved IDS district outline. Drop. |
| A3 | `oznaka_deo` is the road-section identity, and several graph segments share one | `deduplicate_by_section` | **Partly.** CR's analogue is `physical_edge_id` (5,012 physical roads from 9,764 directed edges ✅), with `ID_TRAMO` (4,407 distinct ✅) one level coarser. The concept ports; the column name and the collapse ratio do not. |
| A4 | Within a section, identity/traffic attributes come from the **longest** segment, `road_length` is **summed**, and every disruption metric is aggregated with **max** (worst case) | `deduplicate_by_section` | Portable, but in CR this collapse is already done upstream: `physical_criticality_results.gpkg` is the deduplicated product of notebook 2. Re-doing it in 5a would double-aggregate. |
| A5 | The output CRS is **EPSG:6316** and results are mirrored to parquet + File GDB + Excel | `save_criticality_vector` | **No.** CR convention is a single GeoPackage in **EPSG:8908** under `intermediate_results/gpkg/<stage>/`. |

### 1.2 Flood

| # | Assumption | Holds for CR? |
|---|---|---|
| A6 | A road is flooded if **any** sampled cell exceeds **0.25 m** — an arbitrary trafficability threshold, never justified in the notebook, and applied to a single RP100 layer | Threshold is portable but arbitrary; the single-RP restriction is a real loss in CR, where **all seven JRC return periods (RP10–RP500) are on disk and share one grid** (3841×4201, EPSG:4326, 0.000833° ≈ 90 m ✅). |
| A7 | Exposure is reduced along the road with **`max`** — one deep pixel condemns the whole section | **Actively harmful in CR.** See §3.1: measured length bias, point-biserial r = 0.25 between edge length and flood exposure (p ≈ 2e-143 ✅). |
| A8 | The flood grid systematically **over-floods roads because roads sit on embankments the DEM does not resolve**, and this can be corrected by subtracting a per-category elevation bias derived from surveyed road Z minus DEM | The *diagnosis* is right and applies to CR. The *method* does not port: CR road geometries carry **no Z** (`shapely.has_z` = False on `cr_red_topografica.shp` ✅) and **no DEM exists in `input_files/`** ✅. |
| A9 | The bias is a **fixed dictionary of five constants** — `{IA: 4.601, IM: 3.659, IB/IIA/IIB: 0.82}` m — hard-coded in `utils/criticality_functions.py`, so the notebook's own elevation-bias section (cells 5–11) is **diagnostic only and does not feed the number that is applied** | Worth flagging even for Serbia. The 0.82 m shared by three categories is not derived anywhere in the notebook. Subtracting **4.6 m** from a modelled depth is a very large correction to carry as a literal. |
| A10 | Corrected depth is clipped at 0 and any road with `corrected_max_depth > 0` counts as flood-exposed — note this is `> 0`, **not** the 0.25 m of A6, so the two definitions of "flooded" in one notebook disagree | Do not port the inconsistency. |

### 1.3 The other four hazards

| # | Assumption | Holds for CR? |
|---|---|---|
| A11 | **Snow drift** is a hazard, joined from surveyed drift locations, and its magnitude is drift length (`dužina_sn`) | **No.** Costa Rica has no snow. Drop the hazard entirely. |
| A12 | **Landslides** are *observed occurrences* (`tip == 'Klizište'`), buffered 10 m, so exposure is a record of what has happened | **No — and this is a conceptual change, not a data swap.** CR uses NASA LHASA *susceptibility* (classes 0–5), a modelled propensity, not an inventory. An inventory has recall bias (roads are surveyed, forests are not); a susceptibility grid has none but also no confirmation. Statements about landslide exposure are not comparable between the two countries. |
| A13 | The 10 m landslide buffer is a proxy for "close enough to affect the road" | Not applicable; LHASA is a ~925 m raster, so the equivalent question is which cell the road samples, already settled in 4a. |
| A14 | **Wildfire** exposure is binary — *any* susceptibility class > 0 counts, collapsing a graded raster to yes/no | **No CR wildfire raster exists** in `input_files/` ✅. Drop, or source one. Note the binary collapse would be a poor choice to copy in any case. |
| A15 | **Heat** is the max *future* pavement temperature from a UHI-adjusted raster (step 4c), thresholded at **60 °C**, with `all_touched=True` zonal statistics | **No CR equivalent**: `4c_Temperature.ipynb` was never adapted and no CR temperature raster exists ✅. `all_touched=True` also inflates exposure by design. Drop. |
| A16 | **Future precipitation** is an RCP 8.5 change field thresholded at **≥ 10 % change** | **No CR climate-projection data.** CHIRPS is *observed* 2000–2025 only. 4a is explicit that the Rx1month trend is **not significant** and sets `TREND_AS_HAZARD = False`. There is no CR layer that answers this question. Drop. |

### 1.4 The multi-hazard count

| # | Assumption | Holds for CR? |
|---|---|---|
| A17 | Six hazards are counted with **equal weight** — a road under 3 m of water and a road 1 σ wetter than normal each contribute exactly 1 | Portable mechanically, indefensible substantively, and much worse in CR where only **two** of the four available layers are hazards at all (§4.1). |
| A18 | Each hazard's binary threshold is chosen independently, so the count's meaning depends on how selective each threshold happens to be | Measured for CR in §3.2: under 4a's thresholds only **3.9 % of network length is hazard-free** ✅ and 49 % sits at exactly 2. The count carries almost no information. |
| A19 | A section counts as exposed if **any** of its segments is (max aggregation after dedup) | Portable. |
| A20 | Segments exposed to **no** hazard are dropped from the saved output (`.any(axis=1)` filter in `combine_hazard_exposure`) | Do not port. It makes the saved layer unusable as a denominator, and 5d then scores a set that has already been filtered. Keep all 9,764 edges and carry explicit zero/False flags. |

### 1.5 Cross-cutting

- **A21 — "Exposure" is treated as "impact".** Nothing in 5a models what a flood or landslide *does*
  to a road. VHL/PHL/TKL are the *full-closure* losses from notebook 2's percolation, reported for
  the subset of roads that intersect a hazard footprint. The notebook's figures read as "vehicle
  hours lost to floods"; the quantity is actually "vehicle hours that would be lost if this road,
  which happens to intersect a floodplain, were closed". No fragility curve, no depth-damage
  relationship, no closure probability. This is the single most important thing to state
  explicitly in the CR version — it is a **hazard-screened criticality**, not a risk estimate.
- **A22 — Hazards are independent.** Flood and landslide are both rainfall-driven and will
  co-occur; the count treats them as separate draws.
- **A23 — The network is static under hazard.** Roads are screened one at a time (SPOF), so a
  regional flood closing twenty roads simultaneously is never represented.

---

## 2. What CR actually has

### 2.1 Ready, verified, 1:1 joinable ✅

| Layer | File | Rows | Key |
|---|---|---|---|
| Directed criticality | `gpkg/travel_disruptions/criticality_results.gpkg` | 9,764 | `id` |
| Physical criticality | `gpkg/travel_disruptions/physical_criticality_results.gpkg` | 5,012 | `physical_edge_id` |
| Socioeconomic criticality | `gpkg/travel_disruptions/socioeconomic_criticality.gpkg` | 5,012 | `physical_edge_id` |
| **Hazard exposure (4a)** | `gpkg/hazard_exposure/main_network_hazard_exposure.gpkg` | 9,764 | `id`, `physical_edge_id` |

Join keys verified identical: `id` sets match exactly, `physical_edge_id` sets match exactly ✅.
Metrics available: `vhl, vkl, phl, thl, pkl, tkl`, plus `pct_isolated / pct_unaffected /
pct_delayed` and both disruption averages. 259 edges have `pct_isolated > 0` ✅.

**The decisive structural difference from Serbia: 4a already did the raster sampling.** The Serbia
5a spends most of its length calling DamageScanner and `zonal_stats` inline. In CR that work is
done, registry-driven and vectorised, one cell upstream. CR 5a should **join, cross-tabulate and
map** — it should not open a raster unless it is adding a layer 4a does not have (§4.2).

Hazard columns delivered by 4a, as shares of the 29,528 km network ✅:

| Layer | Distribution by length |
|---|---|
| `flood` (JRC RP100 depth) | No flooding 83.5 % · <0.5 m 0.3 % · 0.5–1 m 4.2 % · 1–2 m 1.6 % · **>2 m 10.4 %** |
| `landslide` (LHASA 0–5) | Very low 4.4 % · Low 23.7 % · Moderate 17.8 % · High 16.9 % · Very high 37.1 % |
| `precip_anomaly` (2025 vs 2000–24, σ) | Drier 1.6 % · Near normal 17.0 % · Wetter 14.2 % · **Much wetter 66.7 %** |
| `precip_rx1month` (20-yr RL) | Low 24.0 % · Moderate 33.4 % · High 29.6 % · Very high 12.5 % |

### 2.2 On disk but unused

- **`flood_hazard_jrc/` holds seven return periods** (RP10, 20, 50, 75, 100, 200, 500), all on one
  grid ✅. 4a samples RP100 only.
- **`CR_RVN_ESTRUCTURAS_V2/`** — 1,962 structures, of which **1,778 cross water**
  (RIO 1,092 · QUEBRADA 620 · CANAL 52 · ESTERO 14) ✅. Bridges and culverts at water crossings are
  the classic CR road-failure point and are the nearest CR analogue to Serbia's point-hazard joins.
- **`cr_red_topografica.shp` attributes**: `SUPERFICIE` (unpaved `N` on 1,301 of 4,764 roads ✅),
  `REDUNDANCI` (no redundancy on 983 ✅), `rep_cost_k` (present on 2,880 ✅).
- `vul_f` and `vul_eq` are **100 % null** on both the road and structure layers ✅ — the schema
  suggests flood and earthquake vulnerability were intended but never populated. Do not plan around
  them.

### 2.3 Absent

No DEM · no road Z · no wildfire raster · no temperature raster · no seismic raster · no climate
projections · no snow. Five of Serbia's six hazards have no CR counterpart.

---

## 3. Measured problems with the 4a hazard columns as a basis for 5a

These are the reason 5a needs more than a column rename.

### 3.1 The flood layer is length-biased and physically implausible ✅

- 770 edges are flood-exposed — 7.9 % of edges but **16.5 % of length** (4,869 km).
- Mean depth on exposed edges **3.63 m**, median 2.51 m, **max 30.71 m**.
- Exposed edges average **6.32 km** against a network mean of **3.02 km**.
- Point-biserial correlation between edge length and flood exposure: **r = 0.25, p ≈ 1.7e-143**.
- The deepest values sit on the longest edges — Ruta Nacional 2 at 12.8 km (30.7 m) and 27.1 km
  (24.0 m).

This is `stat="max"` doing exactly what it is asked to: a 27 km edge that crosses one river channel
inherits the channel's depth over its whole length. A 30 m fluvial depth is a river cross-section,
not a road surface. **10.4 % of the national road network reported under >2 m in a 1-in-100 event
is not a credible headline** and would propagate straight into 5d's H sub-index.

Measured directly by re-sampling the JRC RP100 grid with length weights ✅: of the 768 edges the
0.25 m rule calls flooded, the **median is actually under >0.25 m on only 13.9 % of its length**,
and **330 of them (43.0 %) are wet on less than a tenth of their length**. `max` is reporting a
point property as a line property.

**Correction — the bridge-deck explanation does not hold.** An earlier draft of this plan cited
"48.6 % of flood-exposed length lies within 50 m of a mapped water-crossing structure" as
corroboration that the model was flagging bridge decks. That statistic is true but was
misinterpreted: it counts whole edges that *pass near* a crossing, which a road over a river
naturally does, and says nothing about where the deep cells driving `max` sit.

The quantity that matters was measured during implementation ✅: of the flood-exposed edges, the
**deepest sampled point lies within 50 m of a water crossing on only 8.3 %**. Masking those cells
moves exposure from 762 to 756 edges and from 4,845 km to 4,839 km — **0.1 % of exposed length** —
and leaves the 30.7 m maximum untouched. Even a 200 m radius only reaches 704 edges / 4,702 km.

So the RP100 over-estimate is **floodplain, not bridge deck**: these roads run *through* modelled
inundation rather than merely crossing it at a structure. The correction that would actually move
these numbers is the DEM/freeboard one (D6) — precisely the input CR does not yet have. The mask is
kept per D5, is right in principle and costs nothing, but it is **not load-bearing** and no result
may be presented as though it were.

### 3.2 The multi-hazard count as currently thresholded is uninformative ✅

Under 4a's own `exposed_if` rules (flood > 0 · landslide ≥ 3 · anomaly ≥ 1 σ · Rx1month ≥ 750 mm),
share of network length by hazard count:

| Hazards | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| Share of length | **3.9 %** | 22.4 % | **49.0 %** | 21.9 % | 2.8 % |

Individually: landslide ≥ 3 catches **5,376 of 9,764 edges**, anomaly ≥ 1 σ catches **7,693** ✅.
An indicator that flags 79 % of the network is not discriminating anything. Thresholds have to be
re-set against the CR distributions before any count is meaningful.

### 3.3 One of the four layers is not a hazard

`precip_anomaly` is *observed 2025 relative to 2000–2024*. 4a says so plainly. A wet 2025 is a
description of one year, not a recurrence probability, and it is not commensurate with an RP100
flood depth or a 20-year return level. It belongs in the notebook as context, **not** as a term in
a hazard count or in 5d's H index.

### 3.4 Criticality is already concentrated on exposed roads

Flood-exposed edges carry **26.6 %** of total network VHL; landslide ≥ 3 edges carry **59.1 %** ✅.
Because exposure is so widespread (§3.2), these shares mostly reflect how much of the network each
threshold selects, not a meaningful concentration of criticality on hazardous roads. Every such
number in the CR notebook needs its length share printed beside it as the denominator.

---

## 4. The plan

### 4.0 Scope split between 4a and 5a

Sampling lives in 4a. Two of the fixes below (a better reduction statistic, the multi-RP stack) are
sampling changes, so the honest home for them is 4a's registry. Recommendation:

- **4a** gains: length-aware flood reduction (§4.3), the multi-RP flood stack (§4.4), the bridge
  layer (§4.2). One `HazardLayer` entry each — that is what the registry is for.
- **5a** consumes 4a's GeoPackage and does the criticality crossing, scoring and mapping. It opens
  no raster.

**Settled (D1): the fixes go in 4a's registry and 4a is re-run.** 5a stays a pure consumer and opens
no raster. Re-run cost is the ~4 min permutation test; everything else is seconds.

### 4.0b Sampling: DamageScanner is **not** used on the CR side

This has to be stated in the notebook itself, because a reader coming from the Serbia pipeline will
expect it and its absence would otherwise look like an oversight.

**What Serbia uses.** `DamageScanner(...).exposure(asset_type="roads")` → `VectorExposure` →
`_overlay_raster_vector` → `exactextract.exact_extract(hazard, geoms, ["coverage", "values"])`.
DamageScanner samples nothing itself; it is a wrapper. exactextract computes the true geometric
intersection of each feature with each grid cell and returns **two parallel lists per feature** —
one raster value and one overlap measure per intersected cell. The hazard bbox is cut into tiles
(0.5° geographic / 50 km metric), one `exact_extract` call runs per tile, and `_remove_duplicates`
re-concatenates the lists for features spanning tiles. Where the hazard CRS is not metric,
`_convert_to_meters` converts each per-cell coverage by interpolating that distance along the line
from its first vertex and taking the geodesic length.

**What CR uses.** `4a.sample_raster_to_roads`: densify each road to half the raster resolution with
`shapely.segmentize`, convert vertex coordinates through the inverse affine transform, and
groupby-reduce to **one scalar per road** with the layer's declared `stat`.

**Measured differences** (JRC RP100 grid, whole CR network, against a 2.3 m near-exact reference) ✅:

| | Result |
|---|---|
| Cells touched | 4a 390,506 vs reference 407,628 — **4a misses 4.2 %** (road clips a cell corner with no vertex inside) |
| Effect on `max` | differs on **54 of 9,764 edges (0.6 %)**; median error 0.000 m, p99 0.000 m, one outlier where 4a missed a 29 m cell |
| Effect on a length-share | length-weighted share at 4a's res/2 spacing matches the reference to within **0.005** |

So for the `max` reduction that D2 settles on, exactextract's exactness buys **0.6 % of edges**. The
difference that sounds most important is the least important one.

**The differences that do matter, and why the choice stands:**

1. **Scalar vs distribution — and it is the CR side that is lossy.** DamageScanner returns every
   cell value along the road; 4a reduces on the spot and discards the rest. That means a
   share-above-threshold, a quantile, or a multi-RP exceedance **cannot be recovered from 4a's
   saved GeoPackage** and must be added inside the sampler. This is the concrete reason D1 puts the
   work in 4a. It is a real cost of the CR design and should be named as such, not glossed.
2. **Derived layers.** `HazardLayer.source` is typed `Path | Callable[[], Raster]`, because two CR
   hazards (the CHIRPS anomaly, the GEV return level) are computed in-notebook as numpy arrays, not
   read from disk. DamageScanner expects an xarray/rasterio hazard object, so each derived grid
   would need wrapping. The affine lookup handles both identically.
3. **Explicit nodata.** 4a declares nodata semantics per layer (`nodata_as=0.0` for flood, because
   outside a JRC floodplain means dry; `None` for landslide, because there it means unknown).
   DamageScanner has no equivalent — Serbia relies on the raster being a `filled_depth` product.
4. **Failure modes.** DamageScanner's tile loop wraps each tile in `except Exception` and continues;
   roads in a failed tile return empty lists and, under `return_full=False` (what Serbia uses), are
   **dropped from the result and read as unexposed**, with no input/output reconciliation. 4a prints
   `sampled: N/9764` and the exposed count per layer, and out-of-grid vertices become explicit NaN.
5. **Dependencies.** `criticality2` has no `damagescanner`, `xarray`, `rioxarray` or `rasterstats`.
   Because `utils/criticality_functions.py` imports `xarray` at module level (line 24), the Serbia
   5a's **first code cell fails at import** in the CR kernel ✅.
6. **Line support in the installed build.** In `criticality_env`'s exactextract 0.3.0, LineStrings
   return empty for *every* operation (`count` 0, `mean` NaN, `cell_id` empty, both strategies) ✅.
   The Serbia notebook's stored output shows 1,322 features returned when it was run, so some other
   build supported lines — but that path is not reproducible here today.

**Not recorded anywhere.** `4a_Hazard_maps_CR.ipynb` is untracked in git, so there is no commit
message or diff explaining the original choice, and nothing in `MD/` discusses it. Note also that
Serbia's own `4a` never used DamageScanner either — it appears only in `1b`, `5a` and `5b`. CR's 4a
did not *replace* DamageScanner; it moved road-level sampling forward into a step that never had a
sampler. Points 1–4 above are the case for keeping the current arrangement on its merits; points
5–6 are circumstantial.

**When to revisit.** Adopt exactextract if a future hazard needs true partial-cell area weighting
(a polygon-based hazard, or a coarse grid where 4.2 % missed cells matters), or if per-cell
distributions are wanted for their own sake. That would mean adding the four packages to
`criticality2` and pinning an exactextract with linear-geometry support — verify on a line before
relying on it.

### 4.0c Extensibility — adding hazards later

The registry is the extension point and must stay that way. **Adding a hazard is one
`HazardLayer(...)` entry in 4a and one row in 5a's reporting loop — no other cell changes.** Any
work done under this plan that breaks that property is a regression.

Candidates already anticipated, none currently possible for lack of data:

| Candidate | What it needs | Note |
|---|---|---|
| Seismic PGA | a CR ground-motion raster (e.g. a 475-year PGA grid) | CR is highly seismic; 4a already carries a commented-out placeholder entry for exactly this |
| Wildfire | a CR susceptibility raster | Serbia's binary "any class > 0" collapse should **not** be copied — use the graded classes |
| Pavement heat | a CR temperature raster; `4c_Temperature.ipynb` was never adapted | |
| Climate projections | CORDEX/CMIP downscaled precipitation for CR | would restore the "future change" axis that A16 currently has no CR source for |
| Road-surface modifier | already on disk: `SUPERFICIE` unpaved on 1,301 of 4,764 roads ✅ | a vulnerability modifier rather than a hazard — keep the distinction explicit |

New hazards should declare `stat`, `breaks`, `class_labels`, `nodata_as` and `exposed_if`
deliberately rather than copying a neighbour's, and each addition must print its own selectivity
(share of network length flagged), per §4.5.

### 4.1 Hazard set for CR

| Serbia | CR |
|---|---|
| Flood (RP100, bias-corrected) | **Flood** — multi-RP exceedance, `max` > 0.25 m per D2, length share as diagnostic (§4.3–4.4) |
| Landslide (observed inventory) | **Landslide** — LHASA susceptibility as a graded 0–5 ordinal score per D3, not a binary flag (§4.5) |
| Snow drift | *dropped* — no snow |
| Wildfire | *dropped* — no CR raster |
| Pavement heat | *dropped* — no CR raster |
| Future precipitation (RCP 8.5) | *dropped* — no CR projections |
| — | **Rx1month 20-yr return level** — rainfall-intensity hazard (probabilistic, so commensurate) |
| — | **Water-crossing structures** — proposed, §4.2 |
| — | `precip_anomaly` — **context panel only, not a hazard** (§3.3) |

So: **two established hazards, one rainfall-intensity proxy, one optional structural hazard.** The
CR notebook must not pretend to Serbia's six.

### 4.2 New CR hazard: water-crossing structures

1,778 bridges/culverts over RIO/QUEBRADA/CANAL/ESTERO ✅. Per physical road: count of water
crossings, and a flag for crossings of the temporary/low-capacity types visible in `TIP_ESTR`
(`Cercha media altura - Tipo Bailey temporal`, 155 ✅; `Alcantarilla`, 162 ✅). This is a point-hazard
spatial join — structurally the same operation as Serbia's snow-drift and landslide joins, so the
notebook keeps a familiar shape while the content becomes Costa Rican.

**Settled (D5): both roles, as two clearly separate columns.** A bridge is simultaneously a
**vulnerability** (single point of failure, scour, the Bailey-temporary stock) and a **protection**
(deck above the design flood). Both readings are legitimate and both are used here, so they must
never share a column or a caption:

| Column | Role | Meaning |
|---|---|---|
| `n_water_crossings`, `has_temporary_structure` | **vulnerability** | the road depends on N structures over water; failure of any one severs it |
| `flood_bridge_masked` (bool) + the masked depth columns | **protection** | flood vertices within the mask radius were excluded before reducing, because the deck sits above the water |

Every figure and table using one must say which. **Measured size of the protection role: small.**
Masking at 50 m moves flood exposure by 6 edges / 6 km ✅ (§3.1) — the mask is correct in principle
and kept, but it is not what makes the flood layer over-estimate. §4.8's figure therefore reports
*where the mask can reach* (the 8.3 % of exposed edges whose deepest point is at a crossing) rather
than a before/after pair of near-identical maps.

### 4.3 Replacing the elevation-bias correction

Serbia's method needs road Z and a DEM. CR has neither today ✅, so it cannot be ported now — see
*DEM and road Z* below for how the path is kept open. In its place, three measures, in the order I
would apply them:

1. **Report the length share as a diagnostic** — but keep `max` as the exposure rule.

   **Settled (D2): exposure stays Serbia's rule — depth > 0.25 m anywhere on the edge.** The
   length bias measured in §3.1 is therefore carried deliberately, for continuity with the Serbia
   pipeline. The consequence has to travel with every headline number: when 5a reports
   "*N* km flood-exposed", that is the length of edges that touch >0.25 m somewhere, and the
   median such edge is wet on 13.9 % of itself ✅.

   Because the rule is `max`, and **`max` is invariant to how vertices are weighted**, the
   length-weighting work below is *not* required to implement it. `flood_share_gt25` is still worth
   computing and saving as a **reported diagnostic column** — it costs one array on a pass that is
   already running, and it is what lets the headline number be sanity-checked rather than argued
   about. It does not enter the exposure flag. *(Assumption made in the absence of a decision; say
   so and it comes out.)*

   **Where weighting does still matter.** 4a's `sample_raster_to_roads` densifies
   with `shapely.segmentize`, which *adds* vertices without removing existing ones, and the CR
   geometries are already far denser than the sampling step: median **153 original vertices per
   edge**, and **91.6 % of edges already carry vertices closer than the 46 m step** ✅, so
   densification is nearly a no-op. Vertex spacing therefore varies with road sinuosity — the
   median edge is sampled 3.7× denser than uniform, the p99 edge 29× — and
   **corr(vertex count, road length) is only 0.64** ✅. A share-of-vertices statistic is therefore
   not a share-of-length statistic.

   Measured on the flood grid over the 762 edges the D2 rule flags ✅, both quantities being
   fractions of an edge so the difference is in percentage points of length: mean absolute
   difference **0.035**, **p99 0.21**, max 0.30. Worst case is edge 9686 — 1.80 km, 233 sample
   points at 7.7 m mean spacing — where vertex-share reads 0.738 against a true length-share of
   0.439.

   **The error is scatter, not a directional bias.** Mean *signed* difference is −0.0064; vertex-share
   runs high on 346 edges and low on 404; and the national flooded length comes out 851 km by
   vertex-weighting vs 882 km by length-weighting — agreement to 3.5 % ✅. So the weighting matters
   when **individual edges are ranked, thresholded or mapped** by their flooded share, and hardly at
   all for national totals. That is precisely the per-edge use the diagnostic column above is for,
   which is why it should be length-weighted even though nothing else depends on it.

   Weighting each vertex by half the distance to each neighbour fixes it exactly — length-share at
   4a's existing res/2 spacing matches a 2.3 m reference sampling to within **0.005** ✅. So the fix
   costs one extra array, and no new library.

   This also affects the two layers 4a **already** reduces with `stat="mean"`: `precip_rx1month` and
   `precip_anomaly` are currently vertex-weighted means. The practical effect is small because both
   grids are coarse (median difference 0, but tails of −38/+55 mm on Rx1month, and 24 edges cross
   the 750 mm exposure threshold when reweighted; the 5.5 km anomaly grid moves 12 edges) ✅ — worth
   fixing while the sampler is open, not worth a separate pass.
2. **Mask bridge decks.** Drop flood vertices within `BRIDGE_MASK_M` of a water-crossing structure
   before reducing. **Measured effect: 762 → 756 exposed edges, 4,845 → 4,839 km ✅** — 0.1 % of
   exposed length, maximum depth unchanged. Implemented per D5 and correct in principle, but it is
   a rounding error against the problem in §3.1, not a fix for it. Reported honestly in 4a §7c.
3. **Sanity cap.** Depths above a stated ceiling are river cross-sections, not road inundation.
   Flag rather than silently clip.

#### DEM and road Z — in scope, at a later stage

**Settled (D6): yes, but later.** The elevation question is the *right* question — A8's diagnosis is
sound, and §3.1's bridge-deck finding is the same effect seen from another angle. Neither input
exists today ✅, so nothing in the current build depends on them, but the code is written now so that
enabling the path later is a data drop, not a re-derivation.

**Settled (D5, second part): the depth correction runs when road Z and a DEM are both present, and
is skipped when either is `None`.** The branch is therefore gated on *data availability*, not on a
hand-set switch:

- **DEM** — Copernicus GLO-30 and ALOS AW3D30 both cover CR at 30 m. Dropped under
  `input_files/dem/`, it enters as an ordinary registry entry (`stat="mean"`, road-relative
  elevation).
- **Road Z** — `cr_red_topografica.shp` carries none today, but the schema could gain it (the layer
  is named *topográfica*, and `CR_RVN_TOPOGRAFICA_V3` exists) or a surveyed subset could arrive. The
  sampler must not assume 2-D geometry: read Z where present (`shapely.has_z`), ignore it where
  absent, never fail on either.
- **Additive, never destructive.** The correction writes `flood_depth_dem_corrected` **beside** the
  uncorrected `flood_value`, never over it, so before/after stays visible and every earlier number
  remains reconstructible.

**Reproducibility hazard this creates — must be handled, not just noted.** Gating on data
availability means the same notebook and the same code produce different flood numbers depending on
what happens to be sitting in `input_files/`. Two people, two answers, no diff to explain it.
Required mitigations, all cheap:

1. The notebook **prints which path it took** at the point of decision — DEM found / not found,
   road Z present / absent, correction applied / skipped.
2. The saved layer carries an explicit **`flood_correction_applied` boolean column**, so any
   downstream consumer can tell which regime produced a row.
3. The plan and the notebook header record that flood columns are **regime-dependent**, and that
   comparing runs across regimes is invalid.

Without these three, D6 silently converts a reproducible pipeline into an unreproducible one. With
them, the gate is a feature.

**Explicitly not recommended in any scenario:** a CR analogue of the hard-coded per-category offset
(A9) — `{IA: 4.601, IM: 3.659, IB/IIA/IIB: 0.82}`. Even with both a DEM and road Z, the honest
construction is a derived road-relative elevation, computed and shown, not five literals. And note
that a DEM alone does not reproduce Serbia's method: that method is *measured Z minus DEM*, so
without road Z the Serbia derivation stays unavailable no matter which DEM is obtained.

### 4.4 Multi-RP flood exceedance (the biggest available gain)

All seven JRC grids are aligned ✅, so per edge: the **smallest return period at which the settled
D2 rule fires** — i.e. max depth > 0.25 m anywhere on the edge — as `flood_min_rp`, plus max depth
at each RP. Applying the same rule across all seven grids generalises D2 rather than competing with
it: same threshold, same reduction, seven probabilities instead of one. That converts a binary
RP100 flag into an **annual exceedance probability** — a road first flooded at RP10 (10 %/yr) is
plainly worse than one first flooded at RP500 (0.2 %/yr), and the current layer cannot tell them
apart. It also gives 5b/5c a real scenario axis and 5d a continuous, well-behaved hazard term in
place of `future_flood_return_period`, which has no CR source.

**Measured result — the gain is real but smaller than this section claimed** ✅. Of 796 edges ever
flooded at any return period, **688 (86 %) already flood at RP10**; the remaining six return periods
share 108 edges. Exposure by length moves only 15.4 % → 17.1 % across RP10 → RP500. So CR's
flood-exposed roads are overwhelmingly *frequently* flooded rather than marginal, and the exceedance
axis separates a large frequent group from a small rare one rather than spreading roads smoothly
over probabilities. That is a substantive finding about the network, not a defect — but calling
multi-RP "the biggest available gain" overstated it, and any scoring that assumes a well-spread
`flood_aep` will be dominated by the RP10 group.

### 4.5 Re-calibrated exposure thresholds

Set each threshold against its CR distribution, and print the length share every threshold selects
next to it so the selectivity is visible (§3.2, §3.4).

**Settled (D3): landslide enters as the graded LHASA class 0–5, not a binary flag.** Every binary cut
is too inclusive to discriminate — `≥ 3` (Moderate+) selects 55 % of edges, `≥ 4` selects 54 % of
length, and even Very high alone is 37.1 % ✅. `landslide_value` is used as an ordinal score
throughout, and `exposed_if` on that layer becomes a reporting convenience only, never an input to
the combined score (§4.7).

Consequence to carry forward: the notebook then has **one binary hazard (flood, per D2) and one
graded hazard (landslide)**, so any cross-tab that puts them side by side must say which is which.
The multi-hazard count in §4.7 cannot mix them without a stated banding of the landslide score.

### 4.6 Criticality × hazard crossing — the analytical core

For each hazard, at the **physical road** level (5,012 rows — the level 2b and 5d already work at):

- exposed roads, exposed km, and **share of network length** (the denominator, always shown);
- total and share of `vhl, vkl, phl, thl, pkl, tkl` on exposed roads;
- the isolation subset (`pct_isolated > 0`, 259 edges ✅) crossed with each hazard — roads that both
  disconnect places *and* sit in a hazard footprint are the operational headline.

**Settled (D4): the IDS quintile crossing does *not* live in 5a — it moves to 5d.** 5a produces the
hazard × criticality table; the socioeconomic attribution is applied downstream. `socioeconomic_criticality.gpkg`
is therefore **not** read here, and no quintile figure is produced (§4.8).

Two consequences to carry forward:

- 5a's output must stay joinable on `physical_edge_id` so 5d can attach 2b's quintile attribution
  without re-deriving anything. That is already the design (§4.9 keeps all 5,012 physical roads), so
  D4 costs nothing structurally — but it becomes a hard requirement rather than a convenience.
- **The quintile analysis is deferred, not merely relocated.** It now sits behind **I14**: five of
  the seven metrics in 5d's `_HAZARD_METRICS` have no CR source ✅, so 5d cannot run on CR output
  until those lists are rewritten. Nothing is wasted — 2b's attribution already exists on the same
  key — but the equity result arrives later than it would have inside 5a.

### 4.7 Multi-hazard scoring

Replace the equal-weight count (A17–A18) with a **graded score**: each hazard contributes its own
class (0–4 for flood by RP band, 0–5 for LHASA, 0–3 for Rx1month), normalised, then combined. Keep a
binary count alongside it **only** as a descriptive cross-tab, with each threshold's length share
printed. `precip_anomaly` stays out of both.

### 4.8 Figures

| Serbia | CR |
|---|---|
| `elevation_profiles_by_category.png`, `elevation_bias_by_category.png` | *dropped* — no Z, no DEM |
| `flood_exposure_correction.png` | **kept, re-purposed and moved to 4a §7c** — a before/after pair would be two near-identical maps (6 edges differ ✅). It instead maps flood-exposed roads split by whether the deepest point sits at a water crossing (8.3 %) or in open floodplain (91.7 %) — i.e. what the mask can and cannot reach. |
| — | **new**: `flood_length_share.png` — exposed length under the D2 rule vs length actually >0.25 m, the diagnostic that keeps §3.1 visible |
| — | **new**: `bridge_water_crossings.png` — structures as *vulnerability* (§4.2), explicitly captioned as the opposite role to the mask |
| `vehicle_hours_lost_map_flooded.png` | kept — VHL on flood-exposed roads |
| `vhl/phl/tkl_hazards_comparison.png` (2×2: flood/snow/landslide/wildfire) | **2×2 → 1×3**: flood, landslide, Rx1month |
| `hazard_count_map` | replaced by the graded score map (§4.7) |
| — | **new**: `flood_min_rp` map (§4.4) — exceedance probability, not a binary |
| — | *IDS quintile figure* — **not in 5a** (D4); produced in 5d once I14 is resolved |

Basemaps in Web Mercator, everything else EPSG:8908, per project convention.

### 4.9 Output

`intermediate_results/gpkg/hazard_exposure/main_network_hazard_criticality.gpkg`, EPSG:8908,
**all 9,764 directed edges and all 5,012 physical roads retained** — no `.any(axis=1)` drop (A20).
No parquet mirror, no File GDB, no Excel: that is the Serbia scheme.

### 4.10 The framing sentence

The notebook's opening markdown cell must state A21 in plain words: this is **criticality screened
by hazard exposure**, not risk. No fragility curve, no closure probability, no expected annual loss.
Every "VHL due to floods" label is really "VHL of roads that intersect the RP100 floodplain".

---

## 5. Decisions needed before building

| # | Decision | Options | Leaning |
|---|---|---|---|
| **D1** ✔ | Where do the sampling fixes live? | **Settled: extend 4a's registry and re-run 4a.** 5a stays a pure consumer. Re-run cost is the ~4 min permutation test; everything else is seconds. |
| **D2** ✔ | Flood trafficability rule | **Settled: Serbia's rule — depth > 0.25 m anywhere on the edge**, chosen for continuity with the Serbia pipeline. The length bias in §3.1 is accepted knowingly; §4.3 records how it must be reported. |
| **D3** ✔ | Landslide: binary or graded? | **Settled: graded LHASA class 0–5 as an ordinal score**, no binary flag in the combined score. |
| **D4** ✔ | Does 5a carry the IDS quintile crossing, or is that left to 5d? | **Settled: no — it moves to 5d.** 5a does not read `socioeconomic_criticality.gpkg` and produces no quintile figure; its output stays joinable on `physical_edge_id` (§4.6). Defers the equity result behind I14. |
| **D5** ✔ | Bridge structures: hazard, flood mask, or both? | **Settled: both, as two clearly separate columns** (§4.2) — `n_water_crossings` / `has_temporary_structure` for vulnerability, `flood_bridge_masked` + masked depths for protection. **Plus:** keep the depth correction, applied when road Z and a DEM are both non-`None`, skipped otherwise. |
| **D6** ✔ | Is a DEM in scope? | **Settled: yes, at a later stage.** Not needed for the current build; the branch is written now and gated on data availability per D5, so enabling it is a data drop, not a re-derivation. §4.3 records the three reproducibility mitigations this gating makes mandatory. |

**All six decisions are settled — nothing in §5 blocks the build.**

---

## 6. Issues still to be addressed

Distinct from §5: those are decisions awaiting an answer, these are things that are simply not
resolved yet. Grouped by whether they block building 5a.

### 6.1 Blocking — must be settled before or during the build

| # | Issue | Why it blocks |
|---|---|---|
| ~~I1~~ | ~~D5 undecided~~ | **Resolved.** D5 settled: both roles, two columns, mask applied. 4a can be re-run once |
| ~~I1b~~ | ~~Bridge-mask radius must be fixed first~~ | **Resolved, and downgraded.** Set to 50 m; 4a §7c reports 0 / 25 / 50 / 100 / 200 m. The radius barely matters — 200 m still only reaches 704 of 762 edges ✅ — so it is no longer a blocking choice |
| I1c | **D6's regime gating needs its three mitigations written into 4a now** | §4.3 requires the path printout, the `flood_correction_applied` column, and the header note. If the gate ships without them, flood columns silently become regime-dependent and cross-run comparison breaks. Cheap now, expensive to retrofit once outputs exist |
| I2 | **The sanity ceiling in §4.3 item 3 has no number** | The 30.71 m maximum ✅ is unquestionably a river cross-section, but no threshold is defined for "implausible as road inundation". Needs a stated value and a rule (flag, not clip) |
| I3 | **`flood_min_rp` censoring convention undefined** | Edges never flooded at RP500 need an explicit sentinel and a documented meaning ("> 500 yr", not a missing value or a large number that will be averaged) |
| I4 | **Landslide banding for the combined score** | D3 settled the graded 0–5 score, but §4.7 mixes it with a binary flood flag. The banding that makes them commensurable is not yet specified — this is the direct consequence of D3 flagged in §4.5 |
| I5 | **Reporting level not fixed per output** | §4.6 says physical-road level (5,012), but VHL/PHL are computed per directed edge and summed. Each table and figure must state which level it is at; mixing them silently double-counts |

### 6.2 Non-blocking — build can proceed, but these must be recorded

| # | Issue | Status |
|---|---|---|
| I6 | **The 0.25 m trafficability threshold has no stated justification** | Inherited from Serbia, where it is also unjustified (A6). D2 adopted it for continuity, which is a legitimate reason — but the notebook must say "inherited, not derived", not imply a source |
| I7 | **LHASA susceptibility cannot be validated for CR** | No CR landslide inventory in `input_files/` ✅. A12 records that susceptibility and inventory are different quantities; there is currently no way to check LHASA against observed CR failures |
| I8 | **The bridge-mask radius is uncalibrated** | Still true, but now known to be low-stakes: the sensitivity table in 4a §7c shows exposure is nearly flat in the radius ✅. Kept on the list because the *principle* of masking decks is untested against any CR observation |
| I9 | **Rx1month substitutes for Rx1day** | 4a's own recorded assumption; carries into 5a unchanged. A wet month of moderate days and a wet month with one extreme day score identically. Fixable only by obtaining daily CHIRPS |
| I10 | **A21 — exposure is not impact** | By design, not a defect, but it is the single most misreadable property of the output. §4.10 requires it in the header; every figure caption needs it too |
| I11 | **A22/A23 — hazard independence and static network** | Structural limits inherited from the SPOF design. Out of scope to fix (§7), in scope to state |

### 6.3 Repository and pipeline hygiene — outside 5a but affecting it

| # | Issue | Detail |
|---|---|---|
| I12 | **`CLAUDE.md` is stale on the 4a environment** | It states `4a_Hazard_maps_CR.ipynb` "still runs on `criticality_env`", but the notebook's kernelspec says `criticality2`, and everything it imports is available there ✅. One of the two is wrong; likely the doc |
| I13 | **The CR notebooks are untracked in git** | `4a`, `2b`, `5a`–`5d` CR all show as `??` ✅. No history, no diffs, no commit messages — which is why the DamageScanner rationale could not be recovered (§4.0b). Worth committing before the 4a re-run so the change is reviewable |
| I14 | **5d's metric lists have no CR source** | `_HAZARD_METRICS` in `utils/criticality_functions.py` names `future_rainfall_change`, `future_flood_change`, `max_pavement_temp`, `wildfire_susceptibility`, `snow_drift` — **five of seven have no CR data** ✅. 5d cannot run on CR output until they are rewritten. **Escalated by D4**: the IDS quintile crossing now lives in 5d, so this blocks the equity result, not just the combined index |
| I15 | **5b, 5c, 5d CR are still verbatim Serbia copies** | Confirmed byte-identical ✅. The multi-RP work in §4.4 is what would give 5b/5c a real CR scenario axis, so sequencing matters |
| I16 | **4a re-run invalidates downstream artefacts** | Re-running 4a rewrites `main_network_hazard_exposure.gpkg`. Anything already derived from it needs regenerating; currently nothing is, but that will stop being true once 5a exists |
| I17 | **Two edges violate flood monotonicity** | 2 of 9,764 edges show depth *falling* as the return period rises ✅ — the JRC grids disagree with each other there. Tiny, but it means `flood_min_rp` is not guaranteed well-defined on every edge. Reported by 4a §7a on every run |
| I18 | **`flood_min_rp` is highly skewed** | 86 % of ever-flooded edges first flood at RP10 ✅ (§4.4). Any quintile or min-max scoring of `flood_aep` in 5d will be driven by that one group; consider banding by return period rather than scoring the continuous value |

---

## 7. Out of scope

- Re-running the SPOF percolation. 5a reads notebook 2's results; it never recomputes them.
- Any fragility or damage modelling (A21). That is a different notebook.
- Correlated / multi-road hazard events (A23).
- Touching the Serbia `5a_Main_Network_Hazard_Criticality.ipynb` or the Serbia-facing helpers in
  `utils/criticality_functions.py`. CR-specific logic belongs in `src/network_preparation_cr.py`
  or in the notebook.
