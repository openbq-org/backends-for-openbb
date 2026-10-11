"""
Map widgets, part 3: map files and map sources.

FILES. An endpoint of a "type": "map" widget may return a file it already has
instead of rows. The answer is JSON either way:

    GeoJSON     the FeatureCollection itself
    KML         {"kml": "<the text of the file>"}
    GPX         {"gpx": "<the text of the file>"}
    KMZ         {"kmz": "<the bytes of the file as base64>"}
    Shapefile   {"shapefile": "<the bytes of a zip with .shp, .dbf, .prj as base64>"}

The folders of a file become layers, and "data.map.value" names the property
that colours its marks. A file is 4 MB at most as text or base64.

SOURCES. "data.map.sources" declares tiles, GeoJSON or an image that THIS
backend serves, as layers the reader can turn on under the data. The address
of a source must be on the origin of the backend that declares it: the app
refuses any other host. To show imagery of a third party, add a route here that
proxies it (and check that the terms of the provider allow that).

All data here is synthetic and generated in code (see widgets_maps_data.py):
the pictures are procedural gradients, not imagery.
"""

import base64
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
    png,
    ramp,
    rectangle,
    seeded,
    shapefile,
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

def _depots():
    """Six of the stores, as the depots every file of this module shows."""
    return stores()[:36:6]


def _kml_placemark(name: str, data: dict, geometry: str) -> str:
    values = "".join(
        f'<Data name="{escape(key)}"><value>{escape(str(value))}</value></Data>'
        for key, value in data.items()
    )
    return (f"<Placemark><name>{escape(name)}</name>"
            f"<ExtendedData>{values}</ExtendedData>{geometry}</Placemark>")


def _kml_ring(ring) -> str:
    # KML writes a position as "lon,lat" and separates positions with spaces.
    return " ".join(f"{lon},{lat}" for lon, lat in ring)


def _kml_document(overlay: str = "") -> str:
    """A KML document with two folders: delivery zones (polygons) and depots (points)."""
    zones = "".join(
        _kml_placemark(
            zone["zone"],
            {"deliveries": zone["deliveries"], "avg_minutes": zone["avg_minutes"]},
            "<Polygon><outerBoundaryIs><LinearRing><coordinates>"
            f"{_kml_ring(zone['ring'])}</coordinates></LinearRing></outerBoundaryIs></Polygon>",
        )
        for zone in delivery_zones()
    )
    lat, lon = city("Dallas")
    depots = "".join(
        _kml_placemark(
            name,
            {"deliveries": deliveries},
            f"<Point><coordinates>{lon + dx},{lat + dy}</coordinates></Point>",
        )
        for name, dx, dy, deliveries in [
            ("North depot", 0.02, 0.21, 1650), ("East depot", 0.27, -0.03, 1210),
            ("South depot", -0.05, -0.24, 980), ("West depot", -0.3, 0.05, 1420),
        ]
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
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
                (f"Territory {row * 4 + col + 1}", round(200 + rng.random() * 900), round(150 + rng.random() * 70, 1)),
            ))
    parts = shapefile(territories, [("NAME", "C", 24, 0), ("ACCOUNTS", "N", 8, 0), ("YIELD", "N", 8, 1)])
    return zipped({f"territories{extension}": body for extension, body in parts.items()})


