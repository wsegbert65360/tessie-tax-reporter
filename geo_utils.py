import math

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculates the distance in miles between two GPS points using Haversine formula."""
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return float('inf')
    
    # Radius of Earth in miles
    R = 3958.8
    
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi/2)**2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# Exact coordinates for known farm-related points
FARM_LOCATIONS = {
    "HOME_BASE": (38.5321, -93.5210), 
    "CLINTON_FSA": (38.3712, -93.7715),
    "WINDSOR_CHURCH": (38.5315, -93.5188)
}

def check_geofence(lat, lon, threshold_miles=0.15):
    """Returns the name of a known location if within the threshold distance."""
    for name, coords in FARM_LOCATIONS.items():
        # Using a tighter threshold for home/church to avoid overlap
        limit = 0.05 if name in ["HOME_BASE", "WINDSOR_CHURCH"] else threshold_miles
        dist = calculate_distance(lat, lon, coords[0], coords[1])
        if dist <= limit:
            return name
    return None
