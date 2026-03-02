import requests
import time
import os
import json
import logging

logger = logging.getLogger(__name__)

CACHE_FILE = "place_cache.json"

def _load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load place cache: {e}")
            return {}
    return {}

def _save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save place cache: {e}")

# Load cache once at module level
place_cache = _load_cache()

def lookup_business_at_coords(lat, lon, google_key=None):
    """
    Looks up a business name at the given coordinates.
    Tries local cache first, then Google Places, then OpenStreetMap.
    """
    if lat is None or lon is None:
        return None

    cache_key = f"{round(lat, 5)},{round(lon, 5)}"
    if cache_key in place_cache:
        return place_cache[cache_key] if place_cache[cache_key] is not False else None

    name = None

    # 1. Try Google Places (Highest quality business names)
    if google_key:
        try:
            url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lon}&radius=50&key={google_key}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                results = response.json().get('results', [])
                if results:
                    for res in results:
                        types = res.get('types', [])
                        if not any(t in types for t in ['locality', 'neighborhood', 'political', 'route']):
                             name = res.get('name')
                             break
                    if not name:
                        name = results[0].get('name')
        except Exception as e:
            logger.error(f"Google Places lookup failed: {e}")

    # 2. Fallback to OpenStreetMap (Nominatim)
    if not name:
        try:
            headers = {'User-Agent': 'TeslaTaxReporter/1.0'}
            url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                addr = data.get('address', {})
                potential_names = [
                    data.get('name'),
                    addr.get('amenity'),
                    addr.get('shop'),
                    addr.get('office'),
                    addr.get('tourism'),
                    addr.get('leisure'),
                    addr.get('railway')
                ]
                for p_name in potential_names:
                    if p_name:
                        name = p_name
                        break
        except Exception as e:
            logger.error(f"OSM lookup failed: {e}")

    if name:
        place_cache[cache_key] = name
    else:
        place_cache[cache_key] = False # Cache the failure
    
    _save_cache(place_cache)

    return name if name is not False else None

if __name__ == "__main__":
    # Test with a known coordinate
    test_lat, test_lon = 38.530510, -93.523530
    logging.basicConfig(level=logging.INFO)
    print(f"Testing lookup for {test_lat}, {test_lon}...")
    result = lookup_business_at_coords(test_lat, test_lon)
    print(f"Found: {result}")
