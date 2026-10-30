# ArcGIS toolbox: inputs and assumptions to run T1 (notebook 1b) and T2 (notebook 2)

Companion to `MD/arcgis_toolbox_plan.md`. Code: `arcgis_toolbox/` (`cr_common.py`,
`T1_prepare_network.py`, `T2_spof_criticality.py`).

## A. Environment

| Requirement | Why | Status |
|---|---|---|
| Cloned ArcGIS Pro conda env with `geopandas`, `shapely` ≥ 2, `numpy`, `pandas`, `scipy`, `python-igraph`, `matplotlib`, `fiona` | T1 imports `src/network_preparation_cr.py` unchanged (geopandas / shapely / igraph / matplotlib; reads the shapefile with `engine="fiona"`). T2 uses geopandas, shapely `STRtree`, igraph, numpy, pandas | Tested only in `criticality2` (Python 3.14, geopandas 1.1.2, igraph 1.0.0, shapely 2.1.2). **Not tested in an ArcGIS Pro env** — no Pro here |
| Repo checkout on disk, toolbox inside it (`<repo>/arcgis_toolbox/`) or `CR_REPO_ROOT` set | T1 imports `src.network_preparation_cr` (and, transitively, `src/map_style_cr.py`) | Verified by running |
| `PROJ_DATA` / `GDAL_DATA` must not point at another install | In this shell they pointed at `miniforge3` and `to_crs` failed with a proj.db version error. Pro's own env sets these correctly; only matters when testing outside Pro | Seen once, worked around for the tests |
| Local (not OneDrive-placeholder) copies of all inputs | Notebook 2 warns about this; cloud placeholders cannot be opened | Applies to both |

## B. T1 Prepare Network (notebook 1b)

### Inputs
| Parameter | Default | Requirement |
|---|---|---|
| Road network | `input_files/CR_RED_TOPOGRAFICA/cr_red_topografica.shp` | Lines. Required columns: `ID_TRAMO, TRAMO_UID, CLASE, DIRECCION, VEL_KMH, NODO_INI, NODO_FIN, T9…T15`. Must have a CRS (reprojected to EPSG:8908 if different). Geometries must all be valid, non-empty, positive length — otherwise the tool stops and lists them. A geodatabase feature class or map layer is accepted (copied to a temporary GeoPackage first) |
| Output folder | – | Writable. A `T1_prepare_network_<stamp>/` run folder and `Loc/run_config_T1_<stamp>.loc` are created |
| Snap tolerance / search buffer / max passes | 2 m / 30 m / 20 | Notebook values |
| Minimum giant-component length | 95 % | Tool aborts after writing the dropped-road diagnostics if less physical length is retained |
| Statutory default speed | 60 km/h | Last-resort speed |

### Outputs (in the run folder, notebook file and layer names)
`main_network_directed.gpkg` (layer `main_network_directed`), `giant_component_dropped_roads.gpkg`,
`endpoint_snap_log.csv`, `aadt_completeness.csv`, `aadt_fill_sources.csv`.
**Not produced** (figure-only in the notebook): the seven AADT maps, the combined AADT figure, the
one-way direction QA map, the giant-component map.

### Assumptions (all inherited from 1b, none new)
1. EPSG:8908 end to end.
2. Zero AADT is observed data; only nulls are imputed (endpoint-neighbour mean → `CLASE` median → global median, capped by touching roads).
3. Missing `DIRECCION` = bidirectional (`direction_imputed`); two-way AADT is halved per direction.
4. Supplied speeds kept; missing → `CLASE` median → 60 km/h. `LONGITUD` is never used as routing length.
5. Only the strong giant component is kept (here 9,764 of 9,912 directed edges, 98.28 % of physical length).
6. Two assumptions of the tool itself: output is GeoPackage (CR convention), not a file geodatabase; each run writes a new timestamped folder, so downstream tools must be pointed at the run folder.

## C. T2 SPOF Criticality (notebook 2, sections 2–7 and 9)

### Inputs
| Parameter | Default | Requirement |
|---|---|---|
| Directed network | T1 `main_network_directed` | EPSG:8908, metric. Columns: `from_id, to_id, id, physical_edge_id, direction_side, road_length, fft, speed, total_aadt, CLASE`, the seven vehicle-category columns, and for the output also `ID_TRAMO, TRAMO_UID, ID_RUTA, NOMBRE, ADMIN, NODO_INI, NODO_FIN, DIRECCION, source_part_id, speed_source, aadt_imputed, direction_imputed`. `fft` in **hours**, `road_length` in **km**. Must be strongly connected, one edge per one-way road and two per two-way road per `physical_edge_id` |
| Localities | `input_files/CENTROS_POBLACION/centros_poblados_localidades.shp` | Points (polygons → centroids). CRS must exist; non-8908 is reprojected with a warning (the notebook asserts 8908 instead) |
| Population field / name field | `INEC_PROY` / `NOMBRE` | Rows with null or ≤ 0 population are dropped. `CANTÓN` is appended to the label if present |
| Output folder | – | Run folder `T2_spof_criticality_<stamp>/`; percolation cache in `<output folder>/cache/` |
| `DIST_DECAY` / `MAX_TRIPS` / isolation factor / far-snap limit | 1.0 / 25,000 / 2.0 / 5,000 m | Notebook constants. **They must equal the values used by notebook 2b**, which rebuilds the same demand |
| Use cache | true | Re-uses a percolation whose inputs hash identically (network ids, `fft`, `road_length`, OD vertices, population, constants, road count) |
| Test: first N physical roads | 0 (all) | Test mode only; outputs then cover only those roads |

### Outputs (run folder)
`criticality_results.gpkg` (layer `criticality_results`, per directed edge),
`physical_criticality_results.gpkg` (layer `criticality`, per physical road),
`od_nodes.gpkg` (layer `od_nodes`; new — snapped, aggregated OD nodes with population, label, `n_localities`).
**Not produced:** all SPOF figures, the summary statistics (notebook §10), the AADT-vs-criticality
regression and the modelled-vs-observed AADT comparison, the IDS quintile material (→ later tool for 2b).

### Assumptions (all inherited from notebook 2)
1. Gravity demand ∝ Pop_o × Pop_d × exp(−decay × distance / max distance), scaled to `MAX_TRIPS` and rounded **up**.
2. Demand is used only as weights; its absolute scale cancels except through the `ceil` rounding.
3. Isolation penalty = ceil(factor × maximum baseline OD time) hours (21 h with the CR data); an isolated OD pair gets that time.
4. For isolated pairs the *distance* disruption is the removed road's own length — a placeholder, not a detour.
5. A road that delays no OD pair gets exactly 0, not NaN (≈ 40 % of roads).
6. Far-snapping localities (> 5 km) are **kept and flagged**, not dropped.
7. Passengers per vehicle: motorcycles 1.2, cars 2.0, pickups 2.0, buses 30. Tonnes per vehicle: pickups 0.3, light 1.2, medium 3.8, heavy 8.0. `pickup_trucks` counts on both sides; there is no articulated class, so CR tonnage is not comparable with Serbia's. These are constants in `T2_spof_criticality.py`, **not** tool parameters.
8. Traffic is summed over both directed edges when collapsing to the physical road; disruption is identical on both.
9. Locality-to-node snapping is the notebook's `STRtree.nearest` on node coordinates (user decision 4.3).
10. Tool-specific: results are written for the full network unless the test option is used; the cache key does not include the locality geometry, only the OD vertices and populations that result from it.
