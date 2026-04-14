# Geospatial SQL Treasure Hunt

A browser-based geospatial treasure hunt using **DuckDB-WASM** to query
[Overture Maps](https://overturemaps.org/) data scoped to **Greater London** —
no backend required.

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
| **Overture themes** | Places · Addresses · Buildings · Divisions · Transportation |
| **London-only materialisation** | `london_places`, `london_addresses`, `london_buildings` materialised in-memory at init — all queries instant |
| **Schema inspection** | `DESCRIBE` demo queries for every theme (reads Parquet footer only) |
| **Defensive loading** | Multiple fallback column projections tried; graceful messaging when schemas differ |
| **Theme filter** | Filter the clue list by Overture theme |

---

## Quick Start (GitHub Pages)

1. Fork or clone this repository.
2. Go to **Settings → Pages** and set the source branch to `main` (root `/`).
3. GitHub will build and publish the site — usually within 60 seconds.
4. Open the published URL, click **⚡ Init DuckDB**, wait **30-90 s** for the
   one-time London data materialisation, then start exploring!

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

## Overture Data Source

On initialisation the app reads Overture's public Parquet files directly from
the Overture S3 bucket (`s3://overturemaps-us-west-2`) via the DuckDB `httpfs`
extension — no DuckLake catalog, no pre-built release assets needed.

A London bounding-box filter is pushed down into the `read_parquet()` call so
that only row groups intersecting Greater London are fetched.  The result is
materialised as an in-memory DuckDB `TABLE` object for instant re-query.

**Data path:**
```
s3://overturemaps-us-west-2/release/2026-03-18.0/theme=places/type=place/*.parquet
s3://overturemaps-us-west-2/release/2026-03-18.0/theme=addresses/type=address/*.parquet
s3://overturemaps-us-west-2/release/2026-03-18.0/theme=buildings/type=building/*.parquet
...
```

### Updating the release tag

Set `OVERTURE_RELEASE` in `index.html` to the desired Overture release tag
(e.g. `2026-04-15.0`).  No other changes are needed — the app reads directly
from the public S3 bucket.

---

## London Bounding Box

All three materialised tables are pre-filtered to this bbox:

```
west  = -0.51   east  = 0.33
south = 51.28   north = 51.70
```

You can apply a tighter filter to zoom in on a neighbourhood:

**For point data (places, addresses):**
```sql
WHERE lon BETWEEN -0.20 AND -0.05
  AND lat BETWEEN 51.46 AND 51.56   -- central London
```

**For object bboxes (buildings):**
```sql
WHERE xmax >= west  AND xmin <= east
  AND ymax >= south AND ymin <= north
```

---

## Architecture

```
index.html          ← entire app (single static file)
  ├─ MapLibre GL    ← map rendering (CDN)
  └─ DuckDB-WASM    ← in-browser SQL engine (CDN / jsDelivr)
       ├─ httpfs    ← reads Overture Parquet files directly from S3
       └─ spatial   ← enables ST_* geospatial functions

.github/workflows/
  deploy.yml        ← deploys index.html to GitHub Pages
```

No build step. No server. No API keys needed.

### Memory budget

| Table | Approx. rows | In-memory (est.) |
|---|---|---|
| `london_places` | 50 000–80 000 | 6–12 MB |
| `london_addresses` | 500 000–1.5 M | 60–180 MB |
| `london_buildings` | 800 000–1.8 M | 90–250 MB |
| **Total worst-case** | | **≈ 440 MB** |

DuckDB-WASM hard ceiling: **4 GB**.  App `memory_limit`: **3.3 GB**.
Headroom after London tables: **≈ 2.9 GB** — well within the soft limit.

### Why no ART indexes?

DuckDB ART indexes accelerate equality (`=`) and range lookups, but the typical
teaching queries in this app use:

- `lat/lon BETWEEN` — range covering 10–50 % of London rows (too low selectivity for ART to help)
- `category ILIKE` — pattern match (ART cannot index `LIKE`/`ILIKE`)
- `postcode ILIKE` — same

A full vectorised columnar scan over 80 k places takes < 5 ms; over 1.5 M
addresses < 50 ms.  ART indexes would add ~75–110 MB per column with no
measurable query-time benefit for these patterns.  DuckDB's automatic zone-map
(min-max) statistics per row-group already provide free range-scan optimisation.

