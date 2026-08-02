# This code written by Google Gemini given this prompt:
#   Could you write a python function that computes the great circle
#   distance between two points given in longitude and latitude?

import math

def great_circle_distance(lat1: float, lon1: float, lat2: float, lon2: float, radius_earth_km: float = 6371.0) -> float:
    """
    Computes the great-circle distance between two points on the Earth's surface
    given their latitudes and longitudes, using the Haversine formula.

    Args:
        lat1 (float): Latitude of the first point in degrees.
        lon1 (float): Longitude of the first point in degrees.
        lat2 (float): Latitude of the second point in degrees.
        lon2 (float): Longitude of the second point in degrees.
        radius_earth_km (float): The radius of the Earth in kilometers.
                                 Defaults to 6371.0 km (average Earth radius).

    Returns:
        float: The great-circle distance between the two points in kilometers.
    """

    # Convert latitudes and longitudes from degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Haversine formula components
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Calculate the distance
    distance = radius_earth_km * c

    return distance

# Example Usage:
if __name__ == "__main__":
    # Coordinates for New York City (approx)
    nyc_lat, nyc_lon = 40.7128, -74.0060

    # Coordinates for London (approx)
    london_lat, london_lon = 51.5074, -0.1278

    distance_nyc_london = great_circle_distance(nyc_lat, nyc_lon, london_lat, london_lon)
    print(f"Distance between New York City and London: {distance_nyc_london:.2f} km")

    # Coordinates for Los Angeles (approx)
    la_lat, la_lon = 34.0522, -118.2437

    # Coordinates for Tokyo (approx)
    tokyo_lat, tokyo_lon = 35.6895, 139.6917

    distance_la_tokyo = great_circle_distance(la_lat, la_lon, tokyo_lat, tokyo_lon)
    print(f"Distance between Los Angeles and Tokyo: {distance_la_tokyo:.2f} km")

    # Test with same point (should be 0)
    distance_self = great_circle_distance(nyc_lat, nyc_lon, nyc_lat, nyc_lon)
    print(f"Distance from NYC to NYC: {distance_self:.2f} km")
