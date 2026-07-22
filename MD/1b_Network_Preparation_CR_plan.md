# Plan: adapt `1b_Network_Preparation_CR.ipynb` to Costa Rica

Target notebook: `notebooks/1b_Network_Preparation_CR.ipynb`

Implementation status: completed in `notebooks/1b_Network_Preparation_CR.ipynb`, with reusable workflow functions in `src/network_preparation_cr.py`.

## Objective

Replace the inherited Serbia-specific workflow with a Costa Rica workflow that reads the modified cantonal network, fills its existing AADT fields, constructs a directed and strongly connected routing network, and writes the requested GeoPackages and AADT figures.

Primary input:

```python
modified_cantonal_roads_path = (
    data_path / "CR_RED_TOPOGRAFICA" / "cr_red_topografica.shp"
)
```

Primary outputs:

```text
intermediate_results/gpkg/network/main_network_directed.gpkg
intermediate_results/gpkg/giant_component_dropped_roads.gpkg
figures/{traffic_type}_aadt_map.png
figures/AADT_categories_combined.png
figures/giant_component_dropped_roads.png
```

## Source-data audit

The implementation should start by printing and validating this baseline rather than silently assuming the Serbia schema:

| Check | Observed in the current CR shapefile |
|---|---:|
| Features | 4,764 |
| CRS | EPSG:8908, CR-SIRGAS / CRTM05 (metres) |
| `LineString` features | 4,634 |
| `MultiLineString` features | 130 |
| Null/empty/invalid geometries | 0 / 0 / 0 |
| Exact duplicate rows including geometry | 0 |
| `DIRECCION = Bidireccional` | 4,397 |
| `DIRECCION = Unidireccional` | 247 |
| Null `DIRECCION` | 120 |
| Non-null `VEL_KMH` | 4,626 |
| Null `VEL_KMH` | 138 |
| Observed speed values | 20, 40, 60, 80 km/h |
| AADT non-null counts | 3,023–3,030, depending on category |

The source already contains `T9`–`T15`, `VEL_KMH`, `DIRECCION`, `NODO_INI`, and `NODO_FIN`. There is therefore no separate AADT merge and no Serbia/Kosovo filtering step.

## CR field contract

Retain the original CR fields and add descriptive aliases for downstream readability:

| Source | Descriptive field | Meaning |
|---|---|---|
| `T9` | `motorcycles` | Motorcycles |
| `T10` | `pickup_trucks` | Pickup trucks |
| `T11` | `passenger_cars` | Passenger cars / normal cars |
| `T12` | `buses` | Buses |
| `T13` | `light_trucks` | Light trucks |
| `T14` | `medium_trucks` | Medium trucks |
| `T15` | `heavy_trucks` | Heavy trucks |
| derived | `total_aadt` | Row sum of the seven categories after imputation |

Keep `T9`–`T15` in the output; do not replace them with aliases. Preserve `ID_TRAMO` and `TRAMO_UID` as source identifiers, create `source_part_id` after exploding multipart features, and create `physical_edge_id` after intersection splitting. The latter is the stable identifier used to pair forward/reverse directed edges.

Do **not** manufacture an `articulated_vehicles` field. The CR source has no documented equivalent. The current Serbia criticality code expects that field and uses Serbia-specific occupancy/loading assumptions; adapting those formulas is a separate downstream task.

## Proposed notebook structure

### 0. Replace the introductory Markdown

- Change the country and schema descriptions from Serbia to Costa Rica.
- Document the single CR input shapefile and requested GeoPackage outputs.
- Remove `PGDS_2024.shp`, Natural Earth/Kosovo, Parquet, File GDB, and EPSG:6316 references.
- Document the AADT-imputation and direction assumptions below.
- Clear all stale Serbia outputs and execution counts. The current notebook contains about 8.8 MB of embedded output, including Serbia paths and figures.

### 1. Imports, paths, and constants

- Retain GeoPandas, pandas, NumPy, Shapely, igraph, matplotlib, contextily, and the functions imported from `src.simplify`.
- Remove unused Serbia/GDB-specific imports such as `save_gdb_layer` and `Geod`.
- Define:

