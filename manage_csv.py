#!/usr/bin/env python3
"""
Manage Slovenian traffic accident CSV files.

Commands:
  convert   Convert one raw pnYYYY.csv file to UTF-8 CSV with WGS84 coordinates.
  merge     Convert and merge raw data/pnYYYY.csv files into accidents.csv.
  validate  Validate a processed CSV file.
  audit     Compare processed CSV values against raw source CSV values.
  stats     Print quick dataset statistics.
"""

import argparse
import csv
import glob
import os
import re
import sys
from pathlib import Path


DEFAULT_DATA_FOLDER = "data"
DEFAULT_OUTPUT_FILE = "accidents.csv"
DEFAULT_START_YEAR = 2015
DEFAULT_END_YEAR = 2026
ENCODINGS = ("utf-8", "iso-8859-2", "windows-1250", "cp1250")
REQUIRED_COLUMNS = (
    "ZaporednaStevilkaPN",
    "KlasifikacijaNesrece",
    "DatumPN",
    "UraPN",
    "GeoKoordinataX",
    "GeoKoordinataY",
    "year",
    "latitude",
    "longitude",
)


def require_processing_deps():
    try:
        import numpy as np
        import pandas as pd
        from pyproj import Transformer
    except ImportError as exc:
        raise SystemExit(
            "Missing data-processing dependencies. Install them with:\n"
            "  python3 -m pip install -r requirements.txt"
        ) from exc

    return pd, np, Transformer


def get_year_from_filename(filename):
    """Extract year from filenames like pn2004.csv."""
    match = re.search(r"pn(\d{4})", os.path.basename(filename))
    if match:
        return int(match.group(1))
    return None


def parse_years(years_arg):
    if not years_arg:
        return None

    years = set()
    for value in years_arg:
        if "-" in value:
            start, end = value.split("-", 1)
            years.update(range(int(start), int(end) + 1))
        else:
            years.add(int(value))
    return years


def should_process_year(year, start_year=None, end_year=None, specific_years=None):
    if specific_years and year not in specific_years:
        return False
    if start_year is not None and year < start_year:
        return False
    if end_year is not None and year > end_year:
        return False
    return True


def read_raw_csv(csv_file):
    pd, _, _ = require_processing_deps()

    for encoding in ENCODINGS:
        try:
            return pd.read_csv(
                csv_file,
                sep=";",
                encoding=encoding,
                dtype=str,
                keep_default_na=False,
            )
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Could not read {csv_file} with supported encodings")


def read_raw_csv_rows(csv_file):
    for encoding in ENCODINGS:
        try:
            with open(csv_file, "r", encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle, delimiter=";")
                return reader.fieldnames or [], list(reader)
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Could not read {csv_file} with supported encodings")


def has_valid_source_coordinates(row):
    x_value = row.get("GeoKoordinataX", "").strip()
    y_value = row.get("GeoKoordinataY", "").strip()

    if not x_value or not y_value:
        return False

    try:
        return float(x_value) != 0 and float(y_value) != 0
    except ValueError:
        return False


def convert_coordinates_batch(df):
    """Convert D96/TM coordinates to WGS84 coordinates."""
    pd, np, Transformer = require_processing_deps()

    if "GeoKoordinataX" not in df.columns or "GeoKoordinataY" not in df.columns:
        return df

    x_coords = df["GeoKoordinataX"].astype(str).str.strip()
    y_coords = df["GeoKoordinataY"].astype(str).str.strip()

    x_coords = x_coords.replace(["", " "], np.nan)
    y_coords = y_coords.replace(["", " "], np.nan)

    x_coords = pd.to_numeric(x_coords, errors="coerce")
    y_coords = pd.to_numeric(y_coords, errors="coerce")

    valid_mask = (x_coords != 0) & (y_coords != 0) & x_coords.notna() & y_coords.notna()

    df["latitude"] = np.nan
    df["longitude"] = np.nan

    if valid_mask.sum() == 0:
        print("  No valid coordinates found")
        return df

    transformer = Transformer.from_crs("EPSG:3794", "EPSG:4326", always_xy=True)

    # Police CSVs label the D96/TM northing as X and easting as Y.
    lons, lats = transformer.transform(y_coords[valid_mask].values, x_coords[valid_mask].values)

    df.loc[valid_mask, "longitude"] = lons
    df.loc[valid_mask, "latitude"] = lats
    return df


