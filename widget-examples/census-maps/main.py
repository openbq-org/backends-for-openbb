"""A local Census backend: native Shapefile/FileGDB reads, GeoJSON map previews."""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import census
from catalog import DATASETS, SOURCES, VINTAGE

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


def dataset_parameter(format: str) -> dict:
    options = [
        {"label": item.name, "value": key}
        for key, item in DATASETS.items()
        if SOURCES[item.source].format == format and item.spatial
    ]
    return {
        "paramName": "dataset",
        "type": "text",
        "label": "Dataset",
        "value": options[0]["value"],
        "options": options,
    }


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
    for format in ("shapefile", "geodatabase"):
        parameter = dataset_parameter(format)
        label = "Shapefiles" if format == "shapefile" else "Geodatabases"
        for kind, endpoint in (("map", "map"), ("table", "attributes")):
            definitions[f"census_{format}_{kind}"] = {
                "name": f"Census {label} - {'Map preview' if kind == 'map' else 'Original attributes'}",
                "description": "Real DC TIGER/Line data. Map previews are bounded and simplified; attribute pages preserve every original field.",
                "category": "Census",
                "type": kind,
                "endpoint": endpoint,
                "gridData": {"w": 20, "h": 16},
                "params": [parameter, *(page_parameters() if kind == "table" else [])],
                "data": {"map": {}} if kind == "map" else {"table": {"showAll": True}},
            }
    definitions["census_address_ranges"] = {
        "name": "Census address-range relationships",
        "description": "Original nonspatial DBF attributes. Potential address ranges join to edges by TLID; they are not individual address points.",
        "category": "Census",
        "type": "table",
        "endpoint": "address_ranges",
        "gridData": {"w": 40, "h": 12},
        "params": page_parameters(),
        "data": {"table": {"showAll": True}},
    }
    return definitions


@app.get("/apps.json")
def apps():
    tabs = {}
    groups = []
    for index, format in enumerate(("shapefile", "geodatabase"), start=1):
        label = "Shapefiles" if format == "shapefile" else "Geodatabases"
        layout = [
            {
                "i": f"census_{format}_{kind}",
                "x": x,
                "y": 0,
                "w": 20,
                "h": 16,
                "groups": [f"Group {index}"],
            }
            for kind, x in (("map", 0), ("table", 20))
        ]
        if format == "shapefile":
            layout.append(
                {
                    "i": "census_address_ranges",
                    "x": 0,
                    "y": 16,
                    "w": 40,
                    "h": 12,
                    "groups": [],
                }
            )
        tabs[format] = {"id": format, "name": label, "layout": layout}
        groups.append(
            {
                "name": f"Group {index}",
                "widgetIds": [item["i"] for item in layout if item["groups"]],
                "type": "param",
                "paramName": "dataset",
                "defaultValue": dataset_parameter(format)["value"],
            }
        )
    return [
        {
            "name": "Census TIGER/Line",
            "description": "Real Census shapefiles and file geodatabases, read locally with GDAL.",
            "allowCustomization": True,
            "tabs": tabs,
            "groups": groups,
            "prompts": [],
        }
    ]


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
