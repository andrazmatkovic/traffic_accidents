#!/usr/bin/env python3
"""
Fix character encoding issues in CSV files (no external dependencies).
Converts corrupted Slovenian characters (č, š, ž) to proper UTF-8.
"""

import os
import glob

def fix_encoding_simple(input_file, output_file=None):
    """Fix encoding in a file without external dependencies."""
    if output_file is None:
        output_file = input_file
    
    # Read the file as binary
    with open(input_file, 'rb') as f:
        raw_data = f.read()
    
    # Try different encodings in order
    encodings_to_try = [
        'utf-8',
        'windows-1250',  # Central European (most likely for Slovenian)
        'iso-8859-2',    # Latin 2
        'cp1250',        # Windows Central European
    ]
    
    text = None
    used_encoding = None
    
    for encoding in encodings_to_try:
        try:
            text = raw_data.decode(encoding)
            used_encoding = encoding
            break
        except:
            continue
    
    if text is None:
        print(f"  ✗ Could not decode file")
        return
    
    # Write as UTF-8
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(text)
    
    print(f"  ✓ Converted from {used_encoding} to UTF-8")

# Find all CSV files in current directory
csv_files = glob.glob("*.csv")

if not csv_files:
    print("No CSV files found in current directory")
else:
    print(f"Found {len(csv_files)} CSV file(s)\n")
    
    for csv_file in csv_files:
        print(f"Processing: {csv_file}")
        try:
            fix_encoding_simple(csv_file)
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    print("\nDone!")
