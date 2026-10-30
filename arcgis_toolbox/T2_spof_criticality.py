"""
T2 - Single-Point-of-Failure Criticality (Costa Rica)
-----------------------------------------------------
Script-tool version of notebook 2_Main_Network_Criticality_Analysis_CR.ipynb
(sections 2-7 and 9; figures and summary statistics are not part of the tool).

Removes every physical road in turn (both directions), recomputes the
population-weighted OD travel times and reports demand-weighted time / distance
disruption plus vehicle, passenger and tonnage hours / kilometres lost.

Tool parameters (order matters, see read_parameters):
    0  network_in       Feature class   Directed network from T1 (main_network_directed, EPSG:8908)
    1  localities_in    Feature class   Locality points with population (EPSG:8908)
    2  pop_field        Field (INEC_PROY)
    3  name_field       Field (NOMBRE)  Used for OD-node labels only
    4  output_folder    Folder          A run sub-folder is created inside it
    5  dist_decay       Double (1.0)    Gravity-model decay
    6  max_trips        Long (25000)    Trips on the busiest OD pair
    7  isolation_factor Double (2.0)    Isolation penalty = ceil(factor x max baseline OD time, hours)
    8  far_snap_m       Double (5000)   Localities snapping further than this are flagged (kept, not dropped)
    9  use_cache        Boolean (true)  Re-use a previous percolation with identical inputs
    10 test_max_roads   Long (0)        TEST ONLY: process the first N physical roads (0 = all)
    11 directed_results Feature class (derived)  criticality_results (per directed edge)
    12 physical_results Feature class (derived)  criticality (per physical road)
    13 od_nodes         Feature class (derived)  OD nodes with snap diagnostics
"""

import time
import warnings
from pathlib import Path

import cr_common as cr


# ------------------------------------------------------------------
# Constants (stated as assumptions in the notebook; same values here)
# ------------------------------------------------------------------

WORKING_EPSG = 8908

# Passengers per vehicle, by category.
PASSENGER_FACTORS = {
    "motorcycles": 1.2,
    "passenger_cars": 2.0,
    "pickup_trucks": 2.0,
    "buses": 30.0,
}

# Tonnes of freight per vehicle, by category. No articulated class exists in the CR data.
FREIGHT_FACTORS = {
    "pickup_trucks": 0.3,
    "light_trucks": 1.2,
    "medium_trucks": 3.8,
    "heavy_trucks": 8.0,
}

REQUIRED_NETWORK_COLUMNS = [
    "from_id", "to_id", "id", "physical_edge_id", "direction_side",
    "road_length", "fft", "speed", "total_aadt", "CLASE",
    "motorcycles", "pickup_trucks", "passenger_cars", "buses",
    "light_trucks", "medium_trucks", "heavy_trucks",
]

# Columns written to the directed-edge result, in the notebook's order
PREFERRED_COLUMNS = [
    "id", "physical_edge_id", "source_part_id", "from_id", "to_id", "direction_side",
    "ID_TRAMO", "TRAMO_UID", "ID_RUTA", "NOMBRE", "CLASE", "ADMIN",
    "NODO_INI", "NODO_FIN", "DIRECCION",
    "road_length", "speed", "speed_source", "fft",
    "motorcycles", "pickup_trucks", "passenger_cars", "buses",
    "light_trucks", "medium_trucks", "heavy_trucks", "total_aadt",
    "aadt_imputed", "direction_imputed",
    "pct_isolated", "pct_unaffected", "pct_delayed",
    "average_time_disruption", "average_dist_disruption",
    "distance_disruption", "time_disruption",
    "vhl", "vkl", "phl", "thl", "pkl", "tkl",
    "geometry",
]

# Collapse to one row per physical road: traffic is summed over the road's directed
# edges (two-way figure), everything else is identical on both edges and taken once.
SUM_COLS = ["total_aadt", "motorcycles", "pickup_trucks", "passenger_cars", "buses",
            "light_trucks", "medium_trucks", "heavy_trucks",
            "vhl", "vkl", "phl", "thl", "pkl", "tkl"]
