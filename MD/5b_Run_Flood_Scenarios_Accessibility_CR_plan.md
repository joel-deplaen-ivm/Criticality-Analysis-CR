# Plan: `5b_Run_Flood_Scenarios_Accessibility_CR` — flood-scenario accessibility for Costa Rica

Source script: `src/5b_Run_Flood_Scenarios_Accessibility.py` (Serbia)
Current CR copy: `src/5b_Run_Flood_Scenarios_Accessibility_CR.py` — **byte-identical to Serbia** ✅
Target: `notebooks/5b_Run_Flood_Scenarios_Accessibility_CR.ipynb` (currently a 718-byte stub)
Upstream: [4a hazard registry](../notebooks/4a_Hazard_maps_CR.ipynb),
[5a hazard criticality](5a_Main_Network_Hazard_Criticality_CR_plan.md),
[3d hospital accessibility](../notebooks/3d_Baseline_Accesibility_Analysis-hospital_CR.ipynb)
Downstream: `5c_Plot_Flood_Scenarios_Accessibility_CR.ipynb` (still a verbatim Serbia copy)

Status: **built and run end to end on real data.**
`notebooks/5b_Run_Flood_Scenarios_Accessibility_CR.ipynb` is 29 cells and executes with
**0 errors, 0 unexecuted cells, 7 figures**, replacing the 718-byte stub. `src/` and `utils/` are
untouched.

Numbers marked ✅ were measured against the files on disk in `criticality2` on 2026-09-11.

## 0.0 Headline results ✅

`hybas_na_lev08` (22,533 basins continent-wide) yields **124 basins intersecting Costa Rica, 91
touching the network, and 65 holding at least one flood-exposed road — so 65 scenarios.** Median
basin 404 km² (min 14, max 2,284). Level 08 is comfortably the right level; the notebook's
"fewer than 10 scenarios" warning did not fire.

| | loc_nobuf | loc_buf50 | wp_nobuf | wp_buf50 |
|---|---|---|---|---|
| Population isolated (Σ over 65 scenarios) | **576,047** | 565,014 | 493,188 | 489,018 |
| Population affected | **1,449,052** | 1,426,986 | 1,500,121 | 1,490,501 |
| Person-hours added | **3,872,322** | 3,810,161 | 3,324,240 | 3,300,311 |
| Mean % affected per scenario | 0.4 % | 4.7 % | 0.4 % | 4.4 % |

Worst single scenario (`loc_nobuf`, hospitals): basin **7080054830** — 18 roads, 88.9 km, 183,222
people affected, 53,629 isolated, 410,827 person-hours added.

**The configuration matrix earned itself.** The origin set moves person-hours by 14 % (3.87 M vs
3.32 M) and the buffer moves it by 2 %; but the *percentage* columns move by an order of magnitude
(0.4 % vs 4.7 %), purely through the denominator. Quoting a percentage without naming the
configuration would be meaningless, which is why §4.4 forbids it.

87 of the 378 exposed roads span more than one basin and were assigned by majority length ✅ — the
measured size of the placement ambiguity that Serbia's "first intersecting basin" rule hides.

---

## 0. Scope decisions already taken

| | Decision | Consequence |
|---|---|---|
| **Where the code lives** | The CR logic goes in **`notebooks/5b_..._CR.ipynb`**. `src/5b_Run_Flood_Scenarios_Accessibility_CR.py` is **left as-is**, as a Serbia-derived reference. | Nothing in `src/` or `utils/` is edited. See §0.1 — this is viable on measured runtime, and it is a change of plan from "adjust the script", which is worth stating openly. |
| **Origins** | **Both, run as configurations**: `CENTROS_POBLACION/centros_poblados_localidades.shp` (493 localities, 5,167,278 people in `INEC_PROY` ✅) **and** the WorldPop 1 km grid (62,053 cells, 5,137,882 people ✅). | Localities match notebooks 2/2b and stay joinable to 2b's IDS quintiles on `CÓDIGO_DTA`; WorldPop matches 3d and halves the EBAIS degeneracy. Neither dominates — §3.2b, §4.2b. |
| **Population buffer** | **Both, run as configurations**: no buffer, and Serbia's 50 km buffer. | The buffer binds much harder in CR than it first appeared (§3.3) and costs nothing to carry (§3.3b). |
| **Sinks** | Two sectors: **hospitals** (`hospitales_cr.shp`, 27 geocoded ✅) and **EBAIS** (`ebais_cr.shp`, 949 ✅) | Replaces Serbia's five sectors. Factories, agriculture, police and firefighters have **no CR source** ✅. The EBAIS sector has a serious degeneracy problem — §3.2. |
| **Scenario unit** | **HydroBASINS `hybas_na_lev08`** — one scenario per level-08 basin. The file is being downloaded; it is not on disk yet. | Serbia used level 09 on a country 1.7× CR's area; lev08 is the deliberate coarsening. §4.2. |
| **Return period** | **RP100**, matching Serbia's single RP. | The other six return periods run as a sensitivity pass, not as separate scenarios — §3.1. |

**All decisions are now settled.** §5 records the ones whose defaults were proposed rather than
requested, because each of them changes every number in the output.

### 0.1 The reason the Serbia stub exists does not apply to CR ✅

The Serbia 5b notebook is a one-cell stub saying *"not implemented as notebook due to its long
runtime"*. That rationale does not survive the move to Costa Rica, and the measurement is decisive:

| Quantity | Measured ✅ |
|---|---|
| Graph | 3,909 vertices, 9,764 directed edges, single weak component |
| Origins | 493 localities → **485 distinct network vertices** |
| Sinks | 27 hospitals → 27 vertices; 949 EBAIS → **767 vertices** |
| Baseline OD, hospitals | (485 × 27) in **0.181 s** |
| Baseline OD, EBAIS | (485 × 767) in **0.230 s** |
| **One full damaged scenario** (graph copy + edge deletion + OD) | **0.236 s** |

So 500 scenarios × 2 sectors ≈ **4 minutes**, serial. The `ProcessPoolExecutor` in the Serbia
`main()` is unnecessary at this problem size, and the notebook is the right home. The stub's note
must be replaced, not preserved.

Serbia is slow because it samples a continental flood raster inline and runs five sectors over a
much larger settlement table. CR does neither: 4a already did the sampling (§2.2).

### 0.2 On installing `exactextract`

