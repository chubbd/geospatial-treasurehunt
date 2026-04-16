# Geospatial SQL Treasure Hunt

A browser-based geospatial treasure hunt using **DuckDB-WASM** to query
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
| **Theme filter** | Filter clue list by Places / Buildings / Spatial / Schema |

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
3. Reads the pre-built **UK-filtered Parquet files** from GitHub Releases via `httpfs`,
   applying a **Greater London bounding box filter** during the read.
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

Greater London (bbox: W -0.510, S 51.286, E 0.334, N 51.692) is a small slice of the
UK dataset.  Typical in-session footprints at the 2026-03-18.0 release:

| Table | Expected rows | Approx. in-memory |
|---|---|---|
| `london.places` | ~100K | ~20 MB |
| `london.buildings` | ~200K–600K (with polygons) | ~200–400 MB |

Total is well within DuckDB-WASM's practical ~3 GB ceiling.

---

## London Tables

### `london.buildings`
| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR | Overture feature ID |
| `name` | VARCHAR | Building name if present |
| `height` | DOUBLE | Height in metres |
| `num_floors` | INTEGER | Floor count if present |
| `building_area_m2` | INTEGER | Bbox-based footprint approximation in m² |
| `lat` / `lon` | DOUBLE | Centroid (bbox midpoint) |
| `xmin`/`ymin`/`xmax`/`ymax` | DOUBLE | Bounding box corners |
| `geometry` | GEOMETRY | Full polygon/multipolygon for `ST_*` ops |

### `london.places`
| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR | Overture feature ID |
| `name` | VARCHAR | Place name |
| `category` | VARCHAR | Primary category (e.g. `museum`, `restaurant`) |
| `addresses` | LIST<STRUCT> | Nested address entries (e.g. `freeform`, `locality`, `postcode`, `region`, `country`) |
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
       ├─ httpfs         ← reads UK Parquet files from GitHub Releases
       └─ spatial        ← ST_* functions, GEOMETRY type

.github/workflows/
  build-overture-ducklake.yml  ← builds UK-filtered Parquet release assets
  deploy.yml                   ← deploys index.html to GitHub Pages
  duckdbwasmdownload.yml       ← vendors DuckDB-WASM bundle files
```

No build step. No server. No API keys needed.

---

## Overture Data Source

UK-filtered Parquet files are pre-built by the **Build UK Overture Parquets** workflow
and uploaded as GitHub Release assets tagged `overture-uk-{overture_release}`:

```
https://github.com/chubbd/geospatial-treasurehunt/releases/download/overture-uk-2026-03-18.0/
  places_uk.parquet
  buildings_uk.parquet
  divisions_uk.parquet
  segments_uk.parquet
```

At init time, `index.html` reads each Parquet file via `httpfs` with a London bbox
filter and materialises only the London subset into in-memory DuckDB tables.

**Why Hilbert re-sort?**  The pre-built Parquet files are Hilbert-sorted against the UK
extent so that DuckDB can skip row groups outside the London bbox efficiently — only the
London rows need to be fetched from the remote file.

### Rebuilding the data

Run the **Overture Ducklake** workflow manually from the Actions tab:

1. Go to **Actions → Overture Ducklake → Run workflow**.
2. Enter the new Overture release tag (e.g. `2026-04-15.0`).
3. Update `OVERTURE_RELEASE` in `index.html` to the new tag.

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