FIRST_COLS = ["geometry", "CLASE", "NOMBRE", "ID_TRAMO", "ID_RUTA", "ADMIN",
              "NODO_INI", "NODO_FIN", "DIRECCION", "road_length", "speed",
              "aadt_imputed", "pct_isolated", "pct_unaffected", "pct_delayed",
              "average_time_disruption", "average_dist_disruption",
              "distance_disruption", "time_disruption"]

RESULT_COLUMNS = ["physical_edge_id", "pct_isolated", "pct_unaffected", "pct_delayed",
                  "average_time_disruption", "average_dist_disruption",
                  "distance_disruption", "time_disruption"]


# ------------------------------------------------------------------
# Load and validate
# ------------------------------------------------------------------


def load_network(network_in):
    """Read the directed network and re-validate the T1 contract"""
    import numpy as np

    # 1) Read and check required columns
    edges = cr.read_vector(network_in)
    cr.msg(f"Directed edges : {len(edges):,}")
    missing = [c for c in REQUIRED_NETWORK_COLUMNS if c not in edges.columns]
    if missing:
        raise ValueError(f"Network is missing required columns: {missing} (run T1 first)")

    # 2) CRS must be metric EPSG:8908
    if edges.crs is None or edges.crs.to_epsg() != WORKING_EPSG:
        raise ValueError(f"Expected EPSG:{WORKING_EPSG}, found {edges.crs}")
    if edges.crs.axis_info[0].unit_name != "metre":
        raise ValueError("Working CRS must be metric")

    # 3) Routing fields: no nulls, positive length, finite positive fft, unique id
    for col in ["from_id", "to_id", "id", "physical_edge_id", "road_length", "fft"]:
        if edges[col].isna().any():
            raise ValueError(f"{col} contains nulls")
    if not (edges["road_length"] > 0).all():
        raise ValueError("road_length must be strictly positive")
    if not (np.isfinite(edges["fft"]).all() and (edges["fft"] > 0).all()):
        raise ValueError("fft must be finite and positive")
    if not edges["id"].is_unique:
        raise ValueError("edge id must be unique")

    # 4) CLASE carries nulls in the source; label them so they stay visible
    edges["CLASE"] = edges["CLASE"].fillna("Sin clasificar")
    cr.msg(f"Total directed length : {edges['road_length'].sum():,.0f} km")
    cr.msg(f"Unique physical roads : {edges['physical_edge_id'].nunique():,}")
    return edges


def graph_and_groups(edges):
    """Build the directed graph and the physical_edge_id -> [edge id] groups"""
    import pandas as pd

    # 1) Graph must be strongly connected (T1 guarantees it)
    graph = cr.build_graph(edges)
    cr.msg(f"Graph vertices : {graph.vcount():,}   edges : {graph.ecount():,}")
    n_strong = len(graph.connected_components(mode="strong"))
    if n_strong != 1:
        raise AssertionError(f"Graph is not strongly connected ({n_strong} components) - re-run T1")

    # 2) Sister-edge pairing on physical_edge_id (1 edge per one-way road, 2 per two-way road)
    edge_index_by_id = {eid: i for i, eid in enumerate(graph.es["id"])}
    physical_groups = (
        pd.Series(graph.es["id"], name="id")
        .groupby(pd.Series(graph.es["physical_edge_id"], name="physical_edge_id"))
        .apply(list)
    )
    if not set(physical_groups.map(len).unique()) <= {1, 2}:
        raise AssertionError("physical_edge_id groups must contain 1 or 2 edges")
    cr.msg(f"Physical roads to test : {len(physical_groups):,}")
    return graph, edge_index_by_id, physical_groups


