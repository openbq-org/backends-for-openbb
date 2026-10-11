"""
Map widgets, part 2: an endpoint that returns the map itself.

Rows and a column mapping (widgets_maps.py) draw points or shaded regions.
For everything else the endpoint returns a map, and "data.map" can stay empty:

    {
      "title": "...",
      "points":  [{"lat": 41.88, "lon": -87.63, "label": "...", "value": 1}],
      "regions": {"set": "us-states", "items": [{"code": "IA", "value": 1}]},
      "shapes":  [{"type": "line", "coordinates": [[lon, lat], ...]},
                  {"type": "polygon", "coordinates": [[[lon, lat], ...]], "height": 40}],
      "layers":  [{"kind": "flows", "name": "...", "flows": [{"from": ..., "to": ...}]}]
    }

A position is always [longitude, latitude], in that order. A layer has a "kind":
regions, points, lines, polygons, heat, clusters, flows, columns, source, image.

Limits of one map, all layers together: 20,000 points, 4,000 regions, 3,500
lines and areas (100,000 positions), 2,000 flows, 12 layers, 60 steps of time,
4 images and 2 MB as JSON. A map over a limit is not drawn and says why.

All data here is synthetic (see widgets_maps_data.py).
"""

import base64
import math

from fastapi import APIRouter, HTTPException

from core import register_widget
from widgets_maps_data import (
    STATES,
    US_BOUNDS,
    city,
    delivery_zones,
    great_circle,
    loop_buildings,
    png,
    ramp,
    scattered_points,
    seeded,
    state_metric,
    stores,
    temperature_at,
)

router = APIRouter()

# (origin, destination) of the routes and of the flows between cities
ROUTES = [
    ("Chicago", "New York"), ("Chicago", "Dallas"), ("Chicago", "Denver"),
    ("Chicago", "Atlanta"), ("Dallas", "Los Angeles"), ("Dallas", "Miami"),
    ("Denver", "Seattle"), ("Denver", "San Francisco"), ("Atlanta", "Miami"),
    ("Atlanta", "Washington"), ("New York", "Boston"), ("Kansas City", "Minneapolis"),
]


def _routes():
    """One line for each route: a path of [lon, lat] positions and what it carries."""
    return [
        {
            "type": "line",
            "coordinates": great_circle(city(origin), city(destination)),
            "label": f"{origin} to {destination}",
            "value": int(120 + seeded("route", origin, destination).random() * 900),
            "props": {"origin": origin, "destination": destination},
        }
        for origin, destination in ROUTES
    ]


# ============================================================================
# LINES AND FLOWS
# ============================================================================

@register_widget({
    "name": "Map - Lines (routes)",
    "description": "Truck routes between cities as lines, coloured by the loads they carry in a week (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_lines",
    "gridData": {"w": 20, "h": 13},
    "data": {"map": {"title": "Truck routes (synthetic)"}},
})
@router.get("/maps_lines")
def maps_lines():
    """Lines: each one a path of positions, coloured by its value.

    Get right: a position is [longitude, latitude] (GeoJSON order), and a line
    needs two or more. Send the path you want drawn: the map joins the positions
    with straight segments, so a long route needs intermediate positions.
    A map draws up to 3,500 lines and areas with 100,000 positions together.
    """
    return {
        "layers": [
            {
                "kind": "lines",
                "name": "Routes",
                "valueLabel": "Loads per week (synthetic)",
                "shapes": _routes(),
            }
        ]
    }


@register_widget({
    "name": "Map - Flows (origin to destination)",
    "description": "Shipments from Iowa and Illinois to other states as arcs, wider and darker with their value (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_flows",
    "gridData": {"w": 20, "h": 13},
    "data": {"map": {"title": "Grain shipments (synthetic)"}},
})
@router.get("/maps_flows")
def maps_flows():
    """Flows: one arc from an origin to a destination.

    Get right: an end is [lon, lat], {"lat", "lon"}, {"state": "IA"}, {"country":
    "BR"} or {"city": "Chicago"}: with a state or a country the backend needs no
    coordinates. The arc is faint at its start and full at its end, so "from" and
    "to" must not be swapped. A map draws up to 2,000 flows: aggregate first.
    """
    destinations = ["LA", "TX", "WA", "CA", "GA", "NY", "FL", "MN", "MO", "OH"]
    flows = []
    for origin in ("IA", "IL"):
        for destination in destinations:
            flows.append({
                "from": {"state": origin},
                "to": {"state": destination},
                "label": f"{origin} to {destination}",
                "value": int(50 + seeded("flow", origin, destination).random() * 950),
                "props": {"commodity": "Corn" if origin == "IA" else "Soybeans"},
            })
    # An end can also be a position: the river terminal at the Port of New Orleans.
    flows.append({
        "from": {"state": "IA"},
        "to": [-90.07, 29.95],
        "label": "IA to Port of New Orleans",
        "value": 700,
        "props": {"commodity": "Corn"},
    })
    return {
        "layers": [
            {
                "kind": "flows",
                "name": "Shipments",
                "valueLabel": "Shipments (kt, synthetic)",
                "flows": flows,
            }
        ]
    }


