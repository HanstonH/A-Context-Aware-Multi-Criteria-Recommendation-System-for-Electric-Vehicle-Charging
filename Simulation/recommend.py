import pandas as pd
import numpy as np
import xml.etree.ElementTree as ET
import os
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# ========================================================
# 1. Dataset Loading & Enhancement Logic
# ========================================================
def load_and_enhance_data(file_path):
    """Loads CSV and applies K-Means/TOPSIS for categorization and scoring."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Data file not found: {file_path}")
        
    df = pd.read_csv(file_path, low_memory=False)
    
    # Data Cleaning
    df['Gasoline Savings (gallons)'] = df['Gasoline Savings (gallons)'].fillna(0)
    df['Energy (kWh)'] = df['Energy (kWh)'].fillna(df['Energy (kWh)'].mean())
    
    # A. K-Means Clustering: Defining Station "Personas" (UI/UX Core)
    features = df[['Gasoline Savings (gallons)', 'Energy (kWh)']]
    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(features)
    
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    df['Cluster_Tag'] = kmeans.fit_predict(scaled_features)
    
    # Mapping clusters to user-friendly categories
    tag_map = {0: "Standard", 1: "High Performance", 2: "Economic Choice"}
    df['Category'] = df['Cluster_Tag'].map(tag_map)
    
    # B. TOPSIS Algorithm: Calculating Smart Ranking Score
    matrix = df[['Gasoline Savings (gallons)', 'Energy (kWh)']].values
    norm_matrix = matrix / np.sqrt((matrix**2).sum(axis=0))
    weights = np.array([0.6, 0.4])  # Weight: 60% Savings/Eco, 40% Efficiency
    weighted_matrix = norm_matrix * weights
    
    ideal_best = np.max(weighted_matrix, axis=0)
    ideal_worst = np.min(weighted_matrix, axis=0)
    
    d_best = np.sqrt(((weighted_matrix - ideal_best)**2).sum(axis=1))
    d_worst = np.sqrt(((weighted_matrix - ideal_worst)**2).sum(axis=1))
    
    df['Smart_Score'] = d_worst / (d_best + d_worst)
    return df

# ========================================================
# 2. Recommendation Engine
# ========================================================
def get_recommendations(data, target_city, mode='smart'):
    """Filters and ranks stations based on selected criteria."""
    filtered_df = data[data['City'].str.contains(target_city, case=False, na=False)].copy()
    
    if filtered_df.empty:
        return f"No charging stations found in {target_city}."

    if mode == 'cost':
        sort_col = 'Gasoline Savings (gallons)'
    elif mode == 'popularity':
        station_counts = filtered_df['Station Name'].value_counts()
        filtered_df['Popularity Score'] = filtered_df['Station Name'].map(station_counts)
        sort_col = 'Popularity Score'
    else: # Default: 'smart' (TOPSIS Score)
        sort_col = 'Smart_Score'

    recommendations = filtered_df.sort_values(by=sort_col, ascending=False)
    display_cols = ['Station Name', 'Address 1', 'Category', sort_col]
    
    return recommendations[display_cols].drop_duplicates(subset=['Station Name']).head(5)

# ========================================================
# 3. SUMO Real-time Data Integration
# ========================================================
def get_current_ev_status(xml_file):
    """Extracts the latest battery status from SUMO simulation log."""
    if not os.path.exists(xml_file):
        return None  # Trigger Mock Data if file is missing

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        timesteps = root.findall('timestep')
        if not timesteps:
            return None
            
        last_timestep = timesteps[-1]
        vehicle = last_timestep.find('vehicle')
        
        if vehicle is not None:
            return {
                'vehicle_id': vehicle.get('id'),
                'remaining_battery': float(vehicle.get('actualBatteryCapacity'))
            }
    except Exception as e:
        print(f"Error parsing SUMO data: {e}")
    return None

# ========================================================
# 4. Main Execution
# ========================================================
if __name__ == "__main__":
    # Configuration
    csv_file = 'ChargePointData2011-2020-ManullyPreCleaned3.csv'
    sumo_log = r"C:\Users\USER\Desktop\MCU_EV_Project_V2\user_data_log.xml"
    target_city = 'Palo Alto'
    
    print("--- EV Charging Station Recommendation System ---")
    
    # A. Data Initialization
    try:
        processed_data = load_and_enhance_data(csv_file)
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        exit()

    # B. EV Status Check
    ev_status = get_current_ev_status(sumo_log)
    
    # ⚡ Mock Data Logic for UI/UX Demonstrations
    if not ev_status:
        print("⚠️ System Note: Real-time simulation log not found. Using Mock Data for demonstration.")
        ev_status = {
            'vehicle_id': 'MCU_EV_TEST_01',
            'remaining_battery': 5000.0  # Set low to trigger alert
        }
    
    current_battery = ev_status['remaining_battery']
    print(f"\n[Vehicle Status Monitoring]")
    print(f"Vehicle ID: {ev_status['vehicle_id']}")
    print(f"Current Battery: {current_battery:.2f} Wh")
    
    # C. Decision Logic (Threshold: < 20% of 60kWh)
    if current_battery < 12000:
        print(f"\n⚠️ LOW BATTERY ALERT! Finding best charging solutions in {target_city}...")
        
        # Get TOPSIS Smart Recommendations
        results = get_recommendations(processed_data, target_city, mode='smart')
        
        print("\n--- Top Smart Recommendations (TOPSIS Ranking) ---")
        print(results.to_string(index=False))
        print("--------------------------------------------------")
    else:
        print("\n✅ Battery level sufficient. No immediate action required.")