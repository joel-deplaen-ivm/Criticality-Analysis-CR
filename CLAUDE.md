# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A **Costa Rica** adaptation of a road-network criticality and accessibility workflow that was
originally built for Serbia. Both live side by side:

- **Costa Rica (active work)** — `notebooks/*_CR.ipynb` and `src/network_preparation_cr.py`.
- **Serbia (inherited, reference only)** — unsuffixed `notebooks/*.ipynb`, `src/[1-5]*.py`,
  `src/config/network_config.py`, `run_all.py`, `ArcGIS_*/`, and most of `utils/`.

`README.md` documents the **Serbia** pipeline only — its input/output tables, paths and CRS do
not apply to the CR work. Default to the CR side unless asked otherwise, and do not edit Serbia
files to change CR behaviour.

The two halves genuinely differ: CRS (8908 vs 6316), output format (GeoPackage vs
Parquet + File GDB), conda env, and config style. Do not mix their conventions.

## Environment

```bash
~/opt/anaconda3/envs/criticality2/bin/python
```

`criticality2` (Python 3.14.2, geopandas 1.1.2) is the CR environment and the kernel of every
CR notebook except `4a_Hazard_maps_CR.ipynb`, which still runs on `criticality_env`. The conda
base env lacks the OSM GDAL driver, so always use the explicit interpreter path above.

`environment.yml` builds `criticality_env` — the **Serbia** environment, not the CR one.

## Running the analysis

CR work is notebook-driven. Run in numeric order: `1b` → `2` → `2b` → `3d` → `4a`.

Every CR notebook opens with a markdown cell listing its exact inputs, outputs and processing
steps. **Read that cell first** rather than tracing paths through the code.

`run_all.py` runs every `src/*.py` in sorted order — Serbia only, and it assumes
`intermediate_results/` is already populated.

There is no test suite and no linter configuration in this repository.

## CR conventions

- **CRS: EPSG:8908** (CR-SIRGAS / CRTM05, metres) end to end. Web Mercator is used only for
  basemap tiles.
- **Outputs**: `intermediate_results/gpkg/<stage>/*.gpkg`, where `<stage>` is `network` or
  `travel_disruptions`. Caches go to `intermediate_results/parquet/<stage>/`.
  The Serbia mirroring scheme (`parquet/` + `database/*.gdb` + `excel/`, see
  `src/config/network_config.py`) is **not** used on the CR side.
- **Paths**: each CR notebook sets `BASE_DIR = Path.cwd().parent` and defines its own path
  constants near the top. `src/config/network_config.py` is Serbia-only — never wire CR
  notebooks to it.
- **Caching**: expensive steps (SPOF percolation, OD matrices) write parquet caches and are
  skipped on re-run. Keep that pattern when adding steps.
- **Figures** go to `figures/`, named after the analysis (e.g. `SPOF_results_2x2.png`).
- **Maps**: draw the data, then finish every map with `style_cr_map(ax, crs, ...)` from
  `src/map_style_cr.py` — mainland frame, CARTO Positron basemap, faded surroundings, national
  outline, San José / Liberia / Limón, legend lower left. Do not call `cx.add_basemap` or
  `ax.legend` directly on a map. Decisions are in `MD/map_style_cr_plan.md`. The basemap key
  lives in `.carto_api_key` (gitignored) or `CARTO_BASEMAP_API_KEY`.

## Graph and routing model

- Directed `igraph` graph built on `from_id` / `to_id`.
- `physical_edge_id` groups the two directed edges of one physical road. Single-point-of-failure
  analysis removes the **group**, not an individual edge (5,012 physical roads / 9,764 directed
  edges).
- `fft` = `road_length / speed`, in hours; `road_length` is used for distance metrics.
- Model constants — `DIST_DECAY`, `MAX_TRIPS`, `ISOLATION_PENALTY_FACTOR`, `WORKING_EPSG` —
  must match between notebook `2` and `2b`, which reconstructs the same OD demand.

## Shared code

- `src/network_preparation_cr.py` — the CR-specific module (`CRNetworkPrepConfig`,
  `run_workflow`, snapping / topology / AADT-imputation helpers), driven by
  `1b_Network_Preparation_CR.ipynb`. Put reusable CR logic here, not in `utils/`.
- `src/map_style_cr.py` — the shared CR map style (`style_cr_map`, `add_cr_legend`,
  `get_cr_boundary`), imported by every CR notebook that draws a map.
- `utils/accessibility_functions.py` (step 3), `utils/hazard_functions.py` (step 4),
  `utils/criticality_functions.py` (step 5), `utils/arcgis.py` (.lyrx export) — written for
  Serbia, but imported by the CR step-3d and 4a notebooks. Check their CRS and path assumptions
  before reusing them.

## `MD/` planning documents

`MD/<notebook_stem>_plan.md` is written alongside each substantial CR notebook and records
verified numbers and method decisions (e.g. `MD/2b_Socioeconomic_Criticality_CR_plan.md`).
Keep the plan document in sync when the matching notebook changes.
`MD/branch_management.md` holds the git and cluster (rsync/SLURM) workflow.

## Data is not in git

`input_files/`, `intermediate_results/`, `figures/` are gitignored, as are `*.parquet`, `*.shp`,
`*.tif`, `*.nc`, `*.csv`. Nothing under them can be assumed present in a fresh clone.

Key CR inputs held locally under `input_files/`:

| Folder | Contents |
|---|---|
| `CR_RED_TOPOGRAFICA/` | Modified cantonal road network (`T9`–`T15` AADT classes, `DIRECCION`, `VEL_KMH`) |
| `CENTROS_POBLACION/` | Locality points, one per district, population in `INEC_PROY`, key `CÓDIGO_DTA` |
| `ids_2023_distrital/` | MIDEPLAN Índice de Desarrollo Social 2023 districts, `QUINTIL` I–V, key `CODIGO_DTA` |
| `salud/` | Health facilities (hospitals, EBAIS) for the accessibility notebooks |
| `flood_hazard_jrc/`, `landslide_susceptibility/`, `chirps_cr_*/` | Hazard layers |
| `costa-rica-260713.osm.pbf` | OSM extract for the OSM-based accessibility variant |

## Notebooks

Notebooks are committed **with** their outputs. Use `NotebookEdit` to modify them.
