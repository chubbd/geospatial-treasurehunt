"""Export London snapshots: pip install duckdb==1.5.1; then use --release."""

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import duckdb


BOUNDS = {"west": -0.510, "south": 51.286, "east": 0.334, "north": 51.692}
FILTER_SQL = """
SELECT * EXCLUDE (sources)
FROM source_data
WHERE bbox.xmax >= -0.510 AND bbox.xmin <= 0.334
  AND bbox.ymax >= 51.286 AND bbox.ymin <= 51.692
"""


def sql_string(value):
    return "'" + str(value).replace("'", "''") + "'"


def load_inputs(manifest_dir, release, table, feature_type):
    manifest = manifest_dir / f"london_{table}_{release}.txt"
    urls = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        prefix = (
            f"release/{release}/theme={table}/type={feature_type}/"
        )
        parsed = urlparse(line)
        if (
            parsed.scheme != "s3"
            or parsed.netloc != "overturemaps-us-west-2"
            or not parsed.path.lstrip("/").startswith(prefix)
            or not parsed.path.endswith(".parquet")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(f"Unexpected source in {manifest}: {line}")
        urls.append(
            "https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com"
            + parsed.path
        )
    if not urls or len(urls) != len(set(urls)):
        raise ValueError(f"Empty or duplicate inputs in {manifest}")
    return manifest, urls


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", required=True)
    parser.add_argument(
        "--manifest-dir", type=Path,
        default=Path(__file__).resolve().parent / "manifests",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Validate the identifier before using it in filenames.
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.\d+", args.release):
        parser.error("--release must have the form YYYY-MM-DD.N")

    inputs = {
        table: load_inputs(args.manifest_dir, args.release, table, feature_type)
        for table, feature_type in (("places", "place"), ("buildings", "building"))
    }
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    metadata = {
        "release": args.release,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "duckdb_version": duckdb.__version__,
        "bounds": BOUNDS,
        "selection": "Inclusive bbox overlap; full geometry, no clipping",
        "query": FILTER_SQL.strip(),
        "compression": "ZSTD",
        "row_group_size": 122880,
        "tables": {},
    }
    with duckdb.connect() as con:
        con.execute("SET memory_limit='4GB'")
        con.execute("SET threads=2")
        con.execute("SET preserve_insertion_order=false")
        con.execute(f"SET temp_directory={sql_string(output / 'tmp')}")
        con.execute("INSTALL httpfs; LOAD httpfs")
        con.execute("INSTALL spatial; LOAD spatial")
        for table, (manifest, urls) in inputs.items():
            print(f"Exporting {table} from {len(urls)} inputs…", flush=True)
            con.read_parquet(urls).create_view("source_data", replace=True)
            final = output / f"london_{table}_{args.release}.parquet"
            partial = final.with_suffix(".parquet.partial")
            con.execute(
                f"COPY ({FILTER_SQL}) TO {sql_string(partial)} "
                "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 122880)"
            )
            rows = con.execute(
                "SELECT count(*) FROM read_parquet(?)", [str(partial)]
            ).fetchone()[0]
            if not rows:
                raise ValueError(f"No London rows exported for {table}")
            schema = [
                {"name": row[0], "type": row[1]}
                for row in con.execute(
                    "DESCRIBE SELECT * FROM read_parquet(?)", [str(partial)]
                ).fetchall()
            ]
            partial.rename(final)
            size = final.stat().st_size
            metadata["tables"][table] = {
                "inputs": urls,
                "manifest_sha256": sha256(manifest),
                "output": final.name,
                "rows": rows,
                "bytes": size,
                "sha256": sha256(final),
                "schema": schema,
            }
            print(f"{table}: {rows:,} rows; {size / 1024**2:,.2f} MiB", flush=True)
    metadata["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    (output / "provenance.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Snapshot saved to {output}")


if __name__ == "__main__":
    main()
