import json

# Load data
with open('baldr_targets.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Sort by level descending
sorted_data = sorted(data, key=lambda x: int(str(x.get('lvl', '0')).replace(',', '')), reverse=True)

# Save sorted data
with open('baldr_targets.json', 'w', encoding='utf-8') as f:
    json.dump(sorted_data, f, indent=2)

print(f'Sorted {len(sorted_data)} targets by level (high to low)')
print(f'Top 5 levels: {[(t["name"], t["lvl"]) for t in sorted_data[:5]]}')
