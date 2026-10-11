"""
Map widgets, part 1: rows.

A map widget is declared with "type": "map". Its endpoint returns rows, as the
endpoint of a table does, and "data.map" of the definition names the columns
that say where a row is and what the map says about it:

    "data": {"map": {"lat": "lat", "lon": "lon", "value": "revenue_musd", "label": "city"}}

A row is placed by "lat" and "lon", by "city", or by ONE region column:
"state", "county", "country", "province", "metro" or "district".

All data here is synthetic (see widgets_maps_data.py). The Map widget needs a
Workspace build that includes it. Part 2 (widgets_maps_layers.py) returns whole
maps with layers; part 3 (widgets_maps_files.py) returns files and declares
map sources.
"""

from fastapi import APIRouter

from core import register_widget
from widgets_maps_data import (
    STATE_NAMES,
    STATES,
    YEARS,
    offices,
    one_of,
    state_metric,
    stores,
)

router = APIRouter()


# ============================================================================
# POINTS
# ============================================================================

@register_widget({
    "name": "Map - Points",
    "description": "Points from rows, coloured by revenue and sized by headcount: placed by lat and lon, or by the name of a city (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_points",
    "gridData": {"w": 20, "h": 13},
    "params": [
        {
            "paramName": "place_by",
            "label": "Place by",
            "description": "What places a row: its coordinates (US stores), or the name of its city (offices worldwide)",
            "type": "text",
            "value": "coordinates",
            "options": [
                {"label": "Latitude and longitude", "value": "coordinates"},
                {"label": "City name", "value": "city"},
            ],
        }
    ],
    "data": {
        "map": {
            "lat": "lat",  # the column of the latitude, -90 to 90
            "lon": "lon",  # the column of the longitude, -180 to 180
            "city": "city",  # places a row that has no lat and lon, matched by name in the app
            "country": "country",  # narrows the match of a city: which "London"
            "label": "city",  # the name in the hover card
            "value": "revenue_musd",  # the number the colour scale reads
            "size": "headcount",  # the number the size of a point reads
            "props": ["state", "country", "format", "opened"],  # other columns of the hover card (12 at most)
            "valueLabel": "Revenue (USD m, synthetic)",  # what the legend calls the value
        }
    },
})
@router.get("/maps_points")
def maps_points(place_by: str = "coordinates"):
    """Points from rows. The answer is rows in both cases:

        place_by=coordinates  [{"lat": 41.88, "lon": -87.63, "city": "Chicago", "revenue_musd": 12.4, ...}]
        place_by=city         [{"city": "London", "country": "GB", "revenue_musd": 31.0, ...}]

    Get right: "lat" and "lon" are numbers in two separate columns, and they
    are not swapped: Chicago is lat 41.88, lon -87.63. A row without them is
    placed by its "city" when the mapping names that column: send the country
    (or the state, for US cities) beside it, so "London" is not ambiguous. A
    name that matches nothing is left out and the map says how many. A street
    address is not a place: geocode in the backend. A map draws 20,000 points.
    """
    one_of("place_by", place_by, ["coordinates", "city"])
    return stores() if place_by == "coordinates" else offices()


# ============================================================================
# TIME
# ============================================================================

@register_widget({
    "name": "Map - Time slider",
    "description": "US states shaded by a value for each year from 2016 to 2025: the map gets a slider and a play button (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_time",
    "gridData": {"w": 20, "h": 13},
    "data": {
        "map": {
            "state": "state",  # a region column: USPS code ("CA"), FIPS code as text ("06") or name
            "value": "unemployment_pct",
            "label": "state_name",
            "time": "year",  # the column of the steps: a year, "2024-03", "2024-03-15"
            "valueLabel": "Unemployment rate (%, synthetic)",
        }
    },
})
@router.get("/maps_time")
def maps_time():
    """A map that plays over time: one row for each state and year.

    Get right: name the step column in "time" and keep the steps few: a map has
    at most 60 steps, and regions x steps is at most 4,000 (51 states x 10 years
    = 510 here). Write dates year first ("2024-03") so they sort. The colour
    scale spans all the steps, so a colour means the same number in every year.
    """
    return [
        {
            "state": usps,
            "state_name": name,
            "year": year,
            "unemployment_pct": state_metric(usps, "unemployment_pct", year),
        }
        for year in YEARS
        for usps, name, _region in STATES
    ]


# ============================================================================
# MARKERS, TAGS, RANKS AND CATEGORIES
# ============================================================================

@register_widget({
    "name": "Map - Markers, tags, ranks and categories",
    "description": "Stores where a few rows are singled out: by a sign and a tag from two columns, by a rank and a highlight, or by the colour of a category (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_marks",
    "gridData": {"w": 20, "h": 13},
    "params": [
        {
            "paramName": "style",
            "label": "Single out by",
            "description": "How the map singles out some of the stores",
            "type": "text",
            "value": "signs",
            "options": [
                {"label": "Signs and tags from columns", "value": "signs"},
                {"label": "Ranks and highlights", "value": "ranks"},
                {"label": "Colour by category", "value": "categories"},
            ],
        }
    ],
    "data": {
        "map": {
            "lat": "lat",
            "lon": "lon",
            "label": "city",
            "value": "revenue_musd",
            "marker": "marker",  # "pin", "check", "star", "flag", "ring" or true (the pin)
            "tag": "tag",  # a short text beside the mark, 40 characters at most
            "props": ["state", "opened"],
            "valueLabel": "Revenue (USD m, synthetic)",
        }
    },
})
@router.get("/maps_marks")
def maps_marks(style: str = "signs"):
    """What a mark says besides its value. The shape of the answer follows the parameter:

        style=signs       rows, read by "data.map": [{"lat", "lon", "marker": "star", "tag": "Austin: $61.6M"}]
        style=ranks       a map: {"valueLabel": ..., "points": [{"lat", "lon", "marker": 1, "tag": ...,
                          "markerColor": "positive", "meaning": "Five largest stores"},
                          {"lat", "lon", "highlight": true, ...}]}
        style=categories  a map: {"categoryLabel": ..., "points": [{"lat", "lon", "category": "Outlet"}]}

    Get right: mark FEW rows (the ones that answer a question) and leave the
    cell empty (None) in the others. A column takes the five named signs only.
    A rank (1 to 99), "highlight", "markerColor" (accent, positive, negative,
    neutral or #rrggbb) and "meaning" (the line of the legend, 60 characters)
    are fields of a mark, so the endpoint returns the map itself. A map has 12
    categories at most: group the long tail as "Other" in the backend, and do
    not give a mark both a "category" and a "value".
    """
    one_of("style", style, ["signs", "ranks", "categories"])
    rows = sorted(stores(), key=lambda row: row["revenue_musd"], reverse=True)

    if style == "signs":
        newest = max(rows, key=lambda row: row["opened"])
        for at, row in enumerate(rows):
            row["marker"] = "star" if at < 3 else "flag" if row is newest else None
            row["tag"] = (
                f"{row['city']}: ${row['revenue_musd']}M" if at < 3
                else f"Newest ({row['opened']})" if row is newest
                else None
            )
        return rows

    if style == "ranks":
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
            for row in rows
        ],
    }


# ============================================================================
# A TABLE AND A MAP THAT SHARE A PARAMETER (GROUPING)
# ============================================================================

@router.get("/maps_state_options")
def maps_state_options():
    """The states that have stores, as the options of the shared "state" parameter"""
    with_stores = sorted({row["state"] for row in stores()})
    return [{"label": STATE_NAMES[usps], "value": usps} for usps in with_stores]


@register_widget({
    "name": "Map - Stores by state (table)",
    "description": "Revenue by state. Click a state to move the map beside it, which shares the parameter 'state' (synthetic).",
    "category": "Maps",
    "type": "table",
    "endpoint": "maps_group_table",
    "gridData": {"w": 16, "h": 13},
    "params": [
        {
            "paramName": "state",  # Shared paramName with the maps_group_map widget
            "description": "The state the map beside this table shows",
            "value": "TX",
            "label": "State",
            "type": "endpoint",
            "optionsEndpoint": "/maps_state_options",  # Shared endpoint with maps_group_map
        }
    ],
    "data": {
        "table": {
            "showAll": True,
            "columnsDefs": [
                {
                    "field": "state",
                    "headerName": "State",
                    "cellDataType": "text",
                    "width": 110,
                    "pinned": "left",
                    "renderFn": "cellOnClick",
                    "renderFnParams": {
                        "actionType": "groupBy",
                        "groupBy": {"paramName": "state"},
                    },
                },
                {"field": "state_name", "headerName": "Name", "cellDataType": "text", "width": 160},
                {"field": "stores", "headerName": "Stores", "cellDataType": "number", "formatterFn": "int", "width": 100},
                {"field": "revenue_musd", "headerName": "Revenue (USD m)", "cellDataType": "number", "formatterFn": "none", "width": 160},
            ],
        }
    },
})
@router.get("/maps_group_table")
def maps_group_table(state: str = "TX"):
    """Returns one row for each state that has stores: every row, whatever the parameter"""
    totals = {}
    for row in stores():
        total = totals.setdefault(row["state"], {"stores": 0, "revenue_musd": 0.0})
        total["stores"] += 1
        total["revenue_musd"] = round(total["revenue_musd"] + row["revenue_musd"], 1)
    return [
        {"state": usps, "state_name": STATE_NAMES[usps], **total}
        for usps, total in sorted(totals.items(), key=lambda item: -item[1]["revenue_musd"])
    ]


@register_widget({
    "name": "Map - Stores of the selected state",
    "description": "The stores of one state, chosen in the parameter 'state' or by a click in the table beside it (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_group_map",
    "gridData": {"w": 24, "h": 13},
    "params": [
        {
            "paramName": "state",  # Must match the groupBy.paramName of the table widget
            "description": "The state whose stores are drawn",
            "value": "TX",
            "label": "State",
            "type": "endpoint",
            "optionsEndpoint": "/maps_state_options",
        }
    ],
    "data": {
        "map": {
            "lat": "lat",
            "lon": "lon",
            "label": "city",
            "tag": "city",
            "value": "revenue_musd",
            "size": "revenue_musd",
            "props": ["state", "headcount"],
            "valueLabel": "Revenue (USD m, synthetic)",
        }
    },
})
@router.get("/maps_group_map")
def maps_group_map(state: str = "TX"):
    """A map in a parameter group: it follows the state picked in the table.

    Get right: the map and the table declare the SAME "paramName" (and the same
    "optionsEndpoint"), and apps.json puts both in one group. The endpoint just
    filters by the parameter; the map opens on the rows it gets.
    """
    return [row for row in stores() if row["state"] == state.upper()]
