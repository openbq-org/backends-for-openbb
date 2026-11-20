"""Read original Census archives; derive display geometry separately."""

import json
import os
from pathlib import Path

import pyogrio
from fastapi import HTTPException
from pyproj import Transformer
from shapely import force_2d, from_wkb, get_num_coordinates, transform
from shapely.geometry import mapping

from catalog import DATASETS, SOURCES, VINTAGE

DATA_DIR = Path(os.environ.get("CENSUS_DATA_DIR", Path(__file__).parent / ".data"))
MAX_PREVIEW_FEATURES = 500
MAX_PREVIEW_BYTES = 1_500_000
MAX_PREVIEW_VERTICES = 75_000
PREVIEW_FIELDS = (
    "GEOID",
    "GEOID20",
    "NAMELSAD",
    "FULLNAME",
    "NAME",
    "MTFCC",
    "COUNTYFP",
    "POINTID",
    "AREAID",
    "TLID",
    "LINEARID",
    "ZIPL",
    "ZIPR",
    "ALAND",
    "AWATER",
    "POP20",
    "HOUSING20",
)


def selected(dataset: str):
    definition = DATASETS.get(dataset)
    if definition is None:
        raise HTTPException(404, "Unknown Census dataset. See /datasets.")
    source = SOURCES[definition.source]
    path = DATA_DIR / source.filename
    if not path.is_file():
        raise HTTPException(
            503, f"Missing {source.filename}. Run python prepare.py first."
        )
    return definition, source, path


def metadata(dataset: str) -> dict:
    definition, source, path = selected(dataset)
    info = pyogrio.read_info(path, layer=definition.layer)
    return {
        "dataset": dataset,
        "name": definition.name,
        "format": source.format,
        "vintage": VINTAGE,
        "source_url": source.url,
        "filename": source.filename,
        "geography": definition.geography,
        "layer": info["layer_name"],
        "crs": info["crs"],
        "geometry_type": info["geometry_type"],
        "total_features": int(info["features"]),
        "fields": [
            {"name": name, "type": dtype}
            for name, dtype in zip(info["fields"].tolist(), info["dtypes"].tolist())
        ],
        "layers": [
            {"name": name, "geometry_type": kind}
            for name, kind in pyogrio.list_layers(path).tolist()
        ],
    }


def records(
    dataset: str, *, geometry: bool = False, columns=None, offset=0, limit=None
):
    """One native read for tables, display geometry, or complete derived statistics."""
    definition, _source, path = selected(dataset)
    return pyogrio.read_arrow(
        path,
        layer=definition.layer,
        read_geometry=geometry,
        columns=columns,
        skip_features=offset,
        max_features=limit,
    )


def attributes(dataset: str, page: int, page_size: int) -> list[dict]:
    definition, _source, path = selected(dataset)
    info = pyogrio.read_info(path, layer=definition.layer)
    offset = (page - 1) * page_size
    if offset >= info["features"]:
        return []
    _meta, table = records(dataset, offset=offset, limit=page_size)
    return table.to_pylist()


def feature_collection(
    dataset: str, limit: int | None, simplify_m: float, columns=None
) -> dict:
    definition, source, path = selected(dataset)
    if not definition.spatial:
        raise HTTPException(
            400, "This relationship table has no geometry. Read /attributes instead."
        )
    info = pyogrio.read_info(path, layer=definition.layer)
    fields = [key for key in (columns or PREVIEW_FIELDS) if key in info["fields"]]
    meta, table = records(dataset, geometry=True, columns=fields, limit=limit)
    geometry_column = meta["geometry_name"] or "wkb_geometry"
    to_wgs84 = Transformer.from_crs(info["crs"], "EPSG:4326", always_xy=True)
    to_local = Transformer.from_crs(info["crs"], definition.metric_crs, always_xy=True)
    local_to_wgs84 = Transformer.from_crs(
        definition.metric_crs, "EPSG:4326", always_xy=True
    )
    features = []
    vertices = parts = max_rings = 0
    for row in table.to_pylist():
        wkb = row.pop(geometry_column)
        if wkb is None:
            continue
        geometry = force_2d(from_wkb(wkb))
        if simplify_m:
            geometry = transform(
                geometry, to_local.transform, interleaved=False
            ).simplify(simplify_m, preserve_topology=True)
            geometry = transform(geometry, local_to_wgs84.transform, interleaved=False)
        else:
            geometry = transform(geometry, to_wgs84.transform, interleaved=False)
        if geometry.is_empty:
            continue
        vertices += int(get_num_coordinates(geometry))
        components = list(geometry.geoms) if hasattr(geometry, "geoms") else [geometry]
        parts += len(components)
        max_rings = max(
            max_rings,
            *(
                1 + len(g.interiors) if g.geom_type == "Polygon" else 0
                for g in components
            ),
        )
        label = next(
            (
                row[key]
                for key in ("NAMELSAD", "FULLNAME", "NAME", "GEOID", "GEOID20")
                if row.get(key)
            ),
            definition.name,
        )
        features.append(
            {
                "type": "Feature",
                "geometry": mapping(geometry),
                "properties": {"name": str(label), **row},
            }
        )
    total = int(info["features"])
    return {
        "type": "FeatureCollection",
        "name": f"{definition.name} ({source.format}, {VINTAGE})",
        "features": features,
        "map": {
            "version": 1,
            "notes": [
                f"U.S. Census Bureau {VINTAGE}: {len(features):,} of {total:,} features; display simplified {simplify_m:g} m.",
                "Simplification preserves each feature, not shared boundaries. Original geometry is in the archive download.",
                "Map cards show selected fields. Attribute pages retain every original field.",
            ],
        },
        "preview": {
            "total_features": total,
            "returned_features": len(features),
            "simplify_m": simplify_m,
            "source_format": source.format,
            "source_url": source.url,
            "vertices": vertices,
            "parts": parts,
            "max_rings": max_rings,
        },
    }


def check_display(collection: dict) -> dict:
    counts = collection["preview"]
    if (
        counts["vertices"] > MAX_PREVIEW_VERTICES
        or counts["parts"] > 3_000
        or counts["max_rings"] > 200
    ):
        raise HTTPException(
            413,
            "Preview exceeds the geometry budget. Reduce limit or increase simplify_m.",
        )
    if len(json.dumps(collection).encode()) > MAX_PREVIEW_BYTES:
        raise HTTPException(
            413, "Preview exceeds the size budget. Reduce limit or increase simplify_m."
        )
    return collection


def preview(dataset: str, limit: int, simplify_m: float) -> dict:
    return check_display(
        feature_collection(dataset, limit, simplify_m, columns=PREVIEW_FIELDS[:8])
    )
