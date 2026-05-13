import geopandas as gpd

# Read the GeoJSON
gdf = gpd.read_file("chargers.geojson")

# Extract Lat/Lon from the 'geometry' column for your CSV
gdf['longitude'] = gdf.geometry.x
gdf['latitude'] = gdf.geometry.y

# Drop the geometry column so it's a standard table, then save
df = gdf.drop(columns='geometry')
df.to_csv("chargers.csv", index=False)