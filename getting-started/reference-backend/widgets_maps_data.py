"""
Synthetic datasets and tiny binary writers for the Maps tab.

Everything here is made up from fixed seeds, in code, with the standard library
only: no network, no data files, no new dependency. The only real things are
the codes a map matches rows by (USPS and FIPS codes of the US states, the FIPS
codes of the counties of Iowa, ISO 3166 codes) and the coordinates of cities.

The widgets live in widgets_maps.py (rows), widgets_maps_layers.py (maps with
layers) and widgets_maps_files.py (files and map sources).
"""

import io
import math
import random
import struct
import zipfile
import zlib

# ============================================================================
# PLACES
# ============================================================================

# (USPS code, FIPS code, name, census region, longitude, latitude)
STATES = [
    ("AL", "01", "Alabama", "South", -86.75, 32.79),
    ("AK", "02", "Alaska", "West", -151.06, 64.50),
    ("AZ", "04", "Arizona", "West", -111.59, 34.29),
    ("AR", "05", "Arkansas", "South", -92.36, 34.90),
    ("CA", "06", "California", "West", -119.98, 37.25),
    ("CO", "08", "Colorado", "West", -105.55, 39.00),
    ("CT", "09", "Connecticut", "Northeast", -72.66, 41.62),
    ("DE", "10", "Delaware", "South", -75.40, 38.73),
    ("DC", "11", "District of Columbia", "South", -77.00, 38.90),
    ("FL", "12", "Florida", "South", -81.65, 28.65),
    ("GA", "13", "Georgia", "South", -83.25, 32.65),
    ("HI", "15", "Hawaii", "West", -155.46, 19.60),
    ("ID", "16", "Idaho", "West", -115.06, 44.39),
    ("IL", "17", "Illinois", "Midwest", -89.51, 40.07),
    ("IN", "18", "Indiana", "Midwest", -86.17, 39.91),
    ("IA", "19", "Iowa", "Midwest", -93.22, 42.07),
    ("KS", "20", "Kansas", "Midwest", -98.33, 38.48),
    ("KY", "21", "Kentucky", "South", -85.03, 37.53),
    ("LA", "22", "Louisiana", "South", -91.70, 30.36),
    ("ME", "23", "Maine", "Northeast", -69.12, 45.36),
    ("MD", "24", "Maryland", "South", -77.05, 39.36),
    ("MA", "25", "Massachusetts", "Northeast", -72.15, 42.27),
    ("MI", "26", "Michigan", "Midwest", -84.51, 43.48),
    ("MN", "27", "Minnesota", "Midwest", -94.45, 46.32),
    ("MS", "28", "Mississippi", "South", -89.77, 32.75),
    ("MO", "29", "Missouri", "Midwest", -92.48, 38.37),
    ("MT", "30", "Montana", "West", -109.56, 47.03),
    ("NE", "31", "Nebraska", "Midwest", -100.07, 41.53),
    ("NV", "32", "Nevada", "West", -117.03, 39.36),
    ("NH", "33", "New Hampshire", "Northeast", -71.64, 43.69),
    ("NJ", "34", "New Jersey", "Northeast", -74.77, 39.78),
    ("NM", "35", "New Mexico", "West", -106.05, 34.42),
    ("NY", "36", "New York", "Northeast", -76.10, 42.94),
    ("NC", "37", "North Carolina", "South", -80.16, 35.54),
    ("ND", "38", "North Dakota", "Midwest", -100.45, 47.45),
    ("OH", "39", "Ohio", "Midwest", -82.71, 40.29),
    ("OK", "40", "Oklahoma", "South", -97.23, 35.58),
    ("OR", "41", "Oregon", "West", -120.56, 43.94),
    ("PA", "42", "Pennsylvania", "Northeast", -77.79, 40.87),
    ("RI", "44", "Rhode Island", "Northeast", -71.58, 41.69),
    ("SC", "45", "South Carolina", "South", -80.55, 33.91),
    ("SD", "46", "South Dakota", "Midwest", -100.26, 44.44),
    ("TN", "47", "Tennessee", "South", -86.33, 35.84),
    ("TX", "48", "Texas", "South", -99.98, 31.48),
    ("UT", "49", "Utah", "West", -111.55, 39.32),
    ("VT", "50", "Vermont", "Northeast", -72.74, 44.08),
    ("VA", "51", "Virginia", "South", -79.68, 37.13),
    ("WA", "53", "Washington", "West", -119.68, 47.38),
    ("WV", "54", "West Virginia", "South", -80.66, 38.64),
    ("WI", "55", "Wisconsin", "Midwest", -90.31, 44.63),
    ("WY", "56", "Wyoming", "West", -107.55, 43.00),
]
STATE_NAMES = {usps: name for usps, _fips, name, *_rest in STATES}
CENSUS_REGIONS = ["Northeast", "Midwest", "South", "West"]

