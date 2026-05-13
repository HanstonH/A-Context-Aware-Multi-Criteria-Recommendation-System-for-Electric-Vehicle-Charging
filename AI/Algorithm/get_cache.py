import json
import os


CACHE_FILE = 'data/poi_cache.json'

class CacheManager:
    def __init__(self, cache_file=CACHE_FILE):
        self.cache_file = cache_file
        # Load into memory once so we don't hit the disk constantly
        self.cache_data = self._load_all_from_disk()

    def _load_all_from_disk(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    def _get_key(self, lat, lon):
        """Helper to create a unique string key for the dictionary."""
        return f"{round(lat, 5)},{round(lon, 5)}"

    def check_cache(self, latitude, longitude):
        return self._get_key(latitude, longitude) in self.cache_data

    def get_data(self, latitude, longitude):
        key = self._get_key(latitude, longitude)
        return self.cache_data.get(key)

    def save_to_cache(self, latitude, longitude, data):
        key = self._get_key(latitude, longitude)
        self.cache_data[key] = data
        
        # Write the updated dictionary back to the file
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache_data, f, indent=4)
         

# --- How you use it in your code ---
def main():
    cache_manager = CacheManager()
    cache = cache_manager.load_cache()
    print(cache)
    # Change station id to longitude and latitude
    station_id = "station_001"

    if station_id in cache:
        print("Loading from cache...")
        poi_data = cache[station_id]
        print(poi_data)
    else:
        print("Calling API...")
        # poi_data = get_poi_from_api(lat, lng)
        # cache[station_id] = poi_data
        # save_to_cache(cache)

if __name__ == "__main__":
    main()