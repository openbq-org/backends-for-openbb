# OpenBB Workspace Backend Template

A comprehensive FastAPI application template for OpenBB Workspace that demonstrates various widget types and features.

## Setup

1. Install the required dependencies:

```bash
pip install fastapi uvicorn requests plotly
```

2. Run the application:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 7779
```

The application will be available at `http://localhost:7779`

## Architecture

This FastAPI application is designed to work as a backend for OpenBB Workspace. Here's a breakdown of its architecture:

### Core Application Structure

- FastAPI backend service running on port 7779
- CORS enabled specifically for `https://pro.openbb.co`
- Widget registration using the `@register_widget` decorator pattern
- Modular organization of endpoints and widgets

### Widget Registration Pattern

The application uses a decorator-based approach to register widgets, which combines the UI/UX configuration with the API endpoint implementation. This is achieved through the `@register_widget` decorator that:

- Defines the widget's appearance and behavior in the OpenBB Workspace UI
- Automatically registers the widget configuration in the `WIDGETS` registry
- Links the UI configuration directly to its corresponding API endpoint
- Maintains a single source of truth for widget definitions

### Available Widget Types

1. **Markdown Widgets**
   - Basic markdown display
   - Support for images (URL and local)
   - Error handling
   - Run button functionality
   - Auto-refresh capabilities
   - Stale time indicators

2. **Table Widgets**
   - Basic table display
   - Column definitions and formatting
   - Render functions (color coding, hover cards)
   - Chart integration
   - Time series visualization
   - API endpoint integration

3. **Chart Widgets**
   - Plotly integration
   - Theme support
   - Toolbar configuration
   - Heatmap visualization
   - TradingView integration

4. **Form Widgets**
   - Text input
   - Number input
   - Date picker
   - Boolean toggle
   - Dropdown selection
   - Multi-select options
   - Dependent dropdowns

5. **PDF Widgets**
   - Base64 encoded PDF display
   - URL-based PDF display
   - Multi-PDF viewer

