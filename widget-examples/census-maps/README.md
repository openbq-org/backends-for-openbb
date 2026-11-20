# Census TIGER/Line maps

A standalone OpenBB Workspace backend for real Census Shapefiles and Esri File
Geodatabases. GDAL reads both formats locally; Workspace receives GeoJSON in
longitude/latitude order. ArcGIS and GeoPandas are not required.

The default catalogue uses small District of Columbia extracts so the complete
example is practical on a laptop. [catalog.py](catalog.py) owns the Census URLs,
vintage, datasets, and selected geodatabase layers. No data is downloaded by a
widget request.

## Run locally

Use Python 3.11 or newer, from this directory:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python prepare.py
uvicorn main:app --host 127.0.0.1 --port 7780
```

Connect `http://localhost:7780` in Workspace and open **Census TIGER/Line**.
The app has separate Shapefiles and Geodatabases tabs. Each map and its original
attribute table share a dataset selector. The shapefile tab also exposes the
nonspatial address-range relationship table.

The Map widgets require a Workspace build that supports `"type": "map"`.
API documentation is available at `http://localhost:7780/docs`.

`prepare.py` downloads the original archives into the ignored `.data/` directory.
Set `CENSUS_DATA_DIR` for both preparation and serving to use another directory.
Existing files are reused; remove an archive explicitly to download it again.
Pyogrio wheels include GDAL and OpenFileGDB on supported platforms. If pip falls
back to a source build, use a platform with available wheels or install GDAL
following the [Pyogrio installation guide](https://pyogrio.readthedocs.io/en/latest/install.html).

## Original data and display geometry

The two paths deliberately have different contracts:

- **Map previews** select a bounded number of source features and display fields.
  Geometry is simplified in a local metric projection, then transformed to
  WGS84. The response and map notes state the source count, preview count, and
  simplification. Simplification preserves each feature's topology, not shared
  boundaries between adjacent features. A preview that exceeds the display
  budget returns an actionable error rather than silently dropping features.
- **Attribute pages** read all original fields, preserve identifier strings and
  leading zeros, and page through the complete layer. Change **Page** or **Rows
  per page** on the table. A page is not a dataset-wide total.
- **Archive downloads** return the unchanged source bytes, including full-detail
  geometry and the complete geodatabase. The metadata endpoint lists available
  layers, the source coordinate system, field types, and record counts.

For example:

```text
/map?dataset=gdb_tracts
/map?dataset=shp_roads&limit=100&simplify_m=25
/attributes?dataset=shp_addresses&page=2&page_size=100
/metadata?dataset=gdb_blocks
/download?dataset=shp_tracts
```

The endpoint definitions in [main.py](main.py) are the API reference; the format
reader and display budgets live in [census.py](census.py). `.gdb.zip` files are
opened directly through OpenFileGDB, with an explicit layer name. No temporary
extraction or custom binary parser is needed. A browser does not parse a `.gdb`
file in this example.

## Census semantics

Address-range features contain potential ranges along edges, not individual
address points or a list of buildings. The relationship table has no geometry;
it joins to edge data through `TLID`. Attribute reads retain fields such as
`ZIPL` and `ZIPR` even when those fields are not selected for map cards.

Most layers describe geography and need a separate demographic-data join. Some
block layers include Census population and housing counts. Preserve the vintage
and exact field names when joining: current geography and `GEOID20` are not
interchangeable.

Sources: [Census Shapefiles](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html),
[Census Geodatabases](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-geodatabase-file.html),
and [record layouts](https://www.census.gov/programs-surveys/geography/technical-documentation/complete-technical-documentation/tiger-geodatabase-file.html).

## Extending the example

Add a source and its selected datasets in the catalogue, then prepare its local
files. The metric simplification projection is chosen for DC; choose an
appropriate projection when adding another area.

This is a read-only local example, not an upload or national ingestion service.
Large national datasets should retain their complete geometry and attributes in
backend storage and deliver map geometry through vector tiles or PMTiles.
Converting a national archive to one large GeoJSON response will still exceed
Workspace's display limits. Complete spatial querying and tile generation are
separate additions; this example does not claim to implement them.

## Checks

```bash
pip install pytest httpx httpx2 ruff
python -m pytest -q
ruff check .
ruff format --check .
```

The tests create actual Shapefile and FileGDB fixtures with GDAL and exercise the
HTTP interface without network requests. The explicit preparation step allows
additional live checks against the Census downloads.
