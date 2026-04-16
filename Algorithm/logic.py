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

    def __init__(self):
        self.w_poi = 0.25
        self.w_eff = 0.25
        self.w_dist = 0.25
        self.w_wait = 0.25
    
    def total_score(self, stations_df):
    # 1. Normalize each value
    # 2. Put it into the sum weighted function
    # data = {
    #     'station_id': ['A', 'B', 'C'],
    #     'poi_sum': [45.5, 12.0, 88.2],      # From your POI_score function
    #     'efficiency': [150, 50, 350],      # maxChargeRateKw
    #     'distance': [1200, 300, 4500],     # meters
    #     'waiting_time': [5, 20, 0]         # minutes
    # }

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


    def get_POI(self,  latitude, longitude):
    # Returns JSON file of POI around as well as data of it (max 20 top POI)
        POI = Get_POI()
        return POI.call_API(latitude, longitude)

    def get_distance_score(self, destination_location, user_location):
        return get_distance_ev(destination_location, user_location)
    
    def POI_score(self, data, coordinate_key):
        '''
        data received is on JSON
        Rating * log(Reviews) / 1 + (d/100)
        Note: Counting the number of POI doesn't work since google place (new) only limits 20 per request
        Ways to fix -> perhaps make smaller circles around the diameter, to find other POI (Not good)
        '''
        place_list = pd.json_normalize(data[coordinate_key], record_path=["places"])
        place_distance = pd.json_normalize(data[coordinate_key]['routingSummaries'], record_path=['legs'])
        place = pd.concat([place_list, place_distance], axis=1)

        print(place.columns)
        print(place)

        place['poi_score'] = place.apply(self.calculate_poi_score, axis=1)
        total_poi_score = place['poi_score'].sum()
        return total_poi_score
    
    # Helper function
    def calculate_poi_score(self, row):
        rating = row['rating']
        reviews = row['userRatingCount']
        distance = row['distanceMeters']
        
        # We add 1 to reviews to avoid log(0)
        score = (rating * np.log10(reviews + 1))/ (1 + distance/100)
        return score




def main():
    # data = {
    #     'station_id': ['(longitude, latitude)', '(longitude, latitude)', '(longitude, latitude)'],
    #     'poi_sum': [45.5, 12.0, 88.2],      # From your POI_score function
    #     'efficiency': [150, 50, 350],      # maxChargeRateKw
    #     'distance': [1200, 300, 4500],     # meters
    #     'waiting_time': [5, 20, 0]         # minutes
    # }
    # For now use ev_station_2025 dataset, 
    # Waiting time will be randomized from 0 to 20
    # Distance is from EV_station[0] to other station
    # 

    MOCK_DATASET = r"data\ev_stations_2025.csv"
    EV_station_dataset = pd.read_csv(MOCK_DATASET)
    




if __name__ == "__main__":
    main()