6. **Map Widgets**
   - Points, shaded regions, lines, flows, areas and 3D footprints
   - Heat, clusters, columns, layers and a time slider
   - GeoJSON, KML, KMZ, GPX and shapefile answers
   - Map sources (tiles, GeoJSON, images) served by the backend
   - See [Maps](#maps)

### Widget Features

1. **Auto-refresh**
   - `refetchInterval`: Time between automatic refreshes
   - `staleTime`: Time after which data is considered stale
   - `runButton`: Manual refresh option

2. **Parameter Management**
   - Shared parameters between widgets
   - Dependent parameters
   - Parameter grouping
   - Default values
   - Validation

   > To see a widget **push** a parameter update back to Workspace (so one widget
   > can drive the rest of a synced group), see the
   > [iframe & HtmlViewer parameter bridge example](../../widget-examples/iframe-bridge-example/README.md).

3. **Data Visualization**
   - Table formatting
   - Chart integration
   - Color coding
   - Hover information
   - Interactive elements

4. **Error Handling**
   - HTTP exception handling
   - Error messages
   - Status codes
   - User feedback

### API Endpoints

1. Core Endpoints:
   - `GET /`: Basic API information
   - `GET /widgets.json`: Widget configuration
   - `GET /templates.json`: Template configuration

2. Widget Endpoints:
   - Various widget-specific endpoints for different functionalities
   - Form submission endpoints
   - Data fetching endpoints
   - Configuration endpoints

### Security & Configuration

- CORS properly configured for OpenBB Workspace domain
- FastAPI metadata includes title, description, and version
- All endpoints documented with docstrings
- Input validation and error handling

## Maps

The "Maps" tab of the app shows each kind of map a backend can feed once: twelve widgets, most with one parameter that switches between the variants of that kind. All of it is synthetic and generated in code: no network, no data files, no extra dependency.

> The Map widget (`"type": "map"`) requires a Workspace build that includes the Map widget. On a build without it these widgets are not recognised.

### The minimal map widget

```json
{
  "stores_map": {
    "name": "Stores",
    "description": "Our stores on a map",
    "type": "map",
    "endpoint": "stores",
    "data": { "map": { "lat": "lat", "lon": "lon" } }
  }
}
```

The endpoint returns rows, like a table endpoint: `[{"lat": 41.88, "lon": -87.63}, ...]`. `data.map` names the columns:

| Key | Meaning |
| --- | --- |
| `lat` + `lon` | The place of a row as a point: two number columns |
| `city` (with `country`, `state`) | The place of a row as a point at a city, matched by name in the app. With `lat` and `lon` named too, it places the rows that have no coordinates |
| `zip` | The place of a row as a point at a US ZIP code, as text |
| `state`, `county`, `country`, `province`, `metro`, `district` | The place of a row as a shaded region: exactly one of them |
| `within` | With `province`: the country of every row, as text (`"Canada"`). Not a column |
| `as` | `"points"` with `state` or `country`: a point at the centre of the region instead of a shaded region |
| `value`, `valueLabel` | The number the colour scale reads, and what the legend calls it |
| `size` | The number the size of a point reads |
| `label`, `props` | The name in the hover card, and up to 12 other columns shown there |
| `tag`, `marker` | A short text beside the mark (40 characters), and a sign: `pin`, `check`, `star`, `flag`, `ring` |
| `category` | A text column: one colour and one legend entry for each of its values (12 at most) |
| `color` | A column of `#rgb` or `#rrggbb` colours |
| `time` | The column of the steps of a map that plays (a year, `2024-03`) |
| `height` | For GeoJSON and files: the property that says how high an area stands, in metres |
| `title` | A title over the map |
| `sources` | Map sources this backend serves (see below) |

When rows and columns are not enough, the endpoint returns something else and `data.map` can stay empty:

| The endpoint returns | Used for |
| --- | --- |
| Rows | Points and shaded regions |
| A GeoJSON `FeatureCollection` | Points, lines and areas the backend already has as shapes |
| `{"kml": text}`, `{"gpx": text}`, `{"kmz": base64}`, `{"shapefile": base64 of the zip}` | A file, at most 4 MB. Its folders become layers |
| A map: `{"points": [...], "regions": {...}, "shapes": [...], "layers": [...]}` | Everything else: lines, flows, heat, clusters, columns, several layers, ranks, categories, a view |

`data.map` is fixed in `widgets.json`. A widget whose parameter changes what the map shows (another kind of region, another layer) therefore returns a map, which carries its own `title` and `valueLabel`. Answer a value a parameter cannot have with a 400.

### The widgets

| Widget id | Parameter | Returns | What it teaches |
| --- | --- | --- | --- |
| `maps_points` | `place_by`: `coordinates`, `city` | Rows | Points coloured by a value and sized by another, with a hover card: placed by `lat` and `lon`, or by a city name when a row has no coordinates |
| `maps_regions` | `level`: `states`, `counties`, `countries`, `provinces` | A map | Shaded regions and the code each level is matched by; a scale that crosses zero |
| `maps_flows` | `show`: `lines`, `flows`, `arrows` | A map | Lines as paths of positions, arcs from an origin to a destination, and arrows as short lines the backend computes |
| `maps_footprints` | `extrude`: `off`, `on` | GeoJSON | Polygons coloured by a property, flat or standing as tall as a height in metres |
| `maps_density` | `mode`: `heat`, `clusters`, `columns` | A map | 2,000 points as a density, as clusters with a count, or summed by state as 3D bars |
| `maps_layers` | `open_on`: `data`, `place`, `center`, `bounds`, `tilted` | A map | Four named layers, one of them off until it is turned on, and where the map opens (`view`, `pitch`) |
| `maps_time` | | Rows | A region column and a `time` column: the map gets a slider and a play button |
| `maps_marks` | `style`: `signs`, `ranks`, `categories` | Rows, or a map | A sign and a tag from two columns; ranks, highlights and their line in the legend; a colour for each category |
| `maps_file` | `format`: `geojson`, `kml`, `kmz`, `shapefile`, `gpx` | A file | The five file answers. The same files are served raw under `/maps/files/` |
| `maps_sources` | `turn_on`: `none`, or the id of a source | Rows, or a map | Five map sources declared in `data.map.sources`, turned on by the reader or by the endpoint |
| `maps_group_table` + `maps_group_map` | `state` (shared) | Rows | A table and a map in one parameter group: a click in the table moves the map |

The code is in `widgets_maps.py` (rows), `widgets_maps_layers.py` (maps with layers), `widgets_maps_files.py` (files and sources) and `widgets_maps_data.py` (the synthetic data and the PNG, zip and shapefile writers). The docstring of each endpoint shows the shape of the answer for each value of its parameter.

### Row shapes for each kind of layer

A position is always `[longitude, latitude]`. Every mark also takes `label`, `value`, `tag`, `props`, `color`, `category`, `marker`, `highlight` and `time`.

| `kind` | The layer holds |
| --- | --- |
| `points`, `heat`, `clusters` | `"points": [{"lat": 41.88, "lon": -87.63, "value": 12, "size": 3}]` |
| `regions` | `"regions": {"set": "us-states", "items": [{"code": "IA", "value": 3.1}]}` |
| `lines` | `"shapes": [{"type": "line", "coordinates": [[lon, lat], [lon, lat]]}]` |
| `polygons` | `"shapes": [{"type": "polygon", "coordinates": [[[lon, lat], ...]], "height": 40}]` |
| `flows` | `"flows": [{"from": {"state": "IA"}, "to": [-90.07, 29.95], "value": 700}]` |
| `columns` | `"points": [...]` or `"regions": {...}`, never both |
| `source` | `"source": "demo-temperature"`: the id of a declared source |
| `image` | `"image": {"mime": "image/png", "data": "<base64>", "corners": [[lon, lat] x 4]}` |

A layer also takes `id`, `name`, `valueLabel`, `opacity` (0 to 1) and `visible: false`. The first layer of the list is drawn at the bottom. The sets of `regions` are `us-states`, `us-counties`, `countries`, `admin1` (states and provinces, with `"within": {"country": "Canada"}` for short codes or names), `us-cbsa` (metro areas) and `us-cd119` (congressional districts).

Beside its marks and layers a map takes `title`, `valueLabel`, `categoryLabel`, `view` (one of `{"place": "Texas"}`, `{"center": [lon, lat], "zoom": 6}`, `{"bounds": [west, south, east, north]}`, with an optional `bearing`), `pitch` (0 to 60) and `basemap` (`{"source": "<id>"}`: a declared source with `role: "imagery"` as the backdrop).

Kinds without a widget of their own:

- **`columns` at points**: a `columns` layer with `"points"` in place of `"regions"` stands a bar at each place. `maps_density` shows the bars on regions.
- **`image`**: a picture sent as bytes in the answer (PNG, JPEG or WebP as base64, at most 1.4 MB, 4 in a map), with `corners` as `[lon, lat]` in the order top left, top right, bottom right, bottom left. A map never takes the address of an image. The picture is stretched evenly in Web Mercator between its corners. `maps_file` with `format=kmz` shows a picture inside a file, and `maps_sources` one served by the backend.
- **`polygons` outside GeoJSON**: `"shapes"` of the type `polygon`, with an optional `height` in metres. `maps_footprints` shows the same areas as GeoJSON.
- **`zip`, `metro`, `district`, `as`, `color` and `category` as columns of rows**: read as the table above says. `maps_marks` shows categories on a map the endpoint returns.
- **`value`, `category`, `height` and `time` for a file**: in `data.map`, each names a property of a GeoJSON feature, an `ExtendedData` value of a KML placemark or a column of the `.dbf` table of a shapefile. `maps_file` names none: GeoJSON reads the property `value` by itself, and a KML keeps the colours of its own styles.

### Region codes that match reliably

| Column | Set | Send | Also read |
| --- | --- | --- | --- |
| `state` | `us-states` | USPS code: `CA` | FIPS as text (`06`), the name (`California`) |
| `county` | `us-counties` | Five-digit FIPS as text: `06037` | A name with its state: `Cook County, IL` |
| `country` | `countries` | ISO 3166-1 alpha-3: `USA` | Alpha-2 (`US`), numeric (`840`), the name |
| `province` | `admin1` | ISO 3166-2: `CA-ON` | A short code or a name, with `within` naming the country |
| `metro` | `us-cbsa` | CBSA code: `35620` | The name of the area |
| `district` | `us-cd119` | State and number: `CA-12` | `AK-AL` for a state with one district |

The column is what rows name in `data.map`; the set is what a map the endpoint returns names in `regions.set`. Send codes as text so a leading zero survives. One row for each region: a second row of the same region is not drawn, unless the rows carry `time`. A code that matches nothing is left out and the map says how many; a name that two regions answer to (`Georgia`, `Washington County`) is never guessed.

### Map sources: same origin only

A source is tiles, GeoJSON or a picture that the map draws as a layer under the data:

```json
{
  "id": "demo-temperature",
  "name": "Temperature (synthetic)",
  "kind": "raster-tiles",
  "endpoint": "maps/tiles/temperature/{z}/{x}/{y}.png",
  "attribution": "Synthetic temperature",
  "opacity": 0.7,
  "maxzoom": 8,
  "bounds": [-125.0, 24.0, -66.5, 49.5]
}
```

- **The address must be on the origin of the backend that declares it.** `endpoint` is a path of this backend; `url` is an absolute address on the same origin. A source on any other host is refused. To show imagery of a third party, add a route that proxies it, and check that the terms of the provider allow that.
- `kind` is `raster-tiles`, `raster-dem` (needs `encoding`: `terrarium` or `mapbox`), `geojson` (needs `layers` that say how it is drawn), `image` (needs `coordinates`: four corners), `vector-tiles` or `pmtiles`. This backend serves the first four.
- `attribution` is required. `role: "imagery"` offers a raster source as a backdrop in place of the basemap.
- A declared source is a layer that is off until the reader turns it on in the Layers panel. To have it on when the map opens, the endpoint returns a layer `{"kind": "source", "source": "<id>"}`, or `"basemap": {"source": "<id>"}` for a backdrop. A map carries the id only, never an address.
- The tiles here are procedural gradients made with the standard library. They are not imagery.

### Limits

| Limit | Value |
| --- | --- |
| Points of one map | 20,000 |
| Regions of one map (regions x steps of time) | 4,000 |
| Lines and areas of one map | 3,500, with 100,000 positions together |
| Flows of one map | 2,000 |
| Layers of one map | 12 |
| Steps of time | 60 |
| Categories of one map | 12 |
| Images in one map | 4, each at most 1.4 MB as base64 |
| One map as JSON | 2 MB |
| A file answer (KML, GPX, KMZ, shapefile) | 4 MB as text or base64 |
| Sources of one widget | 16 |

A map over a limit is not drawn and says why, so aggregate in the backend: one row for each region, a year in place of a month, the largest flows.

## Best Practices

1. **Widget Organization**
   - Use categories and subcategories for better organization
   - Group related widgets together
   - Use consistent naming conventions

2. **Parameter Management**
   - Share parameters between related widgets
   - Use dependent parameters when appropriate
   - Provide clear descriptions and labels

3. **Error Handling**
   - Implement proper error handling
   - Provide meaningful error messages
   - Use appropriate HTTP status codes

4. **Performance**
   - Use appropriate refresh intervals
   - Implement stale time indicators
   - Optimize data fetching

5. **Security**
   - Validate all inputs
   - Handle errors gracefully
   - Use proper CORS configuration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request
