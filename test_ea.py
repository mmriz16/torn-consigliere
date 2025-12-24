from crime_advisor import calculate_ea, get_ea_level, get_all_crime_safety

cr = {'selling_illegal_products': 41, 'theft': 523, 'other': 147, 'total': 711}
ea = calculate_ea(cr)
level = get_ea_level(ea)
safety = get_all_crime_safety(ea)

print(f'EA: {ea}')
print(f'Level: {level}')
print('Safety:')
for s in safety:
    print(f"  {s['icon']} {s['name']}: {s['message']}")
