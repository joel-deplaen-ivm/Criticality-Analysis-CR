"""
Shared helpers for the CR criticality ArcGIS toolbox
----------------------------------------------------
Used by T1_prepare_network.py and T2_spof_criticality.py (and later tools).

Runs in a CLONED ArcGIS Pro conda environment that has geopandas, shapely,
numpy, pandas, scipy and python-igraph installed on top of arcpy.  Every tool
also runs outside ArcGIS (plain Python, command-line arguments) so it can be
tested against the notebook outputs; arcpy is optional and only used for
messages, progress and parameter reading.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import arcpy  # type: ignore
except ImportError:  # outside ArcGIS Pro
    arcpy = None


# ------------------------------------------------------------------
# Repository import
# ------------------------------------------------------------------

# T1 reuses the notebook library (src/network_preparation_cr.py) unchanged, so the
# toolbox and the notebook cannot drift apart.  The toolbox folder sits inside the
# repo; CR_REPO_ROOT overrides that if the toolbox is copied elsewhere.
REPO_ROOT = Path(os.environ.get("CR_REPO_ROOT", Path(__file__).resolve().parents[1]))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def require_packages(names: List[str]):
    """Fail with one readable message listing every package missing from the environment"""
    # 1) Try each import without keeping the module
    missing = []
    for name in names:
        try:
            __import__(name)
        except ImportError:
            missing.append(name)

    # 2) Report all missing packages at once, with the install hint
    if missing:
        raise ImportError(
            f"Missing packages in this Python environment: {', '.join(missing)}. "
            "Clone the ArcGIS Pro environment and install them "
            "(e.g. conda install -c conda-forge geopandas python-igraph scipy)."
        )


# ------------------------------------------------------------------
# Messages / parameters
# ------------------------------------------------------------------


def msg(text: str = ""):
    """Write a message to the ArcGIS geoprocessing pane, or stdout outside ArcGIS"""
    if arcpy:
        arcpy.AddMessage(text)
    else:
        # sys.__stdout__: print() may be redirected into this very function (messages_from_print)
        print(text, file=sys.__stdout__, flush=True)


def warn(text: str):
    """Write a warning to the ArcGIS geoprocessing pane, or stdout outside ArcGIS"""
    if arcpy:
        arcpy.AddWarning(text)
    else:
        print(f"WARNING: {text}", flush=True)


class _MessageStream:
    """File-like object that forwards print() output of the notebook library to msg()"""

    def __init__(self):
        self._buf = ""

    def write(self, text):
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            msg(line)
        return len(text)

    def flush(self):
        if self._buf:
            msg(self._buf)
            self._buf = ""


@contextlib.contextmanager
def messages_from_print():
    """Route print() inside the block to the geoprocessing messages"""
    stream = _MessageStream()
    with contextlib.redirect_stdout(stream):
        yield
    stream.flush()


def read_parameters(spec: List[Tuple[str, str]]) -> Dict[str, str]:
    """Read tool parameters by position in ArcGIS, or as --name arguments outside it.

    spec is [(name, default), ...] in the exact order of the tool dialog.
    """
    # 1) Inside ArcGIS: positional GetParameterAsText, empty -> default
    if arcpy:
        out = {}
        for i, (name, default) in enumerate(spec):
            raw = arcpy.GetParameterAsText(i)
            out[name] = raw if raw not in (None, "") else default
        return out

    # 2) Outside ArcGIS: the same names as command-line options
    parser = argparse.ArgumentParser()
    for name, default in spec:
        parser.add_argument(f"--{name}", default=default)
    return vars(parser.parse_args())


def set_outputs(first_index: int, values: List[str]):
    """Return derived output parameters to the tool dialog (no-op outside ArcGIS)"""
    if arcpy:
        for k, v in enumerate(values):
            arcpy.SetParameterAsText(first_index + k, v)


class Progress:
    """Progress bar in ArcGIS (SetProgressor), coarse log lines outside it"""

    def __init__(self, label: str, total: int, log_every: float = 0.1):
        self.label, self.total, self.n = label, max(int(total), 1), 0
        self._next_log = log_every
        self._log_every = log_every
        if arcpy:
            arcpy.SetProgressor("step", label, 0, self.total, 1)

    def step(self):
        self.n += 1
        if arcpy:
            arcpy.SetProgressorPosition(self.n)
        if self.n / self.total >= self._next_log:
            msg(f"  {self.label}: {self.n:,}/{self.total:,} ({100 * self.n / self.total:.0f}%)")
            self._next_log += self._log_every

    def done(self):
        if arcpy:
            arcpy.ResetProgressor()


def timestamp() -> str:
    """Run stamp used in output folder names, e.g. 20251117_134522"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_run_config(out_dir: Path, tool: str, stamp: str, params: Dict[str, object]) -> Path:
    """Dump every parameter of a run to Loc/run_config_<tool>_<stamp>.loc (BSA2 convention)"""
    loc_dir = Path(out_dir) / "Loc"
    loc_dir.mkdir(parents=True, exist_ok=True)
    loc_path = loc_dir / f"run_config_{tool}_{stamp}.loc"
    with open(loc_path, "w", encoding="utf-8") as f:
        for name, value in params.items():
            f.write(f"{name}={value}\n")
    return loc_path


