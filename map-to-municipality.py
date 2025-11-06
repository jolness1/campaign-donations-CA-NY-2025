import os
import csv
import json

INPUT_DIR = 'data/mt-filtered'
GEOJSON_PATH = 'data/mt-municipalities-1m.geojson'
OUTPUT_DIR = 'output/geojson'
OUTPUT_AGG = 'output/aggregated-geojson'
ZIP_MAPPING_PATH = 'data/mt-zipcodes.csv'  # optional zipcode -> lat/lon CSV

def load_municipalities():
	with open(GEOJSON_PATH, encoding='utf-8') as f:
		gj = json.load(f)
	# Map city name (lowercase, stripped) to a single point from the polygon
	city_points = {}
	for feat in gj['features']:
		# Use NAME field - it has the clean city name
		name = feat['properties'].get('NAME')
		if not name:
			continue
		# Clean and normalize: strip whitespace, remove \r\n, convert to lowercase
		name = name.strip().replace('\r\n', '').replace('\r', '').replace('\n', '').lower()
		
		# Handle both Polygon and MultiPolygon geometries
		geom_type = feat['geometry']['type']
		coords = None
		
		if geom_type == 'Polygon':
			# For Polygon: coordinates[0][0] is the first point
			coords = feat['geometry']['coordinates'][0][0]
		elif geom_type == 'MultiPolygon':
			# For MultiPolygon: coordinates[0][0][0] is the first point of the first polygon
			coords = feat['geometry']['coordinates'][0][0][0]
		
		# Ensure coords is a flat [lon, lat] list of numbers
		if coords and isinstance(coords, list) and len(coords) == 2 and all(isinstance(x, (int, float)) for x in coords):
			city_points[name] = coords
			# Also add common aliases
			if name == 'butte-silver bow':
				city_points['butte'] = coords
			elif name == 'anaconda-deer lodge county':
				city_points['anaconda'] = coords
	
	return city_points


def parse_amount(s):
	"""Parse amount-like strings to float. Handles $, commas, empty values."""
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
	# Look for common amount field names (case-insensitive)
	for k in row:
		if not k:
			continue
		kl = k.lower()
		if kl in ('amnt', 'amount'):
			return parse_amount(row.get(k))
	# fallback: try any field that contains 'am' and a digit
	for k in row:
		if k and 'am' in k.lower():
			return parse_amount(row.get(k))
	return 0.0