```python
SNAP_TOLERANCE_M = 2.0
SNAP_SEARCH_BUFFER_M = 30.0
SNAP_MAX_ITERATIONS = 20
MIN_GIANT_COMPONENT_LENGTH_PCT = 95.0
AADT_COLUMNS = ["T9", "T10", "T11", "T12", "T13", "T14", "T15"]
```

- Create `figures/` and `intermediate_results/gpkg/network/` with `parents=True`.
- Use the notebook-safe project-root resolution already used elsewhere, but assert the input exists before reading it.

### 2. Load and validate the CR network

- Read `modified_cantonal_roads_path` with GeoPandas.
- Assert the expected schema, non-null CRS, and projected metre units.
- Reproject to EPSG:8908 only if required; never calculate length or snapping distances in a geographic CRS.
- Validate null, empty, invalid, and zero-length geometries. Stop with a detailed table if any are present.
- Preserve the original row index as `source_row_id`.
- Explode the 130 multipart features to `LineString` parts before snapping/topology. Add `source_part_id` so every resulting physical edge has a stable unique identifier.
- Run exact duplicate diagnostics, but only remove provably identical attributes-and-geometry duplicates. Do not deduplicate on `ID_TRAMO` or `TRAMO_UID`, because those identifiers are not unique in the source.
- Compare geometric length against `LONGITUD` for diagnostics only. Use geometry in EPSG:8908 as the authoritative routing length because `LONGITUD` contains substantial outliers.

### 3. Correct and run iterative endpoint snapping

Keep the requested 2 m tolerance, 30 m candidate buffer, and 20-iteration maximum, but replace the current false-positive behavior:

- Search candidates with a spatial index.
- For endpoint-to-endpoint gaps, move the endpoint to the candidate endpoint.
- For endpoint-to-segment gaps, move the endpoint to the actual nearest point on the candidate segment. `shapely.snap(line, other_line, tolerance)` alone is insufficient because it normally snaps to reference vertices, not an arbitrary interior point.
- Count a snap only when the output coordinates actually changed.
- Rebuild the spatial index after each iteration.
- Stop at zero changes or after exactly 20 iterations (`>=`, not `> 20`).
- Print per-iteration counts and save a small diagnostic table of changed source IDs and distances.
- Assert that no snap exceeds 2 m.

### 4. Build topology once, after all geometry edits

- Create `Network(edges=roads)`.
- Add endpoints.
- Split roads where a network endpoint falls on the interior of another road and at valid intersection nodes, carrying all CR attributes and AADT columns onto split parts.
- Re-add/deduplicate endpoints, assign integer edge/node IDs, and derive `from_id` / `to_id`.
- Assert no topology IDs are `-1`, null, or self-loops unless a self-loop is explicitly retained and documented.
- Report node/edge counts, weak components, degree-one nodes, and the number of newly split edges.
- Review geometric X-crossings carefully: a grade-separated crossing must not become an at-grade routing junction without supporting node evidence.

The old “rebuild topology on Serbia network” step is unnecessary. AADT filling and plotting do not alter geometry, so rebuilding the same topology would only risk changing IDs. If later implementation introduces any geometry edit after this cell, topology must instead be rebuilt immediately after that edit.

### 5. Use the source AADT and fill missing values

There is no AADT load/merge cell. Start from `T9`–`T15` already attached to the CR roads.

Important rules:

- Treat zero as an observed value, not as missing.
- Coerce the seven fields to numeric and reject negative/infinite values.
- Fill each category independently because the seven fields have slightly different missingness.
- Record provenance with `aadt_missing_before`, `aadt_imputed`, and per-category source fields such as `T9_fill_source` (`observed`, `endpoint_mean`, `class_median`, or `global_median`).

Pass 1 — topology-neighbour interpolation:

- Use `from_id` / `to_id` adjacency rather than an O(n²) geometry scan.
- For a missing category, require at least one known neighbouring value at both endpoints.
- Calculate the mean at the start node and the mean at the end node, then assign the mean of those two endpoint means.
- Do not let a missing value in one category prevent another category from being filled.

Pass 2 — class median and neighbour cap:

- For still-missing values, use the median for the CR `CLASE` (`Primaria`, `Secundaria`, `Terciaria`, or `Local`), not Serbia's `kategorija`.
- Where `CLASE` is null or has no usable median, use the overall median for that AADT category and flag it as `global_median`.
- Cap an imputed value at the maximum known value on touching roads, category by category, when such neighbours exist.
- Do not apply a cap when no known touching value exists.

After both passes:

- Recompute the descriptive aliases and `total_aadt` from the seven filled categories.
- Assert all AADT output fields are finite, non-negative, and non-null.
- Print before/after completeness, fill-method counts, and class-level summaries.
- Keep an `aadt_imputed` flag in the final network so observed and modelled traffic can be distinguished downstream.

### 6. Generate CR AADT figures

- Plot the physical, pre-direction-duplication network so bidirectional roads are not drawn twice.
- Produce one map for each of the seven descriptive traffic fields using stable filenames:

```text
motorcycles_aadt_map.png
pickup_trucks_aadt_map.png
passenger_cars_aadt_map.png
buses_aadt_map.png
light_trucks_aadt_map.png
medium_trucks_aadt_map.png
heavy_trucks_aadt_map.png
```

- Replace Serbia-specific fixed bins with documented, data-driven breaks for each CR category (unique quantiles with a fallback when quantile edges collapse). Print the actual thresholds used.
- Use a safe basemap helper so temporary tile/network failure does not abort network preparation.
- Use the full network extent consistently across panels.

There are seven CR categories, not six. The combined figure should therefore be a 4×2 layout containing seven panels and one disabled axis, still saved as `figures/AADT_categories_combined.png`. A six-panel layout would silently omit one requested category.

### 7. Normalize `DIRECCION` and construct directed edges

- Normalize case, accents, and whitespace, then accept only `Bidireccional` and `Unidireccional` as observed values.
- Preserve the original value in `DIRECCION_raw`.
- The 120 null direction values require an explicit policy. Use `Bidireccional` as the routing fallback, set `direction_imputed = True`, and report the affected source IDs. This avoids arbitrarily deleting one travel direction, but the assumption must remain visible in the output.
- Treat the digitized source geometry direction as the permitted direction for `Unidireccional` features. Preserve `NODO_INI` / `NODO_FIN` and generate a one-way QA map or sample because the current data contains no independent forward/reverse code.
- For `Bidireccional` roads:
  - divide the seven AADT categories, descriptive aliases, and `total_aadt` by two exactly once;
  - keep the forward edge;
  - append a reversed copy with `from_id` and `to_id` exchanged.
- For `Unidireccional` roads, retain only the source-direction edge and do not halve AADT.
- Reverse geometry with `shapely.reverse` (or an equivalent geometry-type-safe helper), not `LineString(row.geometry.coords[::-1])`.
- Create new unique directed-edge IDs after concatenation, while retaining `source_part_id`, `physical_edge_id`, and a `direction_side` field (`forward`/`reverse`).
- Assert every bidirectional `physical_edge_id` has exactly two directed edges and every unidirectional `physical_edge_id` has exactly one.

### 8. Assign speed and compute travel time

Use `VEL_KMH` as the primary speed source. The data already provides speed for 4,626 of 4,764 input features, including meaningful within-class variation, so a Serbia-style class lookup would destroy information.

Speed policy:

1. Preserve every finite positive source `VEL_KMH` value, including the two 20 km/h observations.
2. For missing speed on a known `CLASE`, use that class's median observed `VEL_KMH` and flag `speed_source = "class_median"`.
3. For a still-missing/unclassified value, use 60 km/h and flag `speed_source = "statutory_default_60"`.

Costa Rica's current Traffic Law states that posted/demarcated limits control; in the absence of signage/demarcation the general limit is 60 km/h, or 50 km/h in high-density urban areas, with 25 km/h applying in specified pedestrian/school/health/activity areas. The shapefile has no reliable urban-density or special-zone flag, so 60 km/h is the auditable final fallback—not a claim that every unclassified segment is legally signed at 60 km/h. Source: [Ley de Tránsito 9078, Article 98 (Sistema Costarricense de Información Jurídica)](https://pgrweb.go.cr/scij/Busqueda/Normativa/Normas/nrm_articulo.aspx?nValor1=1&nValor2=73504&nValor3=125198&nValor5=99&param1=NRA&strTipM=FA).

