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
A widget whose parameter changes WHAT the map shows returns a map too, because
"data.map" is fixed in widgets.json: the answer then carries its own "title"
and "valueLabel".

Limits of one map, all layers together: 20,000 points, 4,000 regions, 3,500
lines and areas (100,000 positions), 2,000 flows, 12 layers, 60 steps of time,
4 images and 2 MB as JSON. A map over a limit is not drawn and says why.

All data here is synthetic (see widgets_maps_data.py).
"""

import math

from fastapi import APIRouter

from core import register_widget
from widgets_maps_data import (
    CANADA_PROVINCES,
    COUNTRIES,
    IOWA_COUNTIES,
    STATES,
    city,
    great_circle,
    loop_buildings,
    one_of,
    scattered_points,
    seeded,
    state_metric,
    store_points,
)

router = APIRouter()

# (origin, destination) of the routes between cities
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


def _flows():
    """One arc for each shipment: its two ends by state code, or by position."""
    flows = [
        {
            "from": {"state": origin},
            "to": {"state": destination},
            "label": f"{origin} to {destination}",
            "value": int(50 + seeded("flow", origin, destination).random() * 950),
            "props": {"commodity": "Corn" if origin == "IA" else "Soybeans"},
        }
        for origin in ("IA", "IL")
        for destination in ("LA", "TX", "WA", "CA", "GA", "NY", "FL", "MN", "MO", "OH")
    ]
    # An end can also be a position: the river terminal at the Port of New Orleans.
    flows.append({
        "from": {"state": "IA"},
        "to": [-90.07, 29.95],
        "label": "IA to Port of New Orleans",
        "value": 700,
        "props": {"commodity": "Corn"},
    })
    return flows


def _arrows():
    """Wind on a grid over the United States: each arrow is a line of five positions."""
    def at(bearing, distance, origin):
        lon, lat = origin
        return [
            round(lon + distance * math.sin(math.radians(bearing)) / math.cos(math.radians(lat)), 4),
            round(lat + distance * math.cos(math.radians(bearing)), 4),
        ]

    arrows = []
    for lat in range(27, 49, 3):
        for lon in range(-122, -68, 4):
            to = (200 + 60 * math.sin(math.radians(lon * 5)) + 40 * math.cos(math.radians(lat * 8))) % 360
            speed = round(8 + 14 * abs(math.sin(math.radians(lon * 3 + lat * 5))), 1)
            length = 0.5 + speed / 22
            tail = [lon, lat]
            tip = at(to, length, tail)
            arrows.append({
                "type": "line",
                # tail, tip, one side of the head, tip, the other side
                "coordinates": [tail, tip, at(to + 150, length * 0.3, tip), tip, at(to - 150, length * 0.3, tip)],
                "label": f"Wind to {round(to)} degrees",
                "value": speed,
            })
    return arrows


# ============================================================================
# SHADED REGIONS
# ============================================================================

@register_widget({
    "name": "Map - Shaded regions",
    "description": "Regions shaded by a value, at four levels: US states, US counties, countries, or the provinces of a country (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_regions",
    "gridData": {"w": 20, "h": 13},
    "params": [
        {
            "paramName": "level",
            "label": "Level",
            "description": "The kind of region the map shades, each matched by its own code",
            "type": "text",
            "value": "states",
            "options": [
                {"label": "US states (USPS code)", "value": "states"},
                {"label": "US counties (FIPS code)", "value": "counties"},
                {"label": "Countries (ISO 3166-1)", "value": "countries"},
                {"label": "Provinces (ISO 3166-2)", "value": "provinces"},
            ],
        }
    ],
    "data": {"map": {}},
})
@router.get("/maps_regions")
def maps_regions(level: str = "states"):
    """Regions shaded by a value. The answer is a map with "regions": a "set" and one item for each region:

        level=states     {"regions": {"set": "us-states",   "items": [{"code": "CA", "value": 4.1}]}}
        level=counties   {"regions": {"set": "us-counties", "items": [{"code": "19153", "value": 201.3}]}}
        level=countries  {"regions": {"set": "countries",   "items": [{"code": "USA", "value": 2.1}]}}
        level=provinces  {"regions": {"set": "admin1", "within": {"country": "Canada"},
                                      "items": [{"code": "CA-ON", "value": 71.5}]}}

    A widget with ONE level can return rows instead and name the code column in
    "data.map": {"state": "state"}, {"county": "fips"}, {"country": "iso3"} or
    {"province": "code", "within": "Canada"} (see maps_time in widgets_maps.py).

    Get right: one item for each region, and a code that matches reliably, as
    TEXT so a leading zero survives. A state: the USPS code ("CA"). A county:
    the five-digit FIPS code ("19153" = state 19 + county 153; a county name
    alone is ambiguous). A country: an ISO 3166-1 code ("USA", "US"). A
    province: the ISO 3166-2 code ("CA-ON"); with short codes ("ON") or names,
    "within" must name the country. A map shades 4,000 regions, so all 3,231
    counties fit. Values on both sides of zero get a two-colour scale that
    meets at zero, as the countries here show.
    """
    one_of("level", level, ["states", "counties", "countries", "provinces"])
    if level == "states":
        return {
            "title": "Unemployment by state (synthetic)",
            "valueLabel": "Unemployment rate (%, synthetic)",
            "regions": {
                "set": "us-states",
                "items": [
                    {
                        "code": usps,
                        "label": name,
                        "value": state_metric(usps, "unemployment_pct"),
                        "props": {"region": region},
                    }
                    for usps, name, region in STATES
                ],
            },
        }
    if level == "counties":
        return {
            "title": "Corn yield by county, Iowa (synthetic)",
            "valueLabel": "Corn yield (bu/ac, synthetic)",
            "regions": {
                "set": "us-counties",
                "items": [
                    {
                        # The FIPS codes of the counties of Iowa are the odd numbers from 19001.
                        "code": f"19{2 * at + 1:03d}",
                        "label": f"{name} County",
                        "value": round(165 + seeded("yield", name).random() * 60, 1),
                        "props": {"state": "IA"},
                    }
                    for at, name in enumerate(IOWA_COUNTIES)
                ],
            },
        }
    if level == "countries":
        return {
            "title": "GDP growth by country (synthetic)",
            "valueLabel": "GDP growth (%, synthetic)",
            "regions": {
                "set": "countries",
                "items": [
                    {
                        "code": iso3,
                        "label": name,
                        "value": round(-3 + seeded("growth", iso3).random() * 10, 1),
                    }
                    for iso3, name in COUNTRIES
                ],
            },
        }
    return {
        "title": "Housing starts by province, Canada (synthetic)",
        "valueLabel": "Housing starts (thousands, synthetic)",
        "regions": {
            "set": "admin1",  # the states and provinces of every country
            "within": {"country": "Canada"},
            "items": [
                {
                    "code": code,
                    "label": name,
                    "value": round(1 + seeded("starts", code).random() ** 2 * 90, 1),
                }
                for code, name in CANADA_PROVINCES
            ],
        },
    }


# ============================================================================
# LINES, FLOWS AND ARROWS
# ============================================================================

@register_widget({
    "name": "Map - Lines, flows and arrows",
    "description": "Three ways to draw a connection: routes as lines, shipments as arcs from an origin to a destination, and wind as arrows (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_flows",
    "gridData": {"w": 20, "h": 13},
    "params": [
        {
            "paramName": "show",
            "label": "Show",
            "description": "How a connection is drawn: a path, an arc from an origin to a destination, or an arrow",
            "type": "text",
            "value": "lines",
            "options": [
                {"label": "Lines (truck routes)", "value": "lines"},
                {"label": "Flows (shipments)", "value": "flows"},
                {"label": "Arrows (wind direction)", "value": "arrows"},
            ],
        }
    ],
    "data": {"map": {}},
})
@router.get("/maps_flows")
def maps_flows(show: str = "lines"):
    """Lines and flows. The answer is a map with one layer:

        show=lines   {"layers": [{"kind": "lines", "shapes": [{"type": "line", "coordinates": [[lon, lat], ...], "value": 410}]}]}
        show=flows   {"layers": [{"kind": "flows", "flows": [{"from": {"state": "IA"}, "to": [-90.07, 29.95], "value": 700}]}]}
        show=arrows  a "lines" layer again: each arrow is a line of five positions the backend computes

    Get right: a position is [longitude, latitude] (GeoJSON order). A line is
    the path you want drawn: the map joins its positions with straight
    segments, so a long route needs intermediate positions. The end of a flow
    is [lon, lat], {"lat", "lon"}, {"state": "IA"}, {"country": "BR"} or
    {"city": "Chicago"}; the arc is faint at its start and full at its end, so
    "from" and "to" must not be swapped. The map has no arrow mark: send tail,
    tip, one side of the head, tip, the other side. A map draws 3,500 lines
    (100,000 positions) and 2,000 flows: aggregate first.
    """
    one_of("show", show, ["lines", "flows", "arrows"])
    if show == "lines":
        return {
            "title": "Truck routes (synthetic)",
            "layers": [
                {"kind": "lines", "name": "Routes", "valueLabel": "Loads per week (synthetic)", "shapes": _routes()}
            ],
        }
    if show == "flows":
        return {
            "title": "Grain shipments (synthetic)",
            "layers": [
                {"kind": "flows", "name": "Shipments", "valueLabel": "Shipments (kt, synthetic)", "flows": _flows()}
            ],
        }
    return {
        "title": "Wind (synthetic)",
        "layers": [
            {"kind": "lines", "name": "Wind", "valueLabel": "Wind speed (m/s, synthetic)", "shapes": _arrows()}
        ],
    }


# ============================================================================
# AREAS AND 3D FOOTPRINTS (GEOJSON)
# ============================================================================

@register_widget({
    "name": "Map - Areas and 3D footprints (GeoJSON)",
    "description": "Building footprints in the Chicago Loop as GeoJSON polygons, coloured by their floors: flat, or standing as tall as their height in metres (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_footprints",
    "gridData": {"w": 20, "h": 13},
    "params": [
        {
            "paramName": "extrude",
            "label": "Extrude",
            "description": "Whether the features carry the height that makes them stand",
            "type": "text",
            "value": "off",
            "options": [
                {"label": "Off (flat areas)", "value": "off"},
                {"label": "On (3D by height)", "value": "on"},
            ],
        }
    ],
    "data": {
        "map": {
            "title": "Downtown buildings (synthetic)",
            "value": "floors_count",  # the number property of a feature that colours it
            "height": "height_m",  # the number property that says how high an area stands, in METRES
            "valueLabel": "Floors (synthetic)",
        }
    },
})
@router.get("/maps_footprints")
def maps_footprints(extrude: str = "off"):
    """Areas: the endpoint returns a GeoJSON FeatureCollection of polygons.

        extrude=off  {"type": "FeatureCollection", "features": [{"type": "Feature",
                      "properties": {"name": "Adams Tower 3", "floors_count": 41},
                      "geometry": {"type": "Polygon", "coordinates": [[[lon, lat], ...]]}}]}
        extrude=on   the same, and every feature also has "height_m": 159.9

    Get right: return the FeatureCollection itself (not rows with a geometry
    column), close every ring (first position = last position) and name the
    colouring property in "data.map.value". "name" (or "label", "title") is the
    name of a feature; its other scalar properties are in the hover card. An
    area stands when it has the property "data.map.height" names: a NUMBER in
    METRES (not "42 m", not feet). Without that key the properties "height" and
    "floors" (3.2 m each) are read. A height over 1,000 m is drawn at 1,000 m.
    A map draws 3,500 areas; each part of a MultiPolygon counts as one.
    """
    one_of("extrude", extrude, ["off", "on"])
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": building["name"],
                    "floors_count": building["floors"],
                    "use": building["use"],
                    "year_built": building["year_built"],
                    **({"height_m": building["height_m"]} if extrude == "on" else {}),
                },
                "geometry": {"type": "Polygon", "coordinates": [building["ring"]]},
            }
            for building in loop_buildings()
        ],
    }


# ============================================================================
# MANY POINTS: HEAT, CLUSTERS AND COLUMNS
# ============================================================================

@register_widget({
    "name": "Map - Heat, clusters and columns",
    "description": "2,000 orders drawn three ways: as a density, as clusters with a count, or summed by state as 3D bars (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_density",
    "gridData": {"w": 20, "h": 13},
    "params": [
        {
            "paramName": "mode",
            "label": "Draw as",
            "description": "How the 2,000 points are drawn",
            "type": "text",
            "value": "heat",
            "options": [
                {"label": "Heat (density)", "value": "heat"},
                {"label": "Clusters", "value": "clusters"},
                {"label": "Columns (3D bars by state)", "value": "columns"},
            ],
        }
    ],
    "data": {"map": {}},
})
@router.get("/maps_density")
def maps_density(mode: str = "heat"):
    """Too many points for single marks. The answer is a map with one layer:

        mode=heat      {"layers": [{"kind": "heat",     "points": [{"lat": 41.9, "lon": -87.6, "value": 12}]}]}
        mode=clusters  {"layers": [{"kind": "clusters", "points": [{"lat", "lon", "value", "label", "props"}]}]}
        mode=columns   {"layers": [{"kind": "columns",  "regions": {"set": "us-states", "items": [{"code": "IL", "value": 3120}]}}]}

    Get right: a density has no hover card, so send lean points ({"lat", "lon",
    "value"}; "value" is the weight). The single points of clusters are reached
    by zooming in, so a short label and a few props are worth their bytes. A
    "columns" layer holds EITHER "regions" OR "points" (a bar at each place),
    never both, every bar needs a "value", and the map opens tilted. The points
    of a map are 20,000 at most and the whole map 2 MB: aggregate in the
    backend before that, as the columns do.
    """
    one_of("mode", mode, ["heat", "clusters", "columns"])
    orders = scattered_points(2000)
    if mode == "heat":
        return {
            "title": "Order density (synthetic)",
            "layers": [
                {
                    "kind": "heat",
                    "name": "Orders",
                    "valueLabel": "Orders (synthetic)",
                    "points": [
                        {"lat": point["lat"], "lon": point["lon"], "value": point["orders"]}
                        for point in orders
                    ],
                }
            ],
        }
    if mode == "clusters":
        return {
            "title": "Order clusters (synthetic)",
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
                        for at, point in enumerate(orders)
                    ],
                }
            ],
        }
    totals = {}
    for point in orders:
        totals[point["state"]] = totals.get(point["state"], 0) + point["orders"]
    return {
        "title": "Orders by state (synthetic)",
        "layers": [
            {
                "kind": "columns",
                "name": "Orders",
                "valueLabel": "Orders (synthetic)",
                "regions": {
                    "set": "us-states",
                    "items": [{"code": usps, "value": total} for usps, total in sorted(totals.items())],
                },
            }
        ],
    }


# ============================================================================
# SEVERAL LAYERS ON ONE MAP, AND WHERE IT OPENS
# ============================================================================

# What each value of "open_on" adds to the map: a "view", and a "pitch" for the tilt.
VIEWS = {
    "data": {},
    "place": {"view": {"place": "Texas"}},
    "center": {"view": {"center": [-87.63, 41.88], "zoom": 6}},
    "bounds": {"view": {"bounds": [-80.6, 38.4, -66.9, 47.5]}},
    "tilted": {"view": {"center": [-93.5, 42.0], "zoom": 6.5, "bearing": -20}, "pitch": 50},
}


@register_widget({
    "name": "Map - Layers and the opening view",
    "description": "Four layers on one map: shaded states, routes, stores and a density that is off until it is turned on. A parameter says where the map opens (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_layers",
    "gridData": {"w": 40, "h": 15},
    "params": [
        {
            "paramName": "open_on",
            "label": "Open on",
            "description": "Where the map opens. Every layer stays whole.",
            "type": "text",
            "value": "data",
            "options": [
                {"label": "All the data (no view)", "value": "data"},
                {"label": "A place by name (Texas)", "value": "place"},
                {"label": "A centre and a zoom (Chicago)", "value": "center"},
                {"label": "A box (the Northeast)", "value": "bounds"},
                {"label": "Tilted and turned (Iowa)", "value": "tilted"},
            ],
        }
    ],
    "data": {"map": {"title": "Network overview (synthetic)"}},
})
@router.get("/maps_layers")
def maps_layers(open_on: str = "data"):
    """Several layers in one widget, each with a name, a legend entry and a switch.

        {"layers": [{"id": "income", "kind": "regions", "name": "States", "valueLabel": ..., "regions": {...}},
                    {"id": "orders", "kind": "heat", "name": "Order density", "visible": false, "points": [...]},
                    ...],
         "view": {"place": "Texas"}}        open_on=place
         "view": {"center": [-87.63, 41.88], "zoom": 6}      open_on=center
         "view": {"bounds": [-80.6, 38.4, -66.9, 47.5]}      open_on=bounds (west, south, east, north)
         "view": {"center": ..., "zoom": 6.5, "bearing": -20}, "pitch": 50      open_on=tilted

    Get right: the order of "layers" is the drawing order, the FIRST at the
    bottom, so shaded regions go first and points last. Give each layer an "id"
    (lower case, digits, "-" and "_"), a short "name" for the layer panel and a
    "valueLabel" for the legend (each layer has its own scale); "visible": False
    leaves a layer off until the reader turns it on, and "opacity" is 0 to 1. A
    map has 12 layers at most. A view changes where the map LOOKS, not what it
    holds: do not filter the data to "zoom in". Give ONE of "place", "center"
    with "zoom" (0 to 19) or "bounds"; an ambiguous place ("Georgia") is not
    guessed: the map opens on its data and says so.
    """
    one_of("open_on", open_on, VIEWS)
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
                        for usps, name, _region in STATES
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
                "points": store_points(),
            },
        ],
        **VIEWS[open_on],
    }
