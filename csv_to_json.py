#!/usr/bin/env python3
"""
Convert large CSV to compressed JSON format
Usage: python3 csv_to_json.py accidents.csv
"""

import csv
import json
import gzip
import sys
from pathlib import Path

def convert_csv_to_compressed_json(csv_file, output_file=None):
    if output_file is None:
        output_file = Path(csv_file).stem + '.json.gz'
    
    print(f"Reading CSV: {csv_file}")
    data = []
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        total_rows = 0
        
        for idx, row in enumerate(reader):
            if idx % 10000 == 0:
                print(f"  Processed {idx} rows...")
            
            try:
                # Only include rows with valid coordinates
                lat = float(row.get('latitude', ''))
                lon = float(row.get('longitude', ''))
                year = int(row.get('year', ''))
                
                if lat and lon:
                    data.append({
                        'latitude': round(lat, 6),  # Reduce precision for smaller file
                        'longitude': round(lon, 6),
                        'year': year,
                        'KlasifikacijaNesrece': row.get('KlasifikacijaNesrece', ''),
                        'TipNesrece': row.get('TipNesrece', ''),
                        'VremenskeOkoliscine': row.get('VremenskeOkoliscine', ''),
                        'StanjePrometa': row.get('StanjePrometa', ''),
                        'StanjeVozisca': row.get('StanjeVozisca', ''),
                        'VNaselju': row.get('VNaselju', ''),
                        'TekstCesteNaselja': row.get('TekstCesteNaselja', ''),
                        'DatumPN': row.get('DatumPN', ''),
                        'UraPN': row.get('UraPN', '')
                    })
                    total_rows += 1
            except (ValueError, KeyError):
                continue
    
    print(f"Total valid records: {total_rows}")
    
    # Convert to JSON and compress
    print(f"Compressing to: {output_file}")
    json_str = json.dumps(data, separators=(',', ':'))
    print(f"  JSON size: {len(json_str) / 1024 / 1024:.2f} MB")
    
    with gzip.open(output_file, 'wt', encoding='utf-8', compresslevel=9) as f:
        f.write(json_str)
    
    compressed_size = Path(output_file).stat().st_size / 1024 / 1024
    print(f"  Compressed size: {compressed_size:.2f} MB")
    print(f"  Compression ratio: {(1 - compressed_size / (len(json_str) / 1024 / 1024)) * 100:.1f}%")
    print("✓ Done!")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 csv_to_json.py <csv_file> [output_file]")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not Path(csv_file).exists():
        print(f"Error: File not found: {csv_file}")
        sys.exit(1)
    
    convert_csv_to_compressed_json(csv_file, output_file)

