"""Shared map style for the Costa Rica notebooks.

Every CR map is finished with one call, ``style_cr_map(ax, crs=...)``, after the
data layers are drawn. It applies the same frame and furniture to every figure:

* the mainland Costa Rica extent (2 % padding), axes off, equal aspect;
* a CARTO Positron basemap, label-free variant (alpha 0.4), with a small attribution line;
* everything outside Costa Rica (Nicaragua, Panama, the sea) faded with white;
* the national outline;
* the three reference cities San José, Liberia and Limón;
* the legend in the lower left, in one frame style;
* the Aptos font for every figure that imports this module (when installed).

The helpers work in any CRS the notebooks draw in: 3857 (basemap-native),
8908 (CRTM05, the CR working CRS) and 4326 (the hazard rasters in 4a). Tiles
are reprojected by contextily when the axis is not in 3857.

Assumptions (figure framing only; no analysis input is modified):

* Boundary = MIDEPLAN IDS 2023 district polygons, dissolved. Parts farther than
  ``MAINLAND_MAX_DIST_M`` from the largest part are dropped, which removes Isla
  del Coco; the road networks are mainland-only.
* San José is a hard-coded point in the historic centre. CENTROS_POBLACION has
  no single point for the capital: it is split into district heads (Carmen,
  Catedral, Merced, ...). Liberia and Limón are the IGN provincial-head points.

The CARTO basemap needs an API key: without one the endpoint serves
"API KEY REQUIRED" placeholder tiles. The key is read from the environment
variable ``CARTO_BASEMAP_API_KEY`` or from ``<repo>/.carto_api_key``
(gitignored). With neither, the keyless Esri World Gray Canvas is used instead
and a warning is raised.
"""

from __future__ import annotations

import os
import warnings
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
import matplotlib.font_manager as fm
import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import shapely

try:
    import contextily as cx
except Exception as exc:  # optional: a broken tile stack must not stop a notebook
    cx = None
    _CONTEXTILY_IMPORT_ERROR = exc
else:
    _CONTEXTILY_IMPORT_ERROR = None


BASE_DIR = Path(__file__).resolve().parents[1]
DISTRICTS_SHP = BASE_DIR / "input_files" / "ids_2023_distrital" / "ids_2023_distrito.shp"
LOCALITIES_SHP = (
    BASE_DIR / "input_files" / "CENTROS_POBLACION" / "centros_poblados_localidades.shp"
)
TILE_CACHE_DIR = BASE_DIR / "intermediate_results" / "tile_cache"
CARTO_KEY_FILE = BASE_DIR / ".carto_api_key"

WORKING_EPSG = 8908            # CR-SIRGAS / CRTM05, metres
MAINLAND_MAX_DIST_M = 100_000  # drop boundary parts farther than this from the mainland
EXTENT_PAD_FRAC = 0.02         # padding around the mainland boundary

BASEMAP_ALPHA = 0.4
FADE_COLOR = "white"
FADE_ALPHA = 0.5
BOUNDARY_COLOR = "#333333"
BOUNDARY_WIDTH = 1.0

# Draw order. Data layers in the notebooks sit between 0 and ~10.
BASEMAP_Z = -1
FADE_Z = 20
BOUNDARY_Z = 21
CITY_Z = 22
LEGEND_Z = 30

# (lon, lat) for San José only; the others come from CENTROS_POBLACION.
# Label offsets are in points, chosen so no label runs into the sea.
SAN_JOSE_LONLAT = (-84.0796, 9.9326)   # Catedral Metropolitana, central San José
MAIN_CITIES = {
    "San José": {"offset": (6, -11), "ha": "left"},
    "Liberia": {"offset": (6, 4), "ha": "left"},
    "Limón": {"offset": (-6, 4), "ha": "right"},
}

# Legend font sizes are for a map LEGEND_REF_WIDTH_IN wide (a single 12 x 10 in figure).
# On narrower maps they shrink in proportion, down to LEGEND_MIN_SCALE, so the legend
# takes the same share of every map instead of covering the north-east of the country.
LEGEND_REF_WIDTH_IN = 9.3
LEGEND_MIN_SCALE = 0.7
LEGEND_KW = dict(
    loc="lower left",
    fontsize=15,
    title_fontsize=15,
    frameon=True,
    fancybox=True,
    shadow=True,
    framealpha=0.9,
    facecolor="white",
    edgecolor="#cccccc",
)


