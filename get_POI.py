import os
import requests
import pandas as pd
from get_cache import CacheManager
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
BASE_URL = "https://places.googleapis.com/v1/places:searchNearby?key=" + API_KEY

cache = CacheManager()

class Get_POI:
    def __init__(self):
        pass

    def call_API(self, latitude, longitude):
        if cache.check_cache(latitude, longitude):
            print("Using cache")
            return cache.get_data(latitude, longitude)
        
        else:
            headers = {
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.evChargeOptions,places.rating,places.userRatingCount,places.priceLevel,places.currentOpeningHours,places.googleMapsUri,places.websiteUri"
            }

            payload = {
                "includedTypes": ["coffee_shop", "restaurant", "shopping_mall", "park"],
                "locationRestriction": {
                    "circle": {
                        "center": {"latitude": latitude, "longitude": longitude},
                        "radius": 500.0
                    }
                }
            }

            response = requests.post(BASE_URL, json=payload, headers=headers)

            if response.status_code == 200:
                data = response.json() 
                cache.save_to_cache(latitude, longitude, data)
                return data
            else:
                print(f"API Error: {response.status_code}")
                return None
        

# Example usage for a station in Taoyuan
# Use pandas to get coordinate of the EV station

def main():
    MOCK_DATASET = r"data\taiwan_ev_station_mock.csv"
    EV_station_dataset = pd.read_csv(MOCK_DATASET)

    lat, lng = EV_station_dataset.loc[1, ['latitude', 'longitude']]

    get_poi = Get_POI()
    data = get_poi.call_API(latitude=lat, longitude=lng)

    print(data)


if __name__ == "__main__":
    main()
