"""
T1 - Prepare Network (Costa Rica)
---------------------------------
Script-tool version of notebook 1b_Network_Preparation_CR.ipynb.

Cleans the modified cantonal road network, snaps and splits it into a topology,
imputes missing AADT (T9-T15), expands bidirectional roads, adds speed and
free-flow travel time and keeps the strongly connected giant component.

All processing is done by src/network_preparation_cr.py - the same functions the
notebook calls - so the toolbox and the notebook give the same network.  This
file only reads the dialog parameters, points the library at the chosen paths
and writes the outputs.

Tool parameters (order matters, see read_parameters):
    0  roads_in         Feature class / shapefile  Modified cantonal road network (EPSG:8908)
    1  output_folder    Folder                     A run sub-folder is created inside it
    2  snap_tolerance_m Double  (2.0)              Endpoints closer than this are merged
    3  snap_search_m    Double  (30.0)             Search buffer for endpoint-to-segment snapping
    4  snap_max_iter    Long    (20)               Maximum snapping passes
    5  min_giant_pct    Double  (95.0)             Abort if the giant component keeps less physical length
    6  default_speed    Double  (60.0)             Statutory speed (km/h) when speed and class median are missing
    7  main_network     Feature class (derived)    main_network_directed
    8  dropped_roads    Feature class (derived)    giant_component_dropped_roads
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cr_common as cr


# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------


def make_config(source_path, run_dir, scratch, snap_tolerance_m, snap_search_buffer_m,
                snap_max_iterations, min_giant_component_length_pct, statutory_default_speed_kmh):
    """Notebook config class with its fixed repo paths replaced by the tool's paths"""
    from src.network_preparation_cr import CRNetworkPrepConfig

    # 1) The notebook config derives every path from base_dir; override the ones the tool must control
    @dataclass(frozen=True)
    class ToolConfig(CRNetworkPrepConfig):
        source: Optional[Path] = None
        run: Optional[Path] = None

        @property
        def input_path(self):
            return self.source

        @property
        def figure_path(self):
            return self.base_dir / "figures"

        @property
        def gpkg_dir(self):
            return self.run

    # 2) base_dir is scratch: ensure_output_dirs() creates empty folders there, not in the user's data
    return ToolConfig(
        base_dir=scratch,
        snap_tolerance_m=snap_tolerance_m,
        snap_search_buffer_m=snap_search_buffer_m,
        snap_max_iterations=snap_max_iterations,
        min_giant_component_length_pct=min_giant_component_length_pct,
        statutory_default_speed_kmh=statutory_default_speed_kmh,
        add_basemap=False,
        source=source_path,
        run=run_dir,
    )


def stage_source(roads_in, scratch):
    """Return a path the notebook loader can read: shapefiles as is, anything else via a temp GeoPackage"""
    # 1) Plain shapefile / GeoPackage file: read in place
    container, layer = cr.split_container(cr.resolve_input(roads_in))
    if layer is None and container.lower().endswith(".shp"):
        return Path(container)

    # 2) Geodatabase feature class, GeoPackage layer, map layer: copy to a one-layer GeoPackage
    frame = cr.read_vector(roads_in)
    staged = scratch / "roads_source.gpkg"
    frame.to_file(staged, layer="roads_source", driver="GPKG", index=False)
    return staged


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main():
    # 1) Read the script parameters from ArcGIS (or --options outside it)
    p = cr.read_parameters([
        ("roads_in", ""),
        ("output_folder", ""),
        ("snap_tolerance_m", "2.0"),
        ("snap_search_m", "30.0"),
        ("snap_max_iter", "20"),
        ("min_giant_pct", "95.0"),
        ("default_speed", "60.0"),
    ])

    # 2) Validate the minimum required parameters
    if not p["roads_in"]:
        raise ValueError("A road network layer is required.")
    if not p["output_folder"]:
        raise ValueError("An output folder is required.")
    cr.require_packages(["geopandas", "shapely", "igraph", "numpy", "pandas", "matplotlib"])

    # 3) Create the timestamped run folder (BSA2 convention) and log the parameters
    stamp = cr.timestamp()
    out_root = Path(p["output_folder"])
    run_dir = out_root / f"T1_prepare_network_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    cr.write_run_config(out_root, "T1", stamp, p)

    # 4) Run the notebook workflow (stages of 1b, figures off)
    from src.network_preparation_cr import (
        add_speed_and_travel_time,
        build_topology,
        create_directed_edges,
        extract_strong_giant_component,
        fill_missing_aadt,
        load_and_validate_network,
        save_outputs,
        snap_network_iteratively,
    )

    t0 = time.perf_counter()
    with cr.scratch_dir() as scratch, cr.messages_from_print():
        config = make_config(
            stage_source(p["roads_in"], scratch), run_dir, scratch,
            float(p["snap_tolerance_m"]), float(p["snap_search_m"]), int(float(p["snap_max_iter"])),
            float(p["min_giant_pct"]), float(p["default_speed"]),
        )
        roads, _ = load_and_validate_network(config)
        snapped, snap_log = snap_network_iteratively(
            roads,
            tolerance_m=config.snap_tolerance_m,
            search_buffer_m=config.snap_search_buffer_m,
            max_iterations=config.snap_max_iterations,
        )
        snap_log.to_csv(run_dir / "endpoint_snap_log.csv", index=False)
        physical_edges, _, _ = build_topology(snapped)
        physical_edges, completeness, fill_sources = fill_missing_aadt(physical_edges)
        completeness.to_csv(run_dir / "aadt_completeness.csv")
        fill_sources.to_csv(run_dir / "aadt_fill_sources.csv")
        directed, _ = create_directed_edges(physical_edges)
        directed, _ = add_speed_and_travel_time(directed, config)
        giant, dropped, giant_stats = extract_strong_giant_component(directed)

        # 5) Writes the dropped-road diagnostics first, enforces the giant-component rule, re-opens the result
        save_outputs(directed, giant, dropped, giant_stats, config, show=False, make_figures=False)
    cr.msg(f"Finished in {time.perf_counter() - t0:.0f} s")

    # 6) Return the outputs to the tool dialog
    main_gpkg = run_dir / "main_network_directed.gpkg"
    dropped_gpkg = run_dir / "giant_component_dropped_roads.gpkg"
    cr.set_outputs(7, [cr.layer_path(main_gpkg, "main_network_directed"),
                       cr.layer_path(dropped_gpkg, "giant_component_dropped_roads")])
    cr.msg(f"Computation complete: {main_gpkg}")


if __name__ == "__main__":
    main()
