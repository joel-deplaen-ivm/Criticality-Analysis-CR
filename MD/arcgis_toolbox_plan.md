# Plan: CR criticality workflow as an ArcGIS Pro toolbox (BSA2 style)

Status: **plan only, nothing built or run.** Written from the header cells of the CR notebooks,
`src/network_preparation_cr.py` (1,319 lines), and `BSA2.py`. Anything about ArcGIS Pro behaviour
is unverified — no ArcGIS Pro was available in this session.

## 1. What "BSA2 style" means (conventions to copy)

| Convention in BSA2.py | Apply to CR tools |
|---|---|
|1.1 One `.py` per script tool, wired to an `.atbx` tool; parameters read positionally with `arcpy.GetParameterAsText(i)`, outputs returned with `arcpy.SetParameterAsText(i, …)` | Same. One script tool per pipeline stage |
|1.2 `arcpy` + `numpy` + stdlib only (no geopandas / shapely) | Same wherever possible; the **one** exception is `igraph` (see §3) |
|1.3 Flat module of small helpers, each with a docstring and numbered `# 1) … # 2) …` step comments | Same |
|1.4 Section banners (`# Utilities`, `# Raster sampling`, `# Main`), `main()` at the bottom | Same |
|1.5 Raster sampling via `RasterToNumPyArray` + `ExtendTable` (`sample_raster_to_points`) | Reuse **verbatim** for hazard exposure (4a) |
|1.6 `in_memory\…` scratch, deleted after use | Same |
|1.7 Outputs: timestamped feature classes in a `<Tool>.gdb` beside the script (`roads_results_<stamp>`) | Same: `CR_Criticality.gdb`, e.g. `network_<stamp>`, `spof_<stamp>` |
|1.8 `Loc/run_config_<stamp>.loc` dump of every parameter | Same — makes each run reproducible |
|1.9 `arcpy.AddMessage/AddWarning` for progress; `ValueError` for bad parameters at the top of `main()` | Same; **no `tqdm`, no `print`** |
|1.1- Result added to the active map via `ArcGISProject("CURRENT")` | Same, inside try/except |

## 2. Scope — which notebooks become tools

Assumption (please confirm, §7): the "CR notebooks" means the analysis chain
`1b → 2 → 2b → 3d → 4a → 5a → 5b → 5c → 5d`. Figure-only notebooks (`1a`, `5e`) and the OSM
variant of 3d are **not** ported; maps are made in ArcGIS Pro.

| Tool | Notebooks | Core job | Main inputs (parameters) | Output feature class |
|---|---|---|---|---|
| **T1 Prepare Network** | 1b | clean, snap, split, impute AADT, direct, strong giant component | cantonal roads FC | `network_<stamp>` (directed edges: `from_id`, `to_id`, `physical_edge_id`, `fft`, `road_length`, `T9`–`T15`) |
| **T2 SPOF Criticality** | 2 (+2b optional) | gravity OD, remove each `physical_edge_id`, VHL/PHL/PKL/TKL | T1 network, locality points, (opt.) IDS districts | `spof_<stamp>` (+ `spof_physical_<stamp>`); quintile fields if 2b enabled |
| **T3 Baseline Accessibility** | 3d (hospital, EBAIS) | nearest-facility travel time per 1 km cell | T1 network, population grid, facility points | `access_cells_<stamp>` |
| **T4 Hazard Exposure** | 4a | sample hazard rasters onto edges | T1 network, flood / landslide / Rx1month rasters | `hazard_exposure_<stamp>` |
| **T5 Flood-Scenario Accessibility** | 5b + 5c | remove all flood-exposed roads per basin, per-road delay | T1, T4, localities, hospitals, EBAIS, basins | `flood_scenarios_<stamp>`, `flood_road_impact_<stamp>` |
| **T6 Combined Hazard Criticality** | 5a + 5d | join T2/T4/T5, score H, T, A, `CC = norm(H)·(norm(T)+norm(A))`, IDS cross | outputs of T2, T4, T5, (opt.) IDS | `combined_criticality_<stamp>` |

Why 5a+5d and 5b+5c merge: 5a is a join + aggregate that only feeds 5d; 5c is a per-road
projection of 5b's table and feeds only 5d. Neither is useful as a stand-alone GIS step. The
notebook plans in `MD/5*_plan.md` should be read before merging, to keep their documented
decisions (the "not risk" framing, the 7 h isolation penalty, the `0.25 m` flood threshold).

