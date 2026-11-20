"""Curated Census inputs. Small DC extracts keep this example runnable locally."""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

VINTAGE = 2026
CENSUS = "https://www2.census.gov/geo/tiger"


@dataclass(frozen=True)
class Source:
    format: str
    url: str

    @property
    def filename(self) -> str:
        return Path(urlparse(self.url).path).name


SOURCES = {
    "tracts": Source("shapefile", f"{CENSUS}/TIGER2026/TRACT/tl_2026_11_tract.zip"),
    "roads": Source("shapefile", f"{CENSUS}/TIGER2026/ROADS/tl_2026_11001_roads.zip"),
    "water": Source(
        "shapefile", f"{CENSUS}/TIGER2026/AREAWATER/tl_2026_11001_areawater.zip"
    ),
    "addresses": Source(
        "shapefile", f"{CENSUS}/TIGER2026/ADDRFEAT/tl_2026_11001_addrfeat.zip"
    ),
    "ranges": Source("dbf", f"{CENSUS}/TIGER2026/ADDR/tl_2026_11001_addr.zip"),
    "boundaries": Source("geodatabase", f"{CENSUS}/TGRGDB26/tlgdb_2026_11_dc.gdb.zip"),
    "points": Source("shapefile", f"{CENSUS}/TIGER2026/POINTLM/tl_2026_11_pointlm.zip"),
    "landmarks": Source(
        "shapefile", f"{CENSUS}/TIGER2026/AREALM/tl_2026_11_arealm.zip"
    ),
    "rivers": Source(
        "shapefile", f"{CENSUS}/TIGER2026/LINEARWATER/tl_2026_11001_linearwater.zip"
    ),
    "rhode_island": Source(
        "shapefile", f"{CENSUS}/TIGER2026/TRACT/tl_2026_44_tract.zip"
    ),
    "hawaii": Source("shapefile", f"{CENSUS}/TIGER2026/TRACT/tl_2026_15_tract.zip"),
    "geopackage": Source(
        "geopackage", f"{CENSUS}/TGRGPKG26/tlgpkg_2026_11_dc.gpkg.zip"
    ),
}


@dataclass(frozen=True)
class Dataset:
    name: str
    source: str
    layer: str | None = None
    spatial: bool = True
    geography: str = "District of Columbia"
    metric_crs: str = "EPSG:26918"


DATASETS = {
    "shp_points": Dataset("DC point landmarks", "points"),
    "shp_landmarks": Dataset("DC area landmarks", "landmarks"),
    "shp_rivers": Dataset("DC rivers and streams", "rivers"),
    "shp_ri": Dataset(
        "Rhode Island census tracts",
        "rhode_island",
        geography="Rhode Island",
        metric_crs="EPSG:26919",
    ),
    "shp_hi": Dataset(
        "Hawaii census tracts", "hawaii", geography="Hawaii", metric_crs="EPSG:26904"
    ),
    "gpkg_tracts": Dataset("DC GeoPackage census tracts", "geopackage", "Census Tract"),
    "shp_tracts": Dataset("DC census tracts", "tracts"),
    "shp_roads": Dataset("DC roads", "roads"),
    "shp_water": Dataset("DC water areas", "water"),
    "shp_addresses": Dataset("DC address-range features", "addresses"),
    "shp_ranges": Dataset("DC address-range relationships", "ranges", spatial=False),
    "gdb_tracts": Dataset("DC census tracts", "boundaries", "Census_Tract"),
    "gdb_places": Dataset("DC places", "boundaries", "Place"),
    "gdb_state": Dataset("District of Columbia", "boundaries", "State"),
    "gdb_counties": Dataset("DC counties", "boundaries", "County"),
    "gdb_subdivisions": Dataset(
        "DC county subdivisions", "boundaries", "County_Subdivision"
    ),
    "gdb_groups": Dataset("DC block groups", "boundaries", "Block_Group"),
    "gdb_blocks": Dataset("DC 2020 census blocks", "boundaries", "Block20"),
    "gdb_suffixed": Dataset(
        "DC current suffixed blocks", "boundaries", "Suffixed_Blocks"
    ),
}
