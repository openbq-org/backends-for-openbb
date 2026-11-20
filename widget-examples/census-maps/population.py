"""2020 counts and geometry are aggregated from the same complete Block20 layer."""

from collections import defaultdict

from pyproj import Transformer
from shapely import force_2d, from_wkb, transform, union_all
from shapely.geometry import mapping

import census


def block_points() -> list[dict]:
    _meta, table = census.records(
        "gdb_blocks",
        columns=["GEOID20", "POP20", "HOUSING20", "INTPTLAT20", "INTPTLON20"],
    )
    return [
        {
            "lat": float(row["INTPTLAT20"]),
            "lon": float(row["INTPTLON20"]),
            "label": row["GEOID20"],
            "value": row["POP20"],
            "props": {"Housing units (2020)": row["HOUSING20"]},
        }
        for row in table.to_pylist()
        if row["POP20"] is not None and row["POP20"] > 0
    ]


def tracts() -> list[dict]:
    meta, table = census.records(
        "gdb_blocks",
        geometry=True,
        columns=["GEOID20", "POP20", "HOUSING20", "ALAND20"],
    )
    geometry_column = meta["geometry_name"] or "wkb_geometry"
    groups = defaultdict(
        lambda: {"population": 0, "housing": 0, "land_m2": 0, "geometries": []}
    )
    for row in table.to_pylist():
        group = groups[row["GEOID20"][:11]]
        group["population"] += row["POP20"] or 0
        group["housing"] += row["HOUSING20"] or 0
        group["land_m2"] += row["ALAND20"] or 0
        group["geometries"].append(force_2d(from_wkb(row[geometry_column])))
    to_local = Transformer.from_crs(meta["crs"], "EPSG:26918", always_xy=True)
    to_wgs84 = Transformer.from_crs("EPSG:26918", "EPSG:4326", always_xy=True)
    result = []
    for code, group in sorted(groups.items()):
        original = union_all(group.pop("geometries"))
        local = transform(original, to_local.transform, interleaved=False).simplify(
            15, preserve_topology=True
        )
        geometry = transform(local, to_wgs84.transform, interleaved=False)
        point = geometry.representative_point()
        density = (
            group["population"] / (group["land_m2"] / 1_000_000)
            if group["land_m2"] > 0
            else None
        )
        result.append(
            {
                "geoid": code,
                **group,
                "density": density,
                "geometry": mapping(geometry),
                "lon": point.x,
                "lat": point.y,
            }
        )
    return result
