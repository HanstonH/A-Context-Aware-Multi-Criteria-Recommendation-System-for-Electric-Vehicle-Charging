''' 
Make a model that chooses based on 
1. Distance, done
Distance logic that needs to follow the road (not just a straight line from A to B) will not be implemented here
It is assumed that it is already implemented

2. Waiting time (How many people are using)
For waiting time, perhaps use a machine learning model to predict whether it will be vacant when you get there. Then use that value to the algorithm

3. Efficiency (how fast the cable electricity is)
Get from maxChargeRateKw in evChargeOptions PlacesAPI(new)

4. POI score (make own logic), done
'''
import pandas as pd
import numpy as np
import json
from get_Distance_EV import get_distance_ev
from get_POI import Get_POI

class Calculation_Model:

    def __init__(self, user_location):
        self.w_poi = 0.25
        self.w_eff = 0.25
        self.w_dist = 0.25
        self.w_wait = 0.25
        self.user_location = user_location
    
    def process_distances(self, df):
        """
        Applies the external distance function to every row in the dataframe.
        """
        def get_row_dist(row):
            dest = (row['lat'], row['lon'])
            # Call the imported function
            result = get_distance_ev(dest, self.user_location)
            
            # Extract just the meters from the JSON result
            if result and 'routes' in result:
                return result['routes'][0]['distanceMeters']
            return 999999 # Penalty for failed API call
            
        df['distance'] = df.apply(get_row_dist, axis=1)
        return df
    
    def total_score(self, stations_df):
        """
        Calculates the final recommendation score using weighted sum normalization.
        Expects columns: ['poi_sum', 'efficiency', 'distance', 'waiting_time']
        """
        # 1. Normalize POI (Benefit: Higher is better)
        max_poi = stations_df['poi_sum'].max()
        stations_df['n_poi'] = stations_df['poi_sum'] / max_poi if max_poi > 0 else 0

        # 2. Normalize Efficiency (Benefit: Higher is better)
        # Assuming mapped score 1-3 from your efficiency_score function
        stations_df['n_eff'] = stations_df['efficiency'] / 3.0

        # 3. Normalize Distance (Cost: Lower is better)
        d_min = stations_df['distance'].min()
        d_max = stations_df['distance'].max()
        if d_max != d_min:
            # Invert: (Max - Current) / (Max - Min)
            stations_df['n_dist'] = (d_max - stations_df['distance']) / (d_max - d_min)
        else:
            stations_df['n_dist'] = 1.0

        # 4. Normalize Waiting Time (Cost: Lower is better)
        # Using 60 mins as a standard "maximum tolerance" threshold
        stations_df['n_wait'] = (60 - stations_df['waiting_time']).clip(lower=0) / 60

        # 5. Final Weighted Sum
        stations_df['total_score'] = (
            (self.w_poi * stations_df['n_poi']) +
            (self.w_eff * stations_df['n_eff']) +
            (self.w_dist * stations_df['n_dist']) +
            (self.w_wait * stations_df['n_wait'])
        )

        return stations_df.sort_values(by='total_score', ascending=False)

    def efficiency_score(self, connector_string):
        if not connector_string or not isinstance(connector_string, str):
            return 1
    
        # Standardize to lowercase for easier matching
        s = connector_string.lower()
        
        # TIER 3: DC Fast Charging (High Efficiency)
        # These are high-wattage connectors that reduce charging time significantly.
        if any(x in s for x in ['ccs', 'chademo', 'supercharger', 'dc']):
            return 3
        
        # TIER 2: AC Medium Speed (Standard Efficiency)
        # Type 2 is common in Taiwan and Europe for standard public charging.
        if any(x in s for x in ['type 2', 'j1772', 'mennekes']):
            return 2
        
        # TIER 1: Slow / Socket only
        # These usually take several hours to charge.
        return 1


    def get_POI(self, latitude, longitude):
    # Returns JSON file of POI around as well as data of it (max 20 top POI)
        POI = Get_POI()
        return POI.call_API(latitude, longitude)

    def get_distance_score(self, destination_location, user_location):
        return get_distance_ev(destination_location, user_location)
    
    def POI_score(self, data, coordinate_key):
        # Google Places API (New) returns a dict with 'places' and 'routingSummaries' keys
        if not data or 'places' not in data:
            return 0
        
        # Use data directly instead of data[coordinate_key]
        place_list = pd.json_normalize(data, record_path=["places"])
        
        # Safely handle routingSummaries (sometimes missing if no routes found)
        if 'routingSummaries' in data:
            place_distance = pd.json_normalize(data['routingSummaries'], record_path=['legs'])
            place = pd.concat([place_list, place_distance], axis=1)
        else:
            place = place_list
            # Provide a default distance if routing failed (e.g., 500m)
            place['distanceMeters'] = 500 

        # Handle cases where rating or userRatingCount might be missing from some POIs
        place['rating'] = place['rating'].fillna(0)
        place['userRatingCount'] = place['userRatingCount'].fillna(0)

        place['poi_score'] = place.apply(self.calculate_poi_score, axis=1)
        return place['poi_score'].sum()
    
    # Helper function
    def calculate_poi_score(self, row):
        rating = row['rating']
        reviews = row['userRatingCount']
        distance = row['distanceMeters']
        
        # We add 1 to reviews to avoid log(0)
        score = (rating * np.log10(reviews + 1))/ (1 + distance/100)
        return score

    def process_all_stations(self, df):
        """
        Iterates through the dataframe, fetches POI data, 
        and calculates the POI sum for each row.
        """
        # 1. Create a unique key for each station based on coordinates
        # This matches the 'coordinate_key' used in your JSON data
        df['coord_key'] = df.apply(lambda row: f"{row['lat']},{row['lon']}", axis=1)
        

        def row_pipeline(row):
            # A. Fetch the raw JSON data (API Call)
            # Pro-tip: In a real scenario, you'd check a CACHE here first!
            raw_json = self.get_POI(row['lat'], row['lon'])
            
            # B. Calculate the POI Score for this specific row
            # We pass the coord_key so the function knows which part of the JSON to read
            score = self.POI_score(raw_json, row['coord_key'])
            return score

        # 2. Apply the pipeline to every row
        print("Fetching POI data and calculating scores... this may take a moment.")
        df['poi_sum'] = df.apply(row_pipeline, axis=1)
        
        return df




def main():
    # data = {
    #     'station_id': ['(latitude, longitude)', '(latitude, longitude)', '(latitude, longitude)'],
    #     'poi_sum': [45.5, 12.0, 88.2],      # From your POI_score function
    #     'efficiency': [1, 2, 3],      # Charger type
    #     'distance': [1200, 300, 4500],     # meters
    #     'waiting_time': [5, 20, 0]         # minutes
    # }
    # For now use ev_station_2025 dataset, 
    # Waiting time will be randomized from 0 to 20
    # Distance is from EV_station[0] to other station
    # TODO: Make the dataframe for it then put it in the function to test

    MOCK_DATASET = r"data\ev_stations_2025.csv"
    EV_station_dataset = pd.read_csv(MOCK_DATASET, nrows=5)

    header_names = pd.read_csv(MOCK_DATASET, nrows=0).columns.tolist()
    user_location = pd.read_csv(MOCK_DATASET, skiprows=51, nrows=1, names=header_names)

    current_user_pos = (user_location.loc[0, 'lat'], user_location.loc[0, 'lon'])
    print(current_user_pos)

    model = Calculation_Model(current_user_pos)

    EV_station_dataset = model.process_distances(EV_station_dataset)
    EV_station_dataset = model.process_all_stations(EV_station_dataset)
    EV_station_dataset['efficiency'] = EV_station_dataset['connector_types'].apply(model.efficiency_score)
    EV_station_dataset['waiting_time'] = np.random.randint(0, 21, size=len(EV_station_dataset))

    final_ranked_df = model.total_score(EV_station_dataset)
    final_ranked_df.to_csv("final_ranked_df.csv")
    print(final_ranked_df)






if __name__ == "__main__":
    main()