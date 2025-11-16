#!/usr/bin/env python3
"""
Utility script for managing traffic accident CSV files
Processes all files from data folder, converts coordinates based on year,
and merges into a single accidents.csv file
"""

import pandas as pd
import glob
import os
import re
from pyproj import Transformer
import numpy as np
import sys

# ============= CONFIGURATION =============
DATA_FOLDER = "data"  # Change this to your data folder path
OUTPUT_FILE = "accidents.csv"

# Year selection options:
# Option 1: Process all years (set both to None)
START_YEAR = 2015  # e.g., 2010
END_YEAR = 2024    # e.g., 2020

# Option 2: Process specific years only (leave empty to use START_YEAR/END_YEAR)
SPECIFIC_YEARS = []  # e.g., [2010, 2011, 2015, 2020]

# =========================================

def get_year_from_filename(filename):
    """Extract year from filename like pn2004.csv"""
    match = re.search(r'pn(\d{4})', filename)
    if match:
        return int(match.group(1))
    return None


def convert_coordinates_batch(df, year):
    """
    Vectorized coordinate conversion - much faster than row-by-row
    Converts all coordinates at once instead of one at a time
    """
    if 'GeoKoordinataX' not in df.columns or 'GeoKoordinataY' not in df.columns:
        return df
    
    # Create copies of coordinate columns
    x_coords = df['GeoKoordinataX'].copy()
    y_coords = df['GeoKoordinataY'].copy()
    
    # Convert to string and strip whitespace
    x_coords = x_coords.astype(str).str.strip()
    y_coords = y_coords.astype(str).str.strip()
    
    # Replace empty/space values with NaN
    x_coords = x_coords.replace(['', ' '], np.nan)
    y_coords = y_coords.replace(['', ' '], np.nan)
    
    # Convert to numeric, invalid values become NaN
    x_coords = pd.to_numeric(x_coords, errors='coerce')
    y_coords = pd.to_numeric(y_coords, errors='coerce')
    
    # Skip zeros and NaN values
    valid_mask = (x_coords != 0) & (y_coords != 0) & (x_coords.notna()) & (y_coords.notna())
    
    # Initialize columns
    df['latitude'] = np.nan
    df['longitude'] = np.nan
    
    if valid_mask.sum() == 0:
        print("  No valid coordinates found")
        return df
    
    try:
        # All data uses D96/TM (EPSG:3794)
        source_crs = "EPSG:3794"
        
        # Transform all valid coordinates at once (vectorized)
        transformer = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
        
        # Extract valid coordinates
        valid_x = x_coords[valid_mask].values
        valid_y = y_coords[valid_mask].values
        
        # Batch transform - use (Y, X) order for D96/TM
        lons, lats = transformer.transform(valid_y, valid_x)
        
        # Put results back into dataframe
        df.loc[valid_mask, 'longitude'] = lons
        df.loc[valid_mask, 'latitude'] = lats
        
    except Exception as e:
        print(f"  Error during coordinate transformation: {e}")
    
    return df


def process_file(csv_file, year):
    """Process a single CSV file with coordinate conversion"""
    
    # Skip files based on year configuration
    if SPECIFIC_YEARS and year not in SPECIFIC_YEARS:
        return None
    if START_YEAR is not None and year < START_YEAR:
        return None
    if END_YEAR is not None and year > END_YEAR:
        return None
    
    filename = os.path.basename(csv_file)
    print(f"Processing: {filename} (year {year})...")
    
    try:
        # Try different encodings
        df = None
        for encoding in ['utf-8', 'iso-8859-2', 'windows-1250', 'cp1250']:
            try:
                df = pd.read_csv(csv_file, sep=';', encoding=encoding)
                break
            except:
                continue
        
        if df is None:
            print(f"  ✗ Could not read file with any encoding")
            return None
        
        # Add year column
        df['year'] = year
        
        # Convert coordinates if columns exist
        if 'GeoKoordinataX' in df.columns and 'GeoKoordinataY' in df.columns:
            print(f"  Converting coordinates (D96/TM for all years)...")
            
            rows_before = len(df)
            df = convert_coordinates_batch(df, year)
            
            # Filter out rows with invalid coordinates
            df = df.dropna(subset=['latitude', 'longitude'])
            rows_after = len(df)
            rows_skipped = rows_before - rows_after
            
            if rows_skipped > 0:
                print(f"  ✓ Loaded {rows_after} rows (skipped {rows_skipped} with missing/invalid coordinates)")
            else:
                print(f"  ✓ Loaded {rows_after} rows")
            
            # Check coordinate bounds for Slovenia
            invalid = df[
                (df['latitude'] < 45) | (df['latitude'] > 47) |
                (df['longitude'] < 13) | (df['longitude'] > 16)
            ]
            if len(invalid) > 0:
                print(f"  ⚠ Warning: {len(invalid)} rows have coordinates outside Slovenia bounds")
        else:
            print(f"  ✓ Loaded {len(df)} rows (no coordinate columns found)")
        
        return df
    
    except Exception as e:
        print(f"  ✗ Error processing file: {e}")
        return None


