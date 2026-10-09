# Shared CR map style — `src/map_style_cr.py`

One function, `style_cr_map(ax, crs, ...)`, finishes every Costa Rica map. It is called
**after** the data layers are drawn. The template is the OSM road map in
`1a_Network_Figures_CR.ipynb`.

## What it applies

| Element | Setting |
|---|---|
| Frame | Mainland Costa Rica bounding box + 2 % padding, equal aspect, axes off |
| Basemap | CARTO Positron, **label-free** variant, alpha 0.4, attribution line bottom-left |
| Outside fade | Everything outside Costa Rica (Nicaragua, Panama, sea) under white at alpha 0.5 |
| Outline | Mainland boundary, `#333333`, 1.0 pt |
| Cities | San José, Liberia, Limón — black dot, bold label with white halo |
| Legend | Upper right; fancy box, shadow, white at alpha 0.9, `#cccccc` edge |

Draw order (zorder): basemap −1 · data 0–10 · fade 20 · outline 21 · cities 22 · legend 30.
Notes drawn in axes coordinates (e.g. a statistics box) need `zorder=30` to sit above the fade.

## Decisions

| # | Decision | Why |
|---|---|---|
| D1 | Cities = San José, Liberia, Limón | Spread across the country: centre, Pacific north-west, Caribbean (user choice, 2026-09-25) |
| D2 | San José is a hard-coded point (−84.0796, 9.9326, Catedral Metropolitana) | `CENTROS_POBLACION` has no point for the capital: it is split into district heads (Carmen, Catedral, Merced, …). Liberia and Limón are the IGN `Ciudad/Cabecera de Provincia` points from that layer |
| D3 | Boundary = IDS 2023 districts dissolved, mainland only | No national boundary file ships with `input_files/`. Parts farther than 100 km from the largest part are dropped (Isla del Coco). Moved here from `1a` |
| D4 | Frame = mainland boundary box | Was the modified cantonal network's box in `1a`, the road network's box + 0.15° in `4a`, and unset elsewhere. All 493 localities lie within 1 km of the mainland boundary, so nothing mapped is cut off |
| D5 | Outside faded, not masked | Neighbouring countries stay faintly readable (user choice) |
| D6 | Label-free Positron | Positron's own place names ("LIBERIA", "LIMÓN") ghosted behind the city labels |
| D7 | Legend font follows map width | 10 / 12 pt on a 9.3 in-wide map (the 12 × 10 in template), scaled down to 70 % on narrower maps. At a fixed 10 / 12 pt the legend covered the north-east of the country on 9–11 in figures. Multi-panel maps pass 8 / 9 pt explicitly |
| D8 | Shared legend of a multi-panel figure goes in the figure's upper-right panel | Replaces the `fig.legend(loc="lower center")` strips in `5a` and `5c` |
| D9 | A second legend on one map goes lower left | Only `2` (snapped localities) |
| D10 | Colour bars are left where they were | They are not legends; `4a` and `2` keep theirs |

## API key

CARTO serves "API KEY REQUIRED" placeholder tiles without a key (checked 2026-09-25 by
fetching a tile with and without it). The key is read from, in order:

1. the environment variable `CARTO_BASEMAP_API_KEY`;
2. the file `.carto_api_key` in the repo root (gitignored).

With neither, the module warns and uses the keyless Esri World Gray Canvas. The key was
previously hard-coded in `1a`; it was never committed.

Tiles are cached on disk in `intermediate_results/tile_cache/`, so only the first run
fetches them. First fetch for the national frame: ~150 s; afterwards ~10 s per map.

## CRS

`crs` is the CRS the data on the axis were drawn in. Used in the notebooks:
3857 (`1a`, `1b`, `2`, `2b`, `5c`), 8908 (`5a`, `5b`, `5d`), 4326 (`4a`, raster-native).
contextily reprojects the tiles when the axis is not in 3857.

## Where it is used

| Notebook / module | Maps |
|---|---|
| `1a_Network_Figures_CR` | OSM, national, modified cantonal, 3-panel comparison, missing AADT |
| `src/network_preparation_cr.py` (`1b`) | 7 AADT maps + 4×2 combined, direction QA, giant component |
| `2_Main_Network_Criticality_Analysis_CR` | 2×2 SPOF (×2), snapped localities, modelled vs observed AADT, residual maps (×4), IDS districts |
| `2b_Socioeconomic_Criticality_CR` | quintile panels + IDS context panel |
| `4a_Hazard_maps_CR` | CHIRPS anomaly panel, Rx1month trend, flood exposure correction, hazard rasters, hazard roads |
| `5a_Main_Network_Hazard_Criticality_CR` | VHL 1×3, flood exceedance, multi-hazard score |
| `5b_Run_Flood_Scenarios_Accessibility_CR` | worst-scenario map |
| `5c_Plot_Flood_Scenarios_Accessibility_CR` | basin depth, impact maps, 2×2 |
| `5d_Combined_Climate_Criticality_CR` | H/T/A 3-panel, combined index |

The `3d` notebooks contain charts only.

## Side effects of adopting it

* `4a`: degree ticks and grid removed (`format_axes`, `frame_map` deleted); the grey
  country fill is replaced by the basemap.
* `2`: `USE_BASEMAP` is now `True` (tiles are cached, so the "cell appears to hang" problem
  only applies to the first run). The IDS district map is now framed on the mainland; it
  previously included Isla del Coco.
* `5c`: basemap changes from Esri World Gray Canvas to keyed Positron.
* `1b`: its maps previously requested Positron without a key, i.e. placeholder tiles.

## Verification

* `1a`, `2`, `2b`, `4a`, `5a`, `5c`, `5d` re-executed end to end in `criticality2`.
* `1b` and `5b` were **not** re-executed (they rebuild the routing network and the flood
  scenarios). Their map code was run against the existing outputs instead, writing to a
  scratch folder, so `figures/*_aadt_map.png`, `AADT_categories_combined.png`,
  `oneway_direction_qa.png`, `giant_component_dropped_roads.png` and
  `flood_scenario_access_delta_map.png` still show the old style until those notebooks
  are next run.