`exactextract` can be installed into `criticality2`, and that would make
`src/5b_Run_Flood_Scenarios_Accessibility_CR.py` *import*. It would not make it *run*, and it does
not change this plan. The import error is the first of about a dozen blockers, not the cause of the
others: the script would still need `hybas_eu_lev09_v1c.shp`, Serbian geocoded Excel files for five
sectors, and network columns CR does not have (`highway`, `bridge`, `osm_id`, and the per-cell
`values` lists) — see A1–A14.

More importantly, **5b should not be sampling rasters at all.** The
[5a plan settled that under D1](5a_Main_Network_Hazard_Criticality_CR_plan.md): sampling lives in
4a's registry, and every step downstream is a consumer. Installing `exactextract` so that 5b can
re-sample RP100 would re-introduce exactly the duplication that decision removed, and the two
samplers would be free to disagree.

**Install it if you want it available; just don't wire 5b to it.** There is one case where it would
genuinely earn its place, and it belongs in 4a rather than here: recovering **per-cell depth
distributions** along each road, which 4a's scalar reduction discards (I3). That would fix the "mean
of maxima" problem in the scenario depth statistics. Before relying on it for that, verify it on a
LineString — the 5a plan recorded that in `criticality_env`'s exactextract 0.3.0, **LineStrings
return empty for every operation** (`count` 0, `mean` NaN, both strategies) ✅, so a working build
has to be confirmed, not assumed.

---

## 1. What the Serbia script assumes, and whether it holds for CR

| # | Assumption | Where | Holds for CR? |
|---|---|---|---|
| A1 | The flood raster is **sampled inside 5b**, via `exactextract` / DamageScanner tiling | `get_exposure_values`, `create_grid` | **No.** 4a already sampled every hazard to every edge, and 5a D1 settled that sampling lives there. `exactextract` is also not installed in `criticality2` — the script raises `ModuleNotFoundError` at import today ✅ — but installing it does not revive this path; see §0.2. Drop the whole sampling path. |
| A2 | Road depths are corrected by a **hard-coded per-category elevation bias**, `{IA: 4.601, IM: 3.659, IB/IIA/IIB: 0.82}` m, keyed off OSM `highway` | `FINAL_BIAS`, `apply_road_elevation_correction` | **No.** CR roads carry no Z and there is no DEM ✅ ([5a plan A8/A9](5a_Main_Network_Hazard_Criticality_CR_plan.md)). CR also has no `highway` or `bridge` column — the network uses `CLASE` / `n_water_crossings`. Drop; 4a's `flood_depth_dem_corrected` / `flood_correction_applied` carry the CR equivalent. |
| A3 | Exposure thresholds are **0.1 m for roads, 0.5 m for bridges** | `main()` | **Inconsistent with the rest of the pipeline.** Serbia's own 5a uses 0.25 m; the 5a plan flagged this as A10. CR 5a settled on **> 0.25 m** (D2 there). Measured cost of the disagreement: at RP100, 0.1 m selects 766 edges / 4,868 km, 0.25 m selects 756 / 4,839 km ✅ — 10 edges. Small, but the pipeline must use one number. |
| A4 | A scenario is one **HydroBASINS level-09 basin** (`hybas_eu_lev09_v1c.shp`), and every exposed road in it fails together | `_get_river_basin`, scenario loop | **Concept ports, file and level do not.** No basin layer is on disk today ✅ (`vectoriales/` is empty); `hybas_na_lev08` is being obtained. The *scenario* idea — all exposed roads in one hydrological unit fail together — is kept unchanged. |
| A5 | Affected population is those within a **50 km buffer** of the basin, buffered in EPSG:3857 | scenario loop | **Partly — and more defensible than it first looked.** CR's population is concentrated in the Valle Central, so the median exposed road's 50 km buffer reaches only **5.8 %** of national population ✅ (§3.3): the filter binds hard rather than doing nothing. Kept as a configuration axis alongside no-buffer (D8), not dropped. The **EPSG:3857 buffering is simply wrong** at CR latitudes and is replaced by 8908, which is already metric. |
| A6 | Edges are removed by **`id`** — one directed edge at a time | scenario loop | **No.** CR removes the **`physical_edge_id` group**, both directions of one physical road (5,012 physical / 9,764 directed), per `CLAUDE.md` and notebook 2. Removing one direction only leaves the road passable the other way. |
| A7 | Removed edges are reported by **`osm_id`** | `save_new_results` | **No such column** in the CR network ✅. Use `physical_edge_id` (and `ID_TRAMO` / `NOMBRE` for readability). |
| A8 | Unreachable origins get a **flat 12-hour penalty**, hard-coded in `get_average_access_time` | `get_average_access_time` | **No.** CR uses `ISOLATION_PENALTY_FACTOR = 2.0` × the maximum baseline OD time, set in notebook 2 and reconstructed in 2b. `CLAUDE.md` requires this constant to match across notebooks. A flat 12 h would silently diverge from 2/2b. |
| A9 | Per-cell depth lists survive to the scenario loop as `base_network["values"]`, and min/mean/max are computed by flattening them | flood-statistics block | **No.** 4a reduces to **one scalar per edge per layer** and discards the distribution ([5a plan §4.0b](5a_Main_Network_Hazard_Criticality_CR_plan.md) names this as a known cost of the CR sampler). The per-scenario depth statistics must be computed from `flood_depth_rp*` scalars instead, and must be labelled as edge-level maxima, not cell values. |
| A10 | Results are **pickles** (`unique_scenarios_*.pkl`, `save_new_results_*.pkl`) plus a CSV, written under `accessibility_analysis/<sector>_criticality_results/` | both sector functions | **No.** CR convention is `intermediate_results/gpkg/<stage>/*.gpkg` with parquet caches under `intermediate_results/parquet/<stage>/`. Pickles of GeoDataFrames are not a durable interchange format and 5c would have to unpickle them. |
| A11 | Five sectors run in parallel with `ProcessPoolExecutor`, each pickling the full network and graph | `main()` | **Unnecessary** at CR size (§0.1) and actively harmful in a notebook. Run serial. |
| A12 | Each basin iteration is wrapped in a bare `except Exception` that writes a row of `None`s | both sector functions | **Do not port.** It converts a bug into a silently-empty scenario. CR should let failures raise, or collect them explicitly and print a reconciliation count at the end. |
| A13 | Population comes from a geocoded Excel of settlements with `latitude`/`longitude`/`Total` | `read_population_data` | **No.** CR uses `CENTROS_POBLACION` (already EPSG:8908, population in `INEC_PROY`) ✅. |
| A14 | Emergency sinks come from geocoded Excel files with an `i.d.` column | `load_and_map_sinks` | **No.** CR sinks are shapefiles keyed on `place_id` (hospitals, filtered to `estado == "OK"` and de-duplicated as in 3d) and on row identity for EBAIS. |
| A15 | `graph.connected_components().giant()` is taken and edges outside it are dropped | `create_graph_for_spatial_matching` | Mechanically fine — the CR graph is already a single weak component ✅, so nothing is dropped. But note this is the **weak** giant by default; reachability is still directional. |