def merge_all_files(data_folder, output_file):
    """Process all CSV files from folder and merge into one"""
    
    if not os.path.exists(data_folder):
        print(f"Error: Folder '{data_folder}' not found!")
        return False
    
    # Find all pnYYYY.csv files
    pattern = os.path.join(data_folder, 'pn*.csv')
    csv_files = sorted(glob.glob(pattern))
    
    if not csv_files:
        print(f"No pn*.csv files found in '{data_folder}'")
        return False
    
    print(f"Found {len(csv_files)} files in '{data_folder}':\n")
    
    dfs = []
    years_processed = []
    
    for csv_file in csv_files:
        year = get_year_from_filename(os.path.basename(csv_file))
        
        if year is None:
            print(f"Skipping {os.path.basename(csv_file)} (could not extract year)")
            continue
        
        df = process_file(csv_file, year)
        
        if df is not None:
            dfs.append(df)
            years_processed.append(year)
    
    if not dfs:
        print("\n✗ No files were successfully processed!")
        return False
    
    print(f"\n{'='*60}")
    print(f"Merging {len(dfs)} files...")
    
    # Merge all dataframes
    merged = pd.concat(dfs, ignore_index=True)
    
    # Remove duplicates based on year + ID (ID resets each year, so we need both)
    if 'ZaporednaStevilkaPN' in merged.columns and 'year' in merged.columns:
        merged = merged.drop_duplicates(subset=['year', 'ZaporednaStevilkaPN'])
    
    # Save merged file
    merged.to_csv(output_file, index=False, encoding='utf-8')
    
    print(f"✓ Merged file saved: {output_file}")
    print(f"\nSummary:")
    print(f"  Total accidents: {len(merged)}")
    print(f"  Years: {min(years_processed)} - {max(years_processed)}")
    print(f"  Unique years: {sorted(set(years_processed))}")
    
    if 'TipNesrece' in merged.columns:
        print(f"  Accident types: {merged['TipNesrece'].nunique()}")
    
    if 'latitude' in merged.columns and 'longitude' in merged.columns:
        valid_coords = merged.dropna(subset=['latitude', 'longitude'])
        print(f"  Rows with valid coordinates: {len(valid_coords)} / {len(merged)}")
    
    return True


# Usage
if __name__ == "__main__":
    print("Traffic Accidents - Batch Processing Tool")
    print("=" * 60)
    print(f"Data folder: {DATA_FOLDER}")
    print(f"Output file: {OUTPUT_FILE}")
    
    # Show year selection info
    if SPECIFIC_YEARS:
        print(f"Years: {sorted(SPECIFIC_YEARS)}")
    elif START_YEAR or END_YEAR:
        start = START_YEAR if START_YEAR else "1995"
        end = END_YEAR if END_YEAR else "2024"
        print(f"Years: {start} - {end}")
    else:
        print(f"Years: All available (1995-2024)")
    
    print("=" * 60 + "\n")
    
    merge_all_files(DATA_FOLDER, OUTPUT_FILE)
