"""Read original Census archives; derive bounded display geometry separately."""

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
# These leave room under Workspace's map budgets for labels and multipart shapes.
MAX_PREVIEW_BYTES = 1_500_000
MAX_PREVIEW_VERTICES = 75_000
PREVIEW_FIELDS = (
    "GEOID",
    "GEOID20",
    "NAME",
    "NAMELSAD",
    "FULLNAME",
    "TLID",
    "LINEARID",
    "MTFCC",
    "ZIPL",
    "ZIPR",
    "LFROMHN",
    "LTOHN",
    "RFROMHN",
    "RTOHN",
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


def attributes(dataset: str, page: int, page_size: int) -> list[dict]:
    definition, _source, path = selected(dataset)
    info = pyogrio.read_info(path, layer=definition.layer)
    offset = (page - 1) * page_size
    if offset >= info["features"]:
        return []
    _meta, table = pyogrio.read_arrow(
        path,
        layer=definition.layer,
        read_geometry=False,
        skip_features=offset,
        max_features=page_size,
    )
    return table.to_pylist()


def preview(dataset: str, limit: int, simplify_m: float) -> dict:
    definition, source, path = selected(dataset)
    if not definition.spatial:
        raise HTTPException(
            400, "This relationship table has no geometry. Read /attributes instead."
        )
    info = pyogrio.read_info(path, layer=definition.layer)
    # Select display fields only. Attribute reads above always retain every original field.
    fields = [key for key in PREVIEW_FIELDS if key in info["fields"]][:8]
    meta, table = pyogrio.read_arrow(
        path,
        layer=definition.layer,
        columns=fields,
        max_features=limit,
    )
    geometry_column = meta["geometry_name"] or "wkb_geometry"
    to_wgs84 = Transformer.from_crs(info["crs"], "EPSG:4326", always_xy=True)
    # All curated extracts are in DC: UTM zone 18N gives simplification units in metres.
    to_local = Transformer.from_crs(info["crs"], "EPSG:26918", always_xy=True)
    local_to_wgs84 = Transformer.from_crs("EPSG:26918", "EPSG:4326", always_xy=True)
    features = []
    vertices = 0
    parts = 0
    for row in table.to_pylist():
        wkb = row.pop(geometry_column)
        if wkb is None:
            continue
        geometry = force_2d(from_wkb(wkb))
        if simplify_m:
            geometry = transform(
                geometry, to_local.transform, interleaved=False
            ).simplify(
                simplify_m,
                preserve_topology=True,
            )
            geometry = transform(geometry, local_to_wgs84.transform, interleaved=False)
        else:
            geometry = transform(geometry, to_wgs84.transform, interleaved=False)
        if geometry.is_empty:
            continue
        vertices += int(get_num_coordinates(geometry))
        parts += len(geometry.geoms) if hasattr(geometry, "geoms") else 1
        if vertices > MAX_PREVIEW_VERTICES or parts > 3_000:
            raise HTTPException(
                413,
                "Preview exceeds the geometry budget. Reduce limit or increase simplify_m.",
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
                "properties": {"name": str(label), "color": "#2980b9", **row},
            }
        )
    total = int(info["features"])
    result = {
        "type": "FeatureCollection",
        "name": f"{definition.name} ({source.format}, {VINTAGE})",
        "features": features,
        "map": {
            "version": 1,
            "notes": [
                f"U.S. Census Bureau, TIGER/Line {VINTAGE}. Preview: {len(features):,} of {total:,} features.",
                f"Geometry simplified by {simplify_m:g} m per feature; shared boundaries may differ. Original geometry is in the archive download.",
                "Map cards show selected fields. The attribute table keeps all original fields and pages through the complete dataset.",
            ],
        },
        "preview": {
            "total_features": total,
            "returned_features": len(features),
            "simplify_m": simplify_m,
            "source_format": source.format,
            "source_url": source.url,
        },
    }
    if len(json.dumps(result).encode()) > MAX_PREVIEW_BYTES:
        raise HTTPException(
            413, "Preview exceeds the size budget. Reduce limit or increase simplify_m."
        )
    return result