@register_widget({
    "name": "Map - Arrows (direction)",
    "description": "Wind as arrows on a grid over the United States: each arrow is a short line the backend computes (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_arrows",
    "gridData": {"w": 20, "h": 13},
    "data": {"map": {"title": "Wind (synthetic)"}},
})
@router.get("/maps_arrows")
def maps_arrows():
    """Arrows: a direction at a place, drawn as a line with a head.

    Get right: the map has no arrow mark, so the backend sends each arrow as a
    line of five positions: tail, tip, one side of the head, tip, the other
    side. Say in the label whether the direction is where the wind blows TO.
    """
    arrows = []
    for lat in range(27, 49, 3):
        for lon in range(-122, -68, 4):
            to = (200 + 60 * math.sin(math.radians(lon * 5)) + 40 * math.cos(math.radians(lat * 8))) % 360
            speed = round(8 + 14 * abs(math.sin(math.radians(lon * 3 + lat * 5))), 1)
            length = 0.5 + speed / 22

            def at(bearing, distance, origin):
                return [
                    round(origin[0] + distance * math.sin(math.radians(bearing)) / math.cos(math.radians(lat)), 4),
                    round(origin[1] + distance * math.cos(math.radians(bearing)), 4),
                ]

            tail = [lon, lat]
            tip = at(to, length, tail)
            arrows.append({
                "type": "line",
                "coordinates": [tail, tip, at(to + 150, length * 0.3, tip), tip, at(to - 150, length * 0.3, tip)],
                "label": f"Wind to {round(to)} degrees",
                "value": speed,
            })
    return {
        "layers": [
            {"kind": "lines", "name": "Wind", "valueLabel": "Wind speed (m/s, synthetic)", "shapes": arrows}
        ]
    }


# ============================================================================
# AREAS AND FOOTPRINTS (GEOJSON)
# ============================================================================

@register_widget({
    "name": "Map - Areas from GeoJSON",
    "description": "Delivery zones around Dallas as GeoJSON polygons, coloured by a number property (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_areas",
    "gridData": {"w": 20, "h": 13},
    "data": {
        "map": {
            "title": "Delivery zones (synthetic)",
            "value": "deliveries",  # the number property of a feature that colours it
            "valueLabel": "Deliveries per week (synthetic)",
        }
    },
})
@router.get("/maps_areas")
def maps_areas():
    """Areas: the endpoint returns a GeoJSON FeatureCollection of polygons.

    Get right: return the FeatureCollection itself (not rows with a geometry
    column), close every ring (first position = last position) and name the
    colouring property in "data.map.value". "name" (or "label", "title") is the
    name of a feature; its other scalar properties are in the hover card.
    A map draws up to 3,500 areas; each part of a MultiPolygon counts as one.
    """
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": zone["zone"],
                    "deliveries": zone["deliveries"],
                    "avg_minutes": zone["avg_minutes"],
                },
                "geometry": {"type": "Polygon", "coordinates": [zone["ring"]]},
            }
            for zone in delivery_zones()
        ],
    }


@register_widget({
    "name": "Map - 3D footprints (extruded areas)",
    "description": "Building footprints in the Chicago Loop that stand as tall as their height in metres (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_footprints_3d",
    "gridData": {"w": 20, "h": 13},
    "data": {
        "map": {
            "title": "Downtown buildings (synthetic)",
            "value": "height_m",  # colours the footprints
            "height": "height_m",  # the property that says how high an area stands, in METRES
            "valueLabel": "Height (m, synthetic)",
        }
    },
})
@router.get("/maps_footprints_3d")
def maps_footprints_3d():
    """Extruded footprints: areas with a height stand on the map.

    Get right: the height is a NUMBER in METRES (not "42 m", not feet), named
    in "data.map.height"; without it the properties "height" and "floors" (3.2 m
    each) are read. A height over 1,000 m is drawn at 1,000 m. The map opens
    tilted when the footprints span a city or less.
    """
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": building["name"],
                    "height_m": building["height_m"],
                    "floors_count": building["floors"],
                    "use": building["use"],
                    "year_built": building["year_built"],
                },
                "geometry": {"type": "Polygon", "coordinates": [building["ring"]]},
            }
            for building in loop_buildings()
        ],
    }


