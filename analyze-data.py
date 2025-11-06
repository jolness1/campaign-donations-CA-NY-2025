import os
import csv

INPUT_DIR = 'data/mt-filtered'
OUTPUT_FILE = 'output/totals.txt'

def get_amount_field(row):
	# Prefer AMNT, fallback to AMOUNT
	return row.get('AMNT') or row.get('AMOUNT')

def parse_amount(val):
	if val is None:
		return 0.0
	val = val.strip().replace('$', '').replace(',', '')
	try:
		return float(val)
	except ValueError:
		return 0.0

def main():
	results = []
	for filename in os.listdir(INPUT_DIR):
		if filename.endswith('-mt.csv'):
			base = filename[:-7]  # remove '-mt.csv'
			path = os.path.join(INPUT_DIR, filename)
			total = 0.0
			with open(path, newline='', encoding='utf-8') as f:
				reader = csv.DictReader(f)
				for row in reader:
					amt = parse_amount(get_amount_field(row))
					total += amt
			# Format as integer if no decimals, else two decimals
			if total.is_integer():
				total_str = f"${int(total)}"
			else:
				total_str = f"${total:.2f}"
			results.append(f"{base} - {total_str}")
	# Write output
	os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
	with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
		for line in results:
			out.write(line + '\n')

if __name__ == '__main__':
	main()