# ---------------------------------------------------------------------------
# Basemap source
# ---------------------------------------------------------------------------
def _carto_api_key() -> str | None:
    key = os.environ.get("CARTO_BASEMAP_API_KEY", "").strip()
    if not key and CARTO_KEY_FILE.exists():
        key = CARTO_KEY_FILE.read_text().strip()
    return key or None


def _basemap_source():
    if cx is None:
        return None
    key = _carto_api_key()
    if key:
        # Label-free variant: Positron's own place names would ghost behind the city labels.
        source = cx.providers.CartoDB.PositronNoLabels.copy()
        source["url"] = f"{source['url']}?key={key}"
        return source
    warnings.warn(
        "No CARTO API key (set CARTO_BASEMAP_API_KEY or create .carto_api_key); "
        "using the keyless Esri World Gray Canvas basemap instead.",
        RuntimeWarning,
    )
    return cx.providers.Esri.WorldGrayCanvas


BASEMAP_SOURCE = _basemap_source()

# Figure font. Aptos ships with Microsoft 365, not with matplotlib; when it is not
# installed the default font is kept and a warning is raised.
FONT_FAMILY = "Aptos"
if any(f.name == FONT_FAMILY for f in fm.fontManager.ttflist):
    plt.rcParams["font.family"] = FONT_FAMILY
else:
    warnings.warn(f"Font '{FONT_FAMILY}' not installed; using matplotlib's default font.",
                  RuntimeWarning)

if cx is not None:
    # Tiles persist between sessions, so re-running a notebook does not refetch them.
    TILE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cx.set_cache_dir(str(TILE_CACHE_DIR))


# ---------------------------------------------------------------------------
# Reference layers
# ---------------------------------------------------------------------------
@lru_cache(maxsize=None)
def _mainland_boundary_8908() -> shapely.Geometry:
    parts = (
        gpd.GeoSeries(gpd.read_file(DISTRICTS_SHP).to_crs(WORKING_EPSG).union_all(),
                      crs=WORKING_EPSG)
        .explode(index_parts=False)
        .reset_index(drop=True)
    )
    mainland = parts.loc[parts.area.idxmax()]
    return parts[parts.distance(mainland) <= MAINLAND_MAX_DIST_M].union_all()


def get_cr_boundary(crs=WORKING_EPSG) -> gpd.GeoSeries:
    """Mainland Costa Rica as a one-row GeoSeries in *crs*."""
    return gpd.GeoSeries([_mainland_boundary_8908()], crs=WORKING_EPSG).to_crs(crs)


def get_cr_extent(crs=3857) -> tuple[tuple[float, float], tuple[float, float]]:
    """``(xlim, ylim)`` of the padded mainland boundary in *crs*."""
    minx, miny, maxx, maxy = get_cr_boundary(crs).total_bounds
    pad_x = EXTENT_PAD_FRAC * (maxx - minx)
    pad_y = EXTENT_PAD_FRAC * (maxy - miny)
    return (minx - pad_x, maxx + pad_x), (miny - pad_y, maxy + pad_y)


@lru_cache(maxsize=None)
def _main_cities_4326() -> gpd.GeoDataFrame:
    localities = gpd.read_file(LOCALITIES_SHP)
    heads = localities[localities["TIPO"].eq("Ciudad/Cabecera de Provincia")]
    heads = heads.set_index("NOMBRE").to_crs(4326)
    points = {"San José": shapely.Point(SAN_JOSE_LONLAT)}
    for name in MAIN_CITIES:
        if name not in points:
            points[name] = heads.geometry.loc[name]
    return gpd.GeoDataFrame(
        {"name": list(MAIN_CITIES)},
        geometry=[points[name] for name in MAIN_CITIES],
        crs=4326,
    )


def get_main_cities(crs=3857) -> gpd.GeoDataFrame:
    """San José, Liberia and Limón as points in *crs*."""
    return _main_cities_4326().to_crs(crs)


# ---------------------------------------------------------------------------
# Map furniture
# ---------------------------------------------------------------------------
def set_cr_extent(ax, crs=3857) -> None:
    """Frame *ax* on mainland Costa Rica."""
    xlim, ylim = get_cr_extent(crs)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)