def process_file(csv_file, year, keep_invalid=False):
    filename = os.path.basename(csv_file)
    print(f"Processing: {filename} (year {year})...")

    df = read_raw_csv(csv_file)
    df["year"] = str(year)

    if "GeoKoordinataX" not in df.columns or "GeoKoordinataY" not in df.columns:
        print(f"  Loaded {len(df)} rows (no coordinate columns found)")
        return df

    print("  Converting coordinates (D96/TM -> WGS84)...")
    rows_before = len(df)
    df = convert_coordinates_batch(df)

    if not keep_invalid:
        df = df.dropna(subset=["latitude", "longitude"])

    rows_after = len(df)
    rows_skipped = rows_before - rows_after

    if rows_skipped:
        print(f"  Loaded {rows_after} rows (skipped {rows_skipped} with missing/invalid coordinates)")
    else:
        print(f"  Loaded {rows_after} rows")

    invalid = df[
        (df["latitude"] < 45)
        | (df["latitude"] > 47)
        | (df["longitude"] < 13)
        | (df["longitude"] > 16)
    ]
    if len(invalid) > 0:
        print(f"  Warning: {len(invalid)} rows have coordinates outside Slovenia bounds")

    return df


def convert_file(input_file, output_file=None, year=None, keep_invalid=False):
    year = year or get_year_from_filename(input_file)
    if year is None:
        raise SystemExit("Could not infer year from filename. Pass --year YYYY.")

    output_file = output_file or f"{Path(input_file).stem}_converted.csv"
    df = process_file(input_file, year, keep_invalid=keep_invalid)
    df.to_csv(output_file, index=False, encoding="utf-8", na_rep="")
    print(f"Saved converted file: {output_file}")
    return True


def merge_all_files(data_folder, output_file, start_year=None, end_year=None, years=None, keep_invalid=False):
    pd, _, _ = require_processing_deps()

    if not os.path.exists(data_folder):
        print(f"Error: Folder '{data_folder}' not found")
        return False

    csv_files = sorted(glob.glob(os.path.join(data_folder, "pn*.csv")))
    if not csv_files:
        print(f"No pn*.csv files found in '{data_folder}'")
        return False

    print(f"Found {len(csv_files)} files in '{data_folder}':\n")

    dfs = []
    years_processed = []

    for csv_file in csv_files:
        year = get_year_from_filename(csv_file)
        if year is None:
            print(f"Skipping {os.path.basename(csv_file)} (could not extract year)")
            continue
        if not should_process_year(year, start_year, end_year, years):
            continue

        try:
            df = process_file(csv_file, year, keep_invalid=keep_invalid)
        except Exception as exc:
            print(f"  Error processing file: {exc}")
            continue

        dfs.append(df)
        years_processed.append(year)

    if not dfs:
        print("\nNo files were successfully processed")
        return False

    print(f"\n{'=' * 60}")
    print(f"Merging {len(dfs)} files...")

    merged = pd.concat(dfs, ignore_index=True)

    if "ZaporednaStevilkaPN" in merged.columns and "year" in merged.columns:
        merged = merged.drop_duplicates(subset=["year", "ZaporednaStevilkaPN"])

    merged.to_csv(output_file, index=False, encoding="utf-8", na_rep="")

    print(f"Saved merged file: {output_file}")
    print("\nSummary:")
    print(f"  Total accidents: {len(merged)}")
    print(f"  Years: {min(years_processed)} - {max(years_processed)}")
    print(f"  Unique years: {sorted(set(years_processed))}")

    if "TipNesrece" in merged.columns:
        print(f"  Accident types: {merged['TipNesrece'].nunique()}")

    if "latitude" in merged.columns and "longitude" in merged.columns:
        valid_coords = merged.dropna(subset=["latitude", "longitude"])
        print(f"  Rows with valid coordinates: {len(valid_coords)} / {len(merged)}")

    return True


