"""Map presentations of the real Census inputs, with explicit derived measures."""

import base64

import census
import population
from examples import EXAMPLES

ROAD_SOURCE = {
    "id": "census-dc-roads",
    "name": "All DC roads",
    "kind": "geojson",
    "endpoint": "sources/roads.geojson",
    "role": "overlay",
    "attribution": "U.S. Census Bureau, TIGER/Line 2026",
    "bounds": [-77.13, 38.79, -76.90, 39.0],
    "layers": [{"type": "line", "color": "#f59e0b", "width": 1.7, "label": "FULLNAME"}],
}


def road_source() -> dict:
    return census.feature_collection(
        "shp_roads", None, 10, columns=("FULLNAME", "MTFCC")
    )


def _points(kind: str) -> dict:
    points = population.block_points()
    return {
        "title": EXAMPLES[kind].title,
        "layers": [
            {
                "id": "blocks",
                "name": "Populated 2020 blocks",
                "kind": kind,
                "valueLabel": "Population (2020)",
                "points": points,
            }
        ],
        "notes": [
            "U.S. Census Bureau, Block20. All source blocks were read; only blocks with positive population are plotted.",
            "Heat is relative concentration; cluster counts are blocks, not residents.",
        ],
    }


def _population(mode: str) -> dict:
    tracts = population.tracts()
    key, label = {
        "population": ("population", "Population (2020)"),
        "density": ("density", "People per km² of land (2020)"),
        "housing": ("housing", "Housing units (2020)"),
        "columns": ("population", "Population (2020)"),
    }[mode]
    notes = [
        "2020 Census counts and tract boundaries aggregated from the complete Block20 layer.",
        "Tracts are dissolved from the same 2020 block geometry; these are not 2026 population estimates.",
    ]
    if mode == "columns":
        return {
            "title": EXAMPLES[mode].title,
            "pitch": 45,
            "notes": notes,
            "layers": [
                {
                    "kind": "columns",
                    "name": "2020 tract population",
                    "valueLabel": label,
                    "points": [
                        {
                            "lat": row["lat"],
                            "lon": row["lon"],
                            "label": row["geoid"],
                            "value": row[key],
                            "props": {"Housing units": row["housing"]},
                        }
                        for row in tracts
                    ],
                }
            ],
        }
    return {
        "type": "FeatureCollection",
        "name": EXAMPLES[mode].title,
        "map": {"version": 1, "notes": notes, "basemap": {"roads": False}},
        "features": [
            {
                "type": "Feature",
                "geometry": row["geometry"],
                "properties": {
                    "name": row["geoid"],
                    "value": row[key],
                    "valueLabel": label,
                    "GEOID20": row["geoid"],
                    "Population 2020": row["population"],
                    "Housing units 2020": row["housing"],
                },
            }
            for row in tracts
        ],
    }


def _marks(collection: dict, kind: str, color: str) -> list[dict]:
    marks = []
    for feature in collection["features"]:
        geometry = feature["geometry"]
        coordinates = geometry["coordinates"]
        properties = feature["properties"]
        common = {
            "label": properties["name"],
            "color": color,
            "props": {key: value for key, value in properties.items() if key != "name"},
        }
        if kind == "points":
            marks.append({"lon": coordinates[0], "lat": coordinates[1], **common})
        else:
            parts = (
                coordinates if geometry["type"].startswith("Multi") else [coordinates]
            )
            marks.extend(
                {"type": "polygon", "coordinates": part, **common} for part in parts
            )
    return marks


def render(example_id: str) -> dict:
    example = EXAMPLES[example_id]
    mode = example.mode
    if mode in ("heat", "clusters"):
        return _points(mode)
    if mode in ("population", "density", "housing", "columns"):
        return _population(mode)
    if mode == "shapefile":
        _definition, _source, path = census.selected(example.datasets[0])
        return {"shapefile": base64.b64encode(path.read_bytes()).decode()}
    if mode == "source":
        return {
            "title": example.title,
            "layers": [{"kind": "source", "source": ROAD_SOURCE["id"]}],
            "view": {"bounds": ROAD_SOURCE["bounds"]},
            "notes": [
                "Complete DC road layer served by a connected GeoJSON source; no record sampling."
            ],
        }
    if mode == "layers":
        tracts = census.check_display(census.feature_collection("shp_tracts", 1000, 15))
        water = census.check_display(census.feature_collection("shp_water", 1000, 10))
        points = census.check_display(census.feature_collection("shp_points", 1000, 0))
        return {
            "title": example.title,
            "view": {"bounds": ROAD_SOURCE["bounds"]},
            "layers": [
                {
                    "id": "tracts",
                    "name": "Census tracts",
                    "kind": "polygons",
                    "opacity": 0.25,
                    "shapes": _marks(tracts, "polygons", "#a78bfa"),
                },
                {
                    "id": "water",
                    "name": "Water areas",
                    "kind": "polygons",
                    "shapes": _marks(water, "polygons", "#38bdf8"),
                },
                {
                    "id": "roads",
                    "name": "All roads",
                    "kind": "source",
                    "source": ROAD_SOURCE["id"],
                },
                {
                    "id": "landmarks",
                    "name": "Point landmarks",
                    "kind": "points",
                    "points": _marks(points, "points", "#f472b6"),
                },
            ],
            "notes": [
                "Four independent Census layers. Use Layers to change visibility or opacity."
            ],
        }
    simplify = 50 if mode in ("counties", "water_share") else 10
    columns = (
        (
            "FULLNAME",
            "TLID",
            "LFROMHN",
            "LTOHN",
            "RFROMHN",
            "RTOHN",
            "ZIPL",
            "ZIPR",
            "MTFCC",
        )
        if mode == "addresses"
        else None
    )
    collection = census.feature_collection(example.datasets[0], 1000, simplify, columns)
    collection["name"] = example.title
    if mode in ("land", "water_share", "counties"):
        collection["map"]["basemap"] = {"roads": False}
    if mode in ("counties", "land_use"):
        collection["map"].update(
            category=True,
            categoryLabel="County FIPS" if mode == "counties" else "MTFCC family",
        )
    for feature in collection["features"]:
        props = feature["properties"]
        if mode == "land":
            props.update(value=props["ALAND"] / 1_000_000, valueLabel="Land area (km²)")
        elif mode == "water_share":
            total = props["ALAND"] + props["AWATER"]
            props.update(
                value=100 * props["AWATER"] / total if total else None,
                valueLabel="Water share (%)",
            )
        elif mode == "counties":
            props["category"] = props["COUNTYFP"]
        elif mode == "land_use":
            props["category"] = props["MTFCC"][:3] + "xx"
        else:
            props["color"] = {
                "water": "#0ea5e9",
                "river": "#38bdf8",
                "landmarks": "#f472b6",
                "addresses": "#f59e0b",
                "groups": "#a78bfa",
                "geopackage": "#34d399",
            }[mode]
    return census.check_display(collection)
