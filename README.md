# Traffic Accidents in Slovenia

Interactive map of traffic accidents in Slovenia: [prometnenesrece.si](https://prometnenesrece.si).

Data source: [Slovenian Police - Traffic Safety](https://www.policija.si/o-slovenski-policiji/statistika/prometna-varnost).

## Website

The public site is a static GitHub Pages website. It serves:

- `index.html` for the Leaflet map UI.
- `accidents.json.gz` for the compressed accident dataset used by the browser.
- `decompress-worker-json.js` to decompress the dataset in a Web Worker.

## Data Pipeline

Install the data-processing dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Merge raw Police CSV files from `data/pnYYYY.csv` into `accidents.csv`:

```bash
python3 manage_csv.py merge data accidents.csv
```

Regenerate the browser payload:

```bash
python3 csv_to_json.py accidents.csv accidents.json.gz
```

Validate the processed CSV:

```bash
python3 manage_csv.py validate accidents.csv
```

Print quick dataset statistics:

```bash
python3 manage_csv.py stats accidents.csv
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

## License

This project is licensed under the Creative Commons Attribution-NonCommercial 4.0 International License. See [LICENSE](LICENSE).
