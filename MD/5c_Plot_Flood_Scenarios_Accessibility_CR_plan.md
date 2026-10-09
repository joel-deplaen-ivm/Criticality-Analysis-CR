# Plan: `5c_Plot_Flood_Scenarios_Accessibility_CR` — per-road flood-scenario impacts for Costa Rica

Source notebook: `notebooks/5c_Plot_Flood_Scenarios_Accessibility.ipynb` (Serbia)
Current CR copy: `notebooks/5c_Plot_Flood_Scenarios_Accessibility_CR.ipynb` — **18 cells, verbatim Serbia,
kernel `criticality_env`** ✅ (only the filename differs)
Upstream: [5b flood-scenario accessibility](5b_Run_Flood_Scenarios_Accessibility_CR_plan.md) —
built, run, outputs on disk ✅
Downstream: `notebooks/5d_Combined_Climate_Criticality_CR.ipynb` (still a verbatim Serbia copy)

Status: **built and run end to end on real data.**
`notebooks/5c_Plot_Flood_Scenarios_Accessibility_CR.ipynb` is 18 cells on the `criticality2` kernel
and executes with **0 errors, 0 unexecuted cells, 4 figures** ✅, replacing the verbatim Serbia copy.
`src/` and `utils/` are untouched. Deviations made during implementation are in §6.1b.

Every number marked ✅ was measured — against the 5b outputs on 2026-09-11, and against the notebook's
own run on 2026-09-15.

---

## 0. Headline

Serbia's 5c does two jobs, and only one of them is plotting.

1. It **turns basin-scenario results into a per-road layer** — each flood-exposed edge inherits the
   mean delay of the scenario that removed it, as `travel_time_impact` — and saves seven such layers
   (`hospital_impacts.parquet`, `factory_impacts…`, `police…`, `fire…`, `road…`, `rail…`, `port…`).
2. It draws the maps.

Job 1 is load-bearing: those seven layers are exactly 5d's `_ACCESSIBILITY_METRICS`
(`utils/criticality_functions.py:2523`), the **A** sub-index of the combined climate-criticality
score. Nothing on the CR side produces a per-road layer today — 5b stops at scenario level (65 rows)
and origin level (66,035 rows). **5c_CR is the only bridge between 5b and 5d**, which is why it is
being built as layers **and** maps (D1).

The mechanical port is small; the schema has no overlap. Of 5c's eight imported helpers, **three are
reusable, five are not** (§1). The substantive work is deciding what a per-road impact number means
in Costa Rica, and §3 is four measurements saying the Serbia answer does not survive the move
unchanged.

### 0.1 The one number that matters most ✅

Under Serbia's own definition of the metric (D2, requested), applied to CR:

