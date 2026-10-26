# Geospatial SQL Dashboard

A browser-based geospatial SQL dashboard using **DuckDB-WASM** to query
[Overture Maps](https://overturemaps.org/) data for **Greater London** — no backend required.

## Live Demo

**GitHub Pages:** [https://chubbd.github.io/geospatial-treasurehunt/](https://chubbd.github.io/geospatial-treasurehunt/)

> ⚠️ **Must be served over HTTP(S).** The app uses `SharedArrayBuffer` (required by
> DuckDB-WASM) which is blocked by browsers when opened via `file://`. Use GitHub Pages,
> a local HTTP server, or any static hosting service.

---

## Features

| Feature | Details |
|---|---|
| **Map** | MapLibre GL (dark basemap, click-to-inspect popups) |
| **SQL editor** | Multi-line textarea with Ctrl/Cmd+Enter shortcut to run |
| **London tables** | `london.places` · `london.buildings` |
| **Full polygon geometry** | Buildings materialised with complete polygon footprints for `ST_*` ops |
| **Spatial SQL** | `ST_Distance`, `ST_Intersects`, `ST_Contains`, `ST_GeomFromText` and more |
| **Schema inspection** | `DESCRIBE` and row-count queries for every London table |
| **Sidebar guide** | Hideable in-app tutorial with copyable geospatial SQL examples |

---

## Quick Start (GitHub Pages)

1. Fork or clone this repository.
2. Go to **Settings → Pages** and set the source branch to `main` (root `/`).
3. GitHub will build and publish the site — usually within 60 seconds.
4. Open the published URL, click **⚡ Init DuckDB**, wait ~10–30 s for London data to materialise, then start exploring!

---

## Running Locally

Any static file server works.  Examples:

```bash
# Python 3
python -m http.server 8080

# Node.js  (npx)
npx serve .

# VS Code Live Server extension
# — right-click index.html → "Open with Live Server"
```

Then open `http://localhost:8080` in your browser.

> **Do not** open `index.html` directly with `File → Open` in your browser.
> The app will fail with a cross-origin isolation error.

---

## How It Works

On `⚡ Init DuckDB`, the app:

1. Instantiates **DuckDB-WASM** in the browser (EH/SIMD bundle via jsDelivr).
2. Loads the **`httpfs`** and **`spatial`** extensions (both compiled into the bundle).
3. Reads release-specific **London manifests**, downloads their original Overture
   Parquet files in full from S3 over HTTPS, registers them in DuckDB, and applies
   a **Greater London bounding box filter** during ingestion.
4. **Materialises** two in-memory DuckDB tables — `london.places`
   and `london.buildings` — for the rest of the session.

Students then query these tables directly with full spatial SQL — no repeated remote
fetches, no DuckLake catalog, no version-coupling.

### Why London-only materialisation?

| Problem with the old approach | Solution |
|---|---|
| DuckLake spec / storage version mismatch | No DuckLake in the browser at all |
| GeoParquet schema enforcement conflicts | Direct `read_parquet()` with typed projections |
| Full-UK scans for every query | One materialisation per session, London bbox only |
| ST_* unreliable | `LOAD spatial` once at init; geometry stored as `GEOMETRY` type |

### Memory budget

Greater London (bbox: W -0.510, S 51.286, E 0.334, N 51.692) contains the following
measured row counts at release `2026-09-23.0`:

| Table | Rows |
|---|---|
| `london.places` | 490,536 |
| `london.buildings` | 1,978,306 |

Browser memory usage has not been measured for this release. Full-file download
buffers add to table memory, so native DuckDB success does not guarantee that
initialization fits within the browser's memory ceiling.

---

## London Tables

### `london.buildings`
| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR | Overture feature ID |
| `name` | VARCHAR | Building name if present |
| `height` | DOUBLE | Height in metres |
| `num_floors` | INTEGER | Floor count if present |
| `building_area_m2` | BIGINT | Bbox-based footprint approximation in m² |
| `lat` / `lon` | DOUBLE | Centroid (bbox midpoint) |
| `bbox` | STRUCT | Bounding box corners: xmin, ymin, xmax, ymax |
| `geometry` | GEOMETRY | Full polygon/multipolygon for `ST_*` ops |

### `london.places`
| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR | Overture feature ID |
| `name` | VARCHAR | Place name |
| `category` | VARCHAR | Primary category (e.g. `museum`, `restaurant`) |
| `addresses` | LIST<STRUCT> | Nested address entries, e.g. `STRUCT(freeform VARCHAR, locality VARCHAR, postcode VARCHAR, region VARCHAR, country VARCHAR)` |
| `lat` / `lon` | DOUBLE | Point coordinates |
| `geometry` | GEOMETRY | Point geometry for `ST_*` ops |

---

## Example Queries

```sql
-- Tallest buildings in London
SELECT name, height, num_floors, building_area_m2, lat, lon
FROM london.buildings
WHERE height IS NOT NULL
ORDER BY height DESC
LIMIT 20;

-- Museums near Big Ben (51.5074, -0.1278)
SELECT name, category,
  ROUND(ST_Distance(ST_Point(lon, lat), ST_Point(-0.1278, 51.5074)) * 111320, 0)
    AS approx_dist_m
FROM london.places
WHERE category ILIKE '%museum%'
ORDER BY approx_dist_m
LIMIT 10;

-- Buildings whose footprint intersects a search area
SELECT name, height, building_area_m2
FROM london.buildings
WHERE ST_Intersects(
  geometry,
  ST_GeomFromText('POLYGON((-0.082 51.513, -0.078 51.513, -0.078 51.516, -0.082 51.516, -0.082 51.513))')
)
ORDER BY height DESC NULLS LAST;

-- EC1 postcode place addresses
SELECT
  addr.freeform,
  addr.locality,
  addr.postcode,
  addr.region,
  addr.country,
  p.lat,
  p.lon
FROM london.places p
CROSS JOIN UNNEST(p.addresses) AS t(addr)
WHERE addr.postcode ILIKE 'EC1%'
ORDER BY addr.postcode, addr.freeform
LIMIT 40;
```

---

## Architecture

```
index.html               ← entire app (single static file)
  ├─ MapLibre GL         ← map rendering (CDN)
  └─ DuckDB-WASM         ← in-browser SQL engine (CDN / jsDelivr)
       ├─ registered files ← full HTTPS downloads selected by manifests
       └─ spatial        ← ST_* functions, GEOMETRY type

.github/workflows/
  build_parquet_paths.yml      ← generates London manifests and verifies SQL
  build-overture-ducklake.yml  ← legacy DuckLake catalog builder
  deploy.yml                   ← deploys index.html to GitHub Pages
  duckdbwasmdownload.yml       ← vendors DuckDB-WASM bundle files
```

No build step. No server. No API keys needed.

---

## Overture Data Source

The dashboard selects Overture release `2026-09-23.0`. Its source file inventory is
stored in:

```
manifests/london_places_2026-09-23.0.txt
manifests/london_buildings_2026-09-23.0.txt
```

At init time, `index.html` converts these S3 paths to HTTPS URLs and downloads each
whole source object. The bbox filter reduces materialized rows, not download size.
September's `names.primary` and `taxonomy.primary` fields are exposed as `name`
and `category`; plotting coordinates use bbox midpoints. Original columns other
than `sources` remain available.

Upstream release files can expire. Manifests alone do not preserve their bytes;
use the local freeze exporter below before the selected release is removed.

### Rebuilding the data

Run the **Build London Parquet manifests (Overture)** workflow from Actions:

1. Select the branch to update.
2. Enter an available Overture release tag (e.g. `2026-09-23.0`).
3. Update `OVERTURE_RELEASE` in `index.html` to the new tag.

### Freezing London Parquets locally

After generating and verifying manifests for an available release, install
`duckdb==1.5.1` in a Python virtual environment and run `freeze_london.py`:

```bash
python freeze_london.py --release YYYY-MM-DD.N --output /absolute/path/to/new-snapshot
```

Replace `YYYY-MM-DD.N` with the verified release. The script reads both
release-specific files from `manifests/` beside the script; use `--manifest-dir`
to point to a separate copy of those manifests. Copy the manifests as well as the
script when running outside this checkout.

It applies the dashboard's inclusive London bbox-overlap predicate, retains full
geometry, excludes `sources`, and writes ZSTD-compressed places and buildings
Parquets. It prints row counts and sizes and writes `provenance.json` containing
input URLs, manifest and output SHA-256 checksums, schema, bounds, and export
settings. These are filtered derivatives, not byte-for-byte input archives.

The output directory must not already exist. Use a location outside this
repository to avoid accidentally committing large exports. Internet access,
several GB of RAM, and free disk space for temporary spill files are required;
DuckDB's 4 GB memory setting does not limit total process memory. Exported
geometry must be checked with the browser's DuckDB-Wasm version before deployment.

---

## Greater London Bounding Box

```
west  = -0.510   east  = 0.334
south = 51.286   north = 51.692
```

All `london.*` tables are already filtered to this extent — no extra bbox clause needed
in student queries.  Add a tighter filter to zoom into a specific borough or street:

```sql
-- Canary Wharf area
WHERE lat BETWEEN 51.490 AND 51.520
  AND lon BETWEEN -0.040 AND 0.010
```