# ------------------------------------------------------------------
# Paths / vector IO
# ------------------------------------------------------------------


def resolve_input(text: str) -> str:
    """Turn a map-layer name or dialog entry into a catalog path (identity outside ArcGIS)"""
    # 1) A layer picked from the map is a name, not a path
    if arcpy and text and not os.path.exists(text):
        try:
            return arcpy.Describe(text).catalogPath
        except Exception:
            pass
    return text


def split_container(path: str) -> Tuple[str, Optional[str]]:
    """Split 'x.gpkg/layer' or 'x.gdb\\fc' into (container, layer); plain files give layer None"""
    # 1) Normalise separators, then look for a container extension followed by a layer
    p = path.replace("\\", "/")
    for ext in (".gpkg", ".gdb"):
        i = p.lower().find(ext + "/")
        if i != -1:
            return p[: i + len(ext)], p[i + len(ext) + 1:]
    return path, None


def read_vector(path: str, layer: Optional[str] = None):
    """Read a shapefile, GeoPackage layer or file-geodatabase feature class with geopandas"""
    import geopandas as gpd

    # 1) Resolve 'container/layer' notation, an explicit layer argument wins
    container, embedded = split_container(resolve_input(path))
    layer = layer or embedded

    # 2) Read; layer None lets GDAL pick the only layer
    if layer:
        return gpd.read_file(container, layer=layer)
    return gpd.read_file(container)


def layer_path(gpkg: Path, layer: str) -> str:
    """Path form ArcGIS Pro uses for a GeoPackage layer: <file>.gpkg\\<layer>"""
    return f"{gpkg}{os.sep}{layer}"


def write_gpkg(frame, path: Path, layer: str):
    """Write a GeoDataFrame to a fresh single-layer GeoPackage (empty frames keep their schema)"""
    # 1) Start from a clean file so a re-run never appends
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)

    # 2) Empty frames need an explicit schema (same helper the notebook library uses)
    if frame.empty:
        from src.network_preparation_cr import _write_empty_geopackage

        _write_empty_geopackage(frame, path, layer)
    else:
        frame.to_file(path, layer=layer, driver="GPKG", index=False)


@contextlib.contextmanager
def scratch_dir():
    """Temporary folder removed after the tool finishes"""
    with tempfile.TemporaryDirectory(prefix="cr_toolbox_") as tmp:
        yield Path(tmp)


# ------------------------------------------------------------------
# Graph / OD model (shared by T2 and later tools)
# ------------------------------------------------------------------

# Routing attributes carried onto graph edges.  Deliberately minimal: the
# percolation loop copies the graph once per iteration (same as notebook 2).
GRAPH_EDGE_ATTRS = ["id", "physical_edge_id", "road_length", "fft"]


def build_graph(edges):
    """Directed igraph graph on from_id / to_id carrying GRAPH_EDGE_ATTRS"""
    import igraph as ig

    # 1) TupleList takes the FIRST TWO columns as endpoints: order is load-bearing
    graph_cols = ["from_id", "to_id"] + GRAPH_EDGE_ATTRS
    graph = ig.Graph.TupleList(
        edges[graph_cols].itertuples(index=False),
        edge_attrs=GRAPH_EDGE_ATTRS,
        directed=True,
    )

    # 2) Every row must have become one edge
    if graph.ecount() != len(edges):
        raise AssertionError("Edge count mismatch - check column ordering")
    return graph


def run_shortest_paths(graph, vertex_ids, weighting="fft"):
    """All-pairs shortest path matrix between OD vertices under the given edge weight"""
    import numpy as np

    return np.array(graph.distances(source=vertex_ids, target=vertex_ids, weights=weighting))


def create_demand(node_pop, od_time, dist_decay, maxtrips):
    """Gravity model: Demand_a,b = Pop_a * Pop_b * exp(-decay * normalised distance)"""
    import numpy as np

    # 1) Distance normalised by its maximum, population outer product
    normalized_dist = np.asarray(od_time / od_time.max())
    pop = np.asarray(node_pop, dtype=float)
    demand = np.outer(pop, pop) * np.exp(-dist_decay * normalized_dist)

    # 2) No self-trips; scale the busiest pair to maxtrips and round up
    np.fill_diagonal(demand, 0)
    demand = (demand / demand.max()) * maxtrips
    return np.ceil(demand).astype(int)


def fingerprint(*arrays_and_values) -> str:
    """Short hash of arrays / scalars, used to key the percolation cache"""
    import numpy as np

    h = hashlib.sha1()
    for item in arrays_and_values:
        if isinstance(item, np.ndarray):
            h.update(np.ascontiguousarray(item).tobytes())
        else:
            h.update(repr(item).encode())
    return h.hexdigest()[:16]
