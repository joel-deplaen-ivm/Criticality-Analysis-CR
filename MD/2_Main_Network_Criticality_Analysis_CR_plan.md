# Plan: adapt `2_Main_Network_Criticality_Analysis` to Costa Rica

Source notebook: `notebooks/2_Main_Network_Criticality_Analysis.ipynb` (Serbia, left unchanged)
Target notebook: `notebooks/2_Main_Network_Criticality_Analysis_CR.ipynb` (new)

Implementation status: **completed** in `notebooks/2_Main_Network_Criticality_Analysis_CR.ipynb`, verified by a clean-kernel top-to-bottom run against both CR inputs. See [Implementation notes](#implementation-notes) for the decisions taken during implementation and how they differ from or refine this plan.

This plan covers **the notebook only**. No changes to `src/`, `utils/`, `src/config/network_config.py`, or any other notebook are in scope — see [Out of scope](#out-of-scope) for the consequences that follow.

## Inputs

```text
population:        input_files/CENTROS_POBLACION/centros_poblados_localidades.shp
                   population attribute: INEC_PROY
                   crs: EPSG:8908 — CR-SIRGAS / CRTM05
directed network:  intermediate_results/gpkg/network/main_network_directed.gpkg
                   crs: EPSG:8908 — CR-SIRGAS / CRTM05
```

These replace the Serbia inputs: the Excel geocoding file `population_NEW_settlement_geocoded.xlsx` (attribute `Total`, WGS84 lat/long columns) and the Parquet network `intermediate_results/parquet/network/main_network_directed.parquet` are both dropped.

Both CR inputs are already in EPSG:8908, so the notebook works in a single metric CRS end to end. This keeps `road_length` (km), `fft` (hours), and locality snapping distances internally consistent, and means no reprojection of the network is required — important, because reprojecting after 1b would change `road_length` and therefore every criticality metric. Web Mercator (3857) is used only for basemap rendering.

## Outputs

```text
intermediate_results/gpkg/travel_disruptions/criticality_results.gpkg   (layer: criticality_results)
figures/SPOF_results_2x2.png
figures/SPOF_PHL_THL_PKL_TKL.png
figures/SPOF_by_road_type_boxplot.png
figures/SPOF_by_road_type_violin.png
figures/SPOF_AADT_vs_criticality.png
```

GeoPackage output mirrors the convention 1b established. The current notebook additionally calls `save_gdb_layer(..., "EPSG:6316")` and `save_excel_mirror(...)` from `utils.hazard_functions`; both must be removed rather than adapted, because EPSG:6316 is the Serbian national grid and editing `utils/` is out of scope.

## Source-data audit

### Directed network — verified

`intermediate_results/gpkg/network/main_network_directed.gpkg` was inspected directly:

| Check | Observed |
|---|---:|
| Directed edges | 9,764 |
| CRS | EPSG:8908 (CR-SIRGAS / CRTM05, metres) |
| Geometry types | `LineString` only |
| Null `from_id` / `to_id` / `id` | 0 / 0 / 0 |
| Null `road_length` / `fft` / `speed` | 0 / 0 / 0 |
| Null `total_aadt` and `T9`–`T15` | 0 |
| Null `CLASE` | 246 |
| `vul_f`, `vul_eq` | 100% null (unused here) |

Routing-relevant fields present: `from_id`, `to_id`, `id`, `physical_edge_id`, `source_part_id`, `direction_side`, `road_length` (km), `speed` (km/h), `fft` (hours), `total_aadt`, the seven descriptive AADT aliases, and provenance flags (`aadt_imputed`, `direction_imputed`, `speed_source`, `aadt_direction_factor`).

### Population layer — NOT verified

`input_files/CENTROS_POBLACION/centros_poblados_localidades.shp` **could not be read** during planning. The `CENTROS_POBLACION` directory contains OneDrive cloud placeholders that report file sizes but occupy zero blocks; every read attempt fails with `Operation timed out` / `OSError [Errno 89] Operation canceled`, including the 399-byte `.prj`. The files must be hydrated locally (open the folder in Finder with OneDrive online, or "Always keep on this device") before the notebook can run or be tested.

The population attribute (`INEC_PROY`) and CRS (EPSG:8908) are given. Still unknown and to be established by an audit cell rather than assumed:

- geometry type (point vs polygon) and therefore whether `.centroid` is needed;
- the locality **name** attribute, needed for demand-heatmap labels;
- feature count, and the number of null / zero / negative `INEC_PROY` rows;
- duplicate or coincident localities.

Sibling files `centros_poblados_localidades.xlsx` and `.qmd` likely document the schema and should be checked once hydrated.

## Field mapping: Serbia → CR

| Serbia field used in notebook | CR replacement | Notes |
|---|---|---|
| `Total` (population Excel) | `INEC_PROY` | INEC projected population per locality |
| `latitude` / `longitude` columns | native geometry | layer is already spatial and already EPSG:8908 |
| `kategorija` (IA/IM/IB/IIA/IIB) | `CLASE` (Primaria/Secundaria/Terciaria/Local) | 246 nulls → label `Sin clasificar` before grouping |
| `kategorija == 'IA'` | `CLASE == 'Primaria'` | top-tier subset in the summary section |
| `oznaka_put` | `NOMBRE` (or `ID_RUTA`) | route identifier in printed examples |
| `oznaka_deo`, `oznaka_deo_left` | `ID_TRAMO`, `TRAMO_UID` | section identifiers |
| `naziv_poce`, `naziv_zavr` | `NODO_INI`, `NODO_FIN` | endpoint references; CR values are node codes, not names |
| `objectid` | `source_row_id` | |
| `smer_gdf1` | `direction_side` + `DIRECCION` | direction is already resolved in 1b |
| `articulated_vehicles` | *(does not exist)* | see [Freight and passenger factors](#freight-and-passenger-factors) |
| EPSG:6316 | EPSG:8908 | |

## Blocking defects to fix

These break or silently corrupt the analysis on CR data and are not cosmetic renames.

### 1. Graph construction reads the wrong columns

```python
graph = ig.Graph.TupleList(edges.itertuples(index=False),
                           edge_attrs=list(edges.columns)[2:], directed=True)
```

`TupleList` takes the **first two columns** as the edge endpoints. In the Serbia Parquet, columns 0–1 happened to be `from_id`/`to_id`. In the CR GeoPackage, column 0 is `source_row_id` and `from_id`/`to_id` sit at positions 34–35. Left unchanged this builds a graph over `source_row_id`/`ID_TRAMO` — it will not raise, it will produce a meaningless network.

Fix: select and order columns explicitly before constructing the graph, and assert the first two are `from_id`, `to_id`.

### 2. Build the routing graph with only routing attributes

`edge_attrs=list(edges.columns)[2:]` attaches all ~60 columns — including `geometry` — to every edge. The percolation loop then calls `graph.copy()` once per iteration (~4,882 times), deep-copying every Shapely geometry each time. Attach only `id`, `physical_edge_id`, `road_length`, and `fft`; keep the rest on the GeoDataFrame and rejoin afterwards. This is a large runtime and memory saving, not a style preference.

### 3. Pair sister edges on `physical_edge_id`

The current pairing inverts `(source, target)`:

```python
edge_lookup = {(e.source, e.target): e.index for e in graph.es}
```

This mispairs whenever two distinct edges share the same node pair (parallel edges), and silently yields `None` when a reverse edge exists under a different node pair. The CR network carries `physical_edge_id` with the 1b contract of exactly one directed edge per `Unidireccional` road and exactly two per `Bidireccional` road. Group by `physical_edge_id` instead, and assert every group size is 1 or 2.

### 4. Do not merge results on the DataFrame index

```python
gdf_results = edges.merge(result_df, left_index=True, right_on='edge_no')
```

`edge_no` is `graph.es[edge]['id']`, i.e. the `id` **column**, while `left_index=True` matches the row index. These coincide only if `id` equals `0..n-1` in row order. Merge on `id` explicitly (`left_on='id'`) and assert one row per input edge with no nulls introduced.

### 5. Population layer loading

Replace the whole Excel block (`pd.read_excel`, `dropna(subset=["latitude","longitude","Total"])`, manual `Point(xy)` construction, `crs="EPSG:4326"`) with a single `gpd.read_file`. Then:

- **remove `set_crs(4326)`** — it would mislabel a layer that is already EPSG:8908 and silently move every locality. Keep `to_crs(edges.crs)` as a no-op guard, after asserting the layer's CRS is EPSG:8908;
- apply `.centroid` only if `geom_type` is polygonal, guarded by a check;
- drop rows with null or non-positive `INEC_PROY`, and report how many were dropped.

## Notebook structure

### 0. Markdown header

Rewrite Purpose / Inputs / Outputs / Key Processing Steps for CR. State the CR inputs and GeoPackage output, the occupancy and tonnage assumptions adopted below, the isolation-penalty value, and the fact that AADT is partly imputed (`aadt_imputed` from 1b). Start from a clean notebook with no Serbia outputs or execution counts carried over.

### 1. Imports and paths

Keep GeoPandas, pandas, NumPy, igraph, Shapely, matplotlib, contextily, seaborn, scipy, tqdm. Remove `Geod` and the `utils.hazard_functions` import. Define paths from the notebook-safe project root and assert both inputs exist before use, with an explicit message about OneDrive hydration if the population file cannot be opened.

### 2. Load and validate the directed network

```python
edges = gpd.read_file(
    intermediate_path / "gpkg" / "network" / "main_network_directed.gpkg",
    layer="main_network_directed",
)
```

Assert: 9,764 rows or a printed deviation; CRS is EPSG:8908; required routing columns present and non-null; `road_length > 0`; `fft > 0` and finite; `id` unique. Label `CLASE` nulls as `Sin clasificar`. Then build the graph per defects 1–3, and assert the graph is strongly connected (1b guarantees this — a failure means the input is stale).

### 3. Audit and load the population layer

A dedicated audit cell first: feature count, CRS, geometry types, all column names with dtypes and null counts, `head()`, and the `INEC_PROY` distribution. Only then apply defect 5. Report the aggregated total population as a sanity check against the ~5.1 million national figure — a large shortfall or excess means `INEC_PROY` is not the field assumed, or localities are duplicated.

### 4. Snap localities to network nodes

Keep the existing node-extraction and `STRtree.nearest` approach, with additions:

- assert every network node id resolves in `vertex_lookup` before use;
- record the snap distance per locality and print min / median / max plus a histogram. Distances are in metres, directly interpretable, since both layers are in EPSG:8908;
- report localities beyond a documented threshold (e.g. 5 km). On a 4,764-segment network some remote localities will snap implausibly far and distort demand. Decide and document whether to keep, drop, or flag them; do not leave the choice implicit;
- report how many localities collapse onto a shared node after `groupby('vertex_id')`, and confirm population is summed rather than lost.

### 5. Baseline matrices and demand

Compute `OD_orig_time` (`fft`) and `OD_orig_dist` (`road_length`). Assert no `inf` in either — with a strongly connected graph there should be none, and an `inf` here silently poisons `normalized_dist`.

Keep the gravity model form (`dist_decay = 1`, `maxtrips = 25000`). Note in the notebook that because demand enters only as weights in `np.average`, its absolute scale cancels out of the reported averages; `maxtrips` matters only through `np.ceil` rounding, which flattens weights if set too low. Keep 25,000 and state this reasoning rather than presenting it as a CR calibration.

Replace the demand-heatmap labels `["Belgrade", "Novi Sad", "", "...", "", "City X"]` with labels taken from the CR locality name column for the highest-demand nodes.

### 6. Percolation loop

Keep the algorithm: remove each physical edge together with its sister, recompute the OD time matrix, summarise. CR-specific changes:

- iterate over `physical_edge_id` groups (defect 3);
- **the isolation penalty must be re-derived.** The Serbia code hard-codes `6` hours in two places (`perc_matrix_time[perc_matrix_time == np.inf] = 6` and `SummariseOD(..., 6, ...)`). Costa Rica spans roughly 356 × 318 km; measure `OD_orig_time.max()` and set the penalty above the observed maximum baseline travel time, defined once as a named constant and printed. A penalty below the longest legitimate trip makes isolation look cheaper than a detour;
- time one iteration and print an ETA before launching the full loop — runtime scales with (number of OD nodes)² × ~4,882 iterations, and the OD count is unknown until the population layer is readable.

`SummariseOD` needs no CR-specific change, but keep its documented quirk visible: for isolated pairs the distance disruption is set to the removed edge's own length, which is a placeholder rather than a measured detour.

### 7. Criticality metrics

`vhl` / `vkl` carry over unchanged (`average_*_disruption × total_aadt`).

#### Freight and passenger factors

The Serbia formulas reference `articulated_vehicles`, which **does not exist in the CR data** — they will raise `KeyError`. CR provides seven categories: `motorcycles`, `pickup_trucks`, `passenger_cars`, `buses`, `light_trucks`, `medium_trucks`, `heavy_trucks`.

Proposed replacement, defined as an explicit commented factor dictionary rather than inline literals:

| Metric | CR composition |
|---|---|
| Passenger (`phl`, `pkl`) | `motorcycles × 1.2` + `passenger_cars × 2` + `pickup_trucks × 2` + `buses × 30` |
| Freight (`thl`, `tkl`) | `pickup_trucks × 0.3` + `light_trucks × 1.2` + `medium_trucks × 3.8` + `heavy_trucks × 8.0` |

Two points must be stated in the notebook as assumptions, not facts:

1. `pickup_trucks` is the largest CR category after `passenger_cars` and serves both personal and goods transport. Counting it on both sides at reduced weight is a modelling choice; assigning it wholly to passengers is the alternative. Either is defensible, but the choice must be visible and applied consistently across `phl`/`pkl`/`thl`/`tkl`.
2. There is no articulated-vehicle category, so the 14.5 t term is dropped and the heaviest CR class tops out at 8.0 t. CR freight tonnage is therefore **not** comparable to the Serbia results.

Carry the factors into the output as metadata columns, or print them, so a reader of `criticality_results.gpkg` can reconstruct how the metrics were formed.

### 8. Figures

All five figures keep their filenames and layouts. Changes:

- group and facet by `CLASE` instead of `kategorija` — box plots, violin plots, and the road-type summary table. CR has 4 classes plus `Sin clasificar` against Serbia's 5, so check tick labels and figure width;
- `to_crs(3857)` for basemaps still works from EPSG:8908;
- **the fixed class breaks are Serbia-calibrated and must be re-derived.** Every panel uses hard-coded bins (`5-15/15-30/30-60/60+ min`, `0-1K/1K-5K/5K-10K/10K-25K/25K+`, `0-5/5-15/15-30/30-60/60+ km`, plus the PKL/TKL variants). CR is a smaller, lower-volume network with a lighter maximum freight class, so these bins will likely collapse most edges into the lowest class. Print each metric's distribution and quantiles first, then set five documented breaks per metric and print the thresholds used. Keep five classes so the existing `linewidth_map` styling stays valid;
- the AADT-vs-criticality regression carries over; confirm `total_aadt` is the intended x-axis given that a substantial share of CR AADT is imputed, and consider distinguishing `aadt_imputed` rows in the scatter.

### 9. Save results

```python
criticality_results_path = (
    intermediate_path / "gpkg" / "travel_disruptions" / "criticality_results.gpkg"
)
criticality_results_path.parent.mkdir(parents=True, exist_ok=True)
results.to_file(criticality_results_path, layer="criticality_results",
                driver="GPKG", index=False)
```

Keep EPSG:8908 in the output so lengths, travel times, and geometry stay consistent with the 1b network.

Rebuild `preferred_columns` from CR fields — the current list is entirely Serbian (`objectid`, `oznaka_deo`, `smer_gdf1`, `kategorija`, `oznaka_deo_left`, `articulated_vehicles`). Because it is filtered with `if c in gdf_results.columns`, a stale list silently drops nearly every column instead of failing, so assert the expected CR columns are all present after filtering.

Remove the `save_gdb_layer` and `save_excel_mirror` calls. Re-open the written layer and verify row count, CRS, geometry type, required columns, and non-null metrics; print a manifest with absolute paths, row counts, CRS, and file size.

### 10. Summary statistics

Keep the structure (delay-class distribution, top-10 tables, per-class breakdown, regression) with `CLASE` / `NOMBRE` substituted, and re-derive the printed PHL/PKL threshold buckets from the CR distribution.

**Delete or replace the national-statistics comparison.** It currently hard-codes Serbian H1-2025 road transport figures — `2069` million passenger-km, `4677` million ton-km, `23.905` million passengers over 180 days, and a bare `11494444` denominator. Applied to CR results these produce numbers that look authoritative and are wrong. Either substitute cited Costa Rican figures (INEC / MOPT / CONAVI) with the source recorded in the notebook, or remove the section entirely. Do not leave the Serbian denominators in place.

## Acceptance criteria

- The notebook runs top-to-bottom from a clean kernel against the two CR inputs, with no manual state from another notebook.
- No executable reference remains to `kategorija`, `oznaka_*`, `naziv_*`, `objectid`, `smer_gdf1`, `articulated_vehicles`, `Total`, `population_NEW_settlement_geocoded.xlsx`, the Parquet network, EPSG:6316, EPSG:4326 `set_crs`, `save_gdb_layer`, or `save_excel_mirror`.
- Everything stays in EPSG:8908 apart from basemap rendering, and the network is never reprojected.
- The graph is built on `from_id`/`to_id` with an assertion, is strongly connected, and carries only routing attributes.
- Sister-edge pairing is by `physical_edge_id`, with every group size 1 or 2.
- Population comes from `INEC_PROY`, every locality snap distance is reported in metres, and the treatment of far-snapping localities is documented.
- The isolation penalty is a named constant derived from and printed against the observed maximum baseline OD time.
- `phl`/`thl`/`pkl`/`tkl` are finite and non-negative, computed from the seven CR categories with factors defined in one visible place.
- All five figures are produced, faceted by `CLASE`, with printed data-driven class breaks.
- `criticality_results.gpkg` reopens and passes the schema / count / CRS checks, and its column list is asserted rather than silently filtered.
- No Serbian national-statistics denominator appears in any printed output.

## Out of scope

Deliberately excluded, because only the notebook is being adjusted:

- `src/2_Main_Network_Criticality_Analysis.py`, which remains the Serbia script.
- `src/config/network_config.py`, which still points at Serbia inputs and the Parquet / File-GDB layout — the notebook therefore defines its own paths rather than importing the config.
- `utils/hazard_functions.py` — hence the GDB and Excel mirrors are dropped rather than reprojected.
- Downstream notebooks. **5a consumes `intermediate_results/parquet/travel_disruptions/criticality_results.parquet`**, which this plan replaces with a GeoPackage at a different location. 5a will not find its input until it is adapted separately; if that is needed sooner, write the Parquet alongside the GeoPackage as an interim measure.

## Implementation notes

Recorded after the notebook was written and run. Everything below is observed behaviour, not
prediction.

### Verified run figures

| Quantity | Value |
|---|---:|
| Directed edges / physical roads | 9,764 / 5,012 |
| Network nodes | 3,909 |
| Localities → OD nodes | 493 → 485 (8 collapsed; population preserved exactly at 5,167,278) |
| Snap distance | median 247 m, p95 2.1 km, max 16.9 km |
| Max baseline OD trip | 10.38 h |
| Isolation penalty (derived) | 21 h |
| Roads whose failure isolates an OD pair | 130 |
| Fully redundant roads (zero disruption) | 1,989 (39.7%) |
| Percolation runtime | ~16 min (485² OD matrix × 5,012 iterations) |
| Output GeoPackage | 9,764 rows, 43 columns, EPSG:8908, 91.8 MB |

### Decisions that refine this plan

**Zero versus NaN disruption.** `SummariseOD` returned `NaN` when a road's removal delayed no OD
pair at all. That is not missing data — it is a fully redundant road, and it turned out to be
**39.7% of the network**. `NaN` would have silently dropped those roads from every map, class
break and summary statistic, and it broke the post-merge assertion. They are now recorded as
`0.0`, with the reasoning in the function body.

**The isolation penalty mattered more than anticipated.** The longest legitimate CR trip is
10.38 h, so the inherited hard-coded 6 h penalty would have made complete isolation *cheaper*
than a long ordinary journey — inverting the ranking for exactly the roads the analysis exists
to find. The derived value is 21 h (2× max baseline).

**Class breaks need an explicit zero class.** With ~40% of roads at exactly zero, plain quantile
breaks stacked several break points on zero and produced a meaningless `0–0` first class. The
implementation gives zero its own grey class and computes quantiles over the strictly positive
values only (`classify_metric`).

**Far-snapping localities are retained, not dropped.** Six localities snap further than 5 km —
Puerto Jiménez (16.9 km), Barra del Colorado (12.3 km), Nancite, Cabanga, Amubri, Delicias. They
are real population in precisely the remote areas where isolation matters, so they are kept and
flagged with `snap_far` rather than discarded.

### Field-mapping corrections

- `oznaka_deo_left` is **not** a field to map. It is a pandas merge suffix artifact from the old
  Serbia AADT join; it is simply absent from `preferred_columns`.
- `ID_TRAMO` is **not unique per row** — 4,407 distinct values across 9,764 directed edges, up to
  14 rows sharing one value, because 1b split sections at intersections and duplicated
  bidirectional roads. It is used only as a human-facing reference back to the source shapefile;
  `id` and `physical_edge_id` are the keys.
- `NODO_INI` / `NODO_FIN` are numeric node codes, not the place names `naziv_poce` / `naziv_zavr`
  carried. Printed output therefore identifies roads by `NOMBRE` (e.g. "Ruta Nacional No. 32")
  plus node codes. Deriving readable endpoints by spatially joining section ends to the locality
  layer remains a possible improvement; it was not implemented.

### Known modelling caveat carried over

For isolated OD pairs the distance disruption is set to the removed road's own length, since no
route exists from which to measure a detour. This shows up in the results — Ruta Nacional No. 3
records a 989-minute average delay against a 0.6 km average detour. The delay is meaningful; the
detour figure for isolating roads is a placeholder. This behaviour is inherited from the Serbian
implementation and is documented in the notebook rather than changed.

## Prerequisite

The `CENTROS_POBLACION` files must be hydrated from OneDrive before implementation can begin or be tested. Until then the population half of this notebook cannot be written against a verified schema — `INEC_PROY` and EPSG:8908 are known, but the geometry type and locality-name field are not, and §3's audit output is what settles them.