| | loc/hospitals | wp/hospitals | loc/EBAIS | wp/EBAIS |
|---|---|---|---|---|
| Scenarios with ≥ 1 affected origin (of 65) | **46** | 64 | **17** | 57 |
| Exposed roads receiving a value (of 378) | **326** | 377 | **138** | 359 |
| Roads ≥ 10 min (Serbia's cut) | 307 | 366 | 113 | 335 |
| Median per-road impact | **138.6 min** | 104.9 min | 400.8 min | 277.7 min |
| Max per-road impact | 389.7 min | 368.8 min | 418.0 min | 416.7 min |

The isolation penalty is **7 h = 420 min** ✅, and **31.8 % of affected origin-rows (loc/hospitals)
are fully isolated** ✅. The medians above sit at 33 % and 95 % of the penalty respectively: this
metric is measuring the penalty constant more than it is measuring travel time. That is a property of
the chosen definition, not a defect in the data, and §3.1 says what has to travel with it.

---

## 1. What Serbia's 5c assumes, and whether it holds for CR

| # | Assumption | Where | Holds for CR? |
|---|---|---|---|
| A1 | Scenario results arrive as **pickled dicts** keyed by basin, each holding `scenario_outcome` (a DataFrame) and `real_edges_to_remove` | `calculate_service_criticality` | **No.** 5b_CR writes parquet + GeoPackage (its A10 / §4.6). The unpickling path has no CR input to read. |
| A2 | Removed edges are identified by **`osm_id`** | `calculate_service_criticality:1667` | **No such column.** CR partitions on `physical_edge_id`, and 5b already saved the mapping as `scenario_edges.parquet` (378 rows) ✅ — so the join is a merge, not a string-match. |
| A3 | The base network carries an **`exposed`** boolean and a **`highway`** column, both used to subset and to build the output schema | `calculate_service_criticality:1678-1690` | **No.** CR has `CLASE`, `ID_TRAMO`, `NOMBRE`, `physical_edge_id`; exposure is `flood_depth_rp100 > 0.25` evaluated in 5b, not a stored flag on the network. |
| A4 | Everything is plotted and saved in **EPSG:3857**, and the output layers in **EPSG:6316** | `load_base_network`, `save_impact_layers` call in cell 3 | **No.** CR is **EPSG:8908** end to end; 3857 is for basemap tiles only (`CLAUDE.md`). Note `plot_service_criticality` plots `base_network` *as given* and reprojects only the edges — so the CR network must be handed to it already in 3857 or the two layers land in different places. |
| A5 | Basin flood statistics come from **`SRB_flood_statistics_per_Basin_basins_scenario.csv`** with columns `basinID` and `mean water depth (m)`, computed by flattening per-cell `values` lists | `load_basins`, `plot_basin_water_depths`; `src/5b:416-445` | **File no, method yes.** No such CSV exists, and 4a discarded the per-cell lists (5b I3). But the **method is reproducible with `rasterio`** — prototyped, 6,748 cells over the 378 exposed roads in ~14 s ✅ — and D7 adopts it. 5c therefore computes the statistic itself rather than reading a CSV. §3.4. |
| A6 | The base network is a **parquet** file whose giant component is re-derived here | `load_base_network:1628` | **No.** CR reads `gpkg/network/main_network_directed.gpkg`, and 5b measured the graph as a **single weak component** ✅ — the giant-component step removes nothing and can go. |
| A7 | The per-road metric is the **unweighted mean positive delay** over affected origins, with infinities replaced by 1 h | `calculate_service_criticality:1671-1698` | **Concept kept (D2, requested), mechanics change.** CR has no infinities left to replace — 5b substitutes the isolation penalty before writing — so the `np.isinf → 1` guard is dead code that would silently mis-handle nothing. But the penalty now sits *inside* the mean: §3.1. |
| A8 | Five sectors exist: healthcare, police, fire, factory, agriculture (road / rail / port sinks) | cells 7–13 | **No.** CR has **two**: hospitals and EBAIS, plus 5b's `ebais_noncolocated` reading. Police, fire, factories and agriculture have no CR source (5b §0 D4). Cells 8, 9, 10, 12, 13 and the `calculate_agri_criticality` / `plot_agri_criticality_3x1` imports are deleted, not adapted. |
| A9 | There is exactly **one configuration**, and it is not neutral: one origin set (a geocoded settlement Excel) and the population **already restricted to the 50 km buffer** before `Delta` is computed — so Serbia's per-road metric is a **`buf50`** number | `src/5b:473-489` | **No.** 5b emits a 2 × 2 matrix (`loc`/`wp` × `nobuf`/`buf50`) and three sector readings — **780 summary rows** ✅. 5c must choose what the saved layer is keyed on and say so (§3.2, D4). Note the asymmetry: D4's `nobuf` default is a **departure** from Serbia's fixed `buf50`, not an absence of a choice. Measured cost ≤ 6.8 min ✅ (§3.3). |
| A10 | Roads with **< 10 min** delay are dropped from the layer entirely | `calculate_service_criticality:1700` | **Mechanically fine, semantically wrong for 5d.** 5d joins with `add_impact_column` (`:2125`), which reindexes and leaves unjoined roads as **NaN** — so a road measured at 4 min impact and a road never evaluated become indistinguishable. §3.3, D5. |
| A11 | Outputs are **parquet + File GDB + Excel**, under `parquet/local_accessibility/` | `save_impact_layers` → `save_criticality_vector` | **No.** CR writes `gpkg/<stage>/*.gpkg` with parquet caches, no GDB and no Excel (`CLAUDE.md`). |
| A12 | The 2 × 2 figure is **hospitals / factories / police / fire**, saved to a hard-coded `criticality_2x2.png` | `plot_criticality_2x2:2011` | **Panels are labelled A–D only**, with no hardcoded service names ✅, so the function is structurally reusable for a CR 2 × 2 of *sector × origin set*. The **fixed output filename** is the problem: it would collide with Serbia's figure in the shared `figures/` directory. D8. |

### 1.1 Which imports survive

> **Superseded by implementation.** Nothing in `utils/criticality_functions.py` can be *imported* in
> `criticality2` at all: the module does `import xarray` and `from damagescanner.core import
> DamageScanner` at module level and neither package is installed ✅. The three "reusable" entries
> below were therefore **copied verbatim into the notebook** instead of imported — see §6.1b.

| Helper | Verdict |
|---|---|
| `print_delay_category_counts` | **Copy verbatim.** Needs only `impact_class` (Serbia labels) + `travel_time_impact` in hours, which D2/D3 preserve. Behaviour unchanged, so output stays comparable. |
| `plot_service_criticality` | **Not used.** Unimportable, and hard-wired to `IMPACT_LABELS`, so it can only render Serbia's bins — which D3 reserves for the tables. |
| `IMPACT_BINS` / `IMPACT_LABELS` / `IMPACT_COLORS` / `IMPACT_WIDTHS` | **Copy verbatim** as the comparability set (D3). Four literals; copying costs nothing and avoids adding two heavy dependencies to the env. |
| `calculate_service_criticality` | **Reimplement in the notebook** — A1, A2, A3 all bite at once. |
| `load_basins` | **Drop** — A5, no such CSV. |
| `load_base_network` | **Drop** — A6; one `gpd.read_file` replaces it. |
| `plot_basin_water_depths` | **Reimplement, but only just.** D7 makes the CR statistic genuinely the same quantity, and the 0–4 m classes fit the measured distribution ✅, so the function would work if handed a frame with a `mean water depth (m)` column. The blocker is the **hardcoded output filename** `basin_water_depths.png`, which would overwrite Serbia's figure — the same collision as `plot_criticality_2x2` (A12). |
| `calculate_agri_criticality`, `plot_agri_criticality_3x1`, `plot_criticality_2x2`, `save_impact_layers` | **Drop** — A8 (no CR sectors), A12 (filename), A11 (GDB/Excel). |

Consistent with 5b's D2, **`utils/` is imported where it works and never modified.**

---

## 2. What CR actually has — the 5b outputs, verified ✅

All four files are on disk and were read on 2026-09-11.

| File | Shape | Key columns |
|---|---|---|
| `parquet/flood_scenarios/scenario_summary.parquet` | **780 × 26** | `scenario_id`, `config`, `origin_set`, `buffered`, `sector`, `n_roads`, `km_removed`, `depth_{min,mean_of_max,max}_m`, `population`, `pop_{delayed,isolated,affected}`, `pct_affected`, `mean_delta_min`, `max_delta_min`, `person_hours_added`, `buffer_pop_share_{loc,wp}`, + provenance (`scenario_rp`, `flood_threshold_m`, `isolation_penalty_h`, `buffer_m`, `scenario_unit`) |
| `parquet/flood_scenarios/origins_affected.parquet` | **66,035 × 9** | `scenario_id`, `origin_set`, `sector`, `origin_id`, `population`, `baseline_tt_h`, `scenario_tt_h`, `delta_h`, `in_buffer` |
| `parquet/flood_scenarios/scenario_edges.parquet` | **378 × 2** | `physical_edge_id`, `scenario_id` — the partition |
| `parquet/flood_scenarios/rp_sensitivity.parquet` | 7 × 12 | `RP` + the `summarise()` block |
| `gpkg/travel_disruptions/flood_scenario_accessibility.gpkg` | layer `scenarios`, **780 × 27**, EPSG:8908 ✅ | as `scenario_summary` + basin geometry |

Dimensions: **65 scenarios × 4 configs × 3 sector readings = 780** ✅.
Sectors present: `hospitals`, `ebais`, `ebais_noncolocated`.

Geometry for the roads comes from `gpkg/network/main_network_directed.gpkg` (9,764 directed edges,
5,012 physical roads), dissolved on `physical_edge_id` as 5b already does.

D7 adds one input beyond 5b's outputs: `input_files/flood_hazard_jrc/jrc_flood_cr_RP100_depth.tif`
(EPSG:4326, ~90 m cells, 3.9 MB, nodata −9999) ✅, opened only for the basin depth statistic — see
I9 for the containment that keeps this from reopening 5a D1.

---

## 3. Measured problems that shape the design

### 3.1 The Serbia metric is penalty-dominated, and the bins collapse ✅

D2 (requested) keeps Serbia's definition: `travel_time_impact` = unweighted mean of `delta_h` over
the scenario's affected origins. In CR, 5b has already replaced unreachability with a **7 h isolation
penalty** before writing, so an isolated origin contributes `7 h − baseline` — up to ~6.9 h — to that
mean. **31.8 % of affected origin-rows (loc/hospitals) are isolated** ✅.

The consequence is visible in the binning. Serbia's `IMPACT_BINS` applied to the 307 CR roads that
clear the 10-minute cut ✅:

| Serbia class | 10–20 min | 20–30 | 30–40 | 40–60 | **60+** |
|---|---|---|---|---|---|
| CR roads | 28 | 14 | 24 | 18 | **223** |

**73 % of roads land in the top class.** A map drawn on those bins is one colour, and
`print_delay_category_counts` reports a distribution that is 73 % in its open-ended tail.

This is not an argument against the chosen metric — comparability with the Serbia outputs is a
legitimate reason to keep it, and D2 stands. It is an argument that **the metric and the class
breaks are separate decisions**, and that the second one has to be made on CR's distribution (D3).
Measured quantiles of the per-road impact, loc/hospitals ✅:

| p0 | p20 | p40 | p50 | p60 | p80 | p100 |
|---|---|---|---|---|---|---|
| 0.6 min | 32.5 | 125.8 | **138.6** | 202.0 | 339.0 | 389.7 |

Two things must therefore travel with every use of this column, in the notebook and in the figure
captions: it is a **mean including penalised origins**, and the penalty is **7 h, a modelling
constant chosen in 5b**, not an observed travel time.

### 3.2 Coverage of the per-road layer depends on the configuration, heavily ✅

Because a road only gets a value if *some* origin was affected by its scenario, the choice of
configuration decides how much of the exposed network the layer even covers:

| Configuration | Roads with a value (of 378) | Share |
|---|---|---|
| `loc` / hospitals | **326** | 86 % |
| `wp` / hospitals | **377** | 99.7 % |
| `loc` / EBAIS | **138** | 37 % |
| `wp` / EBAIS | **359** | 95 % |

The locality/EBAIS combination leaves **63 % of exposed roads with no value at all** — 5b's EBAIS
co-location finding (its §3.2: 52 % of population sits at 0 min from an EBAIS) reappearing as
sparsity in the road layer. This is the single strongest argument for carrying the origin set as a
column rather than silently picking one (D4).

### 3.3 The buffer axis very nearly collapses for this metric ✅

The `buf50` configurations change the per-scenario mean by **at most 6.8 min (loc/hospitals), 0.7 min
(wp/hospitals), and exactly 0.0 min for both EBAIS arms** ✅, and change the set of roads receiving a
value not at all.

That follows from 5b's I11 — only 0.9 % of affected origin-rows fall outside the buffer — and it
means the 4-way configuration matrix reduces to a **2-way** one (origin set only) for the per-road
layer. Worth stating rather than carrying four near-identical columns and implying they differ.

### 3.4 Basin depth: Serbia's cell-based method is reproducible, and it changes the map ✅

Serbia's `basin_water_depths.png` maps `mean water depth (m)` per basin: it flattens every per-cell
`values` list across the basin's flooded edges into one list and takes min/mean/max
(`src/5b:416-445`). 4a discarded CR's per-cell distributions (5b I3), so the scalar-only equivalent
would be `depth_mean_of_max_m` — a mean of per-road **maxima**.

**D7 (requested) applies Serbia's method instead, and it is feasible.** `exactextract` is absent from
`criticality2` ✅, but `rasterio 1.5.0` is present ✅ and the seven JRC rasters are on disk ✅
(`jrc_flood_cr_RP{10…500}_depth.tif`, EPSG:4326, ~90 m cells, 3.9 MB at RP100). Rasterising each
exposed road with `all_touched=True` reproduces exactly the cell set `exactextract` reports for a
LineString. Prototyped end to end ✅:

| | Measured |
|---|---|
| Cells sampled across the 378 exposed roads | **6,748** (median 8 per road, max 218) |
| Roads returning zero cells | **0** |
| Runtime, all 65 basins | **~14 s**, most of it reading the GeoPackage |
| Dry cells in the sample | **none** — the JRC rasters store dry land as nodata, so all 6,748 are wet ✅ |

That last row settles a question the port would otherwise raise: Serbia does not filter its flattened
list to wet cells, and here it makes no difference at all, so the two readings coincide.

**The two methods disagree substantially**, which is why the change is worth making ✅:

| | cell-based (Serbia) | mean-of-maxima (scalars) |
|---|---|---|
| Median basin depth | **1.76 m** | 3.03 m |
| Mean basin depth | 2.31 m | 3.65 m |
| Max | 10.15 m | 11.88 m |

The cell mean is **lower in 55 of 65 basins**, by a median of 0.99 m and up to 5.99 m; correlation
0.862 ✅. In Serbia's own depth classes the map changes shape rather than shifting uniformly:

| Class | 0–1 m | 1–2 m | 2–3 m | 3–4 m | 4 m+ |
|---|---|---|---|---|---|
| Cell-based ✅ | 16 | **23** | 9 | 10 | **7** |
| Mean-of-maxima ✅ | 11 | 8 | 12 | 11 | **23** |

The scalar method puts 23 basins in the top class; the cell method puts 7. Mapping the scalars would
have overstated basin depth almost everywhere — the mean-of-maxima is biased high by construction,
and now that bias is measured rather than merely flagged (5b I3).

Serbia's 0–1 / 1–2 / 2–3 / 3–4 / 4 m+ bins separate the cell-based distribution well (median 1.76
falls mid-range) and are kept unchanged.

