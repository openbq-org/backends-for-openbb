"""
Map widgets, part 3: map files and map sources.

FILES. An endpoint of a "type": "map" widget may return a file it already has
instead of rows. The answer is JSON either way:

    GeoJSON     the FeatureCollection itself
    KML         {"kml": "<the text of the file>"}
    GPX         {"gpx": "<the text of the file>"}
    KMZ         {"kmz": "<the bytes of the file as base64>"}
    Shapefile   {"shapefile": "<the bytes of a zip with .shp, .dbf, .prj as base64>"}

The folders of a file become layers, and "data.map.value" can name the
property that colours its marks. A file is 4 MB at most as text or base64.

SOURCES. "data.map.sources" declares tiles, GeoJSON or an image that THIS
backend serves, as layers the reader can turn on under the data. The address
of a source must be on the origin of the backend that declares it: the app
refuses any other host. To show imagery of a third party, add a route here that
proxies it (and check that the terms of the provider allow that).

All data here is synthetic and generated in code (see widgets_maps_data.py):
the pictures are procedural gradients, not imagery.
"""

import base64
import json
import math
from functools import lru_cache
from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, Response

from core import register_widget
from widgets_maps_data import (
    US_BOUNDS,
    city,
    delivery_zones,
    elevation_at,
    great_circle,
    one_of,
    png,
    ramp,
    rectangle,
    seeded,
    shapefile,
    store_points,
    stores,
    temperature_at,
    tile_lon_lat,
    zipped,
)

router = APIRouter()

COLD_TO_HOT = [(49, 54, 149), (116, 173, 209), (254, 224, 144), (244, 109, 67), (165, 0, 38)]


# ============================================================================
# THE FILES, BUILT IN CODE
# ============================================================================
# Each file is drawn as it is: its folders are layers, its names are the names
# of the marks, its other values are in the hover card, and a KML keeps the
# colours of its own styles.

def _depots():
    """Six of the stores, as the depots every file of this module shows."""
    return stores()[:36:6]


# The shared styles of the KML document. A KML colour is aabbggrr: alpha, blue, green, red.
KML_STYLES = (
    '<Style id="light"><LineStyle><color>ffe1cc9e</color><width>1</width></LineStyle>'
    "<PolyStyle><color>b3e1cc9e</color></PolyStyle></Style>"
    '<Style id="medium"><LineStyle><color>ffc68f42</color><width>1</width></LineStyle>'
    "<PolyStyle><color>b3c68f42</color></PolyStyle></Style>"
    '<Style id="heavy"><LineStyle><color>ff9c5108</color><width>1</width></LineStyle>'
    "<PolyStyle><color>b39c5108</color></PolyStyle></Style>"
    '<Style id="depot"><IconStyle><color>ff37291f</color></IconStyle></Style>'
)


def _kml_placemark(name: str, style: str, data: dict, geometry: str) -> str:
    values = "".join(
        f'<Data name="{escape(key)}"><value>{escape(str(value))}</value></Data>'
        for key, value in data.items()
    )
    return (f"<Placemark><name>{escape(name)}</name><styleUrl>#{style}</styleUrl>"
            f"<ExtendedData>{values}</ExtendedData>{geometry}</Placemark>")


def _kml_ring(ring) -> str:
    # KML writes a position as "lon,lat" and separates positions with spaces.
    return " ".join(f"{lon},{lat}" for lon, lat in ring)


