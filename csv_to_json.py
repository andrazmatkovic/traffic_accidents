#!/usr/bin/env python3
"""
Convert processed accident CSV data to compressed JSON.

Usage:
  python3 csv_to_json.py accidents.csv accidents.json.gz
  python3 csv_to_json.py --chunks accidents.csv data
"""

import csv
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path


# The source leaves a few categorical values blank. A blank renders as an empty,
# unselectable option in the filter dropdowns, so it gets an explicit value.
UNSPECIFIED = "NEDOLOČENO"

FIELDS = (
    "latitude",
    "longitude",
    "year",
    "KlasifikacijaNesrece",
    "TipNesrece",
    "VremenskeOkoliscine",
    "StanjePrometa",
    "StanjeVozisca",
    "VNaselju",
    "TekstCesteNaselja",
    "DatumPN",
    "UraPN",
)


def category_value(row, field):
    return row.get(field, "").strip() or UNSPECIFIED


def read_accidents(csv_file):
    with open(csv_file, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)

        for idx, row in enumerate(reader):
            if idx % 10000 == 0:
                print(f"  Processed {idx} rows...")

            try:
                lat = float(row.get("latitude", ""))
                lon = float(row.get("longitude", ""))
                year = int(row.get("year", ""))

                if lat and lon:
                    yield {
                        "latitude": round(lat, 6),
                        "longitude": round(lon, 6),
                        "year": year,
                        "KlasifikacijaNesrece": category_value(row, "KlasifikacijaNesrece"),
                        "TipNesrece": category_value(row, "TipNesrece"),
                        "VremenskeOkoliscine": category_value(row, "VremenskeOkoliscine"),
                        "StanjePrometa": category_value(row, "StanjePrometa"),
                        "StanjeVozisca": category_value(row, "StanjeVozisca"),
                        "VNaselju": category_value(row, "VNaselju"),
                        "TekstCesteNaselja": row.get("TekstCesteNaselja", ""),
                        "DatumPN": row.get("DatumPN", ""),
                        "UraPN": row.get("UraPN", ""),
                    }
            except (ValueError, KeyError):
                continue


def write_compressed_json(data, output_file):
    json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    print(f"  JSON size: {len(json_str) / 1024 / 1024:.2f} MB")

    with gzip.open(output_file, "wt", encoding="utf-8", compresslevel=9) as handle:
        handle.write(json_str)

    compressed_size = Path(output_file).stat().st_size / 1024 / 1024
    print(f"  Compressed size: {compressed_size:.2f} MB")
    print(f"  Compression ratio: {(1 - compressed_size / (len(json_str) / 1024 / 1024)) * 100:.1f}%")


def convert_csv_to_compressed_json(csv_file, output_file=None):
    if output_file is None:
        output_file = Path(csv_file).stem + ".json.gz"

    print(f"Reading CSV: {csv_file}")
    data = list(read_accidents(csv_file))
    print(f"Total valid records: {len(data)}")

    print(f"Compressing to: {output_file}")
    write_compressed_json(data, output_file)
    print("Done")


def convert_csv_to_year_chunks(csv_file, output_dir="data"):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    by_year = defaultdict(list)
    values = {
        "years": set(),
        "severities": set(),
        "types": set(),
        "weather": set(),
        "traffic": set(),
        "roadSurface": set(),
        "locationTypes": set(),
    }

    print(f"Reading CSV: {csv_file}")
    for accident in read_accidents(csv_file):
        year = accident["year"]
        by_year[year].append(accident)
        values["years"].add(year)
        values["severities"].add(accident["KlasifikacijaNesrece"])
        values["types"].add(accident["TipNesrece"])
        values["weather"].add(accident["VremenskeOkoliscine"])
        values["traffic"].add(accident["StanjePrometa"])
        values["roadSurface"].add(accident["StanjeVozisca"])
        values["locationTypes"].add(accident["VNaselju"])

    years = sorted(by_year)
    manifest = {
        "defaultYear": years[-1] if years else None,
        "years": years,
        "fields": list(FIELDS),
        "filters": {
            "severities": sorted(values["severities"]),
            "types": sorted(values["types"]),
            "weather": sorted(values["weather"]),
            "traffic": sorted(values["traffic"]),
            "roadSurface": sorted(values["roadSurface"]),
            "locationTypes": sorted(values["locationTypes"]),
        },
        "chunks": [],
    }

    total_rows = 0
    for year in years:
        records = by_year[year]
        output_file = output_path / f"accidents-{year}.json.gz"
        total_rows += len(records)
        print(f"Compressing {year} ({len(records)} records) to: {output_file}")
        write_compressed_json(records, output_file)
        manifest["chunks"].append(
            {
                "year": year,
                "file": f"accidents-{year}.json.gz",
                "records": len(records),
                "bytes": output_file.stat().st_size,
            }
        )

    manifest_file = output_path / "manifest.json"
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Manifest saved: {manifest_file}")
    print(f"Total valid records: {total_rows}")
    print("Done")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 csv_to_json.py <csv_file> [output_file]")
        print("  python3 csv_to_json.py --chunks <csv_file> [output_dir]")
        sys.exit(1)

    if sys.argv[1] == "--chunks":
        if len(sys.argv) < 3:
            print("Usage: python3 csv_to_json.py --chunks <csv_file> [output_dir]")
            sys.exit(1)

        csv_file = sys.argv[2]
        output_dir = sys.argv[3] if len(sys.argv) > 3 else "data"

        if not Path(csv_file).exists():
            print(f"Error: File not found: {csv_file}")
            sys.exit(1)

        convert_csv_to_year_chunks(csv_file, output_dir)
        sys.exit(0)

    csv_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    if not Path(csv_file).exists():
        print(f"Error: File not found: {csv_file}")
        sys.exit(1)

    convert_csv_to_compressed_json(csv_file, output_file)