def _network_geojson() -> dict:
    """One FeatureCollection with the three kinds of geometry: points, lines and polygons."""
    depots = _depots()
    hub = depots[2]
    features = [
        {
            "type": "Feature",
            "properties": {"name": f"{row['city']} depot", "value": row["headcount"], "state": row["state"]},
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
# FILE WIDGETS
# ============================================================================

@register_widget({
    "name": "Map - GeoJSON file",
    "description": "A GeoJSON FeatureCollection with points, lines and polygons, drawn as it is (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_file_geojson",
    "gridData": {"w": 20, "h": 13},
    "data": {"map": {"title": "Depot network (synthetic)", "valueLabel": "Headcount (synthetic)"}},
})
@router.get("/maps_file_geojson")
def maps_file_geojson():
    """GeoJSON: the endpoint returns the FeatureCollection as its JSON answer.

    Get right: GeoJSON positions are [longitude, latitude] in WGS84 (EPSG:4326):
    reproject before you serve anything else. The properties "name" (or "label",
    "title"), "value", "tag" and "color" are read as the name, the number, the
    tag and the colour of a feature; "data.map.value" names another number.
    """
    return _network_geojson()


@register_widget({
    "name": "Map - KML file",
    "description": "The text of a KML document with two folders, which become two layers of the map (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_file_kml",
    "gridData": {"w": 20, "h": 13},
    "data": {
        "map": {
            "title": "Dallas delivery network (synthetic)",
            "value": "deliveries",  # the ExtendedData value that colours the placemarks
        }
    },
})
@router.get("/maps_file_kml")
def maps_file_kml():
    """KML: the endpoint returns {"kml": "<the text of the document>"}.

    Get right: wrap the text in JSON under the key "kml" (a raw .kml answer is
    not read by the widget). Each Folder is a layer with its own switch and its
    own scale, named by the folder, so name the folders for a reader. Links of
    the file (NetworkLink, icons, remote styles) are never followed.
    """
    return {"kml": _kml_document()}


@register_widget({
    "name": "Map - KMZ file",
    "description": "A KMZ archive as base64: the KML of the delivery zones and a ground overlay picture inside the archive (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_file_kmz",
    "gridData": {"w": 20, "h": 13},
    "data": {
        "map": {
            "title": "Dallas delivery network and traffic (synthetic)",
            "value": "deliveries",
        }
    },
})
@router.get("/maps_file_kmz")
def maps_file_kmz():
    """KMZ: the endpoint returns {"kmz": "<base64 of the zip>"}.

    Get right: base64 the BYTES of the archive (standard alphabet, with
    padding). The picture of a GroundOverlay is drawn only when it is INSIDE the
    archive and named by a relative path ("files/traffic.png"): an overlay that
    points at a URL is left out. A file is 4 MB at most as base64.
    """
    return {"kmz": base64.b64encode(_kmz_bytes()).decode("ascii")}


@register_widget({
    "name": "Map - Zipped shapefile",
    "description": "An ESRI Shapefile (.shp, .shx, .dbf, .prj) zipped and sent as base64: 12 sales territories over Iowa (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_file_shapefile",
    "gridData": {"w": 20, "h": 13},
    "data": {
        "map": {
            "title": "Sales territories (synthetic)",
            "value": "YIELD",  # a numeric column of the .dbf table
        }
    },
})
@router.get("/maps_file_shapefile")
def maps_file_shapefile():
    """Shapefile: the endpoint returns {"shapefile": "<base64 of the zip>"}.

    Get right: zip the .shp with its .dbf AND its .prj. The .prj says what the
    numbers are: longitude and latitude (WGS84, NAD83) and Web Mercator are
    read, a layer in any other projection is left out with a note. The name of
    a mark comes from a NAME column of the .dbf table.
    """
    return {"shapefile": base64.b64encode(_shapefile_zip()).decode("ascii")}


@register_widget({
    "name": "Map - GPX file",
    "description": "The text of a GPX file: the track of one truck and a waypoint at each end (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_file_gpx",
    "gridData": {"w": 20, "h": 13},
    "data": {"map": {"title": "Truck 12, Chicago to Denver (synthetic)"}},
})
@router.get("/maps_file_gpx")
def maps_file_gpx():
    """GPX: the endpoint returns {"gpx": "<the text of the file>"}.

    Get right: a GPX position is two ATTRIBUTES, lat="..." lon="...", the other
    way round from GeoJSON and KML. Waypoints, routes and tracks become three
    layers. A track of many thousands of points is worth thinning first: the
    lines of a map hold 100,000 positions together.
    """
    return {"gpx": _gpx_document()}


@router.get("/maps/files/{name}")
def maps_file_download(name: str):
    """The same files as raw bytes, to download or to open in another tool"""
    files = {
        "network.geojson": (lambda: JSONResponse(_network_geojson(), media_type="application/geo+json")),
        "delivery.kml": (lambda: Response(_kml_document(), media_type="application/vnd.google-earth.kml+xml")),
        "delivery.kmz": (lambda: Response(_kmz_bytes(), media_type="application/vnd.google-earth.kmz")),
        "territories.zip": (lambda: Response(_shapefile_zip(), media_type="application/zip")),
        "truck.gpx": (lambda: Response(_gpx_document(), media_type="application/gpx+xml")),
    }
    if name not in files:
        raise HTTPException(status_code=404, detail=f"No such file. The files: {', '.join(files)}")
    return files[name]()


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
    "description": "Stores over map sources this backend serves: temperature tiles, terrain, GeoJSON districts, a radar picture and a backdrop. Turn them on in the Layers panel (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_sources",
    "gridData": {"w": 20, "h": 14},
    "data": {
        "map": {
            "lat": "lat",
            "lon": "lon",
            "label": "city",
            "value": "revenue_musd",
            "props": ["state"],
            "valueLabel": "Revenue (USD m, synthetic)",
            "sources": MAP_SOURCES,  # each is a layer of this map, OFF until the reader turns it on
        }
    },
})
@router.get("/maps_sources")
def maps_sources():
    """Map sources: tiles, GeoJSON and a picture declared in "data.map.sources".

    Get right: SAME ORIGIN. The address of a source must be on the origin of
    the backend that declares it, or the app refuses the source: serve the
    tiles yourself (as the routes below do) or proxy the provider through a
    route of this backend. Real imagery would be proxied or hosted here; these
    tiles are procedural gradients. A declared source is a layer under the data
    that is off until the reader turns it on; a widget declares 16 at most.
    """
    return stores()


@register_widget({
    "name": "Map - Source layers turned on by the endpoint",
    "description": "A map whose endpoint places two declared sources itself: the districts and the temperature tiles are on when it opens (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_source_layers",
    "gridData": {"w": 20, "h": 14},
    "data": {
        "map": {
            "title": "Districts over temperature (synthetic)",
            "sources": [TEMPERATURE_SOURCE, DISTRICTS_SOURCE],
        }
    },
})
@router.get("/maps_source_layers")
def maps_source_layers():
    """A "source" layer: the endpoint names a declared source by its id.

    Get right: the map carries the ID only ({"kind": "source", "source":
    "demo-districts"}), never an address, and the id must be declared in
    "data.map.sources" of a map widget of this backend. A source the endpoint
    lists is on when the map opens, in the order of the layers; a map of
    sources alone needs a "view", because it has no marks to open on.
    """
    return {
        "view": {"bounds": [-106.0, 35.5, -87.0, 45.0]},
        "layers": [
            {"kind": "source", "source": "demo-temperature", "name": "Temperature", "opacity": 0.6},
            {"kind": "source", "source": "demo-districts", "name": "Sales districts"},
        ],
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