def _kml_document(overlay: str = "") -> str:
    """A KML document with two folders: delivery zones (polygons) and depots (points)."""
    zones = "".join(
        _kml_placemark(
            zone["zone"],
            "light" if zone["loads"] < 600 else "medium" if zone["loads"] < 1200 else "heavy",
            {"loads": zone["loads"], "avg_minutes": zone["avg_minutes"]},
            "<Polygon><outerBoundaryIs><LinearRing><coordinates>"
            f"{_kml_ring(zone['ring'])}</coordinates></LinearRing></outerBoundaryIs></Polygon>",
        )
        for zone in delivery_zones()
    )
    lat, lon = city("Dallas")
    depots = "".join(
        _kml_placemark(
            name,
            "depot",
            {"loads": loads},
            f"<Point><coordinates>{lon + dx},{lat + dy}</coordinates></Point>",
        )
        for name, dx, dy, loads in [
            ("North depot", 0.02, 0.21, 1650), ("East depot", 0.27, -0.03, 1210),
            ("South depot", -0.05, -0.24, 980), ("West depot", -0.3, 0.05, 1420),
        ]
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        f"<name>Dallas</name>{KML_STYLES}"
        f"<Folder><name>Delivery zones</name>{zones}</Folder>"
        f"<Folder><name>Depots</name>{depots}</Folder>"
        f"{overlay}</Document></kml>"
    )


def _traffic_picture() -> bytes:
    """A small made-up picture of traffic around Dallas: red in the middle, clear at the edge."""
    def pixel(x, y):
        distance = math.hypot(x - 48, y - 48) / 48
        waves = 0.5 + 0.5 * math.sin(x / 7) * math.cos(y / 9)
        strength = max(0.0, 1 - distance) * (0.6 + 0.4 * waves)
        return (*ramp([(255, 237, 160), (253, 141, 60), (189, 0, 38)], strength), round(190 * min(1, strength * 2)))

    return png(96, 96, pixel)


@lru_cache(maxsize=None)
def _kmz_bytes() -> bytes:
    """A KMZ: a zip with doc.kml and the image its GroundOverlay names by a relative path."""
    lat, lon = city("Dallas")
    overlay = (
        "<GroundOverlay><name>Traffic (picture)</name>"
        "<Icon><href>files/traffic.png</href></Icon>"
        f"<LatLonBox><north>{round(lat + 0.3, 4)}</north><south>{round(lat - 0.3, 4)}</south>"
        f"<east>{round(lon + 0.36, 4)}</east><west>{round(lon - 0.36, 4)}</west></LatLonBox>"
        "</GroundOverlay>"
    )
    return zipped({
        "doc.kml": _kml_document(overlay).encode("utf-8"),
        "files/traffic.png": _traffic_picture(),
    })


@lru_cache(maxsize=None)
def _shapefile_zip() -> bytes:
    """A zipped ESRI Shapefile: 12 made-up sales territories over Iowa, in WGS84."""
    territories = []
    for row in range(3):
        for col in range(4):
            rng = seeded("territory", row, col)
            west, south = -96.4 + col * 1.5, 40.5 + row * 1.0
            territories.append((
                rectangle(west, south, west + 1.4, south + 0.9),
                (f"Territory {row * 4 + col + 1}", round(20 + rng.random() * 90), round(200 + rng.random() * 900)),
            ))
    # The columns of the .dbf table: (name, C for text or N for a number, width, decimals)
    parts = shapefile(territories, [("name", "C", 24, 0), ("accounts", "N", 8, 0), ("loads", "N", 8, 0)])
    return zipped({f"territories{extension}": body for extension, body in parts.items()})


def _network_geojson() -> dict:
    """One FeatureCollection with the three kinds of geometry: points, lines and polygons."""
    depots = _depots()
    hub = depots[2]
    features = [
        {
            "type": "Feature",
            "properties": {"name": f"{row['city']} depot", "value": row["headcount"] * 3, "state": row["state"]},
            "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
        }
        for row in depots
    ]
    features += [
        {
            "type": "Feature",
            "properties": {"name": f"{hub['city']} to {row['city']}"},
            "geometry": {
                "type": "LineString",
                "coordinates": great_circle((hub["lat"], hub["lon"]), (row["lat"], row["lon"]), 16),
            },
        }
        for row in depots
        if row is not hub
    ]
    features += [
        {
            "type": "Feature",
            "properties": {"name": f"{row['city']} service area"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [rectangle(row["lon"] - 1.2, row["lat"] - 0.8, row["lon"] + 1.2, row["lat"] + 0.8)],
            },
        }
        for row in depots
    ]
    return {"type": "FeatureCollection", "features": features}


