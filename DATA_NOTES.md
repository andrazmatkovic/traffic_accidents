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

`python3 manage_csv.py build` runs the whole sequence and then deletes
`accidents.csv`, which is an intermediate rather than a published artifact: the
website never fetches it, and it can be rebuilt from `data/pnYYYY.csv` at any
time. It is not tracked in git, so that a 76 MB blob is not committed on every
data refresh.

Run `python3 manage_csv.py audit data accidents.csv` after regenerating data to
verify that source CSV fields such as `UraPN`, `SifraOdsekaUlice`, and other
identifier/code fields were not converted or reformatted.

## Source Format Changes

The Police changed the raw file format starting with `pn2025.csv`. Both shapes
are handled, but the differences are worth knowing before touching the pipeline:

- **Encoding.** `pn2015.csv` to `pn2024.csv` are UTF-8; `pn2025.csv` onward are
  windows-1250. Encoding is detected per file. Detection cannot rely on decode
  errors alone, because iso-8859-2 maps every byte and so "succeeds" on a
  windows-1250 file while turning S-caron and Z-caron into C1 control
  characters. `detect_encoding` rejects a decode that produces those.
- **Time.** Up to `pn2024.csv`, `UraPN` is a zero-padded `HH.MM`. From
  `pn2025.csv` it is a bare hour with no minutes, using the range 0-24 where 24
  means midnight. `accidents.csv` keeps whichever form the source used, so the
  audit stays byte-exact; `csv_to_json.py` renders the bare hour as `HH.00` for
  the website. The `.00` is padding, not a measured value.
- **Blank categories.** A few rows have an empty `KlasifikacijaNesrece` or
  `VNaselju`. `csv_to_json.py` labels these `NEDOLOČENO` in the browser payload
  so they do not appear as an empty filter option. This is distinct from
  `NEZNANO`, which is a real source category for weather and traffic.

Normalisation for display belongs in `csv_to_json.py`, not in `accidents.csv`.
The audit compares the processed CSV against the raw source field by field, so
reformatting the CSV would defeat the check.

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
