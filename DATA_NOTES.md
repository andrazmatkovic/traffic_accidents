# Data Notes

## Source

The dataset is derived from public CSV files published by the Slovenian Police:

https://www.policija.si/o-slovenski-policiji/statistika/prometna-varnost

Raw files are stored as `data/pnYYYY.csv`. They use semicolon-separated CSV and
D96/TM coordinates.

## Processing

`manage_csv.py` converts the source coordinates to WGS84 latitude/longitude,
adds a `year` column, drops rows without valid coordinates, and merges the
selected years into `accidents.csv`.

The source files contain participant-level rows. The processed map dataset keeps
one row per accident by de-duplicating `year + ZaporednaStevilkaPN`. This makes
the website suitable for accident location visualization, but it is not a full
participant-level analytical dataset.

`csv_to_json.py --chunks accidents.csv data` converts `accidents.csv` into a
small `data/manifest.json` file and per-year `data/accidents-YYYY.json.gz`
chunks. The GitHub Pages website loads the newest year first and downloads the
remaining years in the background.

Run `python3 manage_csv.py audit data accidents.csv` after regenerating data to
verify that source CSV fields such as `UraPN`, `SifraOdsekaUlice`, and other
identifier/code fields were not converted or reformatted.

## Known Limitations

- Rows without valid coordinates are excluded from the map.
- Coordinates are shown as provided by the source data after conversion.
- Current-year data may be partial if the source file is updated during the year.
- Category names and timestamps are preserved from the source data where possible.
- The project is not an official Slovenian Police publication.

## Privacy

The public source data does not contain names. The website should still be used
as an aggregate public-interest map, not as a tool for identifying or profiling
individual people involved in accidents.

## Attribution

Data: Slovenian Police traffic safety statistics.

Map tiles: OpenStreetMap contributors.