def _gpx_document() -> str:
    """A GPX file: a track from Chicago to Denver and a waypoint at each end."""
    path = great_circle(city("Chicago"), city("Denver"), 40)
    points = "".join(f'<trkpt lat="{lat}" lon="{lon}"/>' for lon, lat in path)
    waypoints = "".join(
        f'<wpt lat="{lat}" lon="{lon}"><name>{name}</name></wpt>'
        for name, (lat, lon) in [("Chicago", city("Chicago")), ("Denver", city("Denver"))]
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<gpx version="1.1" creator="reference-backend" xmlns="http://www.topografix.com/GPX/1/1">'
        f"{waypoints}<trk><name>Truck 12 (synthetic)</name><trkseg>{points}</trkseg></trk></gpx>"
    )


# ============================================================================
# THE FILE WIDGET
# ============================================================================

# format: (the name under /maps/files/, the media type of the raw file)
FILES = {
    "geojson": ("network.geojson", "application/geo+json"),
    "kml": ("delivery.kml", "application/vnd.google-earth.kml+xml"),
    "kmz": ("delivery.kmz", "application/vnd.google-earth.kmz"),
    "shapefile": ("territories.zip", "application/zip"),
    "gpx": ("truck.gpx", "application/gpx+xml"),
}


@register_widget({
    "name": "Map - Files",
    "description": "A map drawn from a file the backend already has: GeoJSON, KML, KMZ, a zipped shapefile or GPX. The folders of a file become layers (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_file",
    "gridData": {"w": 20, "h": 13},
    "params": [
        {
            "paramName": "format",
            "label": "Format",
            "description": "The format of the file the endpoint returns: a depot network (GeoJSON), delivery zones in two folders (KML), the same with a picture (KMZ), sales territories (shapefile), the track of a truck (GPX)",
            "type": "text",
            "value": "geojson",
            "options": [
                {"label": "GeoJSON", "value": "geojson"},
                {"label": "KML", "value": "kml"},
                {"label": "KMZ", "value": "kmz"},
                {"label": "Shapefile (zipped)", "value": "shapefile"},
                {"label": "GPX", "value": "gpx"},
            ],
        }
    ],
    # A file needs no column mapping. To colour the marks of a KML, a KMZ or a
    # shapefile by a number, name it here: "value": "loads" (an ExtendedData
    # value or a column of the .dbf table). GeoJSON reads "value" without it.
    "data": {"map": {"valueLabel": "Loads per week (synthetic)"}},
})
@router.get("/maps_file")
def maps_file(format: str = "geojson"):
    """A file as the answer of a map endpoint. The answer is JSON in every format:

        format=geojson    {"type": "FeatureCollection", "features": [...]}   the collection itself
        format=kml        {"kml": "<?xml ...><kml>...</kml>"}                 the text of the file
        format=gpx        {"gpx": "<?xml ...><gpx>...</gpx>"}                 the text of the file
        format=kmz        {"kmz": "UEsDBBQA..."}                              the bytes of the zip as base64
        format=shapefile  {"shapefile": "UEsDBBQA..."}                        a zip of .shp, .shx, .dbf, .prj as base64

    Get right: wrap text and bytes in JSON under the key of the format (a raw
    .kml answer is not read by the widget) and base64 the BYTES of an archive
    (standard alphabet, with padding). Positions are WGS84 (EPSG:4326):
    [longitude, latitude] in GeoJSON, "lon,lat" in KML, the attributes lat="..."
    lon="..." in GPX. A shapefile needs its .prj: longitude and latitude and Web
    Mercator are read, a layer in any other projection is left out with a note.
    Each Folder of a KML and each of waypoints, routes and tracks of a GPX is a
    layer with its own switch, and the colours of the styles of a KML are kept.
    Links of a file (NetworkLink, icons, an overlay at a URL) are never
    followed: the picture of a GroundOverlay is drawn only from INSIDE a KMZ,
    by a relative path. A file is 4 MB at most.
    """
    one_of("format", format, FILES)
    if format == "geojson":
        return _network_geojson()
    if format == "kml":
        return {"kml": _kml_document()}
    if format == "gpx":
        return {"gpx": _gpx_document()}
    if format == "kmz":
        return {"kmz": base64.b64encode(_kmz_bytes()).decode("ascii")}
    return {"shapefile": base64.b64encode(_shapefile_zip()).decode("ascii")}


