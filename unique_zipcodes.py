#!/usr/bin/env python3
"""Extract unique ZIP codes from CSV files under data/mt-filtered and write
unique-zipcodes.csv in repository root. The output has a single header column ZIP
and preserves ZIP+4 entries when present (e.g. 59044-9338).
"""
import csv
import glob
import re

INPUT_GLOB = 'data/mt-filtered/*.csv'
OUTPUT_CSV = 'unique-zipcodes.csv'


def find_zip_in_row(row):
    """Return a ZIP-like token from a CSV row.

    Prefer explicit ZIP columns (ZIP, Zip, zip, etc.) and capture formats like:
      - 5-digit: 59044
      - ZIP+4: 59044-9338
      - 9-digit contiguous: 590449338 -> converted to 59044-9338
    """
    if not row:
        return None
    keys = ['ZIP', 'Zip', 'zip', 'postal', 'postal_code', 'postalcode', 'zipcode']
    # regex to capture 5-digit or 5-4 format
    pat = re.compile(r'(\d{5}(?:-\d{4})?)')
    nine = re.compile(r'(\d{9})')

    for k in keys:
        if k in row and row[k] is not None:
            s = str(row[k]).strip()
            if not s:
                return None
            m = pat.search(s)
            if m:
                return m.group(1)
            m2 = nine.search(s)
            if m2:
                g = m2.group(1)
                return f"{g[:5]}-{g[5:]}"
    # fallback: search all fields
    for v in row.values():
        if v is None:
            continue
        s = str(v)
        m = pat.search(s)
        if m:
            return m.group(1)
        m2 = nine.search(s)
        if m2:
            g = m2.group(1)
            return f"{g[:5]}-{g[5:]}"
    return None


def main():
    files = glob.glob(INPUT_GLOB)
    if not files:
        print(f'No input CSVs found at {INPUT_GLOB}')
        return

    zips = set()
    for path in files:
        try:
            with open(path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    z = find_zip_in_row(row)
                    if z:
                        zips.add(z)
        except Exception as e:
            print(f'Warning: failed to read {path}: {e}')

    sorted_zips = sorted(zips)
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as out:
        w = csv.writer(out)
        w.writerow(['ZIP'])
        for z in sorted_zips:
            w.writerow([z])

    print(f'Wrote {len(sorted_zips)} unique ZIP(s) to {OUTPUT_CSV}')


if __name__ == '__main__':
    main()
