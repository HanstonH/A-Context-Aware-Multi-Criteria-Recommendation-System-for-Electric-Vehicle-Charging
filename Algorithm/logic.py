''' 
Make a model that chooses based on 
1. Distance
Distance logic that needs to follow the road (not just a straight line from A to B) will not be implemented here
It is assumed that it is already implemented

2. Waiting time (How many people are using)
For waiting time, perhaps use a machine learning model to predict whether it will be vacant when you get there. Then use that value to the algorithm

3. Efficiency (how fast the cable electricity is)
Get from maxChargeRateKw in evChargeOptions PlacesAPI(new)

4. POI score (make own logic)
'''
import pandas as pd
import numpy as np
import json
from get_Distance_EV import get_distance_ev
from get_POI import Get_POI

class Calculation_Model:

    def __init__(self):
        pass
    
    def get_POI(self,  latitude, longitude):
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
    with open('data\poi_cache.json', 'r') as file:
        data = json.load(file)

    coordinate_key = "22.98285,120.21156"

    calculation_model = Calculation_Model()
    print(calculation_model.POI_score(data, coordinate_key))

if __name__ == "__main__":
    main()