@router.get("/maps/files/{name}")
def maps_file_download(name: str):
    """The same files as raw bytes, to download or to open in another tool"""
    bodies = {
        "geojson": lambda: json.dumps(_network_geojson()),
        "kml": _kml_document,
        "kmz": _kmz_bytes,
        "shapefile": _shapefile_zip,
        "gpx": _gpx_document,
    }
    for file_format, (file_name, media_type) in FILES.items():
        if name == file_name:
            return Response(bodies[file_format](), media_type=media_type)
    names = ", ".join(file_name for file_name, _media_type in FILES.values())
    raise HTTPException(status_code=404, detail=f"No such file. The files: {names}")


# ============================================================================
# MAP SOURCES: WHAT THE BACKEND DECLARES
# ============================================================================

# One declaration for each source. "endpoint" is a path of THIS backend, like the
# endpoint of a widget ("url" takes an absolute address on the same origin
# instead). "attribution" is required: it is the credit shown on the map.
TEMPERATURE_SOURCE = {
    "id": "demo-temperature",  # a-z, 0-9, "-" and "_", 40 at most: maps name a source by its id
    "name": "Temperature (synthetic)",
    "kind": "raster-tiles",
    "endpoint": "maps/tiles/temperature/{z}/{x}/{y}.png",  # tiles need {z}, {x} and {y}
    "attribution": "Synthetic temperature",
    "role": "overlay",  # "overlay" (the default) or "imagery": a backdrop that replaces the basemap
    "opacity": 0.7,
    "minzoom": 0,
    "maxzoom": 8,  # the map stretches the tiles of this zoom when it is closer
    "bounds": US_BOUNDS,  # [west, south, east, north]: no tile is asked for outside it
    "tileSize": 256,
}
TERRAIN_SOURCE = {
    "id": "demo-terrain",
    "name": "Terrain (synthetic)",
    "kind": "raster-dem",  # tiles whose pixels are heights; drawn as shaded relief
    "endpoint": "maps/tiles/terrain/{z}/{x}/{y}.png",
    "attribution": "Synthetic elevation",
    "encoding": "terrarium",  # required for raster-dem: "terrarium" or "mapbox"
    "minzoom": 0,
    "maxzoom": 8,
    "bounds": US_BOUNDS,
    "tileSize": 256,
}
GRID_SOURCE = {
    "id": "demo-grid",
    "name": "Coordinate grid (synthetic)",
    "kind": "raster-tiles",
    "endpoint": "maps/tiles/grid/{z}/{x}/{y}.png",
    "attribution": "Synthetic backdrop",
    "role": "imagery",  # offered as a backdrop in the Basemap section of the layer panel
    "minzoom": 0,
    "maxzoom": 8,
    "tileSize": 256,
}
DISTRICTS_SOURCE = {
    "id": "demo-districts",
    "name": "Sales districts (synthetic)",
    "kind": "geojson",
    "endpoint": "maps/sources/districts.geojson",
    "attribution": "Synthetic districts",
    "bounds": [-104.0, 36.5, -89.5, 43.5],
    # How vector data is drawn: up to 8 layers of "fill", "line" or "circle", coloured
    # by one colour or by one number property on a scale. Nothing else is read.
    "layers": [
        {
            "type": "fill",
            "color": {"property": "quota_musd", "scale": "sequential", "domain": [10, 60]},
            "opacity": 0.45,
            "label": "name",  # the property the hover card shows as the name
        },
        {"type": "line", "color": "#334155", "width": 1.5},
    ],
}
PICTURE_SOURCE = {
    "id": "demo-radar",
    "name": "Rain radar picture (synthetic)",
    "kind": "image",
    "endpoint": "maps/sources/radar.png",
    "attribution": "Synthetic radar",
    "opacity": 0.75,
    # The four corners of the picture as [lon, lat]: top left, top right, bottom right, bottom left
    "coordinates": [[-98.0, 45.0], [-86.0, 45.0], [-86.0, 38.0], [-98.0, 38.0]],
}
MAP_SOURCES = [TEMPERATURE_SOURCE, TERRAIN_SOURCE, DISTRICTS_SOURCE, PICTURE_SOURCE, GRID_SOURCE]