def main():
	os.makedirs(OUTPUT_DIR, exist_ok=True)
	city_points = load_municipalities()

	# attempt to load zipcode mapping if available; this is optional
	def load_zip_codes():
		zip_points = {}
		# primary expected path
		path = ZIP_MAPPING_PATH
		if not os.path.exists(path):
			# try to find any csv in data/ that contains 'zip'
			for fn in os.listdir('data'):
				if fn.lower().endswith('.csv') and 'zip' in fn.lower():
					path = os.path.join('data', fn)
					break
		if not os.path.exists(path):
			print(f"No ZIP mapping CSV found at {ZIP_MAPPING_PATH} or in data/; ZIP lookups disabled")
			return zip_points
		# read CSV - support a few column name variants
		with open(path, newline='', encoding='utf-8') as zf:
			r = csv.DictReader(zf)
			for row in r:
				# find zip column
				zip_k = None
				lat_k = None
				lon_k = None
				for k in row:
					kl = k.lower()
					if 'zip' == kl or kl.startswith('zip'):
						zip_k = k
					elif kl in ('lat', 'latitude'):
						lat_k = k
					elif kl in ('lon', 'lng', 'long', 'longitude'):
						lon_k = k
				# fallback: attempt common names
				if zip_k is None:
					for k in row:
						if 'zip' in k.lower():
							zip_k = k
				if lat_k is None or lon_k is None:
					for k in row:
						kl = k.lower()
						if 'lat' in kl and lat_k is None:
							lat_k = k
						if ('lon' in kl or 'lng' in kl or 'long' in kl) and lon_k is None:
							lon_k = k
				if not zip_k or not lat_k or not lon_k:
					continue
				raw_zip = (row.get(zip_k) or '').strip()
				if raw_zip == '':
					continue
				# normalize zip token: accept 5-digit, 5-4 (ZIP+4), or 9-digit contiguous
				zip_digits = ''.join(ch for ch in raw_zip if ch.isdigit())
				full = None
				if '-' in raw_zip:
					# assume in correct 5-4 format if it contains a dash
					full = raw_zip
				elif len(zip_digits) == 9:
					full = f"{zip_digits[:5]}-{zip_digits[5:]}"
				elif len(zip_digits) >= 5:
					full = zip_digits[:5]
				else:
					continue
				zip5 = full.split('-')[0]
				try:
					lat = float(row.get(lat_k))
					lon = float(row.get(lon_k))
					# store full token mapping
					zip_points[full] = [lon, lat]
					# ensure a 5-digit fallback exists (don't overwrite existing 5-digit entries)
					if zip5 not in zip_points:
						zip_points[zip5] = [lon, lat]
				except Exception:
					continue
		print(f"Loaded {len(zip_points)} ZIP mappings from {path}")
		return zip_points

	zip_points = load_zip_codes()

	# override/add requested manual coordinates for specific aliases (user-provided lon, lat)
	city_points['butte'] = [-112.5393, 45.9987]
	city_points['anaconda'] = [-112.9438, 46.1243]

	print(f"Loaded {len(city_points)} municipalities")
	print(f"Sample cities: {list(city_points.keys())[:10]}")

	for filename in os.listdir(INPUT_DIR):
		if filename.endswith('-mt.csv'):
			base = filename[:-7]
			input_path = os.path.join(INPUT_DIR, filename)
			output_path = os.path.join(OUTPUT_DIR, f'{base}-mt.geojson')
			features = []
			matched = set()
			unmatched = set()
			# aggregator for this file (only includes matched cities)
			agg = {}
			with open(input_path, newline='', encoding='utf-8') as f:
				reader = csv.DictReader(f)
				for row in reader:
					# Prefer ZIP coordinates for per-row (non-aggregated) features when available
					zip_raw = (row.get('ZIP') or row.get('Zip') or row.get('zip') or '')
					zip_coords = None
					if zip_raw:
						r = str(zip_raw).strip()
						digits = ''.join(ch for ch in r if ch.isdigit())
						full_token = None
						if '-' in r:
							full_token = r
						elif len(digits) == 9:
							full_token = f"{digits[:5]}-{digits[5:]}"
						elif len(digits) >= 5:
							full_token = digits[:5]
						if full_token:
							# try full token first, then 5-digit fallback
							zip_coords = zip_points.get(full_token) or zip_points.get(full_token.split('-')[0])
					city_raw = (row.get('CITY') or row.get('City') or '')
					city = city_raw.strip().lower()
					coords = zip_coords if zip_coords else city_points.get(city)
					if coords:
						matched.add(city)
						# feature for each row
						feature = {
							"type": "Feature",
							"geometry": {"type": "Point", "coordinates": coords},
							"properties": row
						}
						features.append(feature)
						# aggregate amounts
						amt = get_amount_from_row(row)
						if city not in agg:
							agg[city] = {
								'city': city_raw.strip(),
								'state': (row.get('STATE') or row.get('State') or '').strip(),
								'sum': 0.0,
								'coords': coords
							}
						agg[city]['sum'] += amt
					else:
						if city:  # only track non-empty cities
							unmatched.add(city)
			
			geojson = {
				"type": "FeatureCollection",
				"features": features
			}
			with open(output_path, 'w', encoding='utf-8') as out:
				json.dump(geojson, out, indent=2)
			# write aggregated geojson for this file
			os.makedirs(OUTPUT_AGG, exist_ok=True)
			agg_features = []
			for c, info in agg.items():
				coords = info.get('coords')
				if not coords:
					continue
				total = info.get('sum', 0.0)
				# format amount: integer-like values should be whole numbers
				if abs(total - int(total)) < 1e-9:
					amt_str = str(int(total))
				else:
					amt_str = str(total)
				agg_features.append({
					"type": "Feature",
					"geometry": {"type": "Point", "coordinates": coords},
					"properties": {"CITY": info.get('city'), "STATE": info.get('state'), "AMNT": amt_str}
				})
			agg_geo = {"type": "FeatureCollection", "features": agg_features}
			agg_path = os.path.join(OUTPUT_AGG, f'{base}-mt-aggregated.geojson')
			with open(agg_path, 'w', encoding='utf-8') as aout:
				json.dump(agg_geo, aout, indent=2)
			
			print(f"\n{filename}:")
			print(f"  Matched {len(matched)} unique cities: {sorted(matched)}")
			print(f"  Unmatched {len(unmatched)} unique cities: {sorted(unmatched)}")
			print(f"  Aggregated {len(agg_features)} cities written to {agg_path}")

if __name__ == '__main__':
	main()
