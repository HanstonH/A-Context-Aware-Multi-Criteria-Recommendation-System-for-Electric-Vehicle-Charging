import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import os

# Set page to wide mode
st.set_page_config(layout="wide", page_title="EV Station Recommender")

st.title("⚡ EV Charging Station Recommendation Dashboard")

# 1. Load Data
csv_file = "final_recommendations_summary.csv"
if not os.path.exists(csv_file):
    st.error(f"Could not find {csv_file}. Please run your algorithm script first!")
else:
    df = pd.read_csv(csv_file)

    # Sidebar for filters
    st.sidebar.header("Filters")
    min_score = st.sidebar.slider("Minimum Total Score", 0.0, 1.0, 0.5)
    filtered_df = df[df['total_score'] >= min_score]

    # Create two columns
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📍 Interactive Map")
        # Use your current coordinates for the center
        user_lat, user_lon = 50.769938069594645, 3.1240298745922246

        m = folium.Map(location=[user_lat, user_lon], zoom_start=12)

        # Add a special marker for the User
        folium.Marker(
            location=[user_lat, user_lon],
            popup="Your Current Location",
            icon=folium.Icon(color='blue', icon='user', prefix='fa')
        ).add_to(m)

        # Add the charging stations
        for _, row in filtered_df.iterrows():
            color = 'green' if row['total_score'] > 0.8 else 'orange' if row['total_score'] > 0.6 else 'red'
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=row['total_score'] * 15,
                popup=f"{row['title']} (Score: {row['total_score']:.2f})",
                color=color,
                fill=True,
                fill_opacity=0.7
            ).add_to(m)

        st_folium(m, width=700, height=500)

    with col2:
        st.subheader("📊 Decision Breakdown")
        df_plot = filtered_df.copy()
        df_plot['POI'] = df_plot['n_poi'] * 0.25
        df_plot['Efficiency'] = df_plot['n_eff'] * 0.25
        df_plot['Distance'] = df_plot['n_dist'] * 0.25
        df_plot['Wait Time'] = df_plot['n_wait'] * 0.25

        fig = px.bar(df_plot, 
                     y='title', 
                     x=['POI', 'Efficiency', 'Distance', 'Wait Time'],
                     orientation='h',
                     height=500,
                     color_discrete_sequence=px.colors.qualitative.Vivid)
        
        fig.update_layout(barmode='stack', yaxis={'categoryorder':'total ascending'}, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

    # Show the raw data table at the bottom
    st.subheader("📋 Ranked Data")
    st.dataframe(filtered_df[['title', 'total_score', 'distance', 'waiting_time', 'poi_sum']].sort_values('total_score', ascending=False))