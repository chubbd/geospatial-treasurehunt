# Geospatial SQL Treasure Hunt

A browser-based geospatial treasure hunt and spatial SQL teaching experience
powered by **DuckDB-WASM**. On startup the app queries
[Overture Maps](https://overturemaps.org/) data from the public S3 bucket,
filters to the **Greater London** bounding box, and materialises the results
as in-memory DuckDB tables — no backend, no pre-built files, no DuckLake
required.

## Live Demo

**GitHub Pages:** [https://chubbd.github.io/geospatial-treasurehunt/](https://chubbd.github.io/geospatial-treasurehunt/)

> ⚠️ **Must be served over HTTP(S).** The app uses `SharedArrayBuffer` (required by
> DuckDB-WASM) which is blocked by browsers when opened via `file://`. Use GitHub Pages,
> a local HTTP server, or any static hosting service.

---

## Features

| Feature | Details |
|---|---|
| **Map** | MapLibre GL (dark basemap, centred on London, click-to-inspect popups) |
| **SQL editor** | Multi-line textarea with Ctrl/Cmd+Enter shortcut to run |
| **London tables** | `london.places` · `london.addresses` · `london.buildings` |
| **Polygon geometry** | `london.buildings` stores full polygon geometry for spatial queries |
| **Spatial SQL** | `LOAD spatial;` — full ST_* function suite available after init |
| **Clue themes** | Schema · Places · Addresses · Buildings · Spatial (distance, intersection, triangulation) |

---

## Quick Start

1. Fork or clone this repository.
2. Go to **Settings → Pages** and set the source branch to `main` (root `/`).
3. GitHub will publish the site — usually within 60 seconds.
4. Open the published URL, click **⚡ Init DuckDB**, wait for the London tables to
   materialise (~30–120 s on first load), then start exploring!

> **First load is slow** because DuckDB-WASM queries Overture's public S3 bucket,
> applies a London bbox filter, and materialises the results in browser memory.
> Subsequent queries run instantly against the in-memory tables.

---

## Running Locally

Any static file server works. Examples:

```bash
# Python 3
python -m http.server 8080

# Node.js  (npx)
npx serve .

# VS Code Live Server extension
# — right-click index.html → "Open with Live Server"
```

Then open `http://localhost:8080` in your browser.

> **Do not** open `index.html` directly with `File → Open`.
> The app requires cross-origin isolation headers (SharedArrayBuffer).

---

## London Tables

After clicking **⚡ Init DuckDB**, three in-memory tables are available in the
`london` schema:

### `london.buildings`

| Column | Type | Description |
|---|---|---|
| `id` | VARCHAR | Overture feature ID |
| `name` | VARCHAR | Primary name |
| `height` | DOUBLE | Height in metres (may be NULL) |
| `num_floors` | INTEGER | Number of floors (may be NULL) |
| `geometry` | GEOMETRY | Full building polygon (WGS-84) |
| `building_area_m2` | DOUBLE | Footprint area in m² (pre-computed) |
| `lat` | DOUBLE | Centroid latitude |
| `lon` | DOUBLE | Centroid longitude |
| `xmin/ymin/xmax/ymax` | DOUBLE | Bounding box |

> **Memory note**: polygon geometry is the largest contributor to memory use.
> If browser memory is constrained the app falls back to geometry-without-area,
> then to centroid-only. The status bar reports which tier was used.

### `london.places`

| Column | Type | Description |
|---|---|---|
| `id` | VARCHAR | Overture feature ID |
| `name` | VARCHAR | Primary name |
| `category` | VARCHAR | Overture basic category |
| `country` | VARCHAR | Country code |
| `confidence` | DOUBLE | Overture confidence score |
| `lat` | DOUBLE | Latitude |
| `lon` | DOUBLE | Longitude |

### `london.addresses`

| Column | Type | Description |
|---|---|---|
| `id` | VARCHAR | Overture feature ID |
| `street` | VARCHAR | Street name |
| `postcode` | VARCHAR | Postcode |
| `city` | VARCHAR | City |
| `country` | VARCHAR | Country code |
| `lat` | DOUBLE | Latitude |
| `lon` | DOUBLE | Longitude |

---

## Example Queries

```sql
-- All London tables
SHOW ALL TABLES;

-- Sample buildings
SELECT * FROM london.buildings WHERE name IS NOT NULL LIMIT 10;

-- Tallest buildings
SELECT name, height, num_floors, lat, lon
FROM london.buildings
WHERE height IS NOT NULL
ORDER BY height DESC
LIMIT 20;

-- Buildings larger than 1 000 m²
SELECT name, building_area_m2, height, lat, lon
FROM london.buildings
WHERE building_area_m2 > 1000
ORDER BY building_area_m2 DESC
LIMIT 20;

-- Distance from Trafalgar Square
SELECT name, category,
  ROUND(ST_Distance(ST_Point(lon, lat), ST_Point(-0.1281, 51.5080)) * 111000, 1) AS dist_m
FROM london.places
WHERE name IS NOT NULL
ORDER BY dist_m
LIMIT 10;

-- Buildings intersecting a search box (Tate Modern area)
SELECT name, height, building_area_m2
FROM london.buildings
WHERE geometry IS NOT NULL
  AND ST_Intersects(geometry, ST_MakeEnvelope(-0.105, 51.504, -0.093, 51.512))
LIMIT 20;

-- Addresses in EC1 postcode
SELECT street, postcode, lat, lon
FROM london.addresses
WHERE postcode ILIKE 'EC1%'
LIMIT 20;
```

---

## Architecture

```
index.html          ← entire app (single static file)
  ├─ MapLibre GL    ← map rendering (CDN)
  └─ DuckDB-WASM    ← in-browser SQL engine (CDN / jsDelivr)
       ├─ httpfs    ← queries Overture S3 Parquet files at startup
       └─ spatial   ← ST_* spatial functions (LOAD spatial)

.github/workflows/
  deploy.yml             ← deploys index.html to GitHub Pages
  build-overture-ducklake.yml  ← legacy: builds UK Parquet + DuckLake assets
```

**Startup flow:**

1. DuckDB-WASM initialises (bundle from jsDelivr CDN).
2. `LOAD httpfs` + `LOAD spatial` extensions are loaded.
3. An anonymous S3 secret is created for Overture's public bucket.
4. For each theme (places, addresses, buildings), DuckDB queries
   `s3://overturemaps-us-west-2/release/{RELEASE}/theme=.../type=.../*.parquet`
   with a Greater London bbox predicate and materialises the result as an
   in-memory table in the `london` schema.
5. Users query the materialised tables directly — all subsequent queries are
   fast (in-memory).

No build step. No server. No API keys needed.

---

## London Bounding Box

The materialization filter uses the Greater London bbox:

```
west  = -0.51   east  =  0.33
south = 51.28   north = 51.72
```

---

## Memory Budget

DuckDB-WASM has a ~4 GB address-space ceiling. The app caps DuckDB at 3.3 GB
and targets well under 1.5 GB effective in-session footprint to leave room
for query intermediates and spatial operations.

| Table | Estimated size |
|---|---|
| `london.places` | ~10–50 MB |
| `london.addresses` | ~20–80 MB |
| `london.buildings` (with polygons) | ~200–800 MB |
| Spatial/query overhead | ~200–500 MB |

`london.buildings` is the dominant cost. The app tries three materialisation
tiers automatically:

1. **Full**: geometry + `building_area_m2` pre-computed (preferred).
2. **Geometry-only**: polygon stored, area computation skipped.
3. **Centroid-only**: no polygon geometry (lightweight fallback).

The status bar after init reports which tier was used.