def load_od_nodes(localities_in, pop_field, name_field, edges, far_snap_m):
    """Snap localities to the nearest network node and aggregate population per node"""
    import geopandas as gpd
    import numpy as np
    import pandas as pd
    import shapely
    from shapely import STRtree

    # 1) Read localities, CRS must be known; reproject (never set_crs) if it differs
    localities = cr.read_vector(localities_in)
    if localities.crs is None:
        raise ValueError("Locality layer has no CRS")
    if localities.crs.to_epsg() != WORKING_EPSG:
        cr.warn(f"Localities are in {localities.crs}; reprojecting to EPSG:{WORKING_EPSG}")
        localities = localities.to_crs(edges.crs)
    for col in (pop_field, name_field):
        if col not in localities.columns:
            raise ValueError(f"Locality layer has no field '{col}'")

    # 2) Points already; take centroids only if the layer is polygonal
    if localities.geom_type.isin(["Polygon", "MultiPolygon"]).any():
        cr.msg("Polygonal geometry detected - using centroids")
        localities = localities.copy()
        localities["geometry"] = localities.geometry.centroid

    # 3) Keep localities with positive population
    n_before = len(localities)
    localities[pop_field] = pd.to_numeric(localities[pop_field], errors="coerce")
    od = localities.loc[
        localities[pop_field].notna() & (localities[pop_field] > 0) & localities.geometry.notna()
    ].copy()
    od = od.rename(columns={pop_field: "population"}).reset_index(drop=True)
    cr.msg(f"Localities retained : {len(od):,} (dropped {n_before - len(od)} null/non-positive)")
    cr.msg(f"Total population    : {od['population'].sum():,.0f}")

    # 4) Readable label: the name repeats across cantons, so qualify it when the canton exists
    canton = next((c for c in ("CANTÓN", "CANTON", "canton") if c in od.columns), None)
    od["label"] = od[name_field].astype(str)
    if canton:
        od["label"] = od["label"] + " (" + od[canton].astype(str) + ")"

    # 5) Network nodes keyed by the vertex ids used in the graph
    start_points = shapely.get_point(edges.geometry.values, 0)
    end_points = shapely.get_point(edges.geometry.values, -1)
    node_geom = {}
    node_geom.update(dict(zip(edges["from_id"].to_numpy(), start_points)))
    node_geom.update(dict(zip(edges["to_id"].to_numpy(), end_points)))
    nodes = gpd.GeoDataFrame({"node_id": list(node_geom.keys())},
                             geometry=list(node_geom.values()), crs=edges.crs)

    # 6) Nearest node per locality (original snapping: STRtree.nearest)
    nearest_idx = STRtree(nodes.geometry.values).nearest(od.geometry.values)
    od["_node_id"] = nodes["node_id"].to_numpy()[nearest_idx]
    od["snap_distance_m"] = shapely.distance(od.geometry.values, nodes.geometry.to_numpy()[nearest_idx])

    snap = od["snap_distance_m"]
    cr.msg("Snap distance (m): min {:,.0f} / median {:,.0f} / mean {:,.0f} / max {:,.0f}".format(
        snap.min(), snap.median(), snap.mean(), snap.max()))
    n_far = int((snap > far_snap_m).sum())
    cr.msg(f"Localities snapping further than {far_snap_m:,.0f} m : {n_far} ({n_far / len(od) * 100:.1f}%)")

    # 7) Far-snapping localities are retained and flagged, never dropped (notebook policy)
    od["snap_far"] = snap > far_snap_m
    return od


def aggregate_od(od, graph, edges):
    """Aggregate population onto shared network nodes (vertex ids resolved against the graph)"""
    import geopandas as gpd

    # 1) vertex index of each snapped node
    vertex_lookup = {name: idx for idx, name in enumerate(graph.vs["name"])}
    missing = [n for n in od["_node_id"].unique() if n not in vertex_lookup]
    if missing:
        raise AssertionError(f"{len(missing)} node ids absent from the graph")
    od = od.copy()
    od["vertex_id"] = od["_node_id"].map(vertex_lookup)

    # 2) Sum population per vertex, keep the first locality's geometry and label
    grouped = (
        od.groupby("vertex_id")
        .agg(geometry=("geometry", "first"), population=("population", "sum"),
             label=("label", "first"), n_localities=("label", "size"))
        .reset_index()
    )
    grouped = gpd.GeoDataFrame(grouped, geometry="geometry", crs=edges.crs)
    if grouped["population"].sum() != od["population"].sum():
        raise AssertionError("population lost in aggregation")
    cr.msg(f"OD nodes after aggregation : {len(grouped):,} "
           f"({len(od) - len(grouped)} localities collapsed onto shared nodes)")
    return grouped


# ------------------------------------------------------------------
# Percolation
# ------------------------------------------------------------------


