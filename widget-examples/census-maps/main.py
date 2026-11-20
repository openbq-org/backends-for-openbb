"""A local Census backend: native Shapefile/FileGDB reads, GeoJSON map previews."""

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import census
import explanations
import maps
from catalog import DATASETS, SOURCES, VINTAGE
from examples import EXAMPLES, TABS

app = FastAPI(title="Census TIGER/Line Maps")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://pro.openbb.co",
        "https://pro.openbb.dev",
        "http://localhost:1420",
        "http://127.0.0.1:1423",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def page_parameters() -> list[dict]:
    return [
        {"paramName": "page", "type": "number", "label": "Page", "value": 1, "min": 1},
        {
            "paramName": "page_size",
            "type": "number",
            "label": "Rows per page",
            "value": 100,
            "min": 1,
            "max": 1000,
        },
    ]


@app.get("/")
def root():
    return {"name": app.title, "vintage": VINTAGE, "docs": "/docs"}


@app.get("/widgets.json")
def widgets():
    definitions = {}
    for key, example in EXAMPLES.items():
        for kind in ("map", "markdown"):
            definition = {
                "name": example.title if kind == "map" else "About this map",
                "description": example.story
                if kind == "map"
                else "Original file format, Census source, and how to interpret this map.",
                "category": "Census",
                "type": kind,
                "endpoint": f"gallery/{key}" + ("/about" if kind == "markdown" else ""),
                "gridData": {"w": 24 if kind == "map" else 16, "h": 20},
                "params": [],
            }
            if kind == "map":
                definition["data"] = {"map": {}}
                if example.mode in ("source", "layers"):
                    definition["data"]["map"]["sources"] = [maps.ROAD_SOURCE]
            definitions[f"census_{key}_{kind}"] = definition
    # The explorer keeps the complete attribute path separate from the curated maps.
    parameter = {
        "paramName": "dataset",
        "type": "text",
        "label": "Dataset",
        "value": "shp_tracts",
        "options": [
            {"label": f"{item.name} ({SOURCES[item.source].format})", "value": key}
            for key, item in DATASETS.items()
        ],
    }
    definitions["census_attributes"] = {
        "name": "Original Census attributes",
        "description": "Every original field, with paging across the complete selected layer.",
        "category": "Census",
        "type": "table",
        "endpoint": "attributes",
        "gridData": {"w": 40, "h": 16},
        "params": [parameter, *page_parameters()],
        "data": {"table": {"showAll": True}},
    }
    definitions["census_attribute_notes"] = {
        "name": "Working with Census attributes",
        "description": "Identifiers, relationship tables, vintage, and complete data reads.",
        "category": "Census",
        "type": "markdown",
        "endpoint": "attribute_notes",
        "gridData": {"w": 40, "h": 9},
        "params": [],
    }
    return definitions


@app.get("/apps.json")
def apps():
    tabs = {}
    for tab_id, label in TABS.items():
        layout = []
        for row, key in enumerate(
            key for key, example in EXAMPLES.items() if example.tab == tab_id
        ):
            layout.extend(
                [
                    {
                        "i": f"census_{key}_map",
                        "x": 0,
                        "y": row * 20,
                        "w": 24,
                        "h": 20,
                        "groups": [],
                    },
                    {
                        "i": f"census_{key}_markdown",
                        "x": 24,
                        "y": row * 20,
                        "w": 16,
                        "h": 20,
                        "groups": [],
                    },
                ]
            )
        tabs[tab_id] = {"id": tab_id, "name": label, "layout": layout}
    tabs["attributes"] = {
        "id": "attributes",
        "name": "Original attributes",
        "layout": [
            {
                "i": "census_attribute_notes",
                "x": 0,
                "y": 0,
                "w": 40,
                "h": 9,
                "groups": [],
            },
            {"i": "census_attributes", "x": 0, "y": 9, "w": 40, "h": 16, "groups": []},
        ],
    }
    return [
        {
            "name": "Census TIGER/Line",
            "description": "A Census atlas: real boundaries, networks, points, population, 3D, density and layered maps, each with a source guide.",
            "allowCustomization": True,
            "tabs": tabs,
            "groups": [],
            "prompts": [],
        }
    ]


@app.get("/gallery/{example_id}/about")
def gallery_about(example_id: str, request: Request):
    if example_id not in EXAMPLES:
        raise HTTPException(404, "Unknown Census map example.")
    return explanations.about(example_id, str(request.base_url).rstrip("/"))


@app.get("/gallery/{example_id}")
def gallery_map(example_id: str):
    if example_id not in EXAMPLES:
        raise HTTPException(404, "Unknown Census map example.")
    return maps.render(example_id)


@app.get("/sources/roads.geojson")
def road_source():
    return maps.road_source()


@app.get("/attribute_notes")
def attribute_notes():
    return """## Read the original Census attributes

The table below pages through **all original fields** of the selected dataset. Change **Page** to continue; a page is not a complete-dataset total.

- **Identifiers:** keep GEOID, FIPS and ZIP fields as text so leading zeros survive.
- **Address ranges:** the standalone DBF has no geometry. Join TLID to edge data; potential ranges are not individual addresses.
- **Vintage:** POP20 and HOUSING20 are 2020 Census counts. Current boundaries and GEOID20 must not be joined as though they were interchangeable.
- **Original geometry:** use `/download?dataset=<id>` to retain the unchanged Census archive. Map previews may simplify geometry or select fields for display.

[Source concepts and record layouts](https://www.census.gov/programs-surveys/geography/technical-documentation/complete-technical-documentation/tiger-geo-line/2026.html)
"""


@app.get("/datasets")
def datasets():
    return [
        {
            "id": key,
            "name": item.name,
            "format": SOURCES[item.source].format,
            "layer": item.layer,
            "spatial": item.spatial,
            "available": (census.DATA_DIR / SOURCES[item.source].filename).is_file(),
        }
        for key, item in DATASETS.items()
    ]


@app.get("/metadata")
def metadata(dataset: str = "shp_tracts"):
    """Original schema, CRS, feature count and available archive layers."""
    return census.metadata(dataset)


@app.get("/map")
def map_preview(
    dataset: str = "shp_tracts",
    limit: int = Query(500, ge=1, le=census.MAX_PREVIEW_FEATURES),
    simplify_m: float = Query(10, ge=0, le=1000, allow_inf_nan=False),
):
    """Return a WGS84 GeoJSON preview with explicit source counts and simplification."""
    return census.preview(dataset, limit, simplify_m)


@app.get("/attributes")
def attributes(
    dataset: str = "shp_tracts",
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
):
    """Read a page of original attributes, without geometry or map-card field limits."""
    return census.attributes(dataset, page, page_size)


@app.get("/address_ranges")
def address_ranges(
    page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=1000)
):
    return census.attributes("shp_ranges", page, page_size)


@app.get("/download")
def download(dataset: str = "shp_tracts"):
    """Download the unchanged source archive, including original full-detail geometry."""
    _definition, source, path = census.selected(dataset)
    return FileResponse(path, media_type="application/zip", filename=source.filename)
