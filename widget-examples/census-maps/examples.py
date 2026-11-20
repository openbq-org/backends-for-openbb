"""The gallery: each entry owns a map and the explanation beside it."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Example:
    title: str
    tab: str
    datasets: tuple[str, ...]
    mode: str
    story: str
    reading: str
    capability: str


EXAMPLES = {
    "dc_tracts": Example(
        "A city in census tracts",
        "boundaries",
        ("shp_tracts",),
        "land",
        "Explore Washington, DC as a collection of small statistical areas. Each polygon is a census tract, not a ZIP code or a neighborhood boundary.",
        "Colour represents land area in square kilometres. Large tracts are geographically larger; they do not necessarily contain more residents.",
        "GeoJSON polygons, a continuous colour scale, hover cards, and geographic navigation.",
    ),
    "rhode_island": Example(
        "A coastline, islands and inland water",
        "boundaries",
        ("shp_ri",),
        "water_share",
        "Rhode Island's coastal tracts show why detailed GIS boundaries contain holes and disconnected polygon parts.",
        "Colour represents the share of a tract's total area recorded as water: AWATER / (ALAND + AWATER). This is an area measure, not a population measure.",
        "Multipart polygons and holes, calculated numeric properties, and a geographic colour scale.",
    ),
    "hawaii": Example(
        "An archipelago by county",
        "boundaries",
        ("shp_hi",),
        "counties",
        "Hawaii's tracts span multiple islands. County codes supply a categorical comparison across a geographically dispersed state.",
        "Each county has a different colour. Separate islands can belong to the same county; colour is a category, not an intensity.",
        "Categorical legends and multipart geography, with an appropriate local metric projection for display simplification.",
    ),
    "roads": Example(
        "Every DC road in one map source",
        "features",
        ("shp_roads",),
        "source",
        "Inspect the complete county-based road layer rather than the first few hundred records of a preview.",
        "All road features are served as a connected GeoJSON source. FULLNAME is a road name and MTFCC is a Census feature classification. These lines do not represent traffic or a routing graph.",
        "A backend-declared, same-origin GeoJSON source with line styling and feature inspection.",
    ),
    "water": Example(
        "Water as areas",
        "features",
        ("shp_water",),
        "water",
        "The Potomac, Anacostia and smaller water bodies appear as areas with actual boundaries, rather than as lines or points.",
        "Blue polygons represent the areal hydrography layer. Overlapping land-use and water features in other layers are possible.",
        "Polygon geometry, named feature cards, holes and transparent area fills.",
    ),
    "rivers": Example(
        "Water as a network of lines",
        "features",
        ("shp_rivers",),
        "river",
        "Compare linear hydrography with water-area polygons: streams and other linear water features carry a different geometry contract.",
        "The lines follow Census water-feature geometry. They do not encode flow direction, discharge, water quality or flood risk.",
        "LineString and MultiLineString features supplied as GeoJSON.",
    ),
    "landmarks": Example(
        "Point landmarks",
        "features",
        ("shp_points",),
        "landmarks",
        "Census point landmarks locate named facilities and other selected features using an actual point shapefile.",
        "Hover to read FULLNAME and MTFCC. This is a selective Census inventory, not a complete directory of businesses or all places of interest.",
        "Point geometry, hover cards and close-point grouping.",
    ),
    "land_use": Example(
        "Parks, facilities and area landmarks",
        "features",
        ("shp_landmarks",),
        "land_use",
        "Area landmarks describe parks, facilities and selected land-use features. Unlike a tract partition, these areas may overlap each other.",
        "Polygons are coloured by MTFCC family, grouping codes by their first three characters. The full class code remains in the hover card. These codes identify feature types; they are not measured values.",
        "Categorical polygon styling and inspection of overlapping geographic features.",
    ),
    "address_ranges": Example(
        "Address ranges along street edges",
        "features",
        ("shp_addresses",),
        "addresses",
        "Address-range features attach possible house-number ranges to the left and right sides of street edges.",
        "The map is a bounded preview. LFROMHN/LTOHN and RFROMHN/RTOHN describe potential ranges, not individual buildings or confirmed deliverable addresses. ZIPL and ZIPR refer to the two edge sides.",
        "Line features with structured properties, plus original DBF attributes available independently of map-card limits.",
    ),
    "population": Example(
        "2020 population by tract",
        "people",
        ("gdb_blocks",),
        "population",
        "Build a population map from the actual POP20 counts in the FileGDB's Block20 layer, aggregating all source blocks into their 2020 tracts.",
        "Colour represents the sum of 2020 Census population. Tract boundaries are dissolved from those same 2020 blocks, so counts and geography share a vintage. These are 2020 counts, not a 2026 population estimate.",
        "A choropleth from native FileGDB attributes and backend spatial aggregation.",
    ),
    "density": Example(
        "Population density on land",
        "people",
        ("gdb_blocks",),
        "density",
        "The same 2020 block data can answer a different question after normalizing population by land area.",
        "Colour is people per square kilometre of land: sum(POP20) / (sum(ALAND20) / 1,000,000). Water is excluded from the denominator. This is an average across each tract, not a street-level population surface.",
        "A derived numeric measure with an explicit unit and a continuous colour legend.",
    ),
    "housing": Example(
        "Housing units by tract",
        "people",
        ("gdb_blocks",),
        "housing",
        "HOUSING20 provides a second real Census measure from the same block geometries.",
        "Colour represents the sum of housing units in each 2020 tract. A housing-unit count is not an occupied-household count, a vacancy rate or a property listing inventory.",
        "A second analytical view over the same original spatial dataset.",
    ),
    "columns": Example(
        "Population in 3D columns",
        "people",
        ("gdb_blocks",),
        "columns",
        "Compare tract population through a tilted map with one vertical column at a computed interior point of each tract.",
        "Column height is proportional to 2020 population and is scaled for display. It is not building height or elevation. The column position is a representative point of the dissolved tract, not a residential address.",
        "A 3D columns layer, automatic tilt, quantitative colour and interactive feature cards.",
    ),
    "heat": Example(
        "A population-weighted heatmap",
        "people",
        ("gdb_blocks",),
        "heat",
        "Represent populated 2020 blocks by their Census internal-point coordinates, weighted by POP20.",
        "The heat surface emphasizes relative concentrations and changes with zoom. It is not an exact density estimate or a map of individual people. Each weight belongs to an entire block.",
        "A weighted heat layer over thousands of points from real geographic attributes.",
    ),
    "clusters": Example(
        "Populated blocks grouped on the map",
        "people",
        ("gdb_blocks",),
        "clusters",
        "Use the same internal points to explore how grouping changes as the map is zoomed.",
        "Cluster counts count represented populated blocks, not residents. Individual point values carry population, but a cluster's count must not be interpreted as a population total.",
        "Client-side point clustering, interactive zoom and point-level cards.",
    ),
    "native_shapefile": Example(
        "The original zipped Shapefile",
        "formats",
        ("shp_tracts",),
        "shapefile",
        "Send the original small DC tract ZIP to Workspace's native shapefile reader, with its geometry, DBF attributes, projection and encoding files together.",
        "The original ZIP is read in the browser rather than converted to GeoJSON by this backend. The map reader reports any assumptions or display reductions; original attributes remain available through the data explorer.",
        "The native shapefile file-envelope response, including .shp, .dbf, .prj and .cpg sidecars.",
    ),
    "filegdb": Example(
        "One layer from a File Geodatabase",
        "formats",
        ("gdb_groups",),
        "groups",
        "A single zipped .gdb directory contains multiple related geographic layers. This view selects Block_Group explicitly.",
        "Block groups are subdivisions of census tracts. The backend reads the named native layer and converts its display geometry to GeoJSON; Workspace is not parsing the proprietary container in the browser.",
        "Multilayer FileGDB ingestion through GDAL/OpenFileGDB with an explicit layer selection.",
    ),
    "geopackage": Example(
        "The same geography in GeoPackage",
        "formats",
        ("gpkg_tracts",),
        "geopackage",
        "Census also distributes the DC geography in an OGC GeoPackage, an open SQLite-based spatial container.",
        "This view selects the Census Tract layer. Display geometry uses only X/Y; any Z/M dimensions in the original container are not shown. The original archive is retained unchanged.",
        "GeoPackage ingestion alongside Shapefile and FileGDB, normalized to the same GeoJSON display contract.",
    ),
    "layered": Example(
        "A Census map made of several layers",
        "formats",
        ("shp_tracts", "shp_water", "shp_roads", "shp_points"),
        "layers",
        "Combine tract context, water areas, the complete road source and point landmarks into one map.",
        "Open Layers to switch each dataset independently. Each component keeps its own geometry and source meaning. A landmark over a tract does not imply a statistical relationship between them.",
        "Multiple ordered layers, independent visibility and opacity, and a same-origin source alongside local marks.",
    ),
}

TABS = {
    "boundaries": "Boundaries & coastlines",
    "features": "Roads, water & landmarks",
    "people": "People & housing",
    "formats": "Files & layered maps",
}