**Net effect:** of the script's 20 top-level functions, roughly half exist only to sample a raster
that 4a has already sampled, or to load Serbian Excel files that have no CR counterpart. This is a
rewrite around a preserved core (the scenario loop), not an adjustment.

---

## 2. What CR actually has

### 2.1 Inputs, verified ✅

| Layer | File | Rows | Notes |
|---|---|---|---|
| Directed network | `gpkg/network/main_network_directed.gpkg` | 9,764 × 69 | EPSG:8908; `from_id`/`to_id`/`id`/`physical_edge_id`/`fft`/`road_length` |
| Hazard exposure (4a) | `gpkg/hazard_exposure/main_network_hazard_exposure.gpkg` | 9,764 × 41 | joins 1:1 on `id` |
| Localities | `input_files/CENTROS_POBLACION/…shp` | 493 | EPSG:8908, `INEC_PROY` = 5,167,278 |
| Hospitals | `input_files/salud/hospitales_cr.shp` | 27 | EPSG:4326, `estado`, `place_id`, `categoria` |
| EBAIS | `input_files/salud/ebais_cr.shp` | 949 | EPSG:4326 |
| Basins | `input_files/hybas_na_lev01-12_v1c/hybas_na_lev08_v1c.shp` | 22,533 | EPSG:4326; **124 intersect the CR network bbox, 91 touch the network** ✅; median basin 404 km² (min 14, max 2,284) ✅ |

### 2.2 The flood columns 4a already delivers

`flood_depth_rp10 … flood_depth_rp500` (seven return periods), `flood_min_rp`, `flood_rp_censored`,
`flood_aep`, `flood_share_gt0p25`, `flood_depth_implausible`, `max_at_crossing`,
`n_water_crossings`, `has_temporary_structure`, `road_freeboard_m`,
`flood_depth_dem_corrected`, `flood_correction_applied`.

5b opens no raster. It reads this GeoPackage and thresholds a column.

### 2.3 Exposure by return period, measured ✅

Whole network = 29,528 km, 9,764 edges, 5,012 physical roads.

| RP | edges > 0.25 m | physical roads | km | % network km |
|---|---|---|---|---|
| 10 | 688 | 344 | 4,536 | 15.4 % |
| 20 | 704 | 352 | 4,600 | 15.6 % |
| 50 | 722 | 361 | 4,654 | 15.8 % |
| 75 | 742 | 371 | 4,702 | 15.9 % |
| 100 | 756 | 378 | 4,839 | 16.4 % |
| 200 | 778 | 389 | 4,948 | 16.8 % |
| 500 | 796 | 398 | 5,041 | 17.1 % |

`flood_min_rp`: **688 of 796 ever-flooded edges (86 %) already flood at RP10** ✅; the other six
return periods share 108 edges.

---

## 3. Measured problems that shape the design

### 3.1 Return period is a weak scenario axis on its own ✅

Across RP10 → RP500 the exposed set moves from 688 to 796 edges and 4,536 to 5,041 km — a **1.7
percentage-point** change in network share. Seven "scenarios" built on return period alone would be
seven near-identical maps. This confirms and quantifies the correction already recorded in
[5a plan §4.4](5a_Main_Network_Hazard_Criticality_CR_plan.md).

**Consequence:** RP belongs in 5b as a *sensitivity axis over a fixed scenario definition*, not as
the scenario definition itself. The spatial partition (D1) is what creates distinguishable
scenarios; RP shifts them all slightly together.

### 3.2 The EBAIS sector is close to degenerate at this network resolution ✅

| | Hospitals | EBAIS |
|---|---|---|
| Points → distinct network vertices | 27 → **27** | 949 → **767** |
| Share of all 3,909 network nodes occupied by a sink | 0.7 % | **19.6 %** |
| Median nearest-facility time | **24.0 min** | **0.0 min** |
| Mean nearest-facility time | 30.5 min | 2.0 min |
| Localities at **exactly 0 min** | 3 / 493 (0.6 %) | **290 / 493 (58.8 %)** |
| Population share at 0 min | 1.6 % | **52.0 %** |

Nearly one in five network nodes has an EBAIS on it, and **52 % of the population is co-located with
its nearest EBAIS**. For those localities no road closure anywhere can change access time — the
result is structurally zero, not substantively zero. A disruption analysis over EBAIS therefore
reports on at most 48 % of the population, and its headline "share unaffected" will be dominated by
an artefact of snapping.

This does not mean dropping the sector, but it does mean:

- the EBAIS notebook section must **print the co-location share up front** and report all impact
  statistics over the non-degenerate subset as well as the whole;
- hospital access is the defensible headline; EBAIS is a secondary, caveated panel;
- the cause (§3.2b) must be carried **as a `# TODO-fix` comment at the point in the code where
  the EBAIS sinks are snapped**, not only in this document — see §4.1 cell 6.

### 3.2b Would the WorldPop grid fix it? Measured: it halves the problem, at a cost ✅

The obvious candidate fix is to swap the 493 localities for the WorldPop 1 km grid that 3d uses
(`cri_pd_2020_1km_UNadj_ASCII_XYZ.csv`, **62,053 populated cells, 5,137,882 people**, snapping to
**3,297 distinct vertices** of 3,909). Measured on both origin sets, same graph, same sinks:

| | Localities (493) | WorldPop grid (62,053) |
|---|---|---|
| **EBAIS — population at exactly 0 min** | **52.0 %** | **30.6 %** |
| EBAIS — pop-weighted median | 0.0 min | 1.3 min |
| EBAIS — pop-weighted mean | 1.2 min | 3.1 min |
| Hospitals — pop-weighted median | 10.5 min | 11.6 min |
| Hospitals — pop-weighted mean | 19.4 min | 21.6 min |
| Hospitals — population at 0 min | 1.6 % | 1.8 % |
| Origin snap distance, median / p90 / max | **247 m** / 1,425 m / 16.9 km | **2,712 m** / 8,850 m / **40.9 km** |

Three readings, in order of importance:

1. **It does not fix the degeneracy.** 30.6 % of the population still sits at exactly zero minutes
   from an EBAIS. The cause is sink density on the graph (767 of 3,909 nodes), which no choice of
   origin set can change. It is halved, not removed.
2. **It costs a much worse snapping profile.** Median origin-to-network distance rises from 247 m to
   **2.7 km**, because the grid covers the whole country including terrain far from the main
   network, while the localities sit on it by construction. Trading a known 52 % artefact for a
   30 % artefact plus a 2.7 km median snapping error is not obviously a gain.
3. **The hospital headline is robust to the choice**, which is the reassuring part: pop-weighted
   median 10.5 vs 11.6 min, mean 19.4 vs 21.6 ✅. The two origin sets measure the same thing for the
   sector that matters. (Note the *unweighted* cell median is 51.4 min for the grid against 24.0 min
   for localities — that is a median over 62,053 cells, in which an empty mountain cell counts the
   same as San José, and it is not comparable to the locality figure. Only population-weighted
   statistics may be compared across the two.)

**Decision (revised): run both, as configurations** (§4.2b). An earlier revision made localities the
primary set and relegated WorldPop to an optional robustness cell; the table above is too
double-edged for that — localities win decisively on snapping and on joinability to 2b's IDS
quintiles via `CÓDIGO_DTA`, WorldPop wins decisively on the EBAIS degeneracy, and neither dominates.

Running both costs 2.71 s vs 0.44 s per scenario ✅ (§4.2b), which at this problem size is not a
reason to choose. **Localities remain the reporting default** — headline figures quote `loc_nobuf`
unless stated — but every table carries all four configurations, so the reader sees the spread
rather than taking my word for which one mattered.

Sink snap distances are otherwise reasonable — hospitals median 337 m / max 1,555 m; EBAIS median
361 m but **max 27.3 km** ✅, so a handful of EBAIS are nowhere near the main network. Localities
snap at median 247 m, p90 1,425 m, max 16,873 m, with **6 beyond 5 km** ✅.

### 3.3 The 50 km buffer binds hard in CR — correcting an earlier claim in this plan ✅

An earlier revision of this document asserted that the 50 km buffer "covers most of the country" and
so "buys nothing", and recommended dropping it. **That was wrong**, and the measurement is the
reason the buffer is now a scenario axis (§4.2b) rather than a discarded constant.

The error was reasoning from CR's *area* (~51,100 km², ~120 km at its narrowest) instead of from the
*distribution of its population*, which is heavily concentrated in the Valle Central. A 50 km radius
drawn around a flood-exposed road in Limón or Guanacaste reaches very few people.

Measured over the **378 RP100-exposed physical roads** ✅ — for each road individually, the share of
national population within a buffer of it:

| Origin set | Radius | min | p10 | median | p90 | max | roads capturing > 90 % |
|---|---|---|---|---|---|---|---|
| Localities | 25 km | 0.1 % | 0.6 % | **1.6 %** | 4.1 % | 49.3 % | **0 %** |
| Localities | 50 km | 1.3 % | 2.7 % | **5.8 %** | 21.6 % | 66.9 % | **0 %** |
| WorldPop | 25 km | 0.2 % | 0.8 % | **1.7 %** | 4.0 % | 46.5 % | **0 %** |
| WorldPop | 50 km | 0.9 % | 3.0 % | **6.1 %** | 21.9 % | 64.2 % | **0 %** |

**Not one of the 378 roads captures 90 % of the population at 50 km**, and the median captures under
6 %. The buffer is therefore a strong filter, not a formality, and including or excluding it moves
every population-based ratio in the output.

**Two honest limits on this number.** First, the scenario unit is a *basin*, not a single road, and a
basin holding several dispersed exposed roads captures more than any one of them — so these figures
are a **lower bound** on per-basin capture, and the true value cannot be pinned until
`hybas_na_lev08` is on disk. The notebook must print the realised per-basin capture distribution
(§4.2 step 6). Second, the union of *all* exposed roads buffered at 50 km does reach 100 % of the
population ✅ — which is what the earlier claim was accidentally measuring, and it is the wrong unit.

A separate detail in the same code path, unaffected by any of this: Serbia buffers in EPSG:3857,
which is not metric at any real latitude. CR works in EPSG:8908, so distances are already metres.

### 3.3b The buffer is a reporting mask, not a model variant — so the factorial is cheap

Read directly from the Serbia source: `df_population` is subset to the buffer **before**
`get_distance_to_nearest_facility` is called, but that function routes each origin independently
through the graph. An origin's access time does not depend on which other origins are in the frame.

So the buffer changes **only** (a) which origins enter the summary and (b)
`InitialTotalPopulationPerBasin`, the denominator of `AffectedPopRatio`. It changes no travel time.

**Consequence for §4.2b:** compute each origin set **unbuffered, once**, then apply the buffer as a
post-hoc mask over the stored per-origin results. The 2 × 2 configuration matrix therefore costs
**2× the compute, not 4×** — the buffer axis is free.

### 3.4 Baseline connectivity is complete, so all "lost connections" are scenario-induced ✅

Baseline OD matrices to both hospital and EBAIS sinks contain **0 % infinities**. Every isolation in
the results is therefore caused by the scenario, not inherited from the network — a cleaner starting
point than Serbia's, and worth stating so the `Lost_Connections` counts are readable.

---

## 4. The plan

### 4.1 Shape

One notebook, serial, ~14 cells, in the idiom of 3d and 5a: a markdown header cell listing exact
inputs/outputs/steps (per `CLAUDE.md`), hard-coded paths near the top, no `NetworkConfig`.