Calculate vectorized fields in EPSG:8908:

```python
road_length = geometry.length / 1_000  # km
speed = resolved VEL_KMH               # km/h
fft = road_length / speed              # hours
```

- Compare `road_length` with source `LONGITUD` only as a diagnostic.
- Assert `road_length > 0`, `speed > 0`, and finite `fft > 0`.
- If validation fails, print `source_part_id`, source IDs, `CLASE`, `VEL_KMH`, resolved speed/source, lengths, direction, and geometry type, then stop. Do not silently correct invalid `fft`.

### 9. Extract the strongly connected giant component

- Build an explicit directed igraph from `from_id` and `to_id`.
- Request strong components explicitly (`mode="strong"`) rather than relying on a library default.
- Identify the largest strong component by vertex membership and retain only edges whose two endpoints belong to it.
- Report retained/dropped vertices and directed edges.
- Report both directed-edge length and unique physical length using `source_part_id`, so duplication of bidirectional roads does not distort the physical-network diagnostic.
- Build `dropped_gdf` before any assertion.
- Always save dropped roads when non-empty and always create the included-versus-dropped diagnostic map. If nothing is dropped, print that result and document that no non-empty dropped layer exists.
- Save diagnostic outputs before enforcing the threshold so they remain available when the run stops.
- Assert that at least 95% of unique physical network length is represented by the giant component.

### 10. Save GeoPackages and run final contract checks

- Reset the retained edge IDs one final time without changing `from_id` / `to_id`.
- Keep EPSG:8908 in the output so length units and topology geometry remain internally consistent.
- Write with explicit layer names and the GPKG driver:

```python
network.to_file(
    gpkg_dir / "main_network_directed.gpkg",
    layer="main_network_directed",
    driver="GPKG",
    index=False,
)

dropped_gdf.to_file(
    gpkg_dir / "giant_component_dropped_roads.gpkg",
    layer="giant_component_dropped_roads",
    driver="GPKG",
    index=False,
)
```

- Re-open each written layer and verify row count, CRS, geometry type, required columns, and non-null critical fields.
- Confirm no duplicate directed-edge IDs and no orphan `from_id` / `to_id` values.
- Confirm the output contains the expected 1-or-2 directed-edge multiplicity per `physical_edge_id`.
- Print a final manifest containing absolute output paths, layer names, row counts, CRS, and file sizes.

## Acceptance criteria

The notebook adaptation is complete when a clean-kernel run satisfies all of the following:

- It contains no executable Serbia, Kosovo, PGDS, `kategorija`, `smer_gdf1`, Parquet, File GDB, or EPSG:6316 logic.
- It runs from top to bottom against `cr_red_topografica.shp` without manual state from another notebook.
- All topology IDs are valid and all final edges have finite, positive `road_length`, `speed`, and `fft`.
- All seven directional AADT categories and `total_aadt` are finite, non-negative, and retain imputation provenance.
- Direction expansion produces exactly two edges for each bidirectional `physical_edge_id` and one for each unidirectional `physical_edge_id`.
- The strongly connected giant component retains at least 95% of unique physical network length, or the notebook stops only after saving a useful dropped-road GeoPackage and map.
- The requested main-network GeoPackage and all seven individual AADT maps exist.
- `AADT_categories_combined.png` contains all seven CR traffic categories.
- GeoPackages can be reopened and pass the final schema/count/CRS checks.

## Downstream compatibility note

The requested GeoPackage location and CR traffic schema do not match the repository's current Serbia-oriented `NetworkConfig` and criticality formulas. After this notebook is implemented, a separate follow-up should:

- point downstream CR workflows to `intermediate_results/gpkg/network/main_network_directed.gpkg`;
- replace Serbian identifiers/categories in their required-column lists;
- define CR-appropriate passenger occupancy and freight-loading treatment for motorcycles, pickups, and the absence of an articulated-vehicle category.

Until that follow-up is completed, the output is a valid CR directed routing network but is not a drop-in input for the unchanged Serbia criticality scripts.
