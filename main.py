import os
import requests
from get_cache import CacheManager
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
BASE_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

# cache = CacheManager()

def get_poi_count(lat, lng, radius=500):
    """Fetches the number of cafes near a specific coordinate."""
    
    # 2. Define the parameters for the API
    params = {
        "location": f"{lat},{lng}",
        "radius": radius,
        "type": "cafe",
        "key": API_KEY
    }

    try:
        # 3. Send the GET request
        response = requests.get(BASE_URL, params=params)
        
        # 4. Check if the request was successful (Status Code 200)
        response.raise_for_status()
        
        # 5. Parse the JSON data
        data = response.json()
        print(data)
        
        # Count how many results were returned
        return data.get("results", [])

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to API: {e}")
        return 0

# Example usage for a station in Taoyuan
station_lat, station_lng = 120.2115564, 22.9828468
count = get_poi_count(station_lat, station_lng)

print(f"Found {count} cafes nearby for your MCDM model calculation!")