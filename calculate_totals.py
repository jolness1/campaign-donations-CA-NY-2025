#!/usr/bin/env python3
"""Calculate donor count and total amount for a given set of cities in prop-50-mt.csv.

Usage: python3 calculate_totals.py
"""
import csv
from pathlib import Path

INPUT_PATH = Path('data/mt-filtered/prop-50-mt.csv')
# Cities to include (case-insensitive)
CITIES = {
    'whitefish', 'columbia falls', 'kalispell', 'polson', 'ronan',
    'alberton', 'missoula', 'stevensville', 'hamilton'
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

def get_amount_from_row(row):
    # prefer common keys
    for k in row:
        if not k:
            continue
        kl = k.lower()
        if kl in ('amnt', 'amount'):
            return parse_amount(row.get(k))
    # fallback: any field containing 'am'
    for k in row:
        if k and 'am' in k.lower():
            return parse_amount(row.get(k))
    return 0.0

def main():
    if not INPUT_PATH.exists():
        print(f"Input file not found: {INPUT_PATH}")
        return

    donors = 0
    total = 0.0
    max_amt = None
    min_amt = None
    

    with INPUT_PATH.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            city_raw = (row.get('CITY') or row.get('City') or '')
            city = city_raw.strip().lower()
            if city in CITIES:
                donors += 1
                amt = get_amount_from_row(row)
                total += amt
                if max_amt is None or amt > max_amt:
                    max_amt = amt
                if min_amt is None or amt < min_amt:
                    min_amt = amt

    # Format total as rounded dollars with commas
    total_rounded = round(total)
    print(f"Donors: {donors}")
    print(f"Total: ${total_rounded:,}")
    if max_amt is not None:
        print(f"Highest: ${max_amt:,.2f}")
    if min_amt is not None:
        print(f"Lowest: ${min_amt:,.2f}")

if __name__ == '__main__':
    main()