One caveat survives the change: `cell_max_m` reaches **37.29 m** ✅, higher than the scalar maximum of
30.71. The implausible depths are in the JRC raster itself, not in 4a's reduction, so 4a's
`flood_depth_implausible` flag still has to travel with any depth figure (I6).

### 3.5 The contract with 5d shrinks from seven metrics to two

5d's **A** sub-index averages seven accessibility metrics. CR can supply **two** (hospitals, EBAIS),
and one of them — EBAIS — is both structurally degenerate (5b I2) and sparse (§3.2).

5c's job is to emit the layers; it is 5d's job to decide how a two-metric A sub-index is weighted
against H and T. But 5c determines what is *available*, so the layer schema should be written to make
the choice explicit downstream: a `sector` column and a `config` column on every row, never an
inferred default. Flagged as I4.

---

## 4. The plan

### 4.1 Shape — ~14 cells, in the idiom of 5b

```
1  markdown header: purpose, inputs, outputs, steps, the "not risk" framing,
   and the §3.1 caveat on what travel_time_impact contains
2  imports + BASE_DIR + paths + constants (WORKING_EPSG, DEFAULT_CONFIG,
   SECTORS, ORIGIN_SETS); import the three surviving utils helpers (§1.1)
3  load 5b outputs: scenario_summary, origins_affected, scenario_edges;
   assert 780 rows / 65 scenarios / 378 roads; print the provenance stamp
   (scenario_rp, flood_threshold_m, isolation_penalty_h) rather than restating it
4  load the network, dissolve to physical roads on physical_edge_id (EPSG:8908)
5  build the per-road impact table  <- the load-bearing cell (§4.2)
6  diagnostics: coverage table (§3.2) and the buffer-collapse check (§3.3),
   both printed, not asserted
7  impact classes: Serbia bins + CR bins side by side (§4.3), and
   print_delay_category_counts on the Serbia bins for comparability
8  basin depth statistics: sample the RP100 raster along each exposed road with
   rasterio (all_touched=True), flatten per basin, min/mean/max  (D7, §3.4);
   cache to parquet so the raster is opened once
9  basin depth map, Serbia's 0-4 m classes
10 per-sector impact maps: hospitals, EBAIS  (plot_service_criticality)
11 2x2 figure: sector x origin set (§4.5)
12 save: GeoPackage layers + parquet cache (§4.4)
13 reconciliation printout: roads in / roads valued / roads dropped, per config
```

