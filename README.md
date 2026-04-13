# Geospatial SQL Treasure Hunt

A browser-based geospatial treasure hunt using **DuckDB-WASM** to query
UK-pre-filtered [Overture Maps](https://overturemaps.org/) Parquet files — no backend required.

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
| **UK-pre-filtered data** | One Parquet file per theme, pre-built to the UK bbox — no global scans |
| **Schema inspection** | `DESCRIBE` demo queries for every theme |
| **Defensive views** | Multiple fallback projections tried; graceful messaging when schemas differ |
| **Theme filter** | Filter the clue list by Overture theme |

---

## Quick Start (GitHub Pages)

1. Fork or clone this repository.
2. Go to **Settings → Pages** and set the source branch to `main` (root `/`).
3. GitHub will build and publish the site — usually within 60 seconds.
4. Open the published URL, click **⚡ Init DuckDB**, wait ~2–5 s, then start exploring!

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

The app now prefers **GitHub Release assets** in this repository and falls back to
a tiny same-origin **DuckLake catalog** that points at Overture's public S3 files
when the browser cannot read the release assets directly.

The release is tagged `overture-uk-{overture_release}` (e.g.
`overture-uk-2026-03-18.0`) and contains UK-filtered Parquet assets plus an
`overture_uk.ducklake` catalog:

```
https://github.com/chubbd/geospatial-treasurehunt/releases/download/overture-uk-2026-03-18.0/
  places_uk.parquet
  addresses_uk.parquet
  buildings_uk.parquet
  divisions_uk.parquet
  segments_uk.parquet
  overture_uk.ducklake
```

When GitHub Releases are readable from the browser, DuckDB reads a single Parquet
footer per theme instead of discovering headers from hundreds of S3 partition
files. When that path is blocked by browser/CORS behavior, the fallback DuckLake
catalog keeps the site working without hosting the full dataset on GitHub Pages.

**Why Hilbert re-sort?**  Overture's source files are already Hilbert-sorted, but
against a global (world) extent.  Re-sorting the UK subset against the UK extent
tightens the spatial clustering within each row group, so DuckDB-WASM can skip
many more row groups when executing a city-sized bbox query (e.g. "all buildings
in London"), making in-browser queries noticeably faster.  The build workflow uses
DuckDB 1.5.1 for its improved geospatial handling and full GeoParquet support.

### Rebuilding the data

Run the **Build UK Overture Parquets** workflow manually from the Actions tab:

1. Go to **Actions → Build UK Overture Parquets → Run workflow**.
2. Enter the new Overture release tag (e.g. `2026-04-15.0`).
3. The workflow installs DuckDB 1.5.1 + spatial/ducklake extensions, downloads the
   source data from the Overture public S3 bucket, filters to the UK bbox,
   re-sorts by Hilbert curve (UK extent), builds a small `overture_uk.ducklake`
   catalog, and uploads everything to a matching release.
4. Update `OVERTURE_RELEASE` in `index.html` to the new tag.

---

## UK Bounding Box

The Parquet files are pre-filtered to the UK bounding box, so no global scan is
ever needed in the browser.  You can apply a tighter filter to zoom in on a city:

```
west  = -8.75   east  =  1.90
south = 49.80   north = 60.95
```

**For point data (places, addresses):**
```sql
WHERE lon BETWEEN -0.20 AND -0.05
  AND lat BETWEEN 51.46 AND 51.56   -- central London
```

**For object bboxes (buildings, divisions, segments):**
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
       ├─ httpfs    ← reads Parquet files and the hosted DuckLake catalog
       └─ ducklake  ← fallback catalog pointing at Overture S3 Parquet files

.github/workflows/
  build-uk-parquets.yml  ← builds Parquet release assets + DuckLake catalog
  deploy.yml             ← deploys index.html and overture_uk.ducklake to GitHub Pages
```

No build step. No server. No API keys needed.