@register_widget({
    "name": "Map - Sources declared by the backend",
    "description": "Stores over map sources this backend serves: temperature tiles, terrain, GeoJSON districts, a radar picture and a backdrop. Turn them on in the Layers panel, or let the parameter turn one on (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_sources",
    "gridData": {"w": 40, "h": 15},
    "params": [
        {
            "paramName": "turn_on",
            "label": "On when the map opens",
            "description": "The declared source the endpoint turns on itself. With None the reader turns them on in the Layers panel.",
            "type": "text",
            "value": "none",
            "options": [
                {"label": "None", "value": "none"},
                {"label": "Temperature (raster tiles)", "value": "demo-temperature"},
                {"label": "Terrain (elevation tiles)", "value": "demo-terrain"},
                {"label": "Sales districts (GeoJSON)", "value": "demo-districts"},
                {"label": "Rain radar (image)", "value": "demo-radar"},
                {"label": "Coordinate grid (backdrop)", "value": "demo-grid"},
            ],
        }
    ],
    "data": {
        "map": {
            "lat": "lat",
            "lon": "lon",
            "label": "city",
            "value": "revenue_musd",
            "props": ["state", "headcount"],
            "valueLabel": "Revenue (USD m, synthetic)",
            "sources": MAP_SOURCES,  # each is a layer of this map, OFF until it is turned on
        }
    },
})
@router.get("/maps_sources")
def maps_sources(turn_on: str = "none"):
    """Map sources: tiles, GeoJSON and a picture declared in "data.map.sources".

        turn_on=none        rows, read by "data.map": every source is in the Layers panel, off
        turn_on=demo-grid   a map: {"basemap": {"source": "demo-grid"}, "valueLabel": ..., "points": [...]}
        turn_on=<other id>  a map: {"layers": [{"kind": "source", "source": "<id>"},
                                               {"kind": "points", "name": "Stores", "points": [...]}]}

    Get right: SAME ORIGIN. The address of a source must be on the origin of
    the backend that declares it, or the app refuses the source: serve the
    tiles yourself (as the routes below do) or proxy the provider through a
    route of this backend. A map carries the ID of a source only, never an
    address, and the id must be declared in "data.map.sources" of a map widget
    of this backend. A source the endpoint lists is on when the map opens, in
    the order of the layers; a map of sources alone needs a "view", because it
    has no marks to open on. A widget declares 16 sources at most. These tiles
    are procedural gradients, not imagery.
    """
    one_of("turn_on", turn_on, ["none", *(source["id"] for source in MAP_SOURCES)])
    if turn_on == "none":
        return stores()
    stores_layer = {"valueLabel": "Revenue (USD m, synthetic)", "points": store_points()}
    if turn_on == GRID_SOURCE["id"]:
        # A source with "role": "imagery" takes the place of the basemap.
        return {"basemap": {"source": turn_on}, **stores_layer}
    return {
        "layers": [
            {"kind": "source", "source": turn_on},
            {"kind": "points", "name": "Stores", **stores_layer},
        ]
    }


# ============================================================================
# MAP SOURCES: WHAT THE BACKEND SERVES
# ============================================================================

def _in_box(lon: float, lat: float, box) -> bool:
    return box[0] <= lon <= box[2] and box[1] <= lat <= box[3]