### 4.2 The per-road impact table — the one cell that matters

```
origins_affected                     66,035 rows
  -> group by (scenario_id, origin_set, sector), mean of delta_h    # Serbia's A7 definition
  -> merge onto scenario_edges (378 physical roads, 1 scenario each)
  -> merge onto the dissolved physical-road geometry
  = 378 roads x 2 origin sets x 2 sectors = 1,512 rows, long format
```

Three properties worth stating because each is a departure:

- The partition is **1:1 by construction** — 5b assigned each exposed road to exactly one basin by
  majority length — so there is no many-to-many blow-up and no aggregation choice here. Serbia's
  `.isin()` string match on `osm_id` is replaced by a `validate="m:1"` merge, which will *fail loudly*
  if that ever stops being true.
- The buffer is **not** an axis of this table (§3.3). It is reported as a diagnostic in cell 6 and
  then dropped, with the measured 6.8 min maximum printed so the reader sees why.
- `ebais_noncolocated` is **not** carried into the road layer. 5b's I14 established that it shares
  its numerator with `ebais` and differs only in the denominator — and this metric has no
  denominator, so the two would be identical columns. Stated in the notebook, not silently omitted.

### 4.3 Impact classes — two columns, not one

| Column | Breaks | Purpose |
|---|---|---|
| `impact_class` | Serbia's `IMPACT_BINS`: 10–20 / 20–30 / 30–40 / 40–60 / 60+ min | Comparability with the Serbia outputs, and the input `print_delay_category_counts` expects. 73 % of CR roads fall in the top class ✅ — so this column is for tables, not maps. |
| `impact_class_cr` | **< 30 / 30–60 / 60–120 / 120–240 / 240+ min** | The maps. Chosen against the measured quantiles (§3.1: p20 = 32.5, p50 = 138.6, p80 = 339) so the five classes are populated rather than one. |

