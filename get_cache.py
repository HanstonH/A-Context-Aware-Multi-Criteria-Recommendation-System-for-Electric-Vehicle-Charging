import json
import os


CACHE_FILE = 'data/poi_cache.json'
class CacheManager:
    def __init__(self, cache_file=CACHE_FILE):
        self.cache_file = cache_file
        
    def load_cache(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        return {}

    def save_to_cache(self, cache):
        with open(self.cache_file, 'w') as f:
            json.dump(cache, f, indent=4)

# --- How you use it in your code ---
def main():
    cache_manager = CacheManager()
    cache = cache_manager.load_cache()
    print(cache)
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