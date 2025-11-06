import os
import csv

INPUT_DIR = 'data/all-states'
OUTPUT_DIR = 'data/mt-filtered'

def normalize_amount(value):
	if value is None:
		return value
	value = value.strip()
	if value.startswith('$'):
		value = value[1:]
	value = value.replace(',', '')
	try:
		num = float(value)
		if num.is_integer():
			return str(int(num))
		else:
			return str(num)
	except ValueError:
		return value

def filter_mt_entries(input_path, output_path, normalize_amounts=False):
	with open(input_path, newline='', encoding='utf-8') as infile:
		reader = csv.DictReader(infile)
		fieldnames = reader.fieldnames
		with open(output_path, 'w', newline='', encoding='utf-8') as outfile:
			writer = csv.DictWriter(outfile, fieldnames=fieldnames)
			writer.writeheader()
			for row in reader:
				if row.get('STATE') == 'MT':
					if normalize_amounts and 'AMOUNT' in row:
						row['AMOUNT'] = normalize_amount(row['AMOUNT'])
					writer.writerow(row)

def main():
	for filename in os.listdir(INPUT_DIR):
		if filename.endswith('-all.csv'):
			base = filename[:-8]  # remove '-all.csv'
			input_path = os.path.join(INPUT_DIR, filename)
			output_filename = f'{base}-mt.csv'
			output_path = os.path.join(OUTPUT_DIR, output_filename)
			# Only normalize AMOUNT for prop-50
			if base == 'prop-50':
				filter_mt_entries(input_path, output_path, normalize_amounts=True)
			else:
				filter_mt_entries(input_path, output_path)

if __name__ == '__main__':
	main()