Both are derived from the same `travel_time_impact`; nothing is recomputed. The colour ramp
(`IMPACT_COLORS`) is shared so the two readings look like the same family.

### 4.4 Outputs — CR conventions, per `CLAUDE.md`

| File | Contents |
|---|---|
| `intermediate_results/gpkg/travel_disruptions/flood_scenario_impacts.gpkg` | layer `road_impacts` — 1,512 rows, long format, EPSG:8908, one row per road × origin set × sector |
| `intermediate_results/parquet/flood_scenarios/road_impacts.parquet` | the same table as 5d's input and the re-run cache |
| `intermediate_results/parquet/flood_scenarios/basin_cell_depths.parquet` | D7's per-basin cell statistics — `n_cells`, `cell_min_m`, `cell_mean_m`, `cell_max_m` — cached so the raster is sampled once |
| `figures/flood_scenario_basin_depth.png` | §3.4 |
| `figures/flood_scenario_hospital_impact.png`, `…_ebais_impact.png` | §4.1 cell 10 |
| `figures/flood_scenario_impact_2x2.png` | §4.5 |

No File GDB, no Excel, no `local_accessibility/` folder (A11). Every row carries `config`,
`origin_set`, `sector`, and 5b's provenance stamp (`scenario_rp`, `flood_threshold_m`,
`isolation_penalty_h`, `scenario_unit`) so no consumer infers the regime — the rule 5b's §4.6 set.

**Note for 5d:** its Serbia paths (`parquet/local_accessibility/hospital_impacts.parquet`, seven of
them, wide format) do not match this. Repointing 5d is 5d's pass, not 5c's — I3.

### 4.5 Figures

Serbia's five figures map onto CR as follows:

| Serbia | CR |
|---|---|
| `basin_water_depths.png` | `flood_scenario_basin_depth.png` — **same quantity, same 0–4 m classes** (D7); only the filename differs, to avoid overwriting Serbia's figure |
| `hospital_criticality.png` | `flood_scenario_hospital_impact.png` |
| `police_criticality.png`, `fire_criticality.png`, `factory_criticality.png` | **dropped** — no CR sector (A8) |
| `SRB_agri_criticality_{avg,nearest}_3x1.png` | **dropped** — no CR agriculture sinks (A8) |
| `criticality_2x2.png` (4 sectors) | `flood_scenario_impact_2x2.png` — **sector × origin set**: hospitals/loc, hospitals/wp, EBAIS/loc, EBAIS/wp |
| — | `flood_scenario_ebais_impact.png` — new, since EBAIS has no Serbia counterpart |

The 2 × 2 re-purposing is the interesting one: with four sectors gone, the same four panels become
the **sensitivity display** §3.2 asks for. It shows at a glance that EBAIS/loc covers 138 roads while
wp/hospitals covers 377 — which no table communicates as quickly.

Drawn in-notebook rather than through `plot_criticality_2x2`, because that function hardcodes its
output filename (A12) and would collide with Serbia's figure.

### 4.6 Kernel

The notebook must be switched from **`criticality_env` to `criticality2`** ✅ — it is currently on
the Serbia kernel. `contextily 1.7.0`, `geopandas 1.1.2` and `mapclassify` are all present in
`criticality2` ✅, so the basemap path works.

---

## 5. Decisions

Following 5b §5.1: **✔R** = you chose it; **✔A** = I picked the default and it is recorded here and
at the line where it takes effect, reversible but not implicit.

| # | **Serbia's choice** | CR decision | Status |
|---|---|---|---|
| **D1** | Layers **and** maps: 5c produces the seven `*_impacts.parquet` files 5d scores, plus eight figures | **Same shape.** Per-road impact layers and maps; 5b's five figures stay as they are | ✔R |
| **D2** | Unweighted mean positive `Delta` over affected origins, **including** origins charged the flat 12 h penalty (`src/5b:50`, `:513`) | **Same definition**, with CR's derived 7 h penalty in place of the flat 12 h | ✔R |
| **D3** | **One** column, `impact_class`; bins `[0.167, 0.333, 0.5, 0.667, 1.0, ∞]` h → 10–20 / 20–30 / 30–40 / 40–60 / 60+ min (`:1530`, applied `:1702`) | **Two** columns: `impact_class` on Serbia's breaks for comparability, plus `impact_class_cr` (< 30 / 30–60 / 60–120 / 120–240 / 240+) for the maps. **Why:** Serbia's bins put 73 % of CR roads in one class ✅ — D2 fixes the metric but says nothing about the breaks. **Costs:** two columns; any table quoting a class must name which | ✔A |
| **D4** | **No axis.** One origin set, and the population pre-restricted to the 50 km buffer — an implicit **`buf50`** (`src/5b:473-489`) | `origin_set` (`loc`, `wp`) as a **column**; buffer axis reported then dropped, i.e. **`nobuf`**. **Why:** coverage swings 138 → 377 roads across origin sets ✅, the largest sensitivity in the notebook; the buffer moves the metric by ≤ 6.8 min ✅. **Costs:** long-format layer, so 5d selects rather than reads one file; and it is a **departure** from Serbia's `buf50`, not a neutral simplification | ✔A |
| **D5** | **Drops** roads with no impact, in three places: basins whose `scenario_outcome` is not a DataFrame (`:1665`, from the bare `except` at `src/5b:536`), non-`exposed` edges (`:1690`), and `travel_time_impact < 0.167` (`:1700`) | **Keeps** them at `travel_time_impact = 0.0` with `n_affected_origins = 0`. **Why:** 5d's `add_impact_column` turns unjoined roads into NaN, conflating "measured, no impact" (52 roads ✅) with "never evaluated". **Costs:** 1,512 rows not ~1,000; the ≥ 10 min filter moves to plot time | ✔A |
| **D6** | **No counterpart** — Serbia has no degenerate-subset reading; its five sectors are healthcare, police, fire, factory, allagri | `ebais_noncolocated` **not carried** into the road layer. **Why:** 5b I14 — same numerator as `ebais`, differing only in a denominator this metric does not have. **Costs:** nothing numerically; the reason is printed so the absence is not read as an oversight | ✔A |
| **D7** | **True mean of cell depths** — flatten every per-cell `values` list across the basin's flooded edges, take min/mean/max, map in bins `[0,1,2,3,4,∞]` m (`src/5b:416-445`) | **Same method**, re-sampled with `rasterio` since `exactextract` is absent ✅. Prototyped: 6,748 cells, ~14 s ✅. Supersedes an earlier ✔A that used `depth_mean_of_max_m`, which measurement showed is biased high — it puts 23 basins in the top class against the cell method's 7 ✅ (§3.4). **Costs:** 5c re-opens the flood raster, reversing 5a D1 — contained per I9 | ✔R |
| **D8** | **All plotting in `utils/`**; the notebook is a thin 18-cell driver with no matplotlib. `plot_basin_water_depths` and `plot_criticality_2x2` hardcode their filenames | **Figures in-notebook**, except `plot_service_criticality` and `print_delay_category_counts`, imported unchanged. **Why:** `plot_criticality_2x2` would overwrite Serbia's `criticality_2x2.png` in the shared `figures/`. `utils/` is not modified (5b D2) | ✔A |
| **D9** | **parquet + File GDB + Excel**, EPSG:6316, seven wide-format files under `parquet/local_accessibility/` (`save_criticality_vector:49`) | One long-format **GeoPackage layer + parquet cache**, EPSG:8908, no GDB or Excel (A11, `CLAUDE.md`). **Costs:** 5d's Serbia paths break — I3 | ✔A |

**Nothing blocks the build.** D3–D6, D8 and D9 are live assumptions: ratify, override, or leave them
and they stand as recorded. D1, D2 and D7 are settled.

---

## 6. Issues

### 6.1 Blocking

None. All four 5b outputs are on disk and were read ✅.

### 6.1b Deviations from this plan made during implementation

| Where | Deviation | Why |
|---|---|---|
| §1.1 | **Nothing is imported from `utils/`.** `print_delay_category_counts` and the four `IMPACT_*` literals are **copied verbatim** into the notebook's setup cell; `plot_service_criticality` is not used. | `utils/criticality_functions.py` does `import xarray` and `from damagescanner.core import DamageScanner` at module level, and neither is installed in `criticality2` ✅ — so *any* import from it raises `ModuleNotFoundError`. The alternatives were adding two heavy dependencies to the CR env or running 5c on `criticality_env`; copying four literals and one 20-line function is cheaper than either, keeps the numbers exactly comparable, and leaves `utils/` untouched. Same precedent as 5b_CR, which imports nothing from `utils/` ✅. The copies carry a comment saying they must be updated if the originals change. |
| §4.5 | **Basemap is `Esri.WorldGrayCanvas`, not Serbia's `CartoDB.Positron`.** | Verified by fetching tiles for the CR bbox on 2026-09-15: CartoDB returns "API KEY REQUIRED" watermark tiles and `OpenStreetMap.Mapnik` returns HTTP 403 to contextily's default user agent ✅. Esri's is keyless, still served, and the same muted grey style. The first executed run produced four watermarked figures before this was caught. *(Note: the other CR notebooks that call `add_basemap` — 1a, 1b, 2 — have the same latent problem, which is out of 5c's scope.)* **Superseded 2026-10-01:** every CR map, 5c included, now takes its basemap from `src/map_style_cr.style_cr_map` — keyed CartoDB Positron (label-free), with Esri.WorldGrayCanvas only as the fallback when no key is configured. The shared impact legend of the 2×2 moved from a strip under the figure to the upper-right panel. See [map_style_cr_plan.md](map_style_cr_plan.md). |
| §4.4 | Sector figures are named **`flood_scenario_hospitals_impact.png`** / `..._ebais_impact.png` (plural "hospitals"), not `..._hospital_impact.png`. | The name is generated from the `sector` key, so it matches the column value a reader would filter on. |

