"""Exercise real GDAL format reads through the backend's HTTP interface."""

import zipfile

import pyarrow as pa
import pyogrio
import pytest
from fastapi.testclient import TestClient
from shapely import Polygon, get_coordinates, to_wkb
from shapely.geometry import shape

import census
from catalog import SOURCES
from main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(census, "DATA_DIR", tmp_path)
    geometry = [
        Polygon([(-77.04, 38.90), (-77.03, 38.90), (-77.03, 38.91), (-77.04, 38.90)]),
        Polygon([(-77.02, 38.90), (-77.01, 38.90), (-77.01, 38.91), (-77.02, 38.90)]),
    ]
    table = pa.table(
        {
            "GEOID": ["11001000101", "11001000102"],
            "NAME": ["1.01", "1.02"],
            "ZIPL": ["00123", "00124"],
            "ZIPR": ["00456", "00457"],
            **{
                f"EXTRA_{i:02}": pa.array([i, i + 1], type=pa.int32())
                for i in range(14)
            },
            "geometry": [to_wkb(g) for g in geometry],
        }
    )
    for source_id, driver, layer in [
        ("tracts", "ESRI Shapefile", "tracts"),
        ("boundaries", "OpenFileGDB", "Census_Tract"),
    ]:
        folder = tmp_path / source_id
        folder.mkdir()
        target = folder / ("sample.gdb" if driver == "OpenFileGDB" else "tracts.shp")
        pyogrio.write_arrow(
            table,
            target,
            driver=driver,
            layer=layer,
            geometry_name="geometry",
            geometry_type="Polygon",
            crs="EPSG:4269",
        )
        archive = tmp_path / SOURCES[source_id].filename
        with zipfile.ZipFile(archive, "w") as out:
            for entry in folder.rglob("*"):
                if entry.is_file():
                    out.write(entry, entry.relative_to(folder))
    with TestClient(app) as connected:
        yield connected


@pytest.mark.parametrize("dataset", ["shp_tracts", "gdb_tracts"])
def test_preview_reads_both_formats_with_longitude_first(client, dataset):
    response = client.get(
        "/map", params={"dataset": dataset, "limit": 1, "simplify_m": 0}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["preview"]["total_features"] == 2
    assert data["preview"]["returned_features"] == 1
    assert data["features"][0]["properties"]["GEOID"] == "11001000101"
    assert get_coordinates(shape(data["features"][0]["geometry"]))[
        0
    ].tolist() == pytest.approx([-77.04, 38.90])
    assert any("1 of 2" in note for note in data["map"]["notes"])


@pytest.mark.parametrize("dataset", ["shp_tracts", "gdb_tracts"])
def test_attribute_pages_preserve_all_fields_and_identifiers(client, dataset):
    response = client.get(
        "/attributes", params={"dataset": dataset, "page": 2, "page_size": 1}
    )
    assert response.status_code == 200, response.text
    assert response.json() == [
        {
            "GEOID": "11001000102",
            "NAME": "1.02",
            "ZIPL": "00124",
            "ZIPR": "00457",
            **{f"EXTRA_{i:02}": i + 1 for i in range(14)},
        }
    ]
    assert (
        client.get(
            "/attributes", params={"dataset": dataset, "page": 3, "page_size": 1}
        ).json()
        == []
    )


def test_missing_download_is_actionable_and_does_not_fetch(client):
    response = client.get("/map", params={"dataset": "shp_roads"})
    assert response.status_code == 503
    assert "python prepare.py" in response.json()["detail"]


def test_original_archive_download_is_unchanged(client):
    response = client.get("/download", params={"dataset": "gdb_tracts"})
    assert response.status_code == 200
    assert (
        response.content
        == (census.DATA_DIR / SOURCES["boundaries"].filename).read_bytes()
    )


def test_invalid_selection_and_limits_are_rejected(client):
    assert client.get("/map", params={"dataset": "../private"}).status_code == 404
    assert client.get("/map", params={"limit": 501}).status_code == 422
    assert client.get("/attributes", params={"page": 0}).status_code == 422


def test_dbf_relationships_are_tables_not_maps(client, tmp_path):
    table = pa.table(
        {"TLID": pa.array([42], type=pa.int32()), "ZIP": ["00123"], "FROMHN": ["001A"]}
    )
    path = tmp_path / "ranges.dbf"
    pyogrio.write_arrow(table, path, driver="ESRI Shapefile")
    with zipfile.ZipFile(tmp_path / SOURCES["ranges"].filename, "w") as archive:
        archive.write(path, SOURCES["ranges"].filename.removesuffix(".zip") + ".dbf")
        archive.writestr(
            SOURCES["ranges"].filename.removesuffix(".zip") + ".cpg", "UTF-8"
        )
    assert client.get("/address_ranges").json() == [
        {"TLID": 42, "ZIP": "00123", "FROMHN": "001A"}
    ]
    response = client.get("/map", params={"dataset": "shp_ranges"})
    assert response.status_code == 400
    assert "no geometry" in response.json()["detail"]


def test_metadata_exposes_real_geodatabase_layers_and_schema(client):
    response = client.get("/metadata", params={"dataset": "gdb_tracts"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["crs"] == "EPSG:4269"
    assert data["layer"] == "Census_Tract"
    assert data["total_features"] == 2
    assert data["layers"] == [{"name": "Census_Tract", "geometry_type": "MultiPolygon"}]
    assert (
        next(field for field in data["fields"] if field["name"] == "ZIPR")["type"]
        == "object"
    )


def test_projected_source_coordinates_become_wgs84(client, tmp_path):
    from pyproj import Transformer
    from shapely import Point

    x, y = Transformer.from_crs("EPSG:4326", "EPSG:26918", always_xy=True).transform(
        -77.03, 38.90
    )
    table = pa.table({"GEOID": ["11001000101"], "geometry": [to_wkb(Point(x, y))]})
    folder = tmp_path / "projected"
    folder.mkdir()
    pyogrio.write_arrow(
        table,
        folder / "projected.shp",
        driver="ESRI Shapefile",
        geometry_name="geometry",
        geometry_type="Point",
        crs="EPSG:26918",
    )
    with zipfile.ZipFile(tmp_path / SOURCES["tracts"].filename, "w") as archive:
        for path in folder.iterdir():
            archive.write(path, path.name)
    response = client.get("/map", params={"dataset": "shp_tracts", "simplify_m": 0})
    assert response.status_code == 200, response.text
    assert response.json()["features"][0]["geometry"]["coordinates"] == pytest.approx(
        [-77.03, 38.90]
    )
