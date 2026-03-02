import requests
import time
import os

def lookup_business_at_coords(lat, lon, google_key=None):
    """
    Looks up a business name at the given coordinates.
    Tries Google Places if a key is provided, otherwise falls back to OpenStreetMap (Nominatim).
    """
    if lat is None or lon is None:
        return None

    # 1. Try Google Places (Highest quality business names)
    if google_key:
        try:
            url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lon}&radius=50&key={google_key}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                results = response.json().get('results', [])
                if results:
                    # Filter for non-generic types if possible, or just take the first
                    # Avoid "locality", "neighborhood", etc if better options exist
                    for res in results:
                        types = res.get('types', [])
                        if not any(t in types for t in ['locality', 'neighborhood', 'political', 'route']):
                             return res.get('name')
                    return results[0].get('name')
        except Exception as e:
            print(f"[MAPS ERROR] Google Places failed: {e}")

    # 2. Fallback to OpenStreetMap (Nominatim)
    try:
        # Nominatim requires a User-Agent
        headers = {'User-Agent': 'TeslaTaxReporter/1.0'}
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Nominatim returns business names in 'name' or 'amenity' or 'shop' etc.
            addr = data.get('address', {})
            # priority list for names
            potential_names = [
                data.get('name'),
                addr.get('amenity'),
                addr.get('shop'),
                addr.get('office'),
                addr.get('tourism'),
                addr.get('leisure'),
                addr.get('railway')
            ]
            for name in potential_names:
                if name:
                    return name
    except Exception as e:
        print(f"[MAPS ERROR] OSM Lookup failed: {e}")

    return None

if __name__ == "__main__":
    # Test with a known coordinate (e.g., a hardware store in Windsor)
    test_lat, test_lon = 38.530510, -93.523530 # Example near coordinate
    print(f"Testing lookup for {test_lat}, {test_lon}...")
    name = lookup_business_at_coords(test_lat, test_lon)
    print(f"Found: {name}")