### 6.2 Non-blocking, must be recorded

| # | Issue |
|---|---|
| I1 | **`travel_time_impact` is not a travel time in the ordinary sense** (§3.1). It is a mean over affected origins in which ~32 % of contributors carry a 7 h modelling constant ✅. Any sentence of the form "roads in basin X add N minutes" is wrong unless it says "including origins cut off entirely, charged at the 7 h isolation penalty". Consequence of D2, which was chosen deliberately for comparability. |
| I2 | **The per-road number is a scenario-level number replicated onto roads.** Every road removed by the same basin gets the *same* value — Serbia's design, kept. It does not mean that road caused that delay; the whole basin group failed together. A per-road attribution would need the SPOF analysis from notebook 2, which is a different question. |
| I3 | **5d_CR is still a verbatim Serbia copy** and expects seven wide-format `*_impacts.parquet` files under `parquet/local_accessibility/`. 5c will deliver two sectors in one long-format layer under `parquet/flood_scenarios/`. 5d needs its own pass, and its A sub-index will rest on two metrics instead of seven (§3.5). |
| I4 | **The EBAIS road layer is sparse under localities** — 138 of 378 roads ✅. Any statistic over it is over 37 % of the exposed network. The coverage table (cell 6) must print alongside every EBAIS figure. |
| I5 | **Serbia's ≥ 10 min cut is inherited, not derived**, like 5a's 0.25 m threshold before it. Kept for D2 comparability, applied at plot time only (D5), and labelled as inherited. |
| I6 | **Implausible depths are in the raster, not in 4a's reduction.** The cell-based sampling reaches **37.29 m** ✅, above the scalar maximum of 30.71 — so re-sampling does not fix them and 4a's `flood_depth_implausible` flag must still travel with every depth figure. A 37 m road inundation is an artefact, not a flood. |
| I9 | **5c now opens the flood raster, reversing 5a D1** ("sampling lives in 4a; everything downstream is a consumer"). Accepted deliberately under D7, because the scalar alternative is measurably biased (§3.4). **Containment, which must hold:** the second sampler feeds the *descriptive depth statistic only*. Scenario membership, the exposure threshold and the road partition all still come from 4a's scalars via 5b's `scenario_edges.parquet`, so the two samplers cannot disagree about *which* roads flood — only about how deep. If a later change lets raster sampling drive selection in 5c, that containment is gone and 5a D1 has to be reopened properly. |
| I7 | **Scenario independence is inherited** from 5b (its I7) and is invisible in a per-road map: a reader sees a national map of coloured roads and will naturally read it as one event. The caption must say each road's colour comes from its *own* basin scenario, evaluated alone. |
| I8 | **The CR notebooks are untracked in git** — 5c, like 5b/5d/4a/2b/5a, has no history. Worth committing the Serbia-copy state before editing, so the transposition is a readable diff. |

---

## 7. Out of scope

- Re-running 5b, or recomputing any OD matrix. Apart from D7's depth sampling, 5c is a consumer of
  the four 5b outputs.
- Re-running 4a, or letting D7's sampler touch anything but the descriptive depth statistic (I9).
- Editing `utils/criticality_functions.py`, the Serbia `5c` notebook, or anything under `src/`
  (5b D2). Helpers are imported where they work and reimplemented in-notebook where they do not.
- Repointing or rewriting 5d (I3).
- Re-deriving the scenario partition, the exposure threshold, or the isolation penalty — all three
  are 5b's, and 5c reads them from the provenance stamp rather than restating them.
- Any fragility, damage or duration modelling (5b §4.8's framing carries over unchanged).
