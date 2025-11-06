#!/usr/bin/env python3
"""Produce a 'half aggregated' GeoJSON for prop-50:
- Aggregate all donors from BOZEMAN, MISSOULA, LIVINGSTON into three features
  (one per city) with NAME OF CONTRIBUTOR set to the city and AMNT equal to
  the summed amount. Other properties (ZIP, EMPLOYER, etc.) are empty strings.
- For all other rows, produce individual Point features using ZIP coords if
  available (fall back to municipality centroid).

Output: output/part-aggregated/prop-50-mt-partial.geojson
"""
import csv
import json
import os
from pathlib import Path

INPUT_CSV = Path('data/mt-filtered/prop-50-mt.csv')
ZIP_CSV = Path('data/zipcodes.csv')
MUNI_GEOJSON = Path('data/mt-municipalities-1m.geojson')
OUTPUT_DIR = Path('output/part-aggregated')
OUTPUT_FILE = OUTPUT_DIR / 'prop-50-mt-partial.geojson'

# Cities to aggregate (normalized lower-case)
AGG_CITIES = {'bozeman', 'missoula', 'livingston'}

# Fixed coordinates (lon, lat) for aggregated cities
FIXED_COORDS = {
    'bozeman': [-111.0640, 45.6903],
    'missoula': [-113.9957, 46.8729],
    'livingston': [-110.5600, 45.6556],
}


def parse_amount(s):
    if s is None:
        return 0.0
    s = str(s).strip().replace('$', '').replace(',', '')
    if s == '':
        return 0.0
    try:
        return float(s)
    except Exception:
        return 0.0


def load_zip_map():
    # load ZIP mapping similar to other scripts; support ZIP+4 and 5-digit
    mapping = {}
    path = ZIP_CSV if ZIP_CSV.exists() else None
    if not path:
        # try to find any csv with 'zip' in data/
        for fn in os.listdir('data'):
            if fn.lower().endswith('.csv') and 'zip' in fn.lower():
                path = Path('data') / fn
                break
    if not path or not path.exists():
        print('No ZIP mapping found, ZIP lookups disabled')
        return mapping
    with path.open(newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            # heuristics to find columns
            keys = {k.lower(): k for k in row.keys()}
            zip_k = keys.get('zip') or keys.get('postal code') or keys.get('postal_code') or keys.get('postalcode')
            lat_k = keys.get('latitude') or keys.get('lat')
            lon_k = keys.get('longitude') or keys.get('lon') or keys.get('lng')
            if not zip_k or not lat_k or not lon_k:
                for k in row:
                    kl = k.lower()
                    if 'zip' in kl and not zip_k:
                        zip_k = k
                    if 'lat' in kl and not lat_k:
                        lat_k = k
                    if ('lon' in kl or 'lng' in kl) and not lon_k:
                        lon_k = k
            if not zip_k or not lat_k or not lon_k:
                continue
            raw = (row.get(zip_k) or '').strip()
            if not raw:
                continue
            digits = ''.join(ch for ch in raw if ch.isdigit())
            if '-' in raw:
                full = raw
            elif len(digits) == 9:
                full = f"{digits[:5]}-{digits[5:]}"
            else:
                full = digits[:5]
            try:
                lat = float(row.get(lat_k))
                lon = float(row.get(lon_k))
            except Exception:
                continue
            mapping[full] = [lon, lat]
            five = full.split('-')[0]
            if five not in mapping:
                mapping[five] = [lon, lat]
    print(f'Loaded {len(mapping)} ZIP mappings from {path}')
    return mapping


def load_municipal_centroids():
    pts = {}
    if not MUNI_GEOJSON.exists():
        return pts
    with MUNI_GEOJSON.open(encoding='utf-8') as f:
        gj = json.load(f)
    for feat in gj.get('features', []):
        name = feat.get('properties', {}).get('NAME')
        if not name:
            continue
        key = name.strip().lower()
        geom = feat.get('geometry') or {}
        typ = geom.get('type')
        coords = None
        try:
            if typ == 'Polygon':
                coords = geom['coordinates'][0][0]
            elif typ == 'MultiPolygon':
                coords = geom['coordinates'][0][0][0]
        except Exception:
            coords = None
        if coords and isinstance(coords, list) and len(coords) == 2:
            pts[key] = coords
    return pts


def normalize_zip_token(s):
    s = (s or '').strip()
    if not s:
        return None
    digits = ''.join(ch for ch in s if ch.isdigit())
    if '-' in s:
        return s
    if len(digits) == 9:
        return f"{digits[:5]}-{digits[5:]}"
    if len(digits) >= 5:
        return digits[:5]
    return None


def main():
    zip_map = load_zip_map()
    muni_pts = load_municipal_centroids()

    if not INPUT_CSV.exists():
        print(f'Input not found: {INPUT_CSV}')
        return

    # accumulators
    agg_sums = {c: 0.0 for c in AGG_CITIES}
    agg_counts = {c: 0 for c in AGG_CITIES}
    features = []

    with INPUT_CSV.open(newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            city_raw = (row.get('CITY') or row.get('City') or '')
            city = city_raw.strip().lower()
            amt = parse_amount(row.get('AMNT') or row.get('AMOUNT') or '')

            if city in AGG_CITIES:
                agg_sums[city] += amt
                agg_counts[city] += 1
                continue

            # non-aggregated: produce per-row feature
            # prefer ZIP mapping
            zip_raw = (row.get('ZIP') or row.get('Zip') or row.get('zip') or '')
            zip_tok = normalize_zip_token(zip_raw)
            coords = None
            if zip_tok:
                coords = zip_map.get(zip_tok)
            if not coords:
                coords = muni_pts.get(city)
            if not coords:
                # skip if no coords
                continue
            features.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': coords}, 'properties': row})

    # add aggregated features (one per AGG_CITIES city)
    for c in AGG_CITIES:
        total = agg_sums.get(c, 0.0)
        if total == 0.0:
            continue
        coords = FIXED_COORDS.get(c)
        if not coords:
            # fallback to municipality centroid
            coords = muni_pts.get(c)
        if not coords:
            continue
        props = {
            'NAME OF CONTRIBUTOR': c.title(),
            'AMNT': str(int(round(total))) if abs(total - int(total)) < 1e-9 else str(total)
        }
        # ensure other common columns are present but empty
        for k in ['ZIP', 'EMPLOYER', 'ADDRESS', 'PHONE']:
            props[k] = ''
        features.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': coords}, 'properties': props})

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = {'type': 'FeatureCollection', 'features': features}
    with OUTPUT_FILE.open('w', encoding='utf-8') as fo:
        json.dump(out, fo, indent=2)

    print(f'Wrote {len(features)} features to {OUTPUT_FILE}')
    for c in AGG_CITIES:
        print(f'{c.title()}: donors={agg_counts.get(c,0)}, total=${int(round(agg_sums.get(c,0.0))):,}')


if __name__ == '__main__':
    main()
