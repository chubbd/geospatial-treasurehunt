# Geospatial SQL Treasure Hunt

A browser-based geospatial treasure hunt using **DuckDB-WASM** to query remote
[Overture Maps](https://overturemaps.org/) Parquet data from public S3 — no backend required.

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
| **UK bbox pre-filtering** | Views (`places_uk`, `addresses_uk`, `buildings_uk`, …) that restrict scans to Great Britain + NI |
| **Schema inspection** | `DESCRIBE` demo queries for every theme |
| **Defensive views** | Multiple fallback projections tried; graceful messaging when schemas differ |
| **Theme filter** | Filter the clue list by Overture theme |

---

## Quick Start (GitHub Pages)

1. Fork or clone this repository.
2. Go to **Settings → Pages** and set the source branch to `main` (root `/`).
3. GitHub will build and publish the site — usually within 60 seconds.
4. Open the published URL, click **⚡ Init DuckDB**, wait ~15–30 s, then start exploring!

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

Data is read live from the public Overture Maps Azure Blob Storage container
(CORS-enabled, no credentials required):

```
https://overturemapswestus2.blob.core.windows.net/release/2025-07-23.0/
```

At initialisation the app calls Azure's public [List Blobs REST API](https://learn.microsoft.com/en-us/rest/api/storageservices/list-blobs)
to discover the exact `.parquet` file URLs for each theme, then passes them as
an explicit array to DuckDB's `read_parquet([url1, url2, …])`.  This sidesteps
the DuckDB-WASM limitation where glob wildcards (`*`) cannot be expanded over
plain HTTPS.

Themes queried:

| Theme | Prefix |
|---|---|
| Places | `theme=places/type=place/` |
| Addresses | `theme=addresses/type=address/` |
| Buildings | `theme=buildings/type=building/` |
| Divisions | `theme=divisions/type=division/` |
| Transportation | `theme=transportation/type=segment/` |

---

## UK Bounding Box

All demo queries pre-filter to the UK bounding box for performance.
Scanning fewer Parquet row groups makes queries dramatically faster in the browser.

```
west  = -8.75   east  =  1.90
south = 49.80   north = 60.95
```

**For point data (places, addresses):**
```sql
WHERE lon BETWEEN -8.75 AND 1.90
  AND lat BETWEEN 49.80 AND 60.95
```

**For object bboxes (buildings, divisions, segments):**
```sql
WHERE bbox.xmax >= -8.75 AND bbox.xmin <= 1.90
  AND bbox.ymax >= 49.80 AND bbox.ymin <= 60.95
```

---

## Architecture

```
index.html          ← entire app (single static file)
  ├─ MapLibre GL    ← map rendering (CDN)
  └─ DuckDB-WASM    ← in-browser SQL engine (CDN / jsDelivr)
       └─ httpfs    ← reads Parquet directly from S3 over HTTP range requests
```

No build step. No server. No API keys needed.