def validate_file(csv_file):
    errors = []
    warnings = []
    row_count = 0
    duplicate_keys = set()
    seen_keys = set()

    with open(csv_file, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []

        missing_columns = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
        if missing_columns:
            errors.append(f"Missing required columns: {', '.join(missing_columns)}")

        for row_number, row in enumerate(reader, start=2):
            row_count += 1

            key = (row.get("year", ""), row.get("ZaporednaStevilkaPN", ""))
            if key in seen_keys:
                duplicate_keys.add(key)
            seen_keys.add(key)

            for column in ("latitude", "longitude"):
                value = row.get(column, "")
                try:
                    float(value)
                except ValueError:
                    errors.append(f"Row {row_number}: invalid {column} '{value}'")

            time_value = row.get("UraPN", "")
            if time_value and not re.fullmatch(r"\d{1,2}\.\d{2}", time_value):
                warnings.append(f"Row {row_number}: suspicious UraPN '{time_value}'")

    if duplicate_keys:
        warnings.append(f"Found {len(duplicate_keys)} duplicate year + ZaporednaStevilkaPN keys")

    print(f"Rows: {row_count}")
    if errors:
        print("\nErrors:")
        for error in errors[:25]:
            print(f"  - {error}")
        if len(errors) > 25:
            print(f"  ... and {len(errors) - 25} more")

    if warnings:
        print("\nWarnings:")
        for warning in warnings[:25]:
            print(f"  - {warning}")
        if len(warnings) > 25:
            print(f"  ... and {len(warnings) - 25} more")

    if errors:
        return False

    print("\nValidation passed")
    return True


def audit_raw_preservation(data_folder, processed_file, start_year=None, end_year=None, years=None):
    if not os.path.exists(data_folder):
        print(f"Error: Folder '{data_folder}' not found")
        return False

    raw_by_key = {}
    source_columns = []

    for csv_file in sorted(glob.glob(os.path.join(data_folder, "pn*.csv"))):
        year = get_year_from_filename(csv_file)
        if year is None or not should_process_year(year, start_year, end_year, years):
            continue

        fieldnames, rows = read_raw_csv_rows(csv_file)
        for fieldname in fieldnames:
            if fieldname not in source_columns:
                source_columns.append(fieldname)

        for row in rows:
            if not has_valid_source_coordinates(row):
                continue

            key = (str(year), row.get("ZaporednaStevilkaPN", ""))
            raw_by_key.setdefault(key, row)

    checked_rows = 0
    errors = []

    with open(processed_file, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        processed_columns = set(reader.fieldnames or [])

        for row_number, processed_row in enumerate(reader, start=2):
            key = (processed_row.get("year", ""), processed_row.get("ZaporednaStevilkaPN", ""))
            raw_row = raw_by_key.get(key)

            if raw_row is None:
                errors.append(f"Row {row_number}: no matching raw row for year/id {key}")
                continue

            checked_rows += 1
            for column in source_columns:
                if column not in processed_columns:
                    continue
                if raw_row.get(column, "") != processed_row.get(column, ""):
                    errors.append(
                        f"Row {row_number} {key} column {column}: "
                        f"raw={raw_row.get(column, '')!r}, processed={processed_row.get(column, '')!r}"
                    )

    print(f"Rows checked: {checked_rows}")
    print(f"Source fields checked per row: {len([c for c in source_columns if c in processed_columns])}")

    if errors:
        print("\nSource preservation errors:")
        for error in errors[:25]:
            print(f"  - {error}")
        if len(errors) > 25:
            print(f"  ... and {len(errors) - 25} more")
        return False

    print("\nRaw source fields preserved")
    return True


def print_stats(csv_file):
    rows = 0
    years = {}
    severities = {}
    missing_coords = 0

    with open(csv_file, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows += 1
            years[row.get("year", "")] = years.get(row.get("year", ""), 0) + 1
            severity = row.get("KlasifikacijaNesrece", "")
            severities[severity] = severities.get(severity, 0) + 1
            if not row.get("latitude") or not row.get("longitude"):
                missing_coords += 1

    print(f"Rows: {rows}")
    if years:
        print(f"Years: {min(years)} - {max(years)} ({len(years)} unique)")
    print(f"Missing coordinates: {missing_coords}")
    print("\nSeverity:")
    for severity, count in sorted(severities.items(), key=lambda item: item[1], reverse=True):
        print(f"  {severity or '(blank)'}: {count}")


def build_parser():
    parser = argparse.ArgumentParser(description="Manage Slovenian traffic accident CSV files")
    subparsers = parser.add_subparsers(dest="command", required=True)

    convert_parser = subparsers.add_parser("convert", help="Convert one raw pnYYYY.csv file")
    convert_parser.add_argument("input_file")
    convert_parser.add_argument("output_file", nargs="?")
    convert_parser.add_argument("--year", type=int, help="Year to use when filename does not contain pnYYYY")
    convert_parser.add_argument("--keep-invalid", action="store_true", help="Keep rows without valid coordinates")

    merge_parser = subparsers.add_parser("merge", help="Merge raw pnYYYY.csv files")
    merge_parser.add_argument("data_folder", nargs="?", default=DEFAULT_DATA_FOLDER)
    merge_parser.add_argument("output_file", nargs="?", default=DEFAULT_OUTPUT_FILE)
    merge_parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    merge_parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    merge_parser.add_argument("--years", nargs="+", help="Specific years or ranges, e.g. 2024 2025 or 2020-2025")
    merge_parser.add_argument("--all-years", action="store_true", help="Ignore default year range")
    merge_parser.add_argument("--keep-invalid", action="store_true", help="Keep rows without valid coordinates")

    validate_parser = subparsers.add_parser("validate", help="Validate a processed CSV file")
    validate_parser.add_argument("csv_file")

    audit_parser = subparsers.add_parser("audit", help="Compare processed CSV values against raw source CSV values")
    audit_parser.add_argument("data_folder", nargs="?", default=DEFAULT_DATA_FOLDER)
    audit_parser.add_argument("processed_file", nargs="?", default=DEFAULT_OUTPUT_FILE)
    audit_parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    audit_parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    audit_parser.add_argument("--years", nargs="+", help="Specific years or ranges, e.g. 2024 2025 or 2020-2025")
    audit_parser.add_argument("--all-years", action="store_true", help="Ignore default year range")

    stats_parser = subparsers.add_parser("stats", help="Print quick dataset statistics")
    stats_parser.add_argument("csv_file")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "convert":
        return 0 if convert_file(args.input_file, args.output_file, args.year, args.keep_invalid) else 1

    if args.command == "merge":
        years = parse_years(args.years)
        start_year = None if args.all_years or years else args.start_year
        end_year = None if args.all_years or years else args.end_year
        ok = merge_all_files(
            args.data_folder,
            args.output_file,
            start_year=start_year,
            end_year=end_year,
            years=years,
            keep_invalid=args.keep_invalid,
        )
        return 0 if ok else 1

    if args.command == "validate":
        return 0 if validate_file(args.csv_file) else 1

    if args.command == "audit":
        years = parse_years(args.years)
        start_year = None if args.all_years or years else args.start_year
        end_year = None if args.all_years or years else args.end_year
        ok = audit_raw_preservation(
            args.data_folder,
            args.processed_file,
            start_year=start_year,
            end_year=end_year,
            years=years,
        )
        return 0 if ok else 1

    if args.command == "stats":
        print_stats(args.csv_file)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