## 3. The hard constraint: igraph

BSA2 hand-rolls Dijkstra (`heapq`) because it only needs one detour per edge. CR needs
all-pairs shortest paths and a percolation over 5,012 physical roads (plus 5b's basin
scenarios). A pure-Python Dijkstra will not be viable; `igraph` is.

- **ArcGIS Pro's default env does not ship `python-igraph`** (unverified for the user's Pro
  version — check `import igraph` in the Pro Python window). Plan: document a *cloned* conda env
  (`arcgispro-py3-cr`) with `python-igraph` added, and make that the env the toolbox runs in.
- `import igraph` is guarded at module top; if missing, `arcpy.AddError` with the install
  instruction, not a traceback.
- Fallback if the user cannot add packages: `scipy.sparse.csgraph.dijkstra` (scipy ships with
  Pro). Needs benchmarking before committing; not assumed to be fast enough for the percolation.
- Runtime: notebook 2 caches its percolation to parquet. A toolbox tool needs a cache too, but
  parquet is not guaranteed in the Pro env — use `.npy`/`.npz` in a `cache/` folder next to the
  GDB, keyed by input hash, with a `Use cache` boolean parameter.

## 4. Porting rules (geopandas → arcpy)

1. **I/O:** `gpd.read_file` → `arcpy.da.FeatureClassToNumPyArray` / `SearchCursor`; writes →
   `ExtendTable` / `InsertCursor` into a copy of the input FC (BSA2's `create_consolidated_copy`
   + `ensure_field` pattern). Never keep a GeoDataFrame.
2. **Geometry:** shapely snapping / splitting in `network_preparation_cr.py` →
   `arcpy.management.Integrate`, `FeatureToLine`, `SplitLine`/`UnsplitLine`, or cursor loops.
   This is the largest rewrite (1,319 lines) and the riskiest for parity with the notebook's
   2 m tolerance / 30 m search buffer / endpoint-snap log. **Parity test required** (§6).
3. **Nearest node snapping** (`sjoin_nearest` equivalent): build a KD-tree on node XY with
   `scipy.spatial.cKDTree` from NumPy arrays; do not use `arcpy.analysis.Near` per point.
4. **CRS:** keep EPSG:8908 end to end. Tool validates the input spatial reference is 8908 (or
   projects with a warning) — do not silently assume it.
5. **Constants** (`DIST_DECAY`, `MAX_TRIPS`, `ISOLATION_PENALTY_FACTOR`, flood threshold 0.25 m,
   2 m / 30 m snap) become **tool parameters with notebook values as defaults**, in an
   "Advanced" parameter category. T2 and the 2b branch must read them from one place (today
   CLAUDE.md requires hand-matching them).
6. **Field names:** ArcGIS caps GDB field names at 64 chars and forbids some characters; the
   notebooks' 41-column hazard table and `*_rp100`-style names need a mapping check
   (`ValidateFieldName`).
7. **Directed edges + `physical_edge_id`:** keep the two-rows-per-physical-road model in the
   FC; SPOF removes the group, as in notebook 2.
8. **Maps / figures:** dropped. `style_cr_map` stays notebook-only. Symbology is delivered as
   `.lyrx` files (`utils/arcgis.py` already exports `.lyrx`; reuse it for T2/T6).

## 5. Repository layout

```
arcgis_toolbox/
  CR_Criticality_Accessibility.atbx          # created in ArcGIS Pro; tools point at the scripts below
  T1_prepare_network.py        # each: banner, helpers, main(), GetParameterAsText
  T2_spof_criticality.py
  T3_baseline_accessibility.py
  T4_hazard_exposure.py
  T5_flood_scenario_accessibility.py
  cr_common.py                 # ensure_field, find_field, split_paths, create_consolidated_copy,
                               # sample_raster_to_points, graph build, OD/gravity, norm helpers
  CR_Criticality.gdb/          # created at runtime (not in git)
  Loc/                         # run_config_<stamp>.loc (not in git)
  README.md                    # parameter tables per tool, env setup
```

`cr_common.py` is the one departure from BSA2's single-file style: T2, T3, T5 share the
graph + gravity code, and duplicating it is exactly the notebook-2-vs-2b drift CLAUDE.md warns
about. The `.atbx` itself is binary-ish (zipped JSON) — commit it, but tool *logic* must live in
the `.py` files, never in the toolbox.

## 6. Build order and verification

