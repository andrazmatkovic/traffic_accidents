#!/usr/bin/env python3
"""
Download zip files from policija.si, unzip them, and delete originals.
Downloads files pn1995.zip through pn2024.zip
"""

import os
import urllib.request
import zipfile
from pathlib import Path

BASE_URL = "https://www.policija.si/baza/"
START_YEAR = 1995
END_YEAR = 2024
OUTPUT_DIR = "data"  # Change this to your desired directory

# Create output directory if it doesn't exist
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

for year in range(START_YEAR, END_YEAR + 1):
    zip_filename = f"pn{year}.zip"
    zip_url = f"{BASE_URL}{zip_filename}"
    zip_path = os.path.join(OUTPUT_DIR, zip_filename)
    
    try:
        print(f"Downloading {zip_filename}...", end=" ", flush=True)
        urllib.request.urlretrieve(zip_url, zip_path)
        print("✓")
        
        print(f"  Unzipping {zip_filename}...", end=" ", flush=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(OUTPUT_DIR)
        print("✓")
        
        print(f"  Deleting {zip_filename}...", end=" ", flush=True)
        os.remove(zip_path)
        print("✓")
        
    except urllib.error.HTTPError as e:
        print(f"✗ (HTTP {e.code})")
    except FileNotFoundError as e:
        print(f"✗ (File not found)")
    except zipfile.BadZipFile:
        print(f"✗ (Not a valid zip file)")
    except Exception as e:
        print(f"✗ ({type(e).__name__}: {e})")

print("\nDone!")
