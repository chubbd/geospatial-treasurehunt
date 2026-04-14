# Geospatial SQL Treasure Hunt

A browser-based geospatial treasure hunt powered by **DuckDB-WASM**.  On first
load the app reads from the Overture Maps public S3 bucket and materialises
three in-memory tables scoped to Greater London:

| Table | Contents |
|---|---|
| `london_places` | POIs — cafes, museums, shops, … |
| `london_addresses` | Street addresses with postcodes |
| `london_buildings` | Building footprints with height/floors |

All queries (including **`ST_*` spatial functions**) run entirely in the browser
against these in-memory tables — no backend, no database file, no data
pre-processing step required.

## Live Demo

**GitHub Pages:** [https://chubbd.github.io/geospatial-treasurehunt/](https://chubbd.github.io/geospatial-treasurehunt/)

> ⚠️ **Must be served over HTTP(S).** The app uses `SharedArrayBuffer`
> (required by DuckDB-WASM) which is blocked by browsers when opened via
> `file://`. Use GitHub Pages, a local HTTP server, or any static hosting
> service.

---

## Features

| Feature | Details |
|---|---|
| **Map** | MapLibre GL (dark basemap, click-to-inspect popups), centred on London |
| **SQL editor** | Multi-line textarea with Ctrl/Cmd+Enter shortcut to run |
| **London tables** | Places · Addresses · Buildings — materialised in-memory at startup |
| **Spatial SQL** | `ST_Distance`, `ST_Point`, `ST_Within` and all other `ST_*` functions enabled via `LOAD spatial` |
| **Schema inspection** | `DESCRIBE` demo queries for every table |
| **Theme filter** | Filter the clue list by Places / Addresses / Buildings / Spatial / Schema |

---

## Quick Start (GitHub Pages)

1. Fork or clone this repository.
2. Go to **Settings → Pages** and set the source branch to `main` (root `/`).
3. GitHub will build and publish the site — usually within 60 seconds.
4. Open the published URL, click **⚡ Init DuckDB**, wait 20–60 s for London
   data to materialise, then start exploring!

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

## Data Source

London data is read live from the **Overture Maps** public S3 bucket at
initialisation:

```
s3://overturemaps-us-west-2/release/2026-03-18.0/
  theme=places/type=place/*.parquet        → london_places
  theme=addresses/type=address/*.parquet   → london_addresses
  theme=buildings/type=building/*.parquet  → london_buildings
```

DuckDB-WASM uses Parquet row-group statistics to skip the vast majority of
row groups outside the Greater London bbox, keeping the initial scan fast.
The materialised tables are held in DuckDB's in-memory store for the rest of
the browser session — all subsequent queries are instant.

**Greater London bounding box used at materialisation:**

```
west  = -0.55   east  =  0.35
south = 51.25   north = 51.75
```

---

## Spatial SQL examples

```sql
-- Nearest places to Tower Bridge
SELECT name, category,
  round(ST_Distance(ST_Point(lon, lat), ST_Point(-0.0754, 51.5055)) * 111000) AS dist_m
FROM london_places
WHERE name IS NOT NULL
ORDER BY dist_m
LIMIT 20;

-- Places within 500 m of St Paul's Cathedral
SELECT name, category, lat, lon
FROM london_places
WHERE ST_Distance(ST_Point(lon, lat), ST_Point(-0.0984, 51.5138)) < 0.0045
ORDER BY ST_Distance(ST_Point(lon, lat), ST_Point(-0.0984, 51.5138))
LIMIT 30;
```

---

## Architecture

```
index.html          ← entire app (single static file)
  ├─ MapLibre GL    ← map rendering (CDN), centred on London
  └─ DuckDB-WASM    ← in-browser SQL engine (vendored JS + CDN WASM)
       ├─ httpfs    ← reads Overture Parquet files from public S3
       └─ spatial   ← ST_* spatial functions

.github/workflows/
  deploy.yml        ← deploys index.html to GitHub Pages on push to main
  duckdbwasmdownload.yml   ← (optional) re-vendor the DuckDB-WASM JS module
  build-overture-ducklake.yml  ← archived; built the old DuckLake catalog
```

No build step.  No server.  No API keys needed.

### Why no DuckLake?

The previous approach fetched a `.ducklake` SQLite catalog from GitHub Releases
and used the `ducklake` DuckDB extension to attach it as a virtual catalog
over Overture S3 Parquet files.  This introduced three coupled version-mismatch
risks (DuckLake spec, DuckDB storage format, GeoParquet schema enforcement).

The current approach removes all three risks by:

1. Reading directly from the Overture S3 Parquet files via `httpfs` (already
   bundled in the DuckDB-WASM EH build — no extension download needed).
2. Materialising the London subset as plain in-memory DuckDB tables once per
   session.
3. Loading the `spatial` extension (also bundled) to enable `ST_*` functions.

OPFS persistence can be added as a future enhancement without changing the
teaching/query layer.