def summarise_od(od_time, fail_value, demand, baseline_time, speed_ratio, edge_length,
                 frac_counter, distance_disruption, time_disruption):
    """Disruption metrics for one removed road, incl. demand-weighted time and distance disruption"""
    import numpy as np

    # 1) Share of OD pairs isolated / unaffected (diagonal is NaN so it never counts)
    n = baseline_time.shape[0]
    total_trips = n * n - n
    pct_isolated = (np.count_nonzero(od_time == fail_value) / total_trips) * 100
    pct_unaffected = (np.count_nonzero(od_time == baseline_time) / total_trips) * 100

    # 2) Delayed pairs: time differs from baseline and is a number
    adj_time = od_time - baseline_time
    delayed_mask = (od_time != baseline_time) & (~np.isnan(od_time))
    delayed_times = adj_time[delayed_mask]
    delayed_speeds = speed_ratio[delayed_mask]
    delayed_demands = demand[delayed_mask]
    isolated_within_delayed = od_time[delayed_mask] == fail_value

    # 3) Rerouted trips: delay x implied speed. Isolated trips: placeholder = length of the removed road
    delayed_dists = delayed_times * delayed_speeds
    delayed_dists[isolated_within_delayed] = edge_length
    pct_delayed = (delayed_times.shape[0] / total_trips) * 100

    # 4) Demand-weighted averages; a fully redundant road is a real 0, not missing data
    if len(delayed_times) > 0 and delayed_demands.sum() > 0:
        average_time_disruption = np.average(delayed_times, weights=delayed_demands)
        average_dist_disruption = np.average(delayed_dists, weights=delayed_demands)
    else:
        average_time_disruption = 0.0
        average_dist_disruption = 0.0

    return (frac_counter, pct_isolated, pct_unaffected, pct_delayed,
            average_time_disruption, average_dist_disruption,
            distance_disruption, time_disruption)


def run_percolation(graph, edge_index_by_id, physical_groups, vertex_ids, demand,
                    od_orig_time, speed_ratio, penalty_hours):
    """Remove each physical road in turn and summarise the OD disruption"""
    import numpy as np
    import pandas as pd

    # 1) Network totals used for the removed share of length / time
    tot_edge_length = float(np.sum(graph.es["road_length"]))
    tot_edge_time = float(np.sum(graph.es["fft"]))

    # 2) One removal per physical road (both directions together)
    progress = cr.Progress("percolation", len(physical_groups))
    rows = []
    for physical_id, edge_ids in physical_groups.items():
        edge_idx = [edge_index_by_id[i] for i in edge_ids]
        edge_length = float(sum(graph.es[i]["road_length"] for i in edge_idx))

        exp_g = graph.copy()
        exp_g.delete_edges(edge_idx)
        cur_dis_length = 1 - (np.sum(exp_g.es["road_length"]) / tot_edge_length)
        cur_dis_time = 1 - (np.sum(exp_g.es["fft"]) / tot_edge_time)

        perc = cr.run_shortest_paths(exp_g, vertex_ids, weighting="fft")
        np.fill_diagonal(perc, np.nan)
        perc[np.isinf(perc)] = penalty_hours

        rows.append(summarise_od(perc, penalty_hours, demand, od_orig_time, speed_ratio,
                                 edge_length, physical_id, cur_dis_length, cur_dis_time))
        progress.step()
    progress.done()

    # 3) One row per physical road
    return pd.DataFrame(rows, columns=RESULT_COLUMNS)


# ------------------------------------------------------------------
# Criticality metrics and output
# ------------------------------------------------------------------


