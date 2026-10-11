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

from fastapi import APIRouter, HTTPException

from core import register_widget
from widgets_maps_data import (
    CANADA_PROVINCES,
    CENSUS_REGIONS,
    COUNTRIES,
    IOWA_COUNTIES,
    METRICS,
    STATE_NAMES,
    STATES,
    WORLD_OFFICES,
    YEARS,
    seeded,
    state_metric,
    stores,
)

router = APIRouter()


# ============================================================================
# POINTS
# ============================================================================

@register_widget({
    "name": "Map - Points from rows",
    "description": "Stores as points placed by lat and lon, coloured by revenue and sized by headcount (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_points",
    "gridData": {"w": 20, "h": 13},
    "data": {
        "map": {
            "lat": "lat",  # the column of the latitude, -90 to 90
            "lon": "lon",  # the column of the longitude, -180 to 180
            "label": "city",  # the name in the hover card
            "value": "revenue_musd",  # the number the colour scale reads
            "size": "headcount",  # the number the size of a point reads
            "props": ["state", "format", "opened"],  # other columns of the hover card (12 at most)
            "valueLabel": "Revenue (USD m, synthetic)",  # what the legend calls the value
        }
    },
})
@router.get("/maps_points")
def maps_points():
    """Points from rows with lat and lon.

    Get right: "lat" and "lon" are numbers in two separate columns, and they
    are not swapped: Chicago is lat 41.88, lon -87.63. A swapped pair lands in
    the ocean or fails the map (a latitude is -90 to 90). A street address is
    not a place: geocode in the backend. A map draws up to 20,000 points.
    """
    return stores()


@register_widget({
    "name": "Map - Points by city name",
    "description": "Offices placed by the name of their city, no coordinates in the rows (synthetic, global).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_points_by_city",
    "gridData": {"w": 20, "h": 13},
    "data": {
        "map": {
            "city": "city",  # the column of city names, matched in the app
            "country": "country",  # narrows the match: which "London"
            "label": "city",
            "value": "staff",
            "size": "staff",
            "props": ["country"],
            "valueLabel": "Staff (synthetic)",
        }
    },
})
@router.get("/maps_points_by_city")
def maps_points_by_city():
    """Points placed by a city name, for rows that have no coordinates.

    Get right: send the country (and the state, for US cities) beside the city,
    so "London" is not ambiguous. Cities of 25,000 residents or more are known;
    a name that matches nothing is left out and the map says how many.
    """
    return [
        {"city": name, "country": country, "staff": int(40 + seeded("office", name).random() * 900)}
        for name, country in WORLD_OFFICES
    ]


# ============================================================================
# SHADED REGIONS
# ============================================================================

@register_widget({
    "name": "Map - Regions by US state",
    "description": "US states shaded by a value, matched by their two-letter USPS code (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_regions_states",
    "gridData": {"w": 20, "h": 13},
    "data": {
        "map": {
            "state": "state",  # USPS code ("CA"), FIPS code ("06") or name ("California")
            "value": "unemployment_pct",
            "label": "state_name",
            "props": ["region"],
            "valueLabel": "Unemployment rate (%, synthetic)",
        }
    },
})
@router.get("/maps_regions_states")
def maps_regions_states():
    """US states shaded by a value.

    Get right: one row for each state, and a code that matches reliably: the
    two-letter USPS code ("CA") or the two-digit FIPS code as TEXT ("06", so the
    leading zero survives). The second row of a state is not drawn.
    """
    return [
        {
            "state": usps,
            "state_name": name,
            "region": region,
            "unemployment_pct": state_metric(usps, "unemployment_pct"),
        }
        for usps, _fips, name, region, _lon, _lat in STATES
    ]


@register_widget({
    "name": "Map - Regions by US county (FIPS)",
    "description": "The 99 counties of Iowa shaded by a value, matched by their five-digit FIPS code (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_regions_counties",
    "gridData": {"w": 20, "h": 13},
    "data": {
        "map": {
            "county": "fips",  # five-digit FIPS code as text: "19153"
            "value": "yield_bu_ac",
            "label": "county",
            "props": ["state"],
            "valueLabel": "Corn yield (bu/ac, synthetic)",
        }
    },
})
@router.get("/maps_regions_counties")
def maps_regions_counties():
    """US counties shaded by a value.

    Get right: the five-digit FIPS code as TEXT ("19153" = state 19 + county
    153; "06037" keeps its zero). A county name alone is ambiguous ("Washington
    County" is in many states): a name only matches with its state ("Polk County, IA").
    A map shades up to 4,000 regions, so all 3,231 counties fit.
    """
    return [
        {
            "fips": f"19{2 * at + 1:03d}",
            "county": f"{name} County",
            "state": "IA",
            "yield_bu_ac": round(165 + seeded("yield", name).random() * 60, 1),
        }
        for at, name in enumerate(IOWA_COUNTIES)
    ]


@register_widget({
    "name": "Map - Regions by country (ISO)",
    "description": "Countries shaded by a value that goes below and above zero, matched by ISO 3166-1 alpha-3 code (synthetic, global).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_regions_countries",
    "gridData": {"w": 20, "h": 13},
    "data": {
        "map": {
            "country": "iso3",  # ISO alpha-3 ("USA"), alpha-2 ("US"), numeric (840) or name
            "value": "gdp_growth_pct",
            "label": "country",
            "valueLabel": "GDP growth (%, synthetic)",
        }
    },
})
@router.get("/maps_regions_countries")
def maps_regions_countries():
    """Countries shaded by a value.

    Get right: ISO 3166-1 codes match reliably ("USA", "US" or 840); names work
    too but spellings vary. Values on both sides of zero get a two-colour scale
    that meets at zero, with no extra setting.
    """
    return [
        {
            "iso3": iso3,
            "country": name,
            "gdp_growth_pct": round(-3 + seeded("growth", iso3).random() * 10, 1),
        }
        for iso3, name in COUNTRIES
    ]


@register_widget({
    "name": "Map - Regions by province (ISO 3166-2)",
    "description": "The provinces and territories of Canada shaded by a value, matched by ISO 3166-2 code (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_regions_provinces",
    "gridData": {"w": 20, "h": 13},
    "data": {
        "map": {
            "province": "code",  # ISO 3166-2: "CA-ON", "DE-BY", "BR-SP"
            "within": "Canada",  # the country of every row, as text (not a column)
            "value": "housing_starts_k",
            "label": "province",
            "valueLabel": "Housing starts (thousands, synthetic)",
        }
    },
})
@router.get("/maps_regions_provinces")
def maps_regions_provinces():
    """States and provinces of any country, shaded by a value.

    Get right: the ISO 3166-2 code ("CA-ON") matches by itself. With short
    codes ("ON") or names, "within" must name the country, because "ON" alone
    could be a region of several countries.
    """
    return [
        {
            "code": code,
            "province": name,
            "housing_starts_k": round(1 + seeded("starts", code).random() ** 2 * 90, 1),
        }
        for code, name in CANADA_PROVINCES
    ]


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
            "state": "state",
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
        for usps, _fips, name, *_rest in STATES
    ]


# ============================================================================
# MARKERS AND TAGS FROM COLUMNS
# ============================================================================

@register_widget({
    "name": "Map - Markers and tags from columns",
    "description": "Stores where the rows the backend singles out carry a sign and a short text beside the point (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_marks",
    "gridData": {"w": 20, "h": 13},
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
def maps_marks():
    """Signs and tags driven by two columns of the rows.

    Get right: mark FEW rows (the ones that answer a question) and leave the
    cell empty (None) in the others. A column mapping takes the five named
    signs only; ranks, highlights and sign colours need a map with marks (see
    "Map - Ranks, highlights and sign colours" in widgets_maps_layers.py).
    """
    rows = stores()
    top = sorted(rows, key=lambda row: row["revenue_musd"], reverse=True)[:3]
    newest = max(rows, key=lambda row: row["opened"])
    for row in rows:
        row["marker"] = "star" if row in top else "flag" if row is newest else None
        row["tag"] = (
            f"{row['city']}: ${row['revenue_musd']}M" if row in top
            else f"Newest ({row['opened']})" if row is newest
            else None
        )
    return rows


# ============================================================================
# PARAMETERS
# ============================================================================

@register_widget({
    "name": "Map - Parameters",
    "description": "US states shaded by the metric, the year and the census region chosen in the parameters of the widget (synthetic).",
    "category": "Maps",
    "type": "map",
    "endpoint": "maps_parameters",
    "gridData": {"w": 20, "h": 13},
    "params": [
        {
            "paramName": "metric",
            "label": "Metric",
            "description": "The number that shades the states",
            "type": "text",
            "value": "unemployment_pct",
            "options": [
                {"label": "Unemployment rate", "value": "unemployment_pct"},
                {"label": "Median income", "value": "median_income_kusd"},
                {"label": "Population", "value": "population_m"},
            ],
        },
        {
            "paramName": "year",
            "label": "Year",
            "description": "The year of the numbers",
            "type": "text",
            "value": "2025",
            "options": [{"label": str(year), "value": str(year)} for year in YEARS],
        },
        {
            "paramName": "region",
            "label": "Region",
            "description": "Keep the states of one census region",
            "type": "text",
            "value": "all",
            "options": [{"label": "All regions", "value": "all"}]
            + [{"label": region, "value": region} for region in CENSUS_REGIONS],
        },
    ],
    "data": {"map": {"title": "States by metric (synthetic)"}},
})
@router.get("/maps_parameters")
def maps_parameters(metric: str = "unemployment_pct", year: str = "2025", region: str = "all"):
    """A map whose endpoint takes parameters, like any other widget.

    Get right: "data.map" is fixed in widgets.json, so when a parameter changes
    WHAT the value is, return the map itself and write "valueLabel" in the
    answer: { "valueLabel": ..., "regions": { "set": "us-states", "items":
    [{ "code", "value", "label" }] } }. Answer a value a parameter cannot have
    with a 400, never with other rows.
    """
    if metric not in METRICS:
        raise HTTPException(status_code=400, detail=f"metric: one of {', '.join(METRICS)}")
    if not year.isdigit() or int(year) not in YEARS:
        raise HTTPException(status_code=400, detail=f"year: {YEARS[0]} to {YEARS[-1]}")
    if region != "all" and region not in CENSUS_REGIONS:
        raise HTTPException(status_code=400, detail=f"region: all, {', '.join(CENSUS_REGIONS)}")
    return {
        "title": f"{METRICS[metric][0]}, {year}",
        "valueLabel": METRICS[metric][0],
        "regions": {
            "set": "us-states",
            "items": [
                {
                    "code": usps,
                    "label": name,
                    "value": state_metric(usps, metric, int(year)),
                    "props": {"region": state_region},
                }
                for usps, _fips, name, state_region, _lon, _lat in STATES
                if region in ("all", state_region)
            ],
        },
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
