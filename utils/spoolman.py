import requests


def get_spools(spoolman_url):
    url = spoolman_url.rstrip('/')
    resp = requests.get(f'{url}/api/v1/spool', timeout=10)
    resp.raise_for_status()
    spools_raw = resp.json()
    spools = []
    for s in spools_raw:
        filament = s.get('filament') or {}
        vendor = filament.get('vendor') or {}
        name_parts = []
        if vendor.get('name'):
            name_parts.append(vendor['name'])
        if filament.get('name'):
            name_parts.append(filament['name'])

        # Price: check spool-level first, then filament-level
        price = s.get('price')
        if price is None or price == 0:
            price = filament.get('price')
        if price is None:
            price = 0

        location = s.get('location') or ''

        spools.append({
            'id': s.get('id'),
            'name': ' '.join(name_parts) or f"Spule #{s.get('id')}",
            'material': filament.get('material', ''),
            'color_hex': filament.get('color_hex', ''),
            'remaining_weight': s.get('remaining_weight', 0),
            'spool_weight': filament.get('weight', 1000),
            'price': float(price),
            'filament_type': filament.get('material', 'PLA'),
            'location': location,
        })
    return spools
