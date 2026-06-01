import os
import sys

# ========================================================
# 0. Forced Path Configuration (Fixing Traci/SUMO Link)
# ========================================================
sumo_path = r"C:\Users\USER\Downloads\sumo-win64extra-1.26.0\sumo-1.26.0" 
os.environ['SUMO_HOME'] = sumo_path
sys.path.append(os.path.join(sumo_path, 'tools'))

import traci
import pandas as pd
import numpy as np
import xml.etree.ElementTree as ET
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# ========================================================
# 1. Dataset Loading & Enhancement
# ========================================================
def load_and_enhance_data(file_path):
    df = pd.read_csv(file_path, low_memory=False)
    df['Gasoline Savings (gallons)'] = df['Gasoline Savings (gallons)'].fillna(0)
    df['Energy (kWh)'] = df['Energy (kWh)'].fillna(df['Energy (kWh)'].mean())
    
    features = df[['Gasoline Savings (gallons)', 'Energy (kWh)']]
    scaler = StandardScaler()
    scaled = scaler.fit_transform(features)
    
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    df['Category'] = kmeans.fit_predict(scaled)
    tag_map = {0: "Standard", 1: "High Performance", 2: "Economic Choice"}
    df['Category'] = df['Category'].map(tag_map)
    
    matrix = df[['Gasoline Savings (gallons)', 'Energy (kWh)']].values
    norm = matrix / np.sqrt((matrix**2).sum(axis=0))
    weighted = norm * np.array([0.6, 0.4])
    ideal_best = np.max(weighted, axis=0)
    ideal_worst = np.min(weighted, axis=0)
    d_best = np.sqrt(((weighted - ideal_best)**2).sum(axis=1))
    d_worst = np.sqrt(((weighted - ideal_worst)**2).sum(axis=1))
    df['Smart_Score'] = d_worst / (d_best + d_worst)
    return df

# ========================================================
# 2. Recommendation Engine
# ========================================================
def get_recommendations(data, target_city):
    filtered = data[data['City'].str.contains(target_city, case=False, na=False)].copy()
    results = filtered.sort_values(by='Smart_Score', ascending=False)
    return results[['Station Name', 'Address 1', 'Category', 'Smart_Score']].drop_duplicates().head(5)

# ========================================================
# 3. SUMO Real-time Data Integration
# ========================================================
def get_current_ev_status(xml_file):
    if not os.path.exists(xml_file): return None
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        timesteps = root.findall('.//timestep')
        if not timesteps: return None
        vehicle = timesteps[-1].find('vehicle')
        if vehicle is not None:
            return {'vehicle_id': vehicle.get('id'), 'remaining_battery': float(vehicle.get('actualBatteryCapacity'))}
    except Exception as e:
        print(f"Error reading XML: {e}")
    return None

# ========================================================
# 4. Main Execution (優化後的版本)
# ========================================================
if __name__ == "__main__":
    csv_file = 'ChargePointData2011-2020-ManullyPreCleaned3.csv'
    sumo_log = "user_data_log.xml"
    target_city = "Palo Alto"  # 強制鎖定目標城市
    
    print("--- EV Charging Station Recommendation System ---")
    
    # 嘗試啟動模擬器
    try:
        sumo_binary = os.path.join(sumo_path, "bin", "sumo-gui.exe")
        print(f"🚀 Launching SUMO: {sumo_binary}")
        # 啟動模擬，並確保它能產生 battery-output
        traci.start([sumo_binary, "-c", "simulation.sumocfg"])
        
        # 跑 50 步模擬
        for _ in range(50): 
            traci.simulationStep()
        traci.close()
        print("✅ Simulation complete. Data updated in user_data_log.xml\n")
    except Exception as e:
        print(f"⚠️ Simulation Error (Check SUMO paths/config): {e}")

    # 執行分析
    data = load_and_enhance_data(csv_file)
    ev_status = get_current_ev_status(sumo_log)
    
    # 若模擬未產生資料，自動切換至安全模式
    if not ev_status:
        print("🔍 Real-time log not found or incomplete. Using simulation demo mode.")
        ev_status = {'vehicle_id': 'MCU_EV_TEST_01', 'remaining_battery': 5000.0}
    
    print(f"[Monitoring] Vehicle: {ev_status['vehicle_id']} | Battery: {ev_status['remaining_battery']:.2f} Wh")
    
    # 根據電量閾值進行決策
    if ev_status['remaining_battery'] < 12000:
        print(f"\n⚠️ LOW BATTERY ALERT! Finding best charging solutions in {target_city}...")
        recommendations = get_recommendations(data, target_city)
        if not recommendations.empty:
            print("\n--- Top Smart Recommendations (TOPSIS Ranking) ---")
            print(recommendations.to_string(index=False))
            print("-" * 50)
        else:
            print(f"⚠️ No stations found for {target_city}.")
    else:
        print("\n✅ Battery sufficient. No action needed.")