# (city, USPS code of its state, latitude, longitude): the contiguous states
US_CITIES = [
    ("New York", "NY", 40.7128, -74.0060),
    ("Los Angeles", "CA", 34.0522, -118.2437),
    ("Chicago", "IL", 41.8781, -87.6298),
    ("Houston", "TX", 29.7604, -95.3698),
    ("Phoenix", "AZ", 33.4484, -112.0740),
    ("Philadelphia", "PA", 39.9526, -75.1652),
    ("San Antonio", "TX", 29.4241, -98.4936),
    ("San Diego", "CA", 32.7157, -117.1611),
    ("Dallas", "TX", 32.7767, -96.7970),
    ("Austin", "TX", 30.2672, -97.7431),
    ("Jacksonville", "FL", 30.3322, -81.6557),
    ("Columbus", "OH", 39.9612, -82.9988),
    ("Charlotte", "NC", 35.2271, -80.8431),
    ("Indianapolis", "IN", 39.7684, -86.1581),
    ("San Francisco", "CA", 37.7749, -122.4194),
    ("Seattle", "WA", 47.6062, -122.3321),
    ("Denver", "CO", 39.7392, -104.9903),
    ("Washington", "DC", 38.9072, -77.0369),
    ("Boston", "MA", 42.3601, -71.0589),
    ("Nashville", "TN", 36.1627, -86.7816),
    ("Detroit", "MI", 42.3314, -83.0458),
    ("Portland", "OR", 45.5152, -122.6784),
    ("Las Vegas", "NV", 36.1699, -115.1398),
    ("Memphis", "TN", 35.1495, -90.0490),
    ("Atlanta", "GA", 33.7490, -84.3880),
    ("Miami", "FL", 25.7617, -80.1918),
    ("Minneapolis", "MN", 44.9778, -93.2650),
    ("New Orleans", "LA", 29.9511, -90.0715),
    ("Kansas City", "MO", 39.0997, -94.5786),
    ("Omaha", "NE", 41.2565, -95.9345),
    ("Salt Lake City", "UT", 40.7608, -111.8910),
    ("St. Louis", "MO", 38.6270, -90.1994),
    ("Des Moines", "IA", 41.5868, -93.6250),
    ("Cedar Rapids", "IA", 41.9779, -91.6656),
    ("Davenport", "IA", 41.5236, -90.5776),
    ("Sioux City", "IA", 42.4963, -96.4049),
]

# (city, country as ISO 3166-1 alpha-2): placed by name, so no coordinates
WORLD_OFFICES = [
    ("New York", "US"), ("Chicago", "US"), ("San Francisco", "US"),
    ("Toronto", "CA"), ("Mexico City", "MX"), ("Sao Paulo", "BR"),
    ("Buenos Aires", "AR"), ("London", "GB"), ("Paris", "FR"),
    ("Frankfurt", "DE"), ("Madrid", "ES"), ("Amsterdam", "NL"),
    ("Stockholm", "SE"), ("Dubai", "AE"), ("Lagos", "NG"),
    ("Johannesburg", "ZA"), ("Mumbai", "IN"), ("Singapore", "SG"),
    ("Hong Kong", "HK"), ("Tokyo", "JP"), ("Seoul", "KR"), ("Sydney", "AU"),
]

# (ISO 3166-1 alpha-3, name)
COUNTRIES = [
    ("USA", "United States"), ("CAN", "Canada"), ("MEX", "Mexico"),
    ("BRA", "Brazil"), ("ARG", "Argentina"), ("CHL", "Chile"),
    ("COL", "Colombia"), ("PER", "Peru"), ("GBR", "United Kingdom"),
    ("FRA", "France"), ("DEU", "Germany"), ("ESP", "Spain"), ("ITA", "Italy"),
    ("NLD", "Netherlands"), ("SWE", "Sweden"), ("NOR", "Norway"),
    ("POL", "Poland"), ("UKR", "Ukraine"), ("TUR", "Turkey"), ("EGY", "Egypt"),
    ("NGA", "Nigeria"), ("ZAF", "South Africa"), ("KEN", "Kenya"),
    ("ETH", "Ethiopia"), ("MAR", "Morocco"), ("SAU", "Saudi Arabia"),
    ("ARE", "United Arab Emirates"), ("IND", "India"), ("PAK", "Pakistan"),
    ("BGD", "Bangladesh"), ("CHN", "China"), ("JPN", "Japan"),
    ("KOR", "South Korea"), ("IDN", "Indonesia"), ("VNM", "Vietnam"),
    ("THA", "Thailand"), ("PHL", "Philippines"), ("KAZ", "Kazakhstan"),
    ("AUS", "Australia"), ("NZL", "New Zealand"),
]

# (ISO 3166-2 code, name)
CANADA_PROVINCES = [
    ("CA-AB", "Alberta"), ("CA-BC", "British Columbia"), ("CA-MB", "Manitoba"),
    ("CA-NB", "New Brunswick"), ("CA-NL", "Newfoundland and Labrador"),
    ("CA-NS", "Nova Scotia"), ("CA-NT", "Northwest Territories"),
    ("CA-NU", "Nunavut"), ("CA-ON", "Ontario"), ("CA-PE", "Prince Edward Island"),
    ("CA-QC", "Quebec"), ("CA-SK", "Saskatchewan"), ("CA-YT", "Yukon"),
]

# The 99 counties of Iowa in the order of their FIPS codes: 19001, 19003, ... 19197
IOWA_COUNTIES = (
    "Adair,Adams,Allamakee,Appanoose,Audubon,Benton,Black Hawk,Boone,Bremer,"
    "Buchanan,Buena Vista,Butler,Calhoun,Carroll,Cass,Cedar,Cerro Gordo,Cherokee,"
    "Chickasaw,Clarke,Clay,Clayton,Clinton,Crawford,Dallas,Davis,Decatur,Delaware,"
    "Des Moines,Dickinson,Dubuque,Emmet,Fayette,Floyd,Franklin,Fremont,Greene,"
    "Grundy,Guthrie,Hamilton,Hancock,Hardin,Harrison,Henry,Howard,Humboldt,Ida,"
    "Iowa,Jackson,Jasper,Jefferson,Johnson,Jones,Keokuk,Kossuth,Lee,Linn,Louisa,"
    "Lucas,Lyon,Madison,Mahaska,Marion,Marshall,Mills,Mitchell,Monona,Monroe,"
    "Montgomery,Muscatine,O'Brien,Osceola,Page,Palo Alto,Plymouth,Pocahontas,Polk,"
    "Pottawattamie,Poweshiek,Ringgold,Sac,Scott,Shelby,Sioux,Story,Tama,Taylor,"
    "Union,Van Buren,Wapello,Warren,Washington,Wayne,Webster,Winnebago,Winneshiek,"
    "Woodbury,Worth,Wright"
).split(",")

YEARS = list(range(2016, 2026))

# The box of the contiguous United States: [west, south, east, north]
US_BOUNDS = [-125.0, 24.0, -66.5, 49.5]


# ============================================================================
# SYNTHETIC NUMBERS
# ============================================================================

def seeded(*key) -> random.Random:
    """A random generator that gives the same numbers for the same key on every start."""
    return random.Random("|".join(str(part) for part in key))


METRICS = {
    "unemployment_pct": ("Unemployment rate (%, synthetic)", 2.5, 7.5, 1),
    "median_income_kusd": ("Median household income (USD k, synthetic)", 48, 98, 0),
    "population_m": ("Population (millions, synthetic)", 0.6, 39, 1),
}


def state_metric(usps: str, metric: str = "unemployment_pct", year: int = 2025) -> float:
    """One made-up number for a state, a metric and a year, stable across restarts."""
    _label, low, high, digits = METRICS[metric]
    base = low + (high - low) * seeded(usps, metric).random() ** (3 if metric == "population_m" else 1)
    drift = (year - 2020) * (high - low) * 0.01 * (seeded(usps, metric, "trend").random() - 0.4)
    shock = (high - low) * 0.35 if metric == "unemployment_pct" and year == 2020 else 0
    return round(base + drift + shock, digits) if digits else round(base + drift + shock)


def stores():
    """One store for each city of US_CITIES, with a few numbers to show on a map."""
    rows = []
    for at, (city, state, lat, lon) in enumerate(US_CITIES):
        rng = seeded("store", city)
        rows.append({
            "store_id": f"S{at + 1:03d}",
            "city": city,
            "state": state,
            "lat": lat,
            "lon": lon,
            "revenue_musd": round(4 + rng.random() ** 2 * 60, 1),
            "headcount": int(20 + rng.random() * 400),
            "opened": 2005 + int(rng.random() * 21),
            "format": rng.choice(["Flagship", "Standard", "Outlet"]),
        })
    return rows


def scattered_points(count: int = 2000):
    """`count` points around the cities of US_CITIES, thicker around the first ones."""
    rng = seeded("scatter", count)
    weights = [1 / (at + 3) for at in range(len(US_CITIES))]
    points = []
    for _ in range(count):
        _city, state, lat, lon = rng.choices(US_CITIES, weights)[0]
        points.append({
            "lat": round(lat + rng.gauss(0, 0.35), 4),
            "lon": round(lon + rng.gauss(0, 0.45), 4),
            "state": state,
            "orders": int(1 + rng.random() ** 3 * 40),
        })
    return points


def great_circle(start, end, steps: int = 24):
    """Positions [lon, lat] along the shortest path between two (lat, lon) places."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*start, *end))
    angle = 2 * math.asin(math.sqrt(
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    ))
    path = []
    for step in range(steps + 1):
        f = step / steps
        a = math.sin((1 - f) * angle) / math.sin(angle)
        b = math.sin(f * angle) / math.sin(angle)
        x = a * math.cos(lat1) * math.cos(lon1) + b * math.cos(lat2) * math.cos(lon2)
        y = a * math.cos(lat1) * math.sin(lon1) + b * math.cos(lat2) * math.sin(lon2)
        z = a * math.sin(lat1) + b * math.sin(lat2)
        path.append([
            round(math.degrees(math.atan2(y, x)), 4),
            round(math.degrees(math.atan2(z, math.hypot(x, y))), 4),
        ])
    return path


def city(name: str):
    """The (lat, lon) of a city of US_CITIES."""
    return next((lat, lon) for found, _state, lat, lon in US_CITIES if found == name)


def rectangle(west: float, south: float, east: float, north: float):
    """One closed ring [lon, lat] of a box. A ring ends where it starts."""
    return [[west, south], [east, south], [east, north], [west, north], [west, south]]


def delivery_zones():
    """24 made-up delivery zones around Dallas: two rings of 12 wedges, as closed rings."""
    lat0, lon0 = city("Dallas")

    def at(radius, angle):
        return [
            round(lon0 + radius * math.sin(angle) / math.cos(math.radians(lat0)), 4),
            round(lat0 + radius * math.cos(angle), 4),
        ]

    zones = []
    for ring, (inner, outer) in enumerate([(0.08, 0.3), (0.3, 0.62)]):
        for wedge in range(12):
            a0, a1 = math.radians(wedge * 30), math.radians(wedge * 30 + 30)
            arc = [a0 + (a1 - a0) * step / 4 for step in range(5)]
            outline = [at(outer, a) for a in arc] + [at(inner, a) for a in reversed(arc)]
            rng = seeded("zone", ring, wedge)
            zones.append({
                "zone": f"{'Inner' if ring == 0 else 'Outer'} {wedge + 1}",
                "ring": [*outline, outline[0]],
                "deliveries": int(200 + rng.random() * (1800 if ring == 0 else 900)),
                "avg_minutes": round(18 + ring * 14 + rng.random() * 12, 1),
            })
    return zones


def loop_buildings():
    """30 made-up building footprints on a grid in the Chicago Loop, with a height in metres."""
    buildings = []
    for row in range(5):
        for col in range(6):
            rng = seeded("building", row, col)
            west = -87.6360 + col * 0.0019
            south = 41.8770 + row * 0.0013
            floors = int(6 + rng.random() ** 2 * 70)
            buildings.append({
                "building_id": f"B{row * 6 + col + 1:02d}",
                "name": f"{rng.choice(['Wacker', 'LaSalle', 'Monroe', 'Adams', 'Clark'])} "
                        f"{rng.choice(['Tower', 'Exchange', 'Plaza', 'Center'])} {row * 6 + col + 1}",
                "ring": rectangle(
                    round(west, 5), round(south, 5),
                    round(west + 0.0011 + rng.random() * 0.0004, 5),
                    round(south + 0.0007 + rng.random() * 0.0003, 5),
                ),
                "floors": floors,
                "height_m": round(floors * 3.9, 1),
                "use": rng.choice(["Office", "Residential", "Hotel", "Mixed use"]),
                "year_built": 1925 + int(rng.random() * 98),
            })
    return buildings


# ============================================================================
# TINY BINARY WRITERS (standard library only)
# ============================================================================

def png(width: int, height: int, pixel, block: int = 1) -> bytes:
    """A PNG image (8-bit RGBA) whose pixels come from `pixel(x, y) -> (r, g, b, a)`.

    With `block` 2, one pixel in each 2 by 2 square is computed and repeated:
    four times fewer calls for a picture of a smooth field.
    """
    def chunk(kind: bytes, body: bytes) -> bytes:
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body)))

    rows = bytearray()
    for y in range(0, height, block):
        # Each row starts with its filter: 0, none.
        row = b"\x00" + b"".join(bytes(pixel(x, y)) * block for x in range(0, width, block))
        rows.extend(row * block)
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(rows), 6)) + chunk(b"IEND", b""))


def zipped(files: dict) -> bytes:
    """A zip archive of {name: bytes}, the same bytes on every start (fixed dates)."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in files.items():
            archive.writestr(zipfile.ZipInfo(name, date_time=(2025, 1, 1, 0, 0, 0)), body)
    return out.getvalue()


def shapefile(polygons, fields) -> dict:
    """
    An ESRI Shapefile of polygons as {".shp": bytes, ".shx": ..., ".dbf": ..., ".prj": ...}.

    `polygons` is a list of (ring, record): a closed ring of [lon, lat] and the
    values of the record. `fields` is a list of (name, "C" or "N", width, decimals).
    The outline of a shapefile polygon runs clockwise, so a ring that does not is reversed.
    """
    def clockwise(ring):
        area = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:]))
        return ring if area < 0 else ring[::-1]

    def box(points):
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        return min(xs), min(ys), max(xs), max(ys)

    def header(length_words: int) -> bytes:
        every = [point for ring, _record in polygons for point in ring]
        return (struct.pack(">i5ii", 9994, 0, 0, 0, 0, 0, length_words)
                + struct.pack("<ii4d4d", 1000, 5, *box(every), 0, 0, 0, 0))

    records, index, offset = b"", b"", 50
    for number, (ring, _record) in enumerate(polygons, start=1):
        ring = clockwise(ring)
        content = struct.pack("<i4dii", 5, *box(ring), 1, len(ring)) + struct.pack("<i", 0)
        content += b"".join(struct.pack("<2d", x, y) for x, y in ring)
        records += struct.pack(">ii", number, len(content) // 2) + content
        index += struct.pack(">ii", offset, len(content) // 2)
        offset += 4 + len(content) // 2

    record_length = 1 + sum(width for _name, _kind, width, _decimals in fields)
    dbf = struct.pack("<BBBBIHH20x", 3, 125, 1, 1, len(polygons),
                      32 + 32 * len(fields) + 1, record_length)
    for name, kind, width, decimals in fields:
        dbf += struct.pack("<11sc4xBB14x", name.encode("ascii"), kind.encode("ascii"),
                           width, decimals)
    dbf += b"\r"
    for _ring, record in polygons:
        dbf += b" "
        for (name, kind, width, decimals), value in zip(fields, record):
            cell = f"{value:.{decimals}f}".rjust(width) if kind == "N" else str(value).ljust(width)
            dbf += cell[:width].encode("ascii")
    dbf += b"\x1a"
    wgs84 = ('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,'
             '298.257223563]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]')
    return {
        ".shp": header(50 + len(records) // 2) + records,
        ".shx": header(50 + len(index) // 2) + index,
        ".dbf": dbf,
        ".prj": wgs84.encode("ascii"),
    }


# ============================================================================
# TILES
# ============================================================================

def tile_lon_lat(z: int, x: int, y: int, size: int = 256):
    """The longitude of each column and the latitude of each row of a Web Mercator tile."""
    n = 2 ** z
    lons = [(x + (col + 0.5) / size) / n * 360 - 180 for col in range(size)]
    lats = [
        math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + (row + 0.5) / size) / n))))
        for row in range(size)
    ]
    return lons, lats


def ramp(stops, t: float):
    """The colour at `t` (0 to 1) on a list of (r, g, b) stops."""
    t = min(1.0, max(0.0, t)) * (len(stops) - 1)
    low = min(int(t), len(stops) - 2)
    return tuple(round(a + (b - a) * (t - low)) for a, b in zip(stops[low], stops[low + 1]))


def temperature_at(lon: float, lat: float) -> float:
    """A smooth made-up temperature in Celsius: warm in the south, with a few waves."""
    return (34 - (lat - 24) * 1.15
            + 4 * math.sin(math.radians(lon * 6)) * math.cos(math.radians(lat * 9))
            + 3 * math.sin(math.radians(lon * 2.5 + lat * 4)))


def elevation_at(lon: float, lat: float) -> float:
    """A made-up elevation in metres: rolling hills in the east, long ridges in the west."""
    west = max(0.0, min(1.0, (-95 - lon) / 20))
    ridges = (math.sin(math.radians(lon * 110 + lat * 40)) * math.cos(math.radians(lat * 100)) + 1) / 2
    hills = (math.sin(math.radians(lon * 190)) * math.sin(math.radians(lat * 170)) + 1) / 2
    return 150 + west * 1200 + (0.1 + west) * ridges * 3600 + hills * 400
