#!/usr/bin/env python3
"""
Download zip files from policija.si, unzip them, and delete originals.
Downloads pn1995.zip through the current year into data/.

Years the Police have not published yet are reported and skipped: the site
answers those with an HTML page under HTTP 200 rather than a 404, so the
response is checked for being an actual zip.
"""

import datetime
import os
import urllib.request
import zipfile
from pathlib import Path

BASE_URL = "https://www.policija.si/baza/"
START_YEAR = 1995
# Follow the calendar rather than a pinned year, so the current year's file is
# picked up as soon as it is published.
END_YEAR = datetime.date.today().year
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

        if not zipfile.is_zipfile(zip_path):
            print(f"  Skipping {zip_filename} (no data published for {year})")
            continue

        print(f"  Unzipping {zip_filename}...", end=" ", flush=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(OUTPUT_DIR)
        print("✓")

    except urllib.error.HTTPError as e:
        print(f"✗ (HTTP {e.code})")
    except FileNotFoundError as e:
        print(f"✗ (File not found)")
    except zipfile.BadZipFile:
        print(f"✗ (Not a valid zip file)")
    except Exception as e:
        print(f"✗ ({type(e).__name__}: {e})")
    finally:
        # Runs on the skip path and on a mid-extract failure too, so a partial
        # or bogus download is never left behind in the data folder.
        if os.path.exists(zip_path):
            os.remove(zip_path)

print("\nDone!")
