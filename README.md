# Traffic Accidents in Slovenia

Interactive map of traffic accidents in Slovenia: [prometnenesrece.si](https://prometnenesrece.si).

Data source: [Slovenian Police - Traffic Safety](https://www.policija.si/o-slovenski-policiji/statistika/prometna-varnost).

## Website

The public site is a static GitHub Pages website. It serves:

- `index.html` for the Leaflet map UI.
- `styles.css`, `src/i18n.js`, and `src/app.js` for static app assets.
- `data/manifest.json` for available years, record counts, and filter options.
- `data/accidents-YYYY.json.gz` for per-year accident chunks loaded by the browser.
- `decompress-worker-json.js` to decompress the dataset in a Web Worker.

The site loads the latest available year first, then downloads older years in the background. This keeps the first map render small while still making the all-years view available after hydration.

Run it locally with a web server:

```bash
python3 -m http.server 8000
```

Then open <http://localhost:8000>. Opening `index.html` directly with `file://` may fail in some browsers because the app fetches JSON files from `data/`.

Deploy by pushing to the GitHub Pages branch/source:

```bash
git push origin main
```

## Data Pipeline

Install the data-processing dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Rebuild everything the website serves in one step -- merge, validate, audit,
and write the JSON chunks:

```bash
python3 manage_csv.py build
```

`accidents.csv` is an intermediate, not a deliverable: nothing at runtime reads
it and it is reproducible from the raw files, so `build` removes it once the
chunks exist. Pass `--keep-csv` to hold on to it, and note that it is kept
automatically if validation or the audit fails.

The individual steps are still available. Merge raw Police CSV files from
`data/pnYYYY.csv` into `accidents.csv`:

```bash
python3 manage_csv.py merge data accidents.csv
```

Regenerate the browser payload:

```bash
python3 csv_to_json.py --chunks accidents.csv data
```

Validate the processed CSV:

```bash
python3 manage_csv.py validate accidents.csv
```

Audit that raw source fields were preserved exactly:

```bash
python3 manage_csv.py audit data accidents.csv
```

Print quick dataset statistics:

```bash
python3 manage_csv.py stats accidents.csv
```

Recommended update flow:

```bash
python3 manage_csv.py merge data accidents.csv
python3 manage_csv.py validate accidents.csv
python3 manage_csv.py audit data accidents.csv
python3 csv_to_json.py --chunks accidents.csv data
```

## Useful Commands

Convert one raw CSV file:

```bash
python3 manage_csv.py convert data/pn2025.csv
```

Merge all available years instead of the default 2015-2025 range:

```bash
python3 manage_csv.py merge data accidents.csv --all-years
```

Merge specific years:

```bash
python3 manage_csv.py merge data accidents.csv --years 2024 2025
python3 manage_csv.py merge data accidents.csv --years 2020-2025
```

## Data Notes

Raw Police files use semicolon-separated CSV and D96/TM coordinates. The processing script converts coordinates to WGS84 latitude/longitude for Leaflet.

The CSV reader intentionally preserves raw columns as text. This matters for fields such as `UraPN`, `SifraOdsekaUlice`, and `VozniskiStazVMesecih`, where values like `08.10`, `00055`, or `06` must not be converted to `8.1`, `55`, or `6`.

Use `python3 manage_csv.py audit data accidents.csv` after regenerating data to catch accidental type conversion or formatting loss in source columns.

The raw Police CSV files are participant-level records. The processed map dataset keeps one row per accident by de-duplicating `year + ZaporednaStevilkaPN`, so the map is useful for accident locations rather than participant-level analysis.

Rows without valid coordinates are skipped. Coordinates, categories, and timestamps are shown as provided by the source data after format conversion; this project is not an official Police publication.

More detail: [DATA_NOTES.md](DATA_NOTES.md).

## Attribution

Data: Slovenian Police traffic safety statistics.

Map tiles: OpenStreetMap contributors.

## License

This project is licensed under the Creative Commons Attribution-NonCommercial 4.0 International License. See [LICENSE](LICENSE).