# ============================================================================
# MANY POINTS: HEAT AND CLUSTERS
# ============================================================================

@register_widget({
    "name": "Map - Heat (density)",
    "description": "2,000 orders as a density: where the points are thick, weighted by their value (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_heat",
    "gridData": {"w": 20, "h": 13},
    "data": {"map": {"title": "Order density (synthetic)"}},
})
@router.get("/maps_heat")
def maps_heat():
    """Heat: many points drawn as a density.

    Get right: send lean points ({"lat", "lon", "value"}): a density has no
    hover card and no tag, so labels and props are wasted bytes. "value" is the
    weight of a point. The points of a map are 20,000 at most and the whole map
    2 MB, so aggregate in the backend before that (a grid, a sample).
    """
    return {
        "layers": [
            {
                "kind": "heat",
                "name": "Orders",
                "valueLabel": "Orders (synthetic)",
                "points": [
                    {"lat": point["lat"], "lon": point["lon"], "value": point["orders"]}
                    for point in scattered_points(2000)
                ],
            }
        ]
    }


@register_widget({
    "name": "Map - Clusters",
    "description": "2,000 orders as circles with a count where points are close; a click zooms in until they are single points (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_clusters",
    "gridData": {"w": 20, "h": 13},
    "data": {"map": {"title": "Order clusters (synthetic)"}},
})
@router.get("/maps_clusters")
def maps_clusters():
    """Clusters: many points grouped into circles with a count.

    Get right: unlike a density, the single points are reached by zooming in,
    so a label and a few props are worth sending. Keep them short: 2,000 points
    with a label and one prop are about 150 KB of the 2 MB of a map.
    """
    return {
        "layers": [
            {
                "kind": "clusters",
                "name": "Orders",
                "valueLabel": "Orders (synthetic)",
                "points": [
                    {
                        "lat": point["lat"],
                        "lon": point["lon"],
                        "value": point["orders"],
                        "label": f"Order point {at + 1}",
                        "props": {"state": point["state"]},
                    }
                    for at, point in enumerate(scattered_points(2000))
                ],
            }
        ]
    }


# ============================================================================
# COLUMNS (3D BARS)
# ============================================================================

@register_widget({
    "name": "Map - Columns (3D bars)",
    "description": "Bars that stand on the map, as tall as their value, on states or at cities (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_columns",
    "gridData": {"w": 20, "h": 13},
    "params": [
        {
            "paramName": "by",
            "label": "Bars on",
            "description": "Stand the bars on regions (states) or at points (cities)",
            "type": "text",
            "value": "state",
            "options": [
                {"label": "States", "value": "state"},
                {"label": "Cities", "value": "city"},
            ],
        }
    ],
    "data": {"map": {"title": "Revenue as columns (synthetic)"}},
})
@router.get("/maps_columns")
def maps_columns(by: str = "state"):
    """Columns: one bar for each region or for each point, as tall as its value.

    Get right: a "columns" layer holds EITHER "regions" OR "points", never both,
    and every bar needs a "value". The map opens tilted and can be turned.
    """
    if by not in ("state", "city"):
        raise HTTPException(status_code=400, detail="by: state or city")
    layer = {"kind": "columns", "name": "Revenue", "valueLabel": "Revenue (USD m, synthetic)"}
    if by == "city":
        layer["points"] = [
            {"lat": row["lat"], "lon": row["lon"], "label": row["city"], "value": row["revenue_musd"]}
            for row in stores()
        ]
    else:
        totals = {}
        for row in stores():
            totals[row["state"]] = round(totals.get(row["state"], 0) + row["revenue_musd"], 1)
        layer["regions"] = {
            "set": "us-states",
            "items": [{"code": usps, "value": total} for usps, total in sorted(totals.items())],
        }
    return {"layers": [layer]}


# ============================================================================
# SEVERAL LAYERS ON ONE MAP
# ============================================================================

@register_widget({
    "name": "Map - Layers",
    "description": "Four layers on one map: shaded states, routes, stores and a density that is off until it is turned on (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_layers",
    "gridData": {"w": 40, "h": 15},
    "data": {"map": {"title": "Network overview (synthetic)"}},
})
@router.get("/maps_layers")
def maps_layers():
    """Several layers in one widget, each with a name, a legend entry and a switch.

    Get right: the order of "layers" is the drawing order, the FIRST at the
    bottom, so shaded regions go first and points last. Give each layer an "id"
    (lower case, digits, "-" and "_"), a short "name" for the layer panel and a
    "valueLabel" for the legend (each layer has its own scale); "visible": False
    leaves a layer off until the reader turns it on, and "opacity" is 0 to 1.
    A map has up to 12 layers.
    """
    return {
        "layers": [
            {
                "id": "income",
                "kind": "regions",
                "name": "States",
                "valueLabel": "Median income (USD k)",
                "opacity": 0.8,
                "regions": {
                    "set": "us-states",
                    "items": [
                        {"code": usps, "label": name, "value": state_metric(usps, "median_income_kusd")}
                        for usps, _fips, name, *_rest in STATES
                        if usps not in ("AK", "HI")
                    ],
                },
            },
            {
                "id": "routes",
                "kind": "lines",
                "name": "Routes",
                "valueLabel": "Loads per week",
                "shapes": _routes(),
            },
            {
                "id": "orders",
                "kind": "heat",
                "name": "Order density",
                "visible": False,  # listed in the layer panel, off until the reader turns it on
                "points": [
                    {"lat": point["lat"], "lon": point["lon"], "value": point["orders"]}
                    for point in scattered_points(600)
                ],
            },
            {
                "id": "stores",
                "kind": "points",
                "name": "Stores",
                "valueLabel": "Revenue (USD m)",
                "points": [
                    {
                        "lat": row["lat"],
                        "lon": row["lon"],
                        "label": row["city"],
                        "value": row["revenue_musd"],
                        "props": {"state": row["state"], "headcount": row["headcount"]},
                    }
                    for row in stores()
                ],
            },
        ]
    }


# ============================================================================
# RANKS, HIGHLIGHTS AND CATEGORIES
# ============================================================================

@register_widget({
    "name": "Map - Ranks, highlights and sign colours",
    "description": "The five largest stores ranked 1 to 5, the smallest ones highlighted in a warning tone, with a legend line for each (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_marks_ranked",
    "gridData": {"w": 20, "h": 13},
    "data": {"map": {"title": "Largest and smallest stores (synthetic)"}},
})
@router.get("/maps_marks_ranked")
def maps_marks_ranked():
    """Marks beyond the five named signs: a rank, a highlight, a tone, a meaning.

    Get right: these four are fields of a MARK, so the endpoint returns the map
    (a column mapping only takes "marker" with a named sign and "tag").
    "marker" is a sign or a rank from 1 to 99; "highlight": True is an emphasis
    without a sign; "markerColor" is accent, positive, negative, neutral or a
    #rrggbb colour; "meaning" (60 characters) is what the legend says of it.
    """
    rows = sorted(stores(), key=lambda row: row["revenue_musd"], reverse=True)
    points = []
    for at, row in enumerate(rows):
        point = {
            "lat": row["lat"],
            "lon": row["lon"],
            "label": row["city"],
            "value": row["revenue_musd"],
            "props": {"state": row["state"]},
        }
        if at < 5:
            point.update(marker=at + 1, tag=f"{row['city']} ${row['revenue_musd']}M",
                         markerColor="positive", meaning="Five largest stores")
        elif at >= len(rows) - 3:
            point.update(highlight=True, tag=row["city"],
                         markerColor="negative", meaning="Three smallest stores")
        points.append(point)
    return {"valueLabel": "Revenue (USD m, synthetic)", "points": points}


@register_widget({
    "name": "Map - Categories",
    "description": "Stores coloured by a text category, each with its own colour and legend entry (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_categories",
    "gridData": {"w": 20, "h": 13},
    "data": {"map": {"title": "Stores by format (synthetic)"}},
})
@router.get("/maps_categories")
def maps_categories():
    """Categories: a text on each mark gives it a colour of the theme.

    Get right: "category" is a field of a mark and "categoryLabel" names it in
    the legend. A map has 12 categories at most (40 characters each): a mark of
    a 13th has the plain colour of its layer, so group the long tail as "Other"
    in the backend. A mark with a category should not also carry a "value".
    """
    return {
        "categoryLabel": "Store format",
        "points": [
            {
                "lat": row["lat"],
                "lon": row["lon"],
                "label": row["city"],
                "category": row["format"],
                "props": {"state": row["state"], "revenue_musd": row["revenue_musd"]},
            }
            for row in stores()
        ],
    }


# ============================================================================
# WHERE THE MAP OPENS
# ============================================================================

@register_widget({
    "name": "Map - View (where the map opens)",
    "description": "The same stores, opened on a named place, on a centre and a zoom, on a box, or tilted (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_view",
    "gridData": {"w": 20, "h": 13},
    "params": [
        {
            "paramName": "open_on",
            "label": "Open on",
            "description": "Where the map opens. Every store stays on the map.",
            "type": "text",
            "value": "place",
            "options": [
                {"label": "A place by name (Texas)", "value": "place"},
                {"label": "A centre and a zoom (Chicago)", "value": "center"},
                {"label": "A box (the Northeast)", "value": "bounds"},
                {"label": "Tilted and turned (Iowa)", "value": "tilted"},
                {"label": "All the data (no view)", "value": "data"},
            ],
        }
    ],
    "data": {"map": {"title": "Stores (synthetic)"}},
})
@router.get("/maps_view")
def maps_view(open_on: str = "place"):
    """A view: where the map opens, without dropping any data.

    Get right: a view changes where the map LOOKS, not what it holds, so do not
    filter the rows to "zoom in". Give ONE of "place" (a state, a country, a
    city, a US county with its state), "center" [lon, lat] with "zoom" (0 to
    19), or "bounds" [west, south, east, north]; "bearing" turns the view and
    the top-level "pitch" (0 to 60) tilts it. An ambiguous place ("Georgia") is
    not guessed: the map opens on its data and says so.
    """
    views = {
        "place": {"view": {"place": "Texas"}},
        "center": {"view": {"center": [-87.63, 41.88], "zoom": 6}},
        "bounds": {"view": {"bounds": [-80.6, 38.4, -66.9, 47.5]}},
        "tilted": {"view": {"center": [-93.5, 42.0], "zoom": 6.5, "bearing": -20}, "pitch": 50},
        "data": {},
    }
    if open_on not in views:
        raise HTTPException(status_code=400, detail=f"open_on: one of {', '.join(views)}")
    return {
        "valueLabel": "Revenue (USD m, synthetic)",
        "points": [
            {
                "lat": row["lat"],
                "lon": row["lon"],
                "label": row["city"],
                "tag": row["city"] if row["state"] in ("TX", "IA", "IL") else None,
                "value": row["revenue_musd"],
            }
            for row in stores()
        ],
        **views[open_on],
    }


# ============================================================================
# AN IMAGE LAID ON THE MAP
# ============================================================================

@register_widget({
    "name": "Map - Image overlay",
    "description": "A picture the backend renders (a made-up temperature field) laid on four corners, under the stores (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_image",
    "gridData": {"w": 20, "h": 13},
    "data": {"map": {"title": "Temperature picture (synthetic)"}},
})
@router.get("/maps_image")
def maps_image():
    """An image layer: the BYTES of a picture and the four corners it lies on.

    Get right: a map never takes the address of an image, so send the picture
    itself as base64 ("mime": image/png, image/jpeg or image/webp) with
    "corners" as [lon, lat] in this order: top left, top right, bottom right,
    bottom left. Keep it small: 1.4 MB of base64 for one image, 4 images in a
    map. The picture is stretched evenly in Web Mercator between its corners, so
    over a large area render its rows in that projection, as this one does; use
    a tile source for anything detailed (see widgets_maps_files.py).
    """
    west, south, east, north = US_BOUNDS
    width, height = 236, 102
    cold_to_hot = [(49, 54, 149), (116, 173, 209), (254, 224, 144), (244, 109, 67), (165, 0, 38)]

    def mercator(lat):
        return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))

    def pixel(x, y):
        # The map stretches a picture evenly in Web Mercator, so its rows are spaced that way.
        lon = west + (x + 0.5) / width * (east - west)
        y_mercator = mercator(north) - (y + 0.5) / height * (mercator(north) - mercator(south))
        lat = math.degrees(2 * math.atan(math.exp(y_mercator)) - math.pi / 2)
        return (*ramp(cold_to_hot, (temperature_at(lon, lat) + 5) / 45), 170)

    picture = png(width, height, pixel)
    return {
        "layers": [
            {
                "kind": "image",
                "name": "Temperature (picture)",
                "opacity": 0.8,
                "image": {
                    "mime": "image/png",
                    "data": base64.b64encode(picture).decode("ascii"),
                    "corners": [[west, north], [east, north], [east, south], [west, south]],
                },
            },
            {
                "kind": "points",
                "name": "Stores",
                "points": [
                    {"lat": row["lat"], "lon": row["lon"], "label": row["city"]}
                    for row in stores()
                ],
            },
        ]
    }