@lru_cache(maxsize=512)
def _tile(layer: str, z: int, x: int, y: int) -> bytes:
    """One 256 pixel PNG tile of Web Mercator. Each pixel is read at its own lon and lat, so tiles join without a seam."""
    lons, lats = tile_lon_lat(z, x, y)
    if layer == "temperature":
        def pixel(col, row):
            if not _in_box(lons[col], lats[row], US_BOUNDS):
                return (0, 0, 0, 0)  # transparent outside the bounds of the source
            return (*ramp(COLD_TO_HOT, (temperature_at(lons[col], lats[row]) + 5) / 45), 200)
        return png(256, 256, pixel, block=2)
    if layer == "terrain":
        def pixel(col, row):
            # Terrarium: height = red * 256 + green + blue / 256 - 32768, in metres.
            # No pixel is transparent: a pixel without a height would read as a hole.
            height = elevation_at(lons[col], lats[row]) + 32768
            return (int(height) // 256, int(height) % 256, int(height % 1 * 256), 255)
        return png(256, 256, pixel, block=2)
    # "grid": a plain backdrop with a line every 10 degrees (5 from zoom 4, 1 from zoom 7).
    step = 10 if z < 4 else 5 if z < 7 else 1
    width = 360 / 2 ** z / 256  # degrees of longitude of one pixel
    on_lon = [abs(lon / step - round(lon / step)) * step < width * 0.75 for lon in lons]
    on_lat = [
        abs(lat / step - round(lat / step)) * step < width * 0.75 * math.cos(math.radians(lat))
        for lat in lats
    ]
    shades = [ramp([(226, 232, 240), (241, 245, 249), (226, 232, 240)], (lat + 85) / 170) for lat in lats]

    def pixel(col, row):
        return (148, 163, 184, 255) if on_lon[col] or on_lat[row] else (*shades[row], 255)
    return png(256, 256, pixel)


@router.get("/maps/tiles/{layer}/{z}/{x}/{y}.png")
def maps_tile(layer: str, z: int, x: int, y: int):
    """Raster tiles of the sources "demo-temperature", "demo-terrain" and "demo-grid"

    The path has the shape the declaration writes: {z}/{x}/{y}, the standard
    XYZ scheme of Web Mercator. A real backend would read a tile from its own
    store here, or fetch it from a provider and pass it on.
    """
    if layer not in ("temperature", "terrain", "grid"):
        raise HTTPException(status_code=404, detail="No such tile layer")
    if not (0 <= z <= 12 and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
        raise HTTPException(status_code=404, detail="No such tile")
    return Response(
        _tile(layer, z, x, y),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/maps/sources/districts.geojson")
def maps_source_districts():
    """The GeoJSON of the source "demo-districts": one polygon for each sales district

    The app fetches it once and draws it by the "layers" of the declaration.
    The properties a style names ("quota_musd", "name") must be on every feature.
    """
    districts = [
        ("Northern Plains", [-104.0, 40.0, -96.0, 43.5]),
        ("Upper Midwest", [-96.0, 40.0, -89.5, 43.5]),
        ("Southern Plains", [-104.0, 36.5, -96.0, 40.0]),
        ("Lower Midwest", [-96.0, 36.5, -89.5, 40.0]),
    ]
    return JSONResponse(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "name": name,
                        "quota_musd": round(10 + seeded("quota", name).random() * 50, 1),
                    },
                    "geometry": {"type": "Polygon", "coordinates": [rectangle(*box)]},
                }
                for name, box in districts
            ],
        },
        media_type="application/geo+json",
    )


@lru_cache(maxsize=None)
def _radar_picture() -> bytes:
    """A made-up picture of rain: a few soft cells, transparent where it is dry."""
    cells = [(60, 40, 34), (150, 90, 46), (215, 50, 28), (110, 130, 30)]
    green_to_red = [(120, 198, 121), (255, 237, 111), (253, 141, 60), (215, 25, 28)]

    def pixel(x, y):
        rain = max(max(0.0, 1 - math.hypot(x - cx, y - cy) / radius) for cx, cy, radius in cells)
        return (*ramp(green_to_red, rain), round(210 * min(1.0, rain * 2.5)))

    return png(260, 180, pixel)


@router.get("/maps/sources/radar.png")
def maps_source_radar():
    """The picture of the source "demo-radar", laid on the four corners of its declaration"""
    return Response(
        _radar_picture(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )
