"""Prepare the Costa Rican modified cantonal road network for routing.

The source network already contains AADT (T9--T15), direction and speed
attributes.  This module validates those fields, repairs small endpoint gaps,
builds topology, imputes missing AADT values, constructs directed edges,
calculates free-flow travel time and extracts the strongly connected giant
component used by the criticality workflow.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import unicodedata

import geopandas as gpd
import igraph as ig
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPoint, Point
from shapely.ops import split
from shapely.strtree import STRtree

try:
    import contextily as cx
except Exception as exc:  # optional: a broken tile/GDAL stack must not stop routing
    cx = None
    _CONTEXTILY_IMPORT_ERROR = exc
else:
    _CONTEXTILY_IMPORT_ERROR = None


AADT_COLUMNS = ["T9", "T10", "T11", "T12", "T13", "T14", "T15"]
AADT_ALIASES = {
    "T9": "motorcycles",
    "T10": "pickup_trucks",
    "T11": "passenger_cars",
    "T12": "buses",
    "T13": "light_trucks",
    "T14": "medium_trucks",
    "T15": "heavy_trucks",
}
AADT_LABELS = {
    "motorcycles": "Motorcycles",
    "pickup_trucks": "Pickup trucks",
    "passenger_cars": "Passenger cars",
    "buses": "Buses",
    "light_trucks": "Light trucks",
    "medium_trucks": "Medium trucks",
    "heavy_trucks": "Heavy trucks",
}

REQUIRED_SOURCE_COLUMNS = [
    "ID_TRAMO",
    "TRAMO_UID",
    "CLASE",
    "DIRECCION",
    "VEL_KMH",
    "NODO_INI",
    "NODO_FIN",
    *AADT_COLUMNS,
    "geometry",
]


@dataclass(frozen=True)
class CRNetworkPrepConfig:
    """Paths and explicit methodological settings for the CR workflow."""

    base_dir: Path
    snap_tolerance_m: float = 2.0
    snap_search_buffer_m: float = 30.0
    snap_max_iterations: int = 20
    min_giant_component_length_pct: float = 95.0
    statutory_default_speed_kmh: float = 60.0
    working_crs: str = "EPSG:8908"
    figure_dpi: int = 300
    add_basemap: bool = True

    @property
    def input_path(self) -> Path:
        return (
            self.base_dir
            / "input_files"
            / "CR_RED_TOPOGRAFICA"
            / "cr_red_topografica.shp"
        )

    @property
    def figure_path(self) -> Path:
        return self.base_dir / "figures"

    @property
    def gpkg_dir(self) -> Path:
        return self.base_dir / "intermediate_results" / "gpkg" / "network"

    @property
    def main_network_path(self) -> Path:
        return self.gpkg_dir / "main_network_directed.gpkg"

    @property
    def dropped_roads_path(self) -> Path:
        return self.gpkg_dir / "giant_component_dropped_roads.gpkg"

    def ensure_output_dirs(self) -> None:
        self.figure_path.mkdir(parents=True, exist_ok=True)
        self.gpkg_dir.mkdir(parents=True, exist_ok=True)


def _read_vector(path: Path, layer: str | None = None) -> gpd.GeoDataFrame:
    """Use Fiona explicitly so a broken optional pyogrio install is harmless."""

    kwargs: dict[str, Any] = {"engine": "fiona"}
    if layer is not None:
        kwargs["layer"] = layer
    return gpd.read_file(path, **kwargs)


def _safe_add_basemap(ax, crs: Any, enabled: bool = True) -> None:
    if not enabled:
        return
    if cx is None:
        print(f"Basemap skipped: contextily unavailable ({_CONTEXTILY_IMPORT_ERROR})")
        return
    try:
        cx.add_basemap(
            ax=ax,
            crs=crs,
            source=cx.providers.CartoDB.Positron,
            alpha=0.40,
            attribution=False,
        )
    except Exception as exc:
        print(f"Basemap skipped: tiles unavailable ({exc})")


def _finite_numeric(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values.where(np.isfinite(values))


def load_and_validate_network(
    config: CRNetworkPrepConfig,
) -> tuple[gpd.GeoDataFrame, dict[str, Any]]:
    """Load, validate and explode the CR source network to LineStrings."""

    config.ensure_output_dirs()
    if not config.input_path.exists():
        raise FileNotFoundError(f"CR road network not found: {config.input_path}")

    roads = _read_vector(config.input_path)
    missing_columns = [c for c in REQUIRED_SOURCE_COLUMNS if c not in roads.columns]
    if missing_columns:
        raise KeyError(f"CR source is missing required columns: {missing_columns}")
    if roads.crs is None:
        raise ValueError("CR source has no CRS; snapping and length require a metric CRS")

    source_crs = roads.crs
    if roads.crs.to_epsg() != 8908:
        print(f"Reprojecting source network from {roads.crs} to {config.working_crs}")
        roads = roads.to_crs(config.working_crs)

    null_geometry = roads.geometry.isna()
    empty_geometry = roads.geometry.is_empty.fillna(False)
    invalid_geometry = ~roads.geometry.is_valid.fillna(False)
    zero_length = roads.geometry.length.le(0)
    bad_geometry = null_geometry | empty_geometry | invalid_geometry | zero_length
    if bad_geometry.any():
        detail = roads.loc[
            bad_geometry,
            [c for c in ["ID_TRAMO", "TRAMO_UID", "CLASE", "geometry"] if c in roads],
        ].copy()
        raise ValueError(
            "Invalid source geometries found; repair upstream before topology:\n"
            + detail.to_string()
        )

    roads = roads.copy()
    source_feature_count = len(roads)
    roads.insert(0, "source_row_id", np.arange(len(roads), dtype=np.int64))

    duplicate_subset = [column for column in roads.columns if column != "source_row_id"]
    duplicate_count = int(roads.duplicated(subset=duplicate_subset).sum())
    if duplicate_count:
        roads = roads.drop_duplicates(subset=duplicate_subset).reset_index(drop=True)

    deduplicated_count = len(roads)
    multipart_count = int(roads.geom_type.eq("MultiLineString").sum())
    unsupported_types = sorted(
        set(roads.geom_type.dropna()) - {"LineString", "MultiLineString"}
    )
    if unsupported_types:
        raise TypeError(f"Unsupported source geometry types: {unsupported_types}")

    roads = roads.explode(index_parts=False, ignore_index=True)
    roads["source_part_no"] = roads.groupby("source_row_id").cumcount().astype(int)
    roads["source_part_id"] = (
        roads["source_row_id"].astype(str) + ":" + roads["source_part_no"].astype(str)
    )
    if not roads.geom_type.eq("LineString").all():
        raise TypeError("Multipart explosion did not produce only LineString geometries")

    # Source LONGITUD is retained but never used as the routing length.
    length_ratio_summary: dict[str, float] = {}
    if "LONGITUD" in roads:
        source_length = _finite_numeric(roads["LONGITUD"])
        geom_length = roads.geometry.length
        valid_ratio = source_length.notna() & geom_length.gt(0)
        ratios = source_length.loc[valid_ratio] / geom_length.loc[valid_ratio]
        if not ratios.empty:
            length_ratio_summary = {
                "min": float(ratios.min()),
                "median": float(ratios.median()),
                "max": float(ratios.max()),
            }

    stats = {
        "source_crs": str(source_crs),
        "working_crs": str(roads.crs),
        "source_features": source_feature_count,
        "deduplicated_features": deduplicated_count,
        "multipart_features": multipart_count,
        "exploded_lines": len(roads),
        "exact_duplicates_removed": duplicate_count,
        "length_ratio_summary": length_ratio_summary,
    }

    print("CR source validation")
    print(f"  source features       : {source_feature_count:,}")
    print(f"  deduplicated features : {deduplicated_count:,}")
    print(f"  multipart features    : {multipart_count:,}")
    print(f"  exploded LineStrings  : {len(roads):,}")
    print(f"  exact duplicates      : {duplicate_count:,}")
    print(f"  working CRS           : {roads.crs}")
    print("  DIRECCION values:")
    print(roads["DIRECCION"].value_counts(dropna=False).to_string())
    print("  VEL_KMH values:")
    print(roads["VEL_KMH"].value_counts(dropna=False).sort_index().to_string())
    print("  AADT completeness:")
    print(roads[AADT_COLUMNS].notna().mean().mul(100).round(1).astype(str).add("%").to_string())
    return roads.reset_index(drop=True), stats


def _replace_line_endpoints(
    line: LineString,
    start: Point | None,
    end: Point | None,
) -> LineString:
    coords = list(line.coords)
    if start is not None:
        coords[0] = tuple(start.coords[0])
    if end is not None:
        coords[-1] = tuple(end.coords[0])
    result = LineString(coords)
    if result.is_empty or not result.is_valid or result.length <= 0:
        raise ValueError("Endpoint snapping produced an invalid or zero-length line")
    return result


def snap_network_iteratively(
    roads: gpd.GeoDataFrame,
    tolerance_m: float = 2.0,
    search_buffer_m: float = 30.0,
    max_iterations: int = 20,
) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """Move dangling endpoints to the nearest road within *tolerance_m*."""

    if roads.crs is None or roads.crs.is_geographic:
        raise ValueError("Endpoint snapping requires a projected metric CRS")
    if not roads.geom_type.eq("LineString").all():
        raise TypeError("Explode MultiLineStrings before endpoint snapping")

    snapped = roads.copy().reset_index(drop=True)
    log_rows: list[dict[str, Any]] = []
    rejected_proposals: set[tuple[int, int, int]] = set()
    snapped_endpoints: set[tuple[int, int]] = set()

    for iteration in range(1, max_iterations + 1):
        reference_geometries = snapped.geometry.to_list()
        tree = STRtree(reference_geometries)
        changes: list[tuple[int, Point | None, Point | None, list[dict[str, Any]]]] = []

        for edge_index, line in enumerate(reference_geometries):
            endpoints = [Point(line.coords[0]), Point(line.coords[-1])]
            replacements: list[Point | None] = [None, None]
            edge_log: list[dict[str, Any]] = []

            for endpoint_no, endpoint in enumerate(endpoints):
                if (edge_index, endpoint_no) in snapped_endpoints:
                    continue
                candidate_indices = tree.query(endpoint.buffer(search_buffer_m))
                best: tuple[float, int, Point] | None = None
                for candidate_index_raw in candidate_indices:
                    candidate_index = int(candidate_index_raw)
                    if candidate_index == edge_index:
                        continue
                    if (edge_index, endpoint_no, candidate_index) in rejected_proposals:
                        continue
                    candidate = reference_geometries[candidate_index]
                    nearest = candidate.interpolate(candidate.project(endpoint))
                    distance = float(endpoint.distance(nearest))
                    if distance <= 1e-9 or distance > tolerance_m:
                        continue
                    proposal = (distance, candidate_index, nearest)
                    if best is None or proposal[:2] < best[:2]:
                        best = proposal

                if best is not None:
                    distance, candidate_index, nearest = best
                    replacements[endpoint_no] = nearest
                    edge_log.append(
                        {
                            "iteration": iteration,
                            "edge_index": edge_index,
                            "source_part_id": snapped.at[edge_index, "source_part_id"],
                            "endpoint": "start" if endpoint_no == 0 else "end",
                            "target_edge_index": candidate_index,
                            "target_source_part_id": snapped.at[candidate_index, "source_part_id"],
                            "snap_distance_m": distance,
                        }
                    )

            if any(value is not None for value in replacements):
                changes.append(
                    (edge_index, replacements[0], replacements[1], edge_log)
                )

        iteration_change_count = 0
        for edge_index, start, end, edge_log in changes:
            old_geometry = snapped.at[edge_index, "geometry"]
            try:
                new_geometry = _replace_line_endpoints(old_geometry, start, end)
            except ValueError:
                # Very short edges can have both endpoints proposed to the same
                # target. Keep the valid source geometry and block those exact
                # proposals so later iterations do not repeat them.
                for proposal in edge_log:
                    endpoint_no = 0 if proposal["endpoint"] == "start" else 1
                    rejected_proposals.add(
                        (
                            edge_index,
                            endpoint_no,
                            int(proposal["target_edge_index"]),
                        )
                    )
                continue
            if not old_geometry.equals_exact(new_geometry, tolerance=1e-12):
                snapped.at[edge_index, "geometry"] = new_geometry
                log_rows.extend(edge_log)
                iteration_change_count += len(edge_log)
                for proposal in edge_log:
                    endpoint_no = 0 if proposal["endpoint"] == "start" else 1
                    snapped_endpoints.add((edge_index, endpoint_no))

        print(f"Snap iteration {iteration}: {iteration_change_count:,} endpoint changes")
        if iteration_change_count == 0:
            break

    snap_log = pd.DataFrame(log_rows)
    if not snap_log.empty and snap_log["snap_distance_m"].max() > tolerance_m + 1e-9:
        raise AssertionError("A recorded endpoint snap exceeded the configured tolerance")
    print(f"Total endpoint snaps: {len(snap_log):,}")
    return snapped, snap_log


def _intersection_split_points(geometry) -> Iterable[Point]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, Point):
        return [geometry]
    if geometry.geom_type == "MultiPoint":
        return list(geometry.geoms)
    if isinstance(geometry, LineString):
        return [Point(geometry.coords[0]), Point(geometry.coords[-1])]
    if isinstance(geometry, MultiLineString):
        points: list[Point] = []
        for part in geometry.geoms:
            points.extend([Point(part.coords[0]), Point(part.coords[-1])])
        return points
    if isinstance(geometry, GeometryCollection):
        points = []
        for part in geometry.geoms:
            points.extend(_intersection_split_points(part))
        return points
    return []


def _add_interior_point(
    point_store: dict[bytes, Point],
    line: LineString,
    point: Point,
    tolerance: float,
) -> None:
    position = float(line.project(point))
    if position <= tolerance or position >= line.length - tolerance:
        return
    on_line = line.interpolate(position)
    if point.distance(on_line) > tolerance:
        return
    point_store[on_line.wkb] = on_line


def build_topology(
    roads: gpd.GeoDataFrame,
    split_tolerance_m: float = 1e-7,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, dict[str, Any]]:
    """Split line intersections and assign exact endpoint-based node IDs."""

    if not roads.geom_type.eq("LineString").all():
        raise TypeError("Topology builder requires LineString geometries")

    geometries = roads.geometry.to_list()
    tree = STRtree(geometries)
    points_by_edge: list[dict[bytes, Point]] = [dict() for _ in geometries]
    overlap_pairs = 0
    intersection_pairs = 0

    for edge_index, line in enumerate(geometries):
        for other_raw in tree.query(line):
            other_index = int(other_raw)
            if other_index <= edge_index:
                continue
            intersection = line.intersection(geometries[other_index])
            if intersection.is_empty:
                continue
            intersection_pairs += 1
            if intersection.geom_type in {"LineString", "MultiLineString"}:
                overlap_pairs += 1
            for point in _intersection_split_points(intersection):
                _add_interior_point(
                    points_by_edge[edge_index], line, point, split_tolerance_m
                )
                _add_interior_point(
                    points_by_edge[other_index],
                    geometries[other_index],
                    point,
                    split_tolerance_m,
                )

    split_rows: list[dict[str, Any]] = []
    for edge_index, row in roads.iterrows():
        line = row.geometry
        split_points = list(points_by_edge[edge_index].values())
        if split_points:
            try:
                parts = list(split(line, MultiPoint(split_points)).geoms)
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to split source_part_id={row['source_part_id']}: {exc}"
                ) from exc
        else:
            parts = [line]

        ordered_parts: list[tuple[float, LineString]] = []
        for part in parts:
            if part.length <= split_tolerance_m:
                continue
            start_position = float(line.project(Point(part.coords[0])))
            end_position = float(line.project(Point(part.coords[-1])))
            if end_position < start_position:
                part = shapely.reverse(part)
                start_position, end_position = end_position, start_position
            ordered_parts.append((start_position, part))
        ordered_parts.sort(key=lambda value: value[0])

        attributes = row.drop(labels="geometry").to_dict()
        for topology_part_no, (_, part) in enumerate(ordered_parts):
            new_row = attributes.copy()
            new_row["topology_part_no"] = topology_part_no
            new_row["geometry"] = part
            split_rows.append(new_row)

    edges = gpd.GeoDataFrame(split_rows, geometry="geometry", crs=roads.crs)
    edges = edges.reset_index(drop=True)
    edges["physical_edge_id"] = np.arange(len(edges), dtype=np.int64)

    node_lookup: dict[tuple[float, float], int] = {}
    node_points: list[Point] = []
    from_ids: list[int] = []
    to_ids: list[int] = []

    def node_id(coordinate) -> int:
        key = (round(float(coordinate[0]), 8), round(float(coordinate[1]), 8))
        if key not in node_lookup:
            node_lookup[key] = len(node_points)
            node_points.append(Point(coordinate))
        return node_lookup[key]

    for geometry in edges.geometry:
        from_ids.append(node_id(geometry.coords[0]))
        to_ids.append(node_id(geometry.coords[-1]))

    edges["from_id"] = np.asarray(from_ids, dtype=np.int64)
    edges["to_id"] = np.asarray(to_ids, dtype=np.int64)
    edges["id"] = np.arange(len(edges), dtype=np.int64)
    nodes = gpd.GeoDataFrame(
        {"id": np.arange(len(node_points), dtype=np.int64)},
        geometry=node_points,
        crs=roads.crs,
    )

    invalid_topology = edges[["from_id", "to_id"]].isna().any(axis=1)
    if invalid_topology.any() or (edges[["from_id", "to_id"]] < 0).any().any():
        raise AssertionError("Topology contains null or negative node IDs")

    self_loops = edges["from_id"].eq(edges["to_id"])
    graph = ig.Graph.TupleList(
        list(edges[["from_id", "to_id"]].itertuples(index=False, name=None)),
        directed=False,
    )
    weak_component_count = len(graph.connected_components()) if graph.vcount() else 0

    stats = {
        "input_edges": len(roads),
        "topology_edges": len(edges),
        "nodes": len(nodes),
        "new_split_edges": len(edges) - len(roads),
        "intersection_pairs": intersection_pairs,
        "overlap_pairs": overlap_pairs,
        "self_loops": int(self_loops.sum()),
        "weak_components": weak_component_count,
    }
    print("Topology summary")
    for key, value in stats.items():
        print(f"  {key:<22}: {value:,}")
    if self_loops.any():
        print("  Self-loop source parts (retained for inspection):")
        print(
            edges.loc[self_loops, ["physical_edge_id", "source_part_id", "ID_TRAMO"]]
            .head(20)
            .to_string(index=False)
        )
    return edges, nodes, stats


def _edge_adjacency(edges: pd.DataFrame) -> dict[int, list[int]]:
    adjacency: dict[int, list[int]] = defaultdict(list)
    for edge_index, row in edges[["from_id", "to_id"]].iterrows():
        adjacency[int(row["from_id"])].append(edge_index)
        adjacency[int(row["to_id"])].append(edge_index)
    return adjacency


def fill_missing_aadt(
    edges: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, pd.DataFrame, pd.DataFrame]:
    """Fill T9--T15 independently using topology neighbours and CR classes."""

    filled = edges.copy()
    for column in AADT_COLUMNS:
        filled[column] = _finite_numeric(filled[column]).astype(float)
        invalid = filled[column].lt(0)
        if invalid.any():
            raise ValueError(
                f"Negative {column} values found:\n"
                + filled.loc[invalid, ["physical_edge_id", "source_part_id", column]]
                .to_string(index=False)
            )
        filled[f"{column}_fill_source"] = np.where(
            filled[column].notna(), "observed", "missing"
        )
        filled[f"{column}_capped"] = False

    filled["aadt_missing_before"] = filled[AADT_COLUMNS].isna().sum(axis=1).astype(int)
    adjacency = _edge_adjacency(filled)

    # Pass 1: compute updates from a frozen snapshot to avoid row-order effects.
    for column in AADT_COLUMNS:
        snapshot = filled[column].copy()
        updates: dict[int, float] = {}
        for edge_index in snapshot.index[snapshot.isna()]:
            row = filled.loc[edge_index]
            start_neighbours = [
                i for i in adjacency[int(row["from_id"])] if i != edge_index
            ]
            end_neighbours = [
                i for i in adjacency[int(row["to_id"])] if i != edge_index
            ]
            start_values = snapshot.loc[start_neighbours].dropna()
            end_values = snapshot.loc[end_neighbours].dropna()
            if not start_values.empty and not end_values.empty:
                updates[edge_index] = float(
                    (start_values.mean() + end_values.mean()) / 2.0
                )
        if updates:
            update_index = list(updates)
            filled.loc[update_index, column] = pd.Series(updates)
            filled.loc[update_index, f"{column}_fill_source"] = "endpoint_mean"

    # Pass 2: class median, global fallback, and touching-road cap.
    for column in AADT_COLUMNS:
        snapshot = filled[column].copy()
        class_medians = filled.assign(_value=snapshot).groupby("CLASE")["_value"].median()
        global_median = float(snapshot.median())
        if not np.isfinite(global_median):
            raise ValueError(f"Cannot calculate a usable global median for {column}")

        for edge_index in snapshot.index[snapshot.isna()]:
            road_class = filled.at[edge_index, "CLASE"]
            if pd.notna(road_class) and road_class in class_medians.index and pd.notna(class_medians.loc[road_class]):
                value = float(class_medians.loc[road_class])
                source = "class_median"
            else:
                value = global_median
                source = "global_median"

            row = filled.loc[edge_index]
            touching = set(adjacency[int(row["from_id"])]) | set(
                adjacency[int(row["to_id"])]
            )
            touching.discard(edge_index)
            neighbour_values = snapshot.loc[list(touching)].dropna()
            if not neighbour_values.empty:
                maximum = float(neighbour_values.max())
                if value > maximum:
                    value = maximum
                    filled.at[edge_index, f"{column}_capped"] = True

            filled.at[edge_index, column] = value
            filled.at[edge_index, f"{column}_fill_source"] = source

    values = filled[AADT_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise AssertionError("AADT imputation left null, infinite, or negative values")

    for source, alias in AADT_ALIASES.items():
        filled[alias] = filled[source].astype(float)
    filled["total_aadt"] = filled[AADT_COLUMNS].sum(axis=1)
    filled["aadt_imputed"] = filled["aadt_missing_before"].gt(0)
    filled["aadt_cap_applied"] = filled[
        [f"{column}_capped" for column in AADT_COLUMNS]
    ].any(axis=1)

    completeness = pd.DataFrame(
        {
            "category": AADT_COLUMNS,
            "complete_before": [
                int((filled[f"{column}_fill_source"] == "observed").sum())
                for column in AADT_COLUMNS
            ],
            "complete_after": [int(filled[column].notna().sum()) for column in AADT_COLUMNS],
            "total_edges": len(filled),
        }
    )
    completeness["pct_before"] = (
        100 * completeness["complete_before"] / completeness["total_edges"]
    )
    completeness["pct_after"] = (
        100 * completeness["complete_after"] / completeness["total_edges"]
    )

    fill_sources = pd.concat(
        [
            filled[f"{column}_fill_source"]
            .value_counts()
            .rename_axis("fill_source")
            .rename("edges")
            .reset_index()
            .assign(category=column)
            for column in AADT_COLUMNS
        ],
        ignore_index=True,
    )[["category", "fill_source", "edges"]]

    print("AADT completeness before/after imputation")
    print(completeness.round(1).to_string(index=False))
    print("AADT fill sources")
    print(fill_sources.to_string(index=False))
    return filled, completeness, fill_sources


def _quantile_breaks(series: pd.Series, bins: int = 5) -> np.ndarray:
    values = _finite_numeric(series).dropna().to_numpy(dtype=float)
    if values.size == 0:
        raise ValueError("Cannot classify an empty AADT series")
    unique_values = np.unique(values)
    if unique_values.size == 1:
        value = unique_values[0]
        padding = max(abs(value) * 0.01, 0.5)
        return np.array([value - padding, value + padding], dtype=float)
    breaks = np.unique(np.quantile(values, np.linspace(0, 1, bins + 1)))
    if breaks.size < 2:
        return np.array([values.min(), values.max()], dtype=float)
    return breaks


def _break_labels(breaks: np.ndarray) -> list[str]:
    labels: list[str] = []
    for lower, upper in zip(breaks[:-1], breaks[1:]):
        labels.append(f"{lower:,.0f}–{upper:,.0f}")
    return labels


def plot_aadt_maps(
    roads: gpd.GeoDataFrame,
    config: CRNetworkPrepConfig,
    show: bool = True,
) -> dict[str, list[float]]:
    """Save seven individual maps and a 4x2 combined AADT figure."""

    config.ensure_output_dirs()
    physical = roads.to_crs(3857)
    colors = {
        "motorcycles": "#005f73",
        "pickup_trucks": "#9b2226",
        "passenger_cars": "#a53860",
        "buses": "#283618",
        "light_trucks": "#2a9d8f",
        "medium_trucks": "#582f0e",
        "heavy_trucks": "#001219",
    }
    classifications: dict[str, tuple[np.ndarray, list[str]]] = {}
    reported_breaks: dict[str, list[float]] = {}
    for field in AADT_LABELS:
        breaks = _quantile_breaks(physical[field])
        labels = _break_labels(breaks)
        classifications[field] = (breaks, labels)
        reported_breaks[field] = [float(value) for value in breaks]
        print(f"{field} AADT breaks: {reported_breaks[field]}")

    for field, title in AADT_LABELS.items():
        breaks, labels = classifications[field]
        categories = pd.cut(
            physical[field], bins=breaks, labels=labels, include_lowest=True
        )
        fig, ax = plt.subplots(figsize=(12, 10), facecolor="white")
        legend_handles: list[Line2D] = []
        for category_index, label in enumerate(labels):
            subset = physical.loc[categories.eq(label)]
            width = 0.6 + category_index * 0.8
            if not subset.empty:
                subset.plot(
                    ax=ax,
                    color=colors[field],
                    linewidth=width,
                    alpha=0.78,
                    zorder=2 + category_index,
                )
            legend_handles.append(
                Line2D(
                    [0],
                    [0],
                    color=colors[field],
                    linewidth=width,
                    label=label,
                    alpha=0.78,
                )
            )
        _safe_add_basemap(ax, physical.crs, enabled=config.add_basemap)
        ax.legend(
            handles=legend_handles,
            title=f"{title} AADT\n(vehicles/day)",
            loc="upper right",
            frameon=True,
        )
        ax.set_title(f"{title} — Annual Average Daily Traffic", fontweight="bold")
        ax.axis("off")
        fig.tight_layout()
        fig.savefig(
            config.figure_path / f"{field}_aadt_map.png",
            dpi=config.figure_dpi,
            bbox_inches="tight",
        )
        if show:
            plt.show()
        plt.close(fig)

    fig, axes = plt.subplots(4, 2, figsize=(16, 28), facecolor="white")
    axes_flat = axes.ravel()
    letters = list("ABCDEFG")
    for panel_index, (field, title) in enumerate(AADT_LABELS.items()):
        ax = axes_flat[panel_index]
        breaks, labels = classifications[field]
        categories = pd.cut(
            physical[field], bins=breaks, labels=labels, include_lowest=True
        )
        handles: list[Line2D] = []
        for category_index, label in enumerate(labels):
            subset = physical.loc[categories.eq(label)]
            width = 0.5 + category_index * 0.65
            if not subset.empty:
                subset.plot(
                    ax=ax,
                    color=colors[field],
                    linewidth=width,
                    alpha=0.78,
                    zorder=2 + category_index,
                )
            handles.append(
                Line2D(
                    [0],
                    [0],
                    color=colors[field],
                    linewidth=width,
                    label=label,
                    alpha=0.78,
                )
            )
        _safe_add_basemap(ax, physical.crs, enabled=config.add_basemap)
        ax.legend(
            handles=handles,
            title=f"{title}\n(vehicles/day)",
            loc="upper right",
            fontsize=9,
            title_fontsize=10,
            frameon=True,
        )
        ax.text(
            0.03,
            0.97,
            letters[panel_index],
            transform=ax.transAxes,
            va="top",
            fontsize=18,
            fontweight="bold",
            bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "alpha": 0.8},
        )
        ax.axis("off")
    axes_flat[-1].axis("off")
    fig.suptitle("AADT Categories — Modified Cantonal Network", fontsize=18, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    fig.savefig(
        config.figure_path / "AADT_categories_combined.png",
        dpi=config.figure_dpi,
        bbox_inches="tight",
    )
    if show:
        plt.show()
    plt.close(fig)
    return reported_breaks


def _normalise_direction(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = unicodedata.normalize("NFKD", str(value).strip().lower())
    text = "".join(character for character in text if not unicodedata.combining(character))
    if text == "bidireccional":
        return "Bidireccional"
    if text == "unidireccional":
        return "Unidireccional"
    return f"UNKNOWN:{value}"


def plot_direction_qa(
    physical_edges: gpd.GeoDataFrame,
    config: CRNetworkPrepConfig,
    show: bool = True,
) -> Path:
    """Plot one-way edges with small arrows following digitized direction."""

    plot_frame = physical_edges.to_crs(3857)
    one_way = plot_frame.loc[plot_frame["DIRECCION"].eq("Unidireccional")]
    fig, ax = plt.subplots(figsize=(12, 10), facecolor="white")
    plot_frame.plot(ax=ax, color="#CFCFCF", linewidth=0.45, alpha=0.65, zorder=1)
    if not one_way.empty:
        one_way.plot(ax=ax, color="#B2182B", linewidth=1.4, alpha=0.9, zorder=3)
        for line in one_way.geometry:
            start = line.interpolate(0.45, normalized=True)
            end = line.interpolate(0.55, normalized=True)
            ax.annotate(
                "",
                xy=(end.x, end.y),
                xytext=(start.x, start.y),
                arrowprops={
                    "arrowstyle": "-|>",
                    "color": "#B2182B",
                    "lw": 0.35,
                    "alpha": 0.65,
                    "mutation_scale": 5,
                },
                zorder=4,
            )
    _safe_add_basemap(ax, plot_frame.crs, enabled=config.add_basemap)
    ax.legend(
        handles=[
            Line2D([0], [0], color="#CFCFCF", lw=2, label="Bidirectional / assumed bidirectional"),
            Line2D([0], [0], color="#B2182B", lw=2, label="Unidirectional (digitized direction)"),
        ],
        loc="upper right",
        title="Direction QA",
    )
    ax.set_title("One-way Direction QA — Modified Cantonal Network", fontweight="bold")
    ax.axis("off")
    fig.tight_layout()
    output = config.figure_path / "oneway_direction_qa.png"
    fig.savefig(output, dpi=config.figure_dpi, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    return output


def create_directed_edges(
    physical_edges: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, dict[str, Any]]:
    """Expand bidirectional roads and convert two-way traffic to per-direction AADT."""

    directed = physical_edges.copy()
    directed["DIRECCION_raw"] = directed["DIRECCION"]
    normalised = directed["DIRECCION"].map(_normalise_direction)
    unknown = normalised.astype("string").str.startswith("UNKNOWN:", na=False)
    if unknown.any():
        raise ValueError(
            "Unexpected DIRECCION values:\n"
            + directed.loc[unknown, ["physical_edge_id", "source_part_id", "DIRECCION"]]
            .to_string(index=False)
        )
    directed["direction_imputed"] = normalised.isna()
    directed["DIRECCION"] = normalised.fillna("Bidireccional")

    bidirectional = directed["DIRECCION"].eq("Bidireccional")
    flow_columns = [*AADT_COLUMNS, *AADT_ALIASES.values(), "total_aadt"]
    directed.loc[bidirectional, flow_columns] = (
        directed.loc[bidirectional, flow_columns] / 2.0
    )
    directed["aadt_direction_factor"] = np.where(bidirectional, 0.5, 1.0)
    directed["direction_side"] = "forward"

    reversed_edges = directed.loc[bidirectional].copy()
    reversed_edges["geometry"] = reversed_edges.geometry.map(shapely.reverse)
    reversed_edges[["from_id", "to_id"]] = reversed_edges[["to_id", "from_id"]].to_numpy()
    reversed_edges["direction_side"] = "reverse"

    directed = gpd.GeoDataFrame(
        pd.concat([directed, reversed_edges], ignore_index=True),
        geometry="geometry",
        crs=physical_edges.crs,
    )
    directed["id"] = np.arange(len(directed), dtype=np.int64)

    actual_multiplicity = directed.groupby("physical_edge_id").size()
    expected_multiplicity = (
        physical_edges.assign(
            _normalised=physical_edges["DIRECCION"].map(_normalise_direction).fillna("Bidireccional")
        )
        .set_index("physical_edge_id")["_normalised"]
        .map({"Bidireccional": 2, "Unidireccional": 1})
    )
    bad_multiplicity = actual_multiplicity.ne(expected_multiplicity)
    if bad_multiplicity.any():
        raise AssertionError(
            "Directed-edge multiplicity check failed:\n"
            + pd.DataFrame(
                {
                    "actual": actual_multiplicity[bad_multiplicity],
                    "expected": expected_multiplicity[bad_multiplicity],
                }
            ).to_string()
        )

    stats = {
        "physical_edges": len(physical_edges),
        "bidirectional_physical_edges": int(bidirectional.sum()),
        "unidirectional_physical_edges": int((~bidirectional).sum()),
        "imputed_direction_edges": int(directed.loc[directed["direction_side"].eq("forward"), "direction_imputed"].sum()),
        "directed_edges": len(directed),
    }
    print("Direction expansion summary")
    for key, value in stats.items():
        print(f"  {key:<31}: {value:,}")
    return directed, stats


def add_speed_and_travel_time(
    directed_edges: gpd.GeoDataFrame,
    config: CRNetworkPrepConfig,
) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """Preserve source speeds, impute missing speeds, and calculate FFT."""

    network = directed_edges.copy()
    supplied_speed = _finite_numeric(network["VEL_KMH"]).astype(float)
    invalid_supplied = supplied_speed.notna() & supplied_speed.le(0)
    if invalid_supplied.any():
        raise ValueError(
            "Non-positive supplied speeds found:\n"
            + network.loc[
                invalid_supplied,
                ["physical_edge_id", "source_part_id", "CLASE", "VEL_KMH"],
            ].to_string(index=False)
        )

    class_medians = network.assign(_speed=supplied_speed).groupby("CLASE")["_speed"].median()
    network["speed"] = supplied_speed
    network["speed_source"] = np.where(supplied_speed.notna(), "supplied", "missing")

    missing = network["speed"].isna()
    mapped_medians = network.loc[missing, "CLASE"].map(class_medians)
    usable_class_median = mapped_medians.notna()
    class_indices = mapped_medians.index[usable_class_median]
    network.loc[class_indices, "speed"] = mapped_medians.loc[class_indices]
    network.loc[class_indices, "speed_source"] = "class_median"

    remaining = network["speed"].isna()
    network.loc[remaining, "speed"] = config.statutory_default_speed_kmh
    network.loc[remaining, "speed_source"] = "statutory_default_60"

    network["road_length"] = network.geometry.length / 1_000.0
    network["fft"] = network["road_length"] / network["speed"]

    invalid = (
        ~np.isfinite(network["road_length"])
        | network["road_length"].le(0)
        | ~np.isfinite(network["speed"])
        | network["speed"].le(0)
        | ~np.isfinite(network["fft"])
        | network["fft"].le(0)
    )
    if invalid.any():
        detail_columns = [
            "physical_edge_id",
            "source_part_id",
            "ID_TRAMO",
            "TRAMO_UID",
            "CLASE",
            "VEL_KMH",
            "speed",
            "speed_source",
            "road_length",
            "fft",
            "DIRECCION",
        ]
        raise ValueError(
            "Invalid length/speed/fft rows:\n"
            + network.loc[invalid, detail_columns].to_string(index=False)
        )

    speed_summary = (
        network.groupby(["speed_source", "speed"], dropna=False)
        .size()
        .rename("directed_edges")
        .reset_index()
    )
    print("Resolved speed summary")
    print(speed_summary.to_string(index=False))
    return network, speed_summary


def extract_strong_giant_component(
    directed_edges: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, dict[str, Any]]:
    """Retain edges whose endpoints are both in the largest strong component."""

    if directed_edges.empty:
        raise ValueError("Cannot build a graph from an empty directed network")
    tuples = list(
        directed_edges[["from_id", "to_id"]].itertuples(index=False, name=None)
    )
    graph = ig.Graph.TupleList(tuples, directed=True)
    components = graph.connected_components(mode="strong")
    if len(components) == 0:
        raise ValueError("Directed graph contains no strong components")
    giant_vertex_indices = max(components, key=len)
    giant_node_ids = set(graph.vs[giant_vertex_indices]["name"])

    keep = directed_edges["from_id"].isin(giant_node_ids) & directed_edges["to_id"].isin(
        giant_node_ids
    )
    giant = directed_edges.loc[keep].copy().reset_index(drop=True)
    dropped = directed_edges.loc[~keep].copy().reset_index(drop=True)
    giant["id"] = np.arange(len(giant), dtype=np.int64)

    total_physical = (
        directed_edges.drop_duplicates("physical_edge_id")["road_length"].sum()
    )
    kept_physical = giant.drop_duplicates("physical_edge_id")["road_length"].sum()
    physical_fraction = float(kept_physical / total_physical) if total_physical else 0.0
    directed_fraction = float(giant["road_length"].sum() / directed_edges["road_length"].sum())

    stats = {
        "graph_vertices": graph.vcount(),
        "strong_components": len(components),
        "giant_vertices": len(giant_node_ids),
        "directed_edges_total": len(directed_edges),
        "directed_edges_kept": len(giant),
        "directed_edges_dropped": len(dropped),
        "directed_length_fraction": directed_fraction,
        "physical_length_total_km": float(total_physical),
        "physical_length_kept_km": float(kept_physical),
        "physical_length_fraction": physical_fraction,
    }
    print("Strongly connected giant component")
    for key, value in stats.items():
        if "fraction" in key:
            print(f"  {key:<31}: {100 * value:.2f}%")
        elif isinstance(value, float):
            print(f"  {key:<31}: {value:,.2f}")
        else:
            print(f"  {key:<31}: {value:,}")
    return giant, dropped, stats


def plot_giant_component_diagnostics(
    directed_edges: gpd.GeoDataFrame,
    giant_edges: gpd.GeoDataFrame,
    dropped_edges: gpd.GeoDataFrame,
    config: CRNetworkPrepConfig,
    show: bool = True,
) -> Path:
    """Save an included-versus-dropped physical-network map."""

    base = directed_edges.drop_duplicates("physical_edge_id").to_crs(3857)
    kept_ids = set(giant_edges["physical_edge_id"])
    dropped_ids = set(dropped_edges["physical_edge_id"])
    fig, ax = plt.subplots(figsize=(12, 10), facecolor="white")
    base.loc[base["physical_edge_id"].isin(kept_ids)].plot(
        ax=ax, color="#777777", linewidth=0.55, alpha=0.75, zorder=2
    )
    if dropped_ids:
        base.loc[base["physical_edge_id"].isin(dropped_ids)].plot(
            ax=ax, color="#D73027", linewidth=1.5, alpha=0.95, zorder=3
        )
    _safe_add_basemap(ax, base.crs, enabled=config.add_basemap)
    ax.legend(
        handles=[
            Line2D([0], [0], color="#777777", lw=2, label="Included"),
            Line2D([0], [0], color="#D73027", lw=2, label="Dropped"),
        ],
        title="Strong giant component",
        loc="upper right",
    )
    ax.set_title("Strong Giant Component — Included and Dropped Roads", fontweight="bold")
    ax.axis("off")
    fig.tight_layout()
    output = config.figure_path / "giant_component_dropped_roads.png"
    fig.savefig(output, dpi=config.figure_dpi, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    return output


def _fiona_field_type(dtype) -> str:
    if pd.api.types.is_integer_dtype(dtype) or pd.api.types.is_bool_dtype(dtype):
        return "int"
    if pd.api.types.is_float_dtype(dtype):
        return "float"
    return "str"


def _write_empty_geopackage(
    frame: gpd.GeoDataFrame,
    path: Path,
    layer: str,
) -> None:
    import fiona

    properties = {
        column: _fiona_field_type(dtype)
        for column, dtype in frame.drop(columns="geometry").dtypes.items()
    }
    schema = {"geometry": "LineString", "properties": properties}
    with fiona.open(
        path,
        mode="w",
        driver="GPKG",
        layer=layer,
        schema=schema,
        crs_wkt=frame.crs.to_wkt() if frame.crs else None,
    ):
        pass


def _write_geopackage(frame: gpd.GeoDataFrame, path: Path, layer: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    if frame.empty:
        _write_empty_geopackage(frame, path, layer)
    else:
        frame.to_file(
            path,
            layer=layer,
            driver="GPKG",
            engine="fiona",
            index=False,
        )


def save_outputs(
    directed_edges: gpd.GeoDataFrame,
    giant_edges: gpd.GeoDataFrame,
    dropped_edges: gpd.GeoDataFrame,
    giant_stats: dict[str, Any],
    config: CRNetworkPrepConfig,
    show: bool = True,
) -> pd.DataFrame:
    """Save diagnostics first, enforce the 95% rule, then save/re-open output."""

    config.ensure_output_dirs()
    plot_giant_component_diagnostics(
        directed_edges, giant_edges, dropped_edges, config, show=show
    )
    _write_geopackage(
        dropped_edges,
        config.dropped_roads_path,
        "giant_component_dropped_roads",
    )
    print(f"Saved dropped-road diagnostics: {config.dropped_roads_path}")

    retained_pct = 100 * giant_stats["physical_length_fraction"]
    if retained_pct < config.min_giant_component_length_pct:
        raise AssertionError(
            f"Strong giant component retains {retained_pct:.2f}% of unique physical "
            f"network length, below the {config.min_giant_component_length_pct:.2f}% "
            f"threshold. Inspect {config.dropped_roads_path}."
        )

    _write_geopackage(
        giant_edges,
        config.main_network_path,
        "main_network_directed",
    )
    reloaded = _read_vector(
        config.main_network_path, layer="main_network_directed"
    )
    required_output = [
        "id",
        "physical_edge_id",
        "from_id",
        "to_id",
        *AADT_COLUMNS,
        *AADT_ALIASES.values(),
        "total_aadt",
        "road_length",
        "speed",
        "fft",
        "DIRECCION",
        "direction_side",
        "aadt_imputed",
        "speed_source",
    ]
    missing = [column for column in required_output if column not in reloaded]
    if missing:
        raise AssertionError(f"Saved network is missing required fields: {missing}")
    if len(reloaded) != len(giant_edges):
        raise AssertionError(
            f"Saved row count changed: expected {len(giant_edges)}, got {len(reloaded)}"
        )
    if reloaded.crs != giant_edges.crs:
        raise AssertionError(
            f"Saved CRS changed: expected {giant_edges.crs}, got {reloaded.crs}"
        )
    if reloaded["id"].duplicated().any():
        raise AssertionError("Saved directed edge IDs are not unique")
    critical = ["from_id", "to_id", *AADT_COLUMNS, "total_aadt", "road_length", "speed", "fft"]
    if reloaded[critical].isna().any().any():
        raise AssertionError("Saved network contains null critical fields")

    manifest = pd.DataFrame(
        [
            {
                "output": "main_network_directed",
                "path": str(config.main_network_path.resolve()),
                "layer": "main_network_directed",
                "rows": len(reloaded),
                "crs": str(reloaded.crs),
                "size_bytes": config.main_network_path.stat().st_size,
            },
            {
                "output": "giant_component_dropped_roads",
                "path": str(config.dropped_roads_path.resolve()),
                "layer": "giant_component_dropped_roads",
                "rows": len(dropped_edges),
                "crs": str(dropped_edges.crs),
                "size_bytes": config.dropped_roads_path.stat().st_size,
            },
        ]
    )
    print("Output manifest")
    print(manifest.to_string(index=False))
    return manifest


def run_workflow(
    config: CRNetworkPrepConfig,
    make_figures: bool = True,
    show_figures: bool = True,
) -> dict[str, Any]:
    """Execute the complete workflow; the notebook exposes the same stages."""

    roads, load_stats = load_and_validate_network(config)
    snapped, snap_log = snap_network_iteratively(
        roads,
        tolerance_m=config.snap_tolerance_m,
        search_buffer_m=config.snap_search_buffer_m,
        max_iterations=config.snap_max_iterations,
    )
    snap_log.to_csv(config.gpkg_dir / "endpoint_snap_log.csv", index=False)
    physical_edges, nodes, topology_stats = build_topology(snapped)
    physical_edges, completeness, fill_sources = fill_missing_aadt(physical_edges)
    if make_figures:
        aadt_breaks = plot_aadt_maps(physical_edges, config, show=show_figures)
    else:
        aadt_breaks = {}
    directed_edges, direction_stats = create_directed_edges(physical_edges)
    if make_figures:
        plot_direction_qa(physical_edges.assign(
            DIRECCION=physical_edges["DIRECCION"].map(_normalise_direction).fillna("Bidireccional")
        ), config, show=show_figures)
    directed_edges, speed_summary = add_speed_and_travel_time(directed_edges, config)
    giant_edges, dropped_edges, giant_stats = extract_strong_giant_component(directed_edges)
    manifest = save_outputs(
        directed_edges,
        giant_edges,
        dropped_edges,
        giant_stats,
        config,
        show=show_figures,
    )
    return {
        "roads": roads,
        "snapped": snapped,
        "snap_log": snap_log,
        "physical_edges": physical_edges,
        "nodes": nodes,
        "directed_edges": directed_edges,
        "giant_edges": giant_edges,
        "dropped_edges": dropped_edges,
        "load_stats": load_stats,
        "topology_stats": topology_stats,
        "direction_stats": direction_stats,
        "giant_stats": giant_stats,
        "aadt_completeness": completeness,
        "aadt_fill_sources": fill_sources,
        "aadt_breaks": aadt_breaks,
        "speed_summary": speed_summary,
        "manifest": manifest,
    }


__all__ = [
    "AADT_ALIASES",
    "AADT_COLUMNS",
    "AADT_LABELS",
    "CRNetworkPrepConfig",
    "add_speed_and_travel_time",
    "build_topology",
    "create_directed_edges",
    "extract_strong_giant_component",
    "fill_missing_aadt",
    "load_and_validate_network",
    "plot_aadt_maps",
    "plot_direction_qa",
    "plot_giant_component_diagnostics",
    "run_workflow",
    "save_outputs",
    "snap_network_iteratively",
]