def add_basemap_safe(ax, crs=3857, alpha=BASEMAP_ALPHA) -> None:
    """Add the basemap when tiles are reachable; otherwise continue without it."""
    if cx is None:
        warnings.warn(f"Basemap skipped: contextily unavailable ({_CONTEXTILY_IMPORT_ERROR})",
                      RuntimeWarning)
        return
    try:
        cx.add_basemap(
            ax=ax,
            crs=gpd.GeoSeries([], crs=crs).crs,
            source=BASEMAP_SOURCE,
            alpha=alpha,
            attribution=BASEMAP_SOURCE.get("attribution", ""),
            attribution_size=6,
            zorder=BASEMAP_Z,
        )
    except Exception as exc:
        warnings.warn(f"Skipping basemap because tiles could not be loaded: {exc}",
                      RuntimeWarning)


def add_outside_fade(ax, crs=3857) -> None:
    """Wash out everything outside Costa Rica: neighbours and the sea."""
    xlim, ylim = get_cr_extent(crs)
    width, height = xlim[1] - xlim[0], ylim[1] - ylim[0]
    frame = shapely.box(xlim[0] - width, ylim[0] - height, xlim[1] + width, ylim[1] + height)
    outside = frame.difference(get_cr_boundary(crs).iloc[0])
    gpd.GeoSeries([outside], crs=crs).plot(
        ax=ax, color=FADE_COLOR, alpha=FADE_ALPHA, linewidth=0, zorder=FADE_Z
    )


def add_cr_boundary(ax, crs=3857) -> None:
    get_cr_boundary(crs).boundary.plot(
        ax=ax, color=BOUNDARY_COLOR, linewidth=BOUNDARY_WIDTH, zorder=BOUNDARY_Z
    )


def add_main_cities(ax, crs=3857, fontsize=9) -> None:
    """Mark and label San José, Liberia and Limón."""
    halo = [path_effects.withStroke(linewidth=2.5, foreground="white")]
    for name, point in zip(*[get_main_cities(crs)[c] for c in ("name", "geometry")]):
        ax.plot(point.x, point.y, marker="o", markersize=5, color="#111111",
                markeredgecolor="white", markeredgewidth=0.8, zorder=CITY_Z)
        ax.annotate(
            name, xy=(point.x, point.y), xytext=MAIN_CITIES[name]["offset"],
            textcoords="offset points", ha=MAIN_CITIES[name]["ha"], va="center",
            fontsize=fontsize, fontweight="bold", color="#111111",
            path_effects=halo, zorder=CITY_Z,
        )


def add_cr_legend(ax, handles, title=None, **overrides):
    """Lower-left legend in the shared frame style.

    The legend is added as an artist, so a map can carry more than one. Font sizes
    follow the map width unless ``fontsize`` / ``title_fontsize`` are passed.
    """
    width_in = ax.get_position().width * ax.figure.get_figwidth()
    scale = min(1.0, max(LEGEND_MIN_SCALE, width_in / LEGEND_REF_WIDTH_IN))
    scaled = {"fontsize": LEGEND_KW["fontsize"] * scale,
              "title_fontsize": LEGEND_KW["title_fontsize"] * scale}
    legend = ax.legend(handles=handles, title=title, **{**LEGEND_KW, **scaled, **overrides})
    legend.set_zorder(LEGEND_Z)
    ax.add_artist(legend)
    return legend


def add_panel_label(ax, label, fontsize=20) -> None:
    ax.text(0.05, 0.95, label, transform=ax.transAxes, fontsize=fontsize,
            fontweight="bold", va="top", zorder=LEGEND_Z,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))


def style_cr_map(
    ax,
    crs=3857,
    *,
    legend_handles=None,
    legend_title=None,
    legend_kw=None,
    basemap=True,
    fade_outside=True,
    boundary=True,
    cities=True,
    city_fontsize=12,
    panel_label=None,
):
    """Apply the shared CR map style to *ax*. Call after the data layers are drawn.

    *crs* is the CRS the data on *ax* were drawn in. Returns the legend, if any.
    """
    ax.set_aspect("equal")
    ax.set_axis_off()
    # The extent is fixed before the basemap so contextily picks the right zoom.
    set_cr_extent(ax, crs)
    if basemap:
        add_basemap_safe(ax, crs)
    if fade_outside:
        add_outside_fade(ax, crs)
    if boundary:
        add_cr_boundary(ax, crs)
    if cities:
        add_main_cities(ax, crs, fontsize=city_fontsize)
    # Layers added above can autoscale the axis; restore the frame.
    set_cr_extent(ax, crs)
    if panel_label:
        add_panel_label(ax, panel_label)
    if legend_handles:
        return add_cr_legend(ax, legend_handles, legend_title, **(legend_kw or {}))
    return None