1. **cr_common.py + T4** (smallest, pure arcpy, reuses BSA2's `sample_raster_to_points`).
   Verify against `main_network_hazard_exposure.gpkg`: per-edge values equal to notebook 4a
   within raster-sampling tolerance (point-sample vs. whatever 4a uses — **check 4a's method
   first**; BSA2 samples cell centres at 'trib_len' points, 4a may sample along the line).
2. **T1.** Verify: 9,764 directed edges / 5,012 physical roads, ≥95 % physical length in the
   giant component, snap log row-count matches.
3. **T2.** Verify against `criticality_results.gpkg` on a 50-road subset first, then full run;
   compare VHL/PHL per `physical_edge_id` (expect exact match given identical graph and
   constants). Time the full run before building the cache UX.
4. **T3, T5, T6**, each compared against its notebook output.
5. Run all tools in sequence from a clean `.gdb` inside the cloned env; confirm
   `run_config_*.loc` is sufficient to reproduce a run.

Nothing in §6 has been run. Parity thresholds above are proposals, not measured.

### Original questions

1. **Scope.** Is the chain in §2 right? In particular: include 2b (socio-economic quintiles) as
   an option inside T2, as a separate tool, or leave out? Seperate tool
   Port both 3d variants (hospital, EBAIS)as one tool with a facility parameter (my default)? Yes, seperate tool
2. **Environment.** Is installing `python-igraph` into a cloned Pro env acceptable for the
   people who will run this (Costa Rican partners?), or must the toolbox run on a stock Pro
   install? That decides igraph vs. a scipy rewrite.: clone version with library installed on top
3. **CHIRPS Rx1month GEV/Theil–Sen** (4a): the notebook derives return levels with L-moments.
   Port to the toolbox (numpy/scipy), or treat the derived rasters as pre-computed inputs?
   Default proposed: **pre-computed input**, to keep T4 raster-in / table-out.: only riverine flood implementation for now
4. **Reproducibility vs. ArcGIS-native.** Rewrite the 1b geometry cleaning with ArcGIS tools
   (different snapping results, likely a few edges differ) or port the shapely logic to numpy
   to keep results identical? Default proposed: ArcGIS-native, with a documented tolerance on
   the edge count: no use the library used in the nb
5. **Audience/placement.** Does the toolbox live in this repo (my default, `arcgis_toolbox/`) or
   next to BSA2 in the BlueSpot CR project folder? In this repo for now

### User Decision

1.2: avoid arcpy stdlib, keep the original library initially, geopandas and numpy can be added on the cloned environment

1.5: keep sampling strategies of notebook

2: only do the flood hazard, leave the landslide and rainfall for now

T4: Hazard Exposure: flood only

3: igraph will be added to the clones arcpy environment

4.1: keep geopandas

4.2: keep shapely

4.3: keep original nearest node snapping

Make list of input and assumptions required to run notebook

Implement plan for notebooke 1b and 2

### Notes

1. check the nb cells that are not used atm

2. show overlap of functions in BSA2.py and the notebook
## 8. Revision after the user decisions (supersedes §1.2, §3, §4 and §6 where they conflict)

**Decisions applied:** keep the notebook libraries (geopandas, shapely, numpy, pandas, scipy,
igraph) in a cloned Pro env; keep the notebook sampling and nearest-node strategies; scope of
this round = **T1 (1b) and T2 (2)** only; hazard work (T4) is **flood only** — landslide and
rainfall are dropped for now (so also no CHIRPS GEV / Theil–Sen); 2b, 3d-hospital and 3d-EBAIS
are separate tools; toolbox lives in this repo.

What changes in the plan:

| Earlier plan | Now |
|---|---|
| §1.2 / §4.1–4.3: arcpy + numpy only, geopandas → arcpy port, Integrate/FeatureToLine, KD-tree | **No port.** `arcpy` is used only for messages, progress, parameters and layer-name → path resolution; everything else is the notebook code. Outside ArcGIS the same scripts run with `--options`, which is how they were tested here |
| §4.2 largest rewrite (1b geometry) | Gone: T1 imports `src/network_preparation_cr.py`. One backward-compatible edit to it: `save_outputs(..., make_figures=True)` so the tool can skip the map |
| §3 fallback to scipy Dijkstra | Dropped; igraph is in the cloned env |
| §3 cache as `.npy`/`.npz` | CSV in `<output>/cache/`, keyed by a hash of the inputs (parquet/pyarrow not assumed in the Pro env) |
| §1.7 outputs in `CR_Criticality.gdb`, timestamped feature classes | Timestamped **run folder** per tool containing GeoPackages with the notebook's file and layer names (CR convention; keeps downstream notebooks readable). File-geodatabase export is a possible later option |
| §5 T6 combined tool, T4 with three hazards | T4 flood only; T5/T6 not started |

### Built so far (`arcgis_toolbox/`)

| File | Role | Maps to |
|---|---|---|
| `cr_common.py` | arcpy shim (`msg`, `warn`, `read_parameters`, `Progress`), vector IO with `gdb`/`gpkg` layer notation, run-config `.loc`, graph + gravity helpers | BSA2 utilities |
| `T1_prepare_network.py` | wraps the 1b stages | notebook 1b |
| `T2_spof_criticality.py` | notebook 2 §2–7 and §9 as functions + `main()` | notebook 2 |

Inputs and assumptions: `MD/arcgis_toolbox_inputs_assumptions.md`. The `.atbx` itself still has to
be created in ArcGIS Pro (Add script tool → point at the `.py`, parameters in the order given in
each file's docstring). **Not done, not verified:** running inside ArcGIS Pro, the `.atbx`, and the
`SetParameterAsText` derived-output paths (`<file>.gpkg\<layer>` form).

### Note 1 — notebook cells not used by the tools

| Notebook | Cells not ported | Reason |
|---|---|---|
| 1b | 12 (`plot_aadt_maps`), 14's `plot_direction_qa` call, the figure part of `save_outputs` | Figures only. Every other code cell is a stage the tool runs (its `display()` calls are dropped) |
| 2 | 18 (demand heatmap), 21 (single-iteration timing probe), 26 + 28 + 29 + 33–37 (class breaks, maps, plots), 30–32 (save/reload of `physical_results` — replaced by the tool's cache), 40 (re-open check; its assertions and manifest are **commented out** in the notebook), 42–48 (summary statistics, regression, modelled-vs-observed AADT, quasi-quintiles) | Figures / diagnostics |
| 2 | 49–end ("Socio eco": IDS quintile plot) | Belongs to the later 2b tool |
| 2 | 32 reads `criticality_results_path` **before** cell 39 writes it in the same session, so it depends on a file from a previous run | Latent notebook issue; the tool has no such dependency |

### Note 2 — overlap of BSA2.py functions with the notebooks

| BSA2.py | CR notebook / src counterpart | Overlap |
|---|---|---|
| `main()` parameter block, `GetParameterAsText`, `SetParameterAsText`, `AddMessage`, timestamped output, `Loc/run_config_*.loc` | none (notebooks have constants in cells) | Reproduced in `cr_common.py` |
| `split_paths`, `create_consolidated_copy`, `ensure_field`, `find_field` | `read_vector`/`write_gpkg` in `cr_common.py`; `_read_vector`, `_write_geopackage` in `src` | Same role, geopandas instead of arcpy |
| `get_endpoints` (rounded endpoint node keys) | 1b `snap_network_iteratively` / `build_topology` (tolerance snapping, integer `from_id`/`to_id`) | Same idea, 1b is far more thorough |
| `dijkstra` (per-edge detour with `skip_oid`) + `road_loss_analysis` (dead-end → OCU × GDP/day, else COV × detour km × AADT) | notebook 2 percolation + `SummariseOD` + VHL/PHL… | **Conceptual overlap, different metric**: BSA2 = detour of the removed edge's own endpoints, in money; CR = demand-weighted OD delay across all population pairs, in hours/km, isolation penalty instead of OCU × GDP |
| `read_taxonomy_csv` (COV, OCU per T9–T15) | `PASSENGER_FACTORS`, `FREIGHT_FACTORS` | Both map T9–T15 to per-vehicle weights; different quantities |
| `sample_raster_to_points`, `add_raster_field`, `liquefaction_once` | notebook 4a raster sampling onto edges | Same job; **4a's sampling method has not been read or compared yet** — check before T4 |
| `road_geometry` (points every N m, tributary length) | none | CR 4a does not use tributary-length integration |
| `read_vul_db`, `build_vul_key`, `process_roads/components`, `compute_DAE/PAE`, `apply_TRmods`, `compute_mod_totals`, bridge/tunnel/drainage components | none (5a/5b state explicitly "not risk": no fragility, no loss, no climate change) | No CR counterpart; out of scope |