def criticality_metrics(edges, result_df, subset):
    """Join the per-road disruption onto the directed edges and add VHL/VKL/PHL/PKL/THL/TKL"""
    import numpy as np

    # 1) Many-to-one join on physical_edge_id; a test subset keeps only the processed roads
    how = "inner" if subset else "left"
    gdf = edges.merge(result_df, on="physical_edge_id", how=how, validate="many_to_one")
    if not subset and len(gdf) != len(edges):
        raise AssertionError("merge changed the row count")
    if gdf["average_time_disruption"].isna().any():
        raise AssertionError("unmatched edges after merge")

    # 2) Vehicle hours / kilometres lost
    gdf["vhl"] = gdf["average_time_disruption"] * gdf["total_aadt"]
    gdf["vkl"] = gdf["average_dist_disruption"] * gdf["total_aadt"]

    # 3) Passenger and tonnage hours / kilometres lost
    passengers = sum(gdf[col] * f for col, f in PASSENGER_FACTORS.items())
    tonnes = sum(gdf[col] * f for col, f in FREIGHT_FACTORS.items())
    gdf["phl"] = gdf["average_time_disruption"] * passengers
    gdf["pkl"] = gdf["average_dist_disruption"] * passengers
    gdf["thl"] = gdf["average_time_disruption"] * tonnes
    gdf["tkl"] = gdf["average_dist_disruption"] * tonnes

    # 4) Metrics must be finite and non-negative
    for col in ["vhl", "vkl", "phl", "pkl", "thl", "tkl"]:
        if not np.isfinite(gdf[col]).all():
            raise AssertionError(f"{col} contains non-finite values")
        if not (gdf[col] >= 0).all():
            raise AssertionError(f"{col} contains negative values")
    return gdf


