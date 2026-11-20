"""Source provenance and reading guides delivered as real Markdown widgets."""

from urllib.parse import quote

import census
from catalog import DATASETS, SOURCES, VINTAGE
from examples import EXAMPLES

FORMATS = {
    "shapefile": (
        "Esri Shapefile in a ZIP",
        "A shapefile is a bundle: **.shp** stores geometry, **.dbf** stores attributes, **.shx** indexes shapes, **.prj** declares the coordinate system, and **.cpg** declares text encoding. Keep the companion files together.",
    ),
    "geodatabase": (
        "Esri File Geodatabase (.gdb.zip)",
        "A **.gdb** is a directory of database files, compressed here as one ZIP. It contains several named feature classes. This backend uses GDAL's OpenFileGDB reader and selects a layer explicitly; ArcGIS is not required.",
    ),
    "geopackage": (
        "OGC GeoPackage (.gpkg.zip)",
        "A GeoPackage is an open SQLite-based spatial container. Several named layers, their schemas and coordinate systems live in one **.gpkg** file. This backend reads the selected layer directly from the Census ZIP.",
    ),
    "dbf": (
        "dBASE attribute table (.dbf in a ZIP)",
        "This file stores rows and columns without geometry. It can be analyzed as a table and joined to spatial features through a key such as TLID, but it cannot draw a map by itself.",
    ),
}
TECH_DOC = "https://www.census.gov/programs-surveys/geography/technical-documentation/complete-technical-documentation/tiger-geo-line/2026.html"


def about(example_id: str, base_url: str) -> str:
    example = EXAMPLES[example_id]
    sections = [
        f"**{example.title}**",
        example.story,
    ]
    for dataset in example.datasets:
        meta = census.metadata(dataset)
        source = SOURCES[DATASETS[dataset].source]
        format_title, guide = FORMATS[source.format]
        sections.extend(
            [
                f"### Original file: {format_title}",
                guide,
                f"Archive: **{source.filename}**. Published as **TIGER/Line {VINTAGE}** by the **U.S. Census Bureau**.",
                f"[Official Census download]({source.url}) · [Original archive from this backend]({base_url}/download?dataset={quote(dataset)}) · [Full schema and layer list]({base_url}/metadata?dataset={quote(dataset)})",
                f"| Source fact | Value |\n| --- | --- |\n| Geography | {meta['geography']} |\n| Layer | **{meta['layer']}** |\n| Original records | {meta['total_features']:,} |\n| Geometry | {meta['geometry_type'] or 'No geometry'} |\n| Source CRS | **{meta['crs'] or 'Not applicable'}** |",
            ]
        )
    sections.extend(
        [
            "### How to read this map",
            example.reading,
            "### What Workspace is showing",
            example.capability,
            "### Detail and provenance",
            "Original source files are retained unchanged. Except for the native Shapefile example, map geometry is transformed to WGS84 longitude/latitude for display. Preview notes state the feature coverage and simplification. Attribute pages preserve the original fields and identifiers.",
            f"[Census concepts and record layouts]({TECH_DOC})",
        ]
    )
    return "\n\n".join(sections)