```
1  markdown header: inputs, outputs, steps, caveats, the A21 framing sentence
2  imports + BASE_DIR + paths + constants (WORKING_EPSG, FLOOD_THRESHOLD_M,
   ISOLATION_PENALTY_FACTOR, SCENARIO_RP)
3  load network + 4a hazard exposure, assert 1:1 join on `id`, assert EPSG:8908
4  build igraph graph + node table  (reuse utils.accessibility_functions
   .create_graph_for_spatial_matching — imported, not modified)
5  load + snap BOTH origin sets (localities INEC_PROY; WorldPop 1 km cells);
   print snap-distance diagnostics for each -> the §3.2b table
6  load + snap sinks: hospitals (estado=="OK", dedup place_id) and EBAIS;
   print the §3.2 co-location diagnostic; carry the TODO-fix comment below
7  baseline OD: 2 origin sets x 2 sectors -> baseline nearest + average time
8  load hybas_na_lev08, clip to CR, assign each exposed physical road to a basin;
   build the scenario table; print selectivity (roads, km, % network) per basin
   AND the realised per-basin 50 km population capture (§4.2 step 6)
9  scenario loop (cached to parquet): per scenario x origin set x sector, delete
   the physical_edge_id groups, recompute OD, derive deltas.
   UNBUFFERED only -- the buffer is applied afterwards (§3.3b)
9b apply the 50 km mask to the stored results -> the buf50 configurations;
   no routing, no graph work
10 per-scenario depth statistics from flood_depth_rp* scalars (A9 caveat stated)
11 assemble scenario x config x sector summary table (4 configs, §4.2b)
11b RP sensitivity on loc_nobuf only (§4.2b)
12 write outputs (gpkg + parquet cache)
13 figures
14 reconciliation printout: scenarios attempted / completed / failed, edges removed
```

### 4.2 Scenario construction — settled

**One scenario per `hybas_na_lev08` basin**, every flood-exposed physical road in that basin removed
together, at **RP100**, depth **> 0.25 m**.

Serbia's equivalent is level 09 on `hybas_eu`, at RP100, threshold 0.1 m. Two deliberate departures:
the coarser basin level (CR is ~51,100 km² against Serbia's ~88,400, so lev09 would fragment the
country into many basins holding one or zero exposed roads), and the 0.25 m threshold that aligns
5b with 5a for the first time (D5).

**Placement rule.** Serbia's `_get_river_basin` takes the **first** basin a road's geometry
intersects — an arbitrary pick for any road crossing a basin boundary, and silently order-dependent.
For CR, assign each physical road to the basin containing the **greatest share of its length**, and
print how many roads span more than one basin so the size of the ambiguity is on the record rather
than hidden.

**Steps.**

1. Read `hybas_na_lev08`, clip to the dissolved CR outline, reproject to EPSG:8908.
2. **Report the basin count immediately** — total basins intersecting CR, and how many hold ≥ 1
   flood-exposed road. This is the first check that lev08 was the right level: if it yields fewer
   than ~10 scenarios the partition is too coarse and lev09 is the fallback; the cost of finding out
   is one cell. *(Cannot be predicted before the file is on disk — unverified.)*
3. Threshold `flood_depth_rp100 > 0.25` on the 4a exposure layer → **378 physical roads, 4,839 km,
   16.4 % of network length** ✅ (§2.3). Those are what get partitioned; the basin layer only decides
   how they are grouped.
4. Assign each exposed road to its majority-length basin; group to `scenario_id`.
5. **Materialise and save** the `scenario_id → physical_edge_id` mapping to
   `parquet/flood_scenarios/scenario_edges.parquet`, so 5c and any re-run consume the same partition
   without re-deriving it.

Because the partition is nothing but that mapping, swapping the scenario unit later (lev09, or
floodplain connected components — `rasterio` and `scipy` are both installed ✅) is a one-cell change.
Keep it that way.

6. **Print the realised per-basin buffer capture** — for each basin, the share of national population
   within 50 km of it. §3.3's per-road figures are only a lower bound; this is the real number and it
   decides how much the buffer axis matters.

**RP as sensitivity, not as scenarios.** The same basin partition is re-run at RP10…RP500 and
reported as one sensitivity figure (§4.7). §3.1 is the reason this is not seven scenario sets:
exposure moves only 15.4 % → 17.1 % of network length across the whole range ✅.

### 4.2b Configuration matrix — origins × buffer

Both of these were previously written as settled defaults (old D3, old D8). Both are now **run as
configurations**, because §3.2b and §3.3 show each one moves the results materially and neither has
an answer that is obviously right in advance.