def physical_roads(gdf_results, crs):
    """Collapse the directed results to one row per physical road"""
    import geopandas as gpd

    agg = {c: (c, "sum") for c in SUM_COLS}
    agg.update({c: (c, "first") for c in FIRST_COLS})
    physical = gdf_results.groupby("physical_edge_id", as_index=False).agg(**agg)
    physical = gpd.GeoDataFrame(physical, geometry="geometry", crs=crs)
    n_bi = int((gdf_results.groupby("physical_edge_id").size() == 2).sum())
    cr.msg(f"Physical roads : {len(physical):,} ({n_bi:,} bidirectional, {len(physical) - n_bi:,} unidirectional)")
    return physical


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main():
    warnings.simplefilter(action="ignore", category=FutureWarning)
    warnings.simplefilter(action="ignore", category=RuntimeWarning)

    # 1) Read the script parameters from ArcGIS (or --options outside it)
    p = cr.read_parameters([
        ("network_in", ""),
        ("localities_in", ""),
        ("pop_field", "INEC_PROY"),
        ("name_field", "NOMBRE"),
        ("output_folder", ""),
        ("dist_decay", "1.0"),
        ("max_trips", "25000"),
        ("isolation_factor", "2.0"),
        ("far_snap_m", "5000"),
        ("use_cache", "true"),
        ("test_max_roads", "0"),
    ])

    # 2) Validate the minimum required parameters
    if not p["network_in"]:
        raise ValueError("The directed network from T1 is required.")
    if not p["localities_in"]:
        raise ValueError("A locality point layer with population is required.")
    if not p["output_folder"]:
        raise ValueError("An output folder is required.")
    cr.require_packages(["geopandas", "shapely", "igraph", "numpy", "pandas", "scipy"])
    import numpy as np
    import pandas as pd

    dist_decay = float(p["dist_decay"])
    max_trips = int(float(p["max_trips"]))
    iso_factor = float(p["isolation_factor"])
    far_snap_m = float(p["far_snap_m"])
    use_cache = str(p["use_cache"]).lower() == "true"
    test_max = int(float(p["test_max_roads"]))

    # 3) Create the timestamped run folder (BSA2 convention) and log the parameters
    stamp = cr.timestamp()
    out_root = Path(p["output_folder"])
    run_dir = out_root / f"T2_spof_criticality_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    cr.write_run_config(out_root, "T2", stamp, p)
    t0 = time.perf_counter()

    # 4) Network, graph and physical-road groups
    edges = load_network(p["network_in"])
    graph, edge_index_by_id, physical_groups = graph_and_groups(edges)

    # 5) Origin-destination nodes
    od = load_od_nodes(p["localities_in"], p["pop_field"], p["name_field"], edges, far_snap_m)
    grouped_od = aggregate_od(od, graph, edges)
    vertex_ids = grouped_od["vertex_id"].values

    # 6) Baseline matrices, gravity demand and isolation penalty
    od_base_time = cr.run_shortest_paths(graph, vertex_ids, weighting="fft")
    if not np.isfinite(od_base_time).all():
        raise AssertionError("Non-finite baseline travel time - graph not strongly connected?")
    demand = cr.create_demand(grouped_od["population"].values, od_base_time, dist_decay, max_trips)

    od_orig_time = od_base_time.copy()
    od_orig_dist = cr.run_shortest_paths(graph, vertex_ids, weighting="road_length")
    if not np.isfinite(od_orig_dist).all():
        raise AssertionError("Non-finite baseline distance")
    np.fill_diagonal(od_orig_time, np.nan)
    np.fill_diagonal(od_orig_dist, np.nan)
    speed_ratio = od_orig_dist / od_orig_time

    max_baseline_hours = float(np.nanmax(od_orig_time))
    penalty_hours = float(np.ceil(max_baseline_hours * iso_factor))
    cr.msg(f"Baseline travel time : max {max_baseline_hours:.2f} h, mean {np.nanmean(od_orig_time):.2f} h")
    cr.msg(f"Isolation penalty    : {penalty_hours:.0f} h ({iso_factor:g} x the {max_baseline_hours:.2f} h maximum baseline trip)")
    cr.msg(f"Demand               : max {demand.max():,} trips/day on the busiest pair, {demand.sum():,} total")

    # 7) Percolation, optionally limited to the first N physical roads (test) and cached
    subset = test_max > 0
    groups = physical_groups.iloc[:test_max] if subset else physical_groups
    if subset:
        cr.warn(f"TEST MODE: only the first {len(groups)} of {len(physical_groups):,} physical roads are processed")
    key = cr.fingerprint(
        np.asarray(graph.es["id"]), np.asarray(graph.es["physical_edge_id"]),
        np.asarray(graph.es["fft"]), np.asarray(graph.es["road_length"]),
        np.asarray(vertex_ids), grouped_od["population"].to_numpy(),
        dist_decay, max_trips, iso_factor, len(groups),
    )
    cache_path = out_root / "cache" / f"spof_percolation_{key}.csv"
    if use_cache and cache_path.exists():
        cr.msg(f"Using cached percolation: {cache_path}")
        result_df = pd.read_csv(cache_path)
    else:
        result_df = run_percolation(graph, edge_index_by_id, groups, vertex_ids, demand,
                                    od_orig_time, speed_ratio, penalty_hours)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        result_df.to_csv(cache_path, index=False)
    n_redundant = int((result_df["pct_delayed"] == 0).sum())
    cr.msg(f"Physical roads tested   : {len(result_df):,}")
    cr.msg(f"Roads causing isolation : {int((result_df['pct_isolated'] > 0).sum()):,}")
    cr.msg(f"Fully redundant roads   : {n_redundant:,} ({n_redundant / len(result_df) * 100:.1f}%)")

    # 8) Criticality metrics on the directed edges, then per physical road
    gdf_results = criticality_metrics(edges, result_df, subset)
    absent = [c for c in PREFERRED_COLUMNS if c not in gdf_results.columns]
    if absent:
        raise AssertionError(f"Expected columns absent from results: {absent}")
    results = gdf_results[PREFERRED_COLUMNS].copy()
    physical = physical_roads(gdf_results, edges.crs)

    # 9) Write the outputs with the notebook's file and layer names
    directed_gpkg = run_dir / "criticality_results.gpkg"
    physical_gpkg = run_dir / "physical_criticality_results.gpkg"
    od_gpkg = run_dir / "od_nodes.gpkg"
    cr.write_gpkg(results, directed_gpkg, "criticality_results")
    cr.write_gpkg(physical, physical_gpkg, "criticality")
    cr.write_gpkg(grouped_od, od_gpkg, "od_nodes")
    cr.msg(f"Finished in {time.perf_counter() - t0:.0f} s")

    # 10) Return the outputs to the tool dialog
    cr.set_outputs(11, [cr.layer_path(directed_gpkg, "criticality_results"),
                        cr.layer_path(physical_gpkg, "criticality"),
                        cr.layer_path(od_gpkg, "od_nodes")])
    cr.msg(f"Computation complete: {run_dir}")


if __name__ == "__main__":
    main()