|  | **No buffer** (all origins) | **50 km buffer** (Serbia's rule) |
|---|---|---|
| **Localities** (493, `INEC_PROY`) | `loc_nobuf` | `loc_buf50` |
| **WorldPop** (62,053 cells, 1 km) | `wp_nobuf` | `wp_buf50` |

Every scenario is evaluated under all four, for both sectors. Each output row carries a
**`config`** column taking one of those four values — never a default that has to be inferred.

**What each axis tests.** The origin axis asks whether the result is an artefact of representing
population as 493 settlement points; §3.2b already showed the hospital headline is robust to it
(pop-weighted median 10.5 vs 11.6 min ✅) but the EBAIS degeneracy is not (52.0 % vs 30.6 % at zero
✅). The buffer axis asks whether impact is being measured against a local or a national denominator
— which, per §3.3, is a large difference in CR and not the formality it first looked like.

**Cost, measured per scenario** ✅ (graph copy + edge deletion + full OD):

| Origin set | → hospitals (27 sinks) | → EBAIS (767 sinks) | per scenario, both sectors |
|---|---|---|---|
| Localities (485 source vertices) | 0.185 s | 0.251 s | **0.44 s** |
| WorldPop (3,297 source vertices) | 1.231 s | 1.483 s | **2.71 s** |
| | | | **3.15 s total** |

The buffer axis adds **nothing** to this, per §3.3b — it is a mask over results already computed. So
the whole matrix is ~3.15 s per basin: **~5 minutes for 100 basins, ~11 minutes for 200**, serial,
in a notebook. Still no case for `ProcessPoolExecutor`.

**The RP sensitivity pass runs on `loc_nobuf` only.** Seven return periods × the full matrix would be
28 configurations for a factor that moves exposure by 1.7 percentage points (§3.1). One arm is
enough to show the shape; say so rather than implying the sensitivity was run everywhere.

### 4.3 Constants to fix in cell 2, with their justification

| Constant | Value | Source |
|---|---|---|
| `WORKING_EPSG` | 8908 | `CLAUDE.md` |
| `FLOOD_THRESHOLD_M` | 0.25 | 5a D2 — inherited from Serbia's 5a, **not derived**; must be labelled as such (5a plan I6). Supersedes 5b-Serbia's 0.1/0.5 (A3). |
| `SCENARIO_RP` | 100 | Serbia's single RP; the other six run as sensitivity |
| `ISOLATION_PENALTY_FACTOR` | 2.0 | notebook 2 / 2b — `CLAUDE.md` requires these to match |
| `MAX_TRIPS`, `DIST_DECAY` | only if OD demand weighting is used | notebook 2 / 2b |

The isolation penalty replaces Serbia's flat 12 h (A8). The notebook must print the absolute penalty
value it resolves to, since it is derived from the baseline OD maximum rather than fixed.

### 4.3b The EBAIS `TODO-fix` comment

§3.2 is a property of the data that anyone reading the EBAIS numbers will misread unless it is
visible where the numbers are made. It goes in cell 6, at the EBAIS snapping call, verbatim:

```python
# TODO-fix: EBAIS access times are structurally degenerate on this network.
# The 949 EBAIS collapse onto 767 of the graph's 3,909 nodes (19.6%), so 58.8%
# of localities — 52.0% of the population — sit at exactly 0 min from their
# nearest EBAIS and NO road closure can change their access time. Measured
# 2026-09-11; see MD/5b_Run_Flood_Scenarios_Accessibility_CR_plan.md §3.2.
#
# Cause: routing runs on the 1b main network only, so origins and facilities
# both snap to the nearest main-network node and first/last-mile travel is
# invisible. Not fixable in 5b — it needs the full road network (cantonal and
# local roads), which is 1b's scope.
#
# Origin set does not fix it: the WorldPop 1 km grid (62,053 cells) halves it
# but leaves 30.6% of population at 0 min, and worsens origin snapping from a
# 247 m median to 2,712 m. Both sets are run as configurations (§4.2b) so the
# spread is visible rather than assumed away.
#
# Until fixed: report every EBAIS statistic twice — over all origins and over
# the non-co-located subset (203 of 493 localities). Hospitals (27 sinks, 0.7%
# of nodes) are unaffected and carry the headline.
```

The date matters: the comment states a measurement, and measurements go stale when 1b or the health
layers change.

### 4.4 Metrics per scenario × config × sector

At **origin level**, population-weighted (`INEC_PROY` for localities, cell population for WorldPop):

- `baseline_tt`, `scenario_tt`, `delta_tt` (nearest facility);
- `baseline_avg_tt`, `scenario_avg_tt` (average over all sinks — the Serbia `get_average_access_time`
  idea, kept);
- population unaffected / delayed / **isolated** (scenario time hits the isolation penalty);
- for EBAIS, all of the above **also** restricted to the non-co-located subset (203 of 493
  localities; the WorldPop equivalent is whatever cell count the run reports) — §3.2.

At **scenario level**: roads removed, km removed, % network km, min/mean/max flood depth over the
removed set (from `flood_depth_rp*` scalars, labelled per A9), population isolated, total
person-hours added, and the **basin's 50 km population capture** (§4.2 step 6).

Two rules that the configuration matrix makes non-negotiable:

1. **Every share is printed with its denominator**, per the discipline the 5a plan set in §3.4. Under
   `buf50` the denominator is the buffered population, under `nobuf` it is national — the same
   percentage means different things in the two columns, and §3.3 shows the gap is large.
2. **No table reports a single configuration silently.** Either all four `config` values are shown,
   or the one being quoted is named in the caption.

### 4.5 Caching

Per `CLAUDE.md`, the scenario loop writes a parquet cache and is skipped on re-run:
`intermediate_results/parquet/flood_scenarios/scenario_results_<origins>_<sector>_rp<RP>.parquet`.

The cache is keyed on the **origin set**, not on the config, because the buffered variants are
derived from the unbuffered results by masking (§3.3b) and must never be cached as if they were
separate computations — that is how the two would drift apart.

At ~3.15 s/scenario for the whole matrix ✅ the cache is a convenience rather than a necessity, but
the pattern is the repository's and should be kept.

### 4.6 Outputs

| File | Contents |
|---|---|
| `gpkg/travel_disruptions/flood_scenario_accessibility.gpkg` | layers `scenarios` (basin units + summary metrics, one row per scenario × config × sector) and `origins` (per-origin impact, long format) |
| `parquet/flood_scenarios/scenario_results_<origins>_<sector>_rp<RP>.parquet` | the cache and 5c's input |
| `parquet/flood_scenarios/scenario_edges.parquet` | the `scenario_id → physical_edge_id` partition |

Every row carries **`config`** (`loc_nobuf` / `loc_buf50` / `wp_nobuf` / `wp_buf50`), plus
`flood_correction_applied` and the RP and threshold used, so no consumer has to infer which regime
or which configuration produced a number — the reproducibility mitigation the 5a plan made mandatory
under its D6, extended to cover the configuration axis.

No pickles, no CSV-per-basin, no File GDB, no Excel (A10).

### 4.7 Figures → `figures/`

- `flood_scenario_worst_basins.png` — the scenario units ranked by population isolated, under
  `loc_nobuf`, with the other three configurations as faint overlaid series so the spread is on the
  same axes rather than in a different figure;
- `flood_scenario_access_delta_map.png` — origin-level Δ access time for the worst scenario;
- `flood_scenario_config_spread.png` — **new**: the same headline metric under all four
  configurations (§4.2b). This is the figure that earns the factorial: it shows whether the origin
  set or the buffer is doing more of the work, which §3.2b and §3.3 say could plausibly be either;
- `flood_scenario_rp_sensitivity.png` — the headline metric across RP10…RP500 on `loc_nobuf`, which
  is where §3.1's finding (that RP barely moves exposure) becomes visible rather than buried;
- `flood_scenario_hospital_vs_ebais.png` — the two sectors side by side, with the EBAIS panel
  carrying the co-location caveat in its caption.

### 4.8 The framing sentence

Same as 5a §4.10, and it must be in the header cell: **this is not risk.** A scenario removes every
flood-exposed road in a unit with certainty. There is no fragility curve, no closure probability and
no duration. "Population isolated by the X flood scenario" means "population isolated if every road
in X that intersects the RP100 floodplain above 0.25 m were simultaneously impassable".

---

## 5. Decisions

### 5.1 Two kinds of decision, and why the distinction is kept

`CLAUDE.md` requires that when I proceed without asking, I state the assumption I made — in the
response *and* in the code where it takes effect. This section is that statement. It separates:

- **Requested (✔R)** — you chose it. I implement it.
- **Assumed (✔A)** — I picked the default, because there is a defensible right answer and blocking
  on it would have stalled the plan. Each one is reversible by changing one constant, but **each one
  silently changes every number in the output**, so none of them may be left implicit. If you
  disagree with any, say so and the numbers move; say nothing and the plan proceeds as written, with
  the assumption recorded in the notebook at the line where it takes effect.

The distinction is not bureaucratic. An assumed default that nobody ever reviews becomes an
undocumented model choice six months later — which is precisely what Serbia's un-derived 0.82 m
elevation bias and un-justified 0.1 m threshold became. The point of writing them down as
*assumptions* is that they stay visible until someone either ratifies or overrides them.

### 5.2 The decisions

| # | Decision | Status |
|---|---|---|
| **D1** ✔R | Scenario unit | **`hybas_na_lev08`**, one scenario per basin. Level 08, not Serbia's 09, because CR is 1.7× smaller (§4.2). Re-check after the count is printed (step 2 of §4.2). |
| **D2** ✔R | Code location | Notebook; `src/5b_..._CR.py` untouched. Justified on measured runtime (§0.1). |
| **D3** ✔R | Origins | **Both, as configurations** — `CENTROS_POBLACION` (493 localities, `INEC_PROY`) and WorldPop (62,053 cells). Localities are the reporting default; every table carries both (§3.2b, §4.2b). |
| **D4** ✔R | Sinks | Hospitals + EBAIS, two sectors, §3.2 caveat on every EBAIS number, `TODO-fix` in code (§4.3b). |
| **D5** ✔R | Return period | **RP100**. RP10–RP500 run as sensitivity, not as scenarios (§3.1). |
| **D6** ✔A | Exposure threshold | **> 0.25 m**, adopted from 5a D2 and overriding Serbia-5b's 0.1 m / 0.5 m. **Why assumed:** 5a and 5b currently disagree with each other (A3) and one number has to win; 0.25 m is the one the CR pipeline already uses. **What it costs:** at RP100, 0.25 m selects 756 edges / 4,839 km against 0.1 m's 766 / 4,868 ✅ — 10 edges, so the choice is cheap here but must not be made twice. **Caveat that travels with it:** 0.25 m is inherited from Serbia and derived nowhere (5a I6). |
| **D7** ✔A | Removal granularity | **`physical_edge_id` group** — both directions of one physical road. **Why assumed:** `CLAUDE.md` mandates it and notebook 2's SPOF already works this way. **What it costs:** Serbia removes single directed edges by `id`, which leaves the road passable the other way; matching Serbia would make CR's 5b disagree with CR's own 2. Changes every number relative to a literal Serbia port. |
| **D8** ✔R | 50 km buffer | **Both, as configurations** — `nobuf` and `buf50` (§4.2b). **Supersedes an earlier ✔A that dropped the buffer**, on the strength of the §3.3 measurement: the median exposed road's 50 km buffer reaches only 5.8 % of the population ✅, so the buffer binds hard and the earlier reasoning was wrong. Costs no extra compute (§3.3b). |
| **D9** ✔A | Isolation penalty | **`ISOLATION_PENALTY_FACTOR = 2.0` × max baseline OD**, replacing Serbia's flat 12 h. **Why assumed:** `CLAUDE.md` requires this constant to match notebooks 2 and 2b; a flat 12 h would make 5b's isolation cost incommensurable with the criticality results it sits beside. **What it costs:** every "person-hours added" figure scales with it, and it is derived at runtime rather than fixed, so the notebook must print the absolute value it resolves to (§4.3). |

**Nothing blocks the build** once `hybas_na_lev08` is on disk. D6, D7 and D9 remain live assumptions:
ratify them, override them, or leave them and they stand as recorded. D3 and D8 are no longer
assumptions at all — they are axes of the output, which is the more honest resolution where the
evidence genuinely pointed both ways.

### 5.3 Why these two became configurations rather than decisions

Worth stating, because it is a judgement about when to run a factorial rather than choose.

A configuration is warranted when (a) the alternatives are defensible on different grounds, (b) the
choice moves the results materially, and (c) running both is cheap. All three hold here: localities
beat WorldPop on snapping and joinability while WorldPop halves the EBAIS degeneracy (a); the buffer
changes every population denominator and the origin set changes the EBAIS result by 21 percentage
points (b); and the whole matrix costs 3.15 s/scenario because the buffer axis is free (c).

Where any of the three fails, a configuration is just indecision with a `config` column. D6's 0.25 m
threshold is the counter-example: 5a already settled it, and running 0.1 m alongside would move 10
edges ✅ while quietly reopening a question the pipeline has answered. That stays a decision.

---

## 6. Issues

### 6.1 Blocking

| # | Issue |
|---|---|
| ~~I1~~ | ~~`hybas_na_lev08` is not on disk~~ — **Resolved.** Landed at `input_files/hybas_na_lev01-12_v1c/hybas_na_lev08_v1c.shp`; 65 scenarios ✅, level 08 confirmed appropriate (§0.0). Nothing blocks the notebook. |

### 6.1b Deviations from this plan made during implementation

| Where | Deviation | Why |
|---|---|---|
| §4.1 cell 4 | **`utils.accessibility_functions.create_graph_for_spatial_matching` is not used.** The notebook builds its own lean graph. | The utils helper attaches *every* column, geometry included, as an igraph edge attribute. The scenario loop copies the graph once per basin, so that would be very expensive. The notebook uses notebook 2's `GRAPH_EDGE_ATTRS` list instead. `utils/` is untouched. |
| §4.1 cell 5 | **`utils…nearest_network_nodes` is not used**; snapping is vectorised through one `STRtree.nearest` call. | The utils version applies row-wise and is unusably slow on the 62,053-cell WorldPop grid. `utils/` is untouched. |
| §4.3 | **One isolation penalty for the whole notebook**, derived from the largest baseline across all four arms (**7 h** ✅), rather than one per arm. | A per-arm penalty would make the four configurations incomparable, which defeats the point of running them. Still follows notebook 2's rule — isolation must cost more than the longest legitimate journey. |
| §4.6 | Per-origin detail is saved for **affected origins only**, not all origins × all scenarios. | Storing every origin for every scenario is millions of rows of mostly zeros; the summary table already carries the population totals. |
| §4.4 | Added a **buffer-bite diagnostic** (§6.2 I11). | Not in the plan; added because the test run showed the buffer columns can be identical, and that needs saying rather than inferring. |

### 6.2 Non-blocking, must be recorded

| # | Issue |
|---|---|
| I2 | **EBAIS co-location (§3.2) is caused by routing on the main network only.** 3d already records this caveat: localities and facilities snap to the nearest main-network node, so first/last-mile travel is invisible. With 767 EBAIS vertices out of 3,909 it stops being a caveat and becomes the dominant effect. Measured, not asserted: swapping to the WorldPop grid halves it (52.0 % → 30.6 % of population at 0 min) but does not remove it ✅ (§3.2b), confirming the cause is sink density on the graph, not the origin set. Fixing it needs the full road network (cantonal and local roads), which is out of 1b's scope. Carried in code as a `TODO-fix` (§4.3b). |
| I3 | **Only reductions are saved, so scenario depth statistics are a mean of maxima** — `depth_mean_of_max_m` is the unweighted mean over exposed roads of each road's deepest sampled point, not a mean of cell depths. **Correction to an earlier wording here:** this is *not* a limitation of 4a's sampler. `RoadSample` retains the full per-vertex distribution and already exposes `.max()`, a length-weighted `.mean()` and `.share_above()`; the loss happens at the **save boundary**, where only scalars reach the GeoPackage. Recovering a distribution-based statistic is therefore a new reduction in 4a's registry, not a rewrite. |
| I3b | **`depth_*` statistics are unweighted by road length** — a 200 m road counts the same as a 20 km one. Measured across the 65 basins ✅: length-weighting moves the median basin mean 3.03 → 2.83 m and the worst basin 11.88 → **16.18 m**, max discrepancy 6.4 m. These columns are reported, never computed on, so nothing downstream is wrong — but any depth quoted from them should be the length-weighted version. One-line change; `road_length` is already on the frame. |
| I4 | **The 0.25 m threshold is inherited, not derived** (5a I6, D6 here). Carried into 5b unchanged; must be labelled "inherited, not derived" rather than implying a source. |
| I5 | **Two population bases coexist across the pipeline**: 3d uses the WorldPop 1 km grid, 2/2b use the 493 localities. 5b now runs both (D3), which closes the gap for 5b itself but not for the pipeline — pop-weighted hospital median 10.5 vs 11.6 min ✅. **Unweighted** figures across the two are not comparable at all (§3.2b) and the header must say so. Note also that only the locality arm carries `CÓDIGO_DTA`, so a 5d quintile crossing can use `loc_*` configurations only. |
| I6 | **6 localities snap more than 5 km to the network**, max 16.9 km ✅; **EBAIS max snap is 27.3 km** ✅. These should be listed by name, not just counted. |
| I7 | **Scenario independence.** Each unit floods alone; a regional event spanning several units is never represented. Inherited from Serbia (5a A22/A23). |
| I8 | **`flood_min_rp` is highly skewed** — 86 % of ever-flooded edges first flood at RP10 ✅. Any RP-banded presentation will be dominated by that group. |
| I9 | **`5c_Plot_Flood_Scenarios_Accessibility_CR.ipynb` is still a verbatim Serbia copy** and expects the pickle/CSV outputs this plan drops. It will need its own pass once 5b's output schema is fixed. |
| I10 | **The CR notebooks are untracked in git** — 5b's notebook, like 4a/2b/5a/5c/5d, has no history. Worth committing before the first run for record. |
| I11 | **The 50 km buffer discards a little real impact — resolved on real data** ✅. **617 of 66,035 affected origin-rows (0.9 %) fall outside the buffer**, carrying 22,066 people in the locality arm. So the buffer is not merely a denominator choice, and `nobuf` is the safer default — which is what the notebook's §9 diagnostic prints. **This reverses the synthetic-basin result** (0 rows outside), confirming that the synthetic test could not settle the question and was right to be marked unverified. |
| I12 | **RP75, RP100 and RP200 give identical impact totals** ✅ — 400,945 delayed / 470,151 isolated / 3,172,673 person-hours at all three. Confirmed on real data, not an artefact of the synthetic basins: the roads added between those return periods change no origin's connectivity. This is §3.1's finding in its sharpest form and is a result, not a defect. |
| I13 | **`mean_delta_min` / `max_delta_min` are NaN, not 0, when every affected origin is fully isolated** — 176 of 780 rows in the first real run. Fixed during implementation; an earlier build returned 0.0, which read as "no delay" next to a large `pop_isolated`. Any consumer of the parquet must treat NaN here as "undefined", not "zero". |
| I15 | **`buffer_pop_share_wp` was NaN on all 390 `loc` rows** in an earlier build — the scenario-metadata dict was mutated inside the origin loop, so the `wp` key did not exist when the `loc` rows were emitted. A mechanical artefact, not a missing measurement. **Fixed**: both shares are resolved before the loop. Headline totals were unaffected (hospitals `loc_nobuf` 1,449,052 affected / 3,872,322 person-hours before and after ✅). Worth recording because a half-NaN column is the kind of thing a downstream consumer silently drops rows on. |
| I14 | **`ebais` and `ebais_noncolocated` necessarily share the same numerators** ✅ — an origin co-located with an EBAIS has a 0 min baseline and can never be affected, so the subset changes only the denominator (5,167,278 → 2,478,455). This is not redundancy: it is the cleanest possible statement that the flattering EBAIS "share unaffected" is an artefact of co-location. The notebook prints this in §9. |

---

## 7. Out of scope

- Re-running 4a or re-sampling any raster. 5b is a pure consumer of `main_network_hazard_exposure.gpkg`.
- Re-running the SPOF percolation from notebook 2.
- Any fragility, damage or closure-duration modelling (§4.8).
- Editing `src/5b_Run_Flood_Scenarios_Accessibility_CR.py`, the Serbia `src/5b_*.py`,
  `src/config/network_config.py`, `src/simplify.py`, or any function in `utils/` (D2).
  `utils/accessibility_functions.py` is **imported** where useful — `create_graph_for_spatial_matching`,
  `nearest_network_nodes` — never modified.
- Extending the network beyond 1b's main-network scope, which is what I2 would require.
