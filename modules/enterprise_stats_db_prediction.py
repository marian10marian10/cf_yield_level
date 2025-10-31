import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection parameters
DB_USER_DESTINATION = os.getenv('DB_USER_DESTINATION', 'db_admin')
DB_PASSWORD_DESTINATION = os.getenv('DB_PASSWORD_DESTINATION', '')
DB_HOST_DESTINATION = os.getenv('DB_HOST_DESTINATION')
DB_NAME_DESTINATION = os.getenv('DB_NAME_DESTINATION', 'postgres')

def load_prediction_demand_data():
    """Load data from yield_level.mv_25_26_prediction_demand materialized view"""
    try:
        # Create database connection
        connection_string = f"postgresql://{DB_USER_DESTINATION}:{DB_PASSWORD_DESTINATION}@{DB_HOST_DESTINATION}/{DB_NAME_DESTINATION}"
        engine = create_engine(connection_string)
        
        # Load data from the materialized view
        query = "SELECT * FROM yield_level.mv_25_26_prediction_demand"
        df = pd.read_sql(query, engine)
        
        # Close the connection
        engine.dispose()
        
        return df
    except Exception as e:
        st.error(f"Chyba pri načítaní dát: {e}")
        return None

def show_enterprise_stats_db_prediction():
    """Display enterprise statistics using prediction and demand data"""
    st.markdown('<h1 class="main-header">🏭 Štatistiky podniku (Predikcia 25/26)</h1>', unsafe_allow_html=True)
    
    # Load data
    df = load_prediction_demand_data()
    
    if df is None:
        st.error("Nepodarilo sa načítať dáta.")
        return
    
    # Convert yield predictions to numeric, handling potential non-numeric values
    def safe_convert_to_numeric(series):
        try:
            # Try to convert to numeric, coercing errors to NaN
            return pd.to_numeric(series, errors='coerce')
        except:
            # If conversion fails, return NaN
            return pd.Series([float('nan')] * len(series))
    
    # Aggregate data by company
    company_stats = df.groupby('company').agg({
        'parcel_id': 'count',
        'total_demand_n': 'sum',
        'total_demand_p': 'sum',
        'total_demand_k': 'sum',
    }).reset_index()
    
    company_stats.columns = ['Spoločnosť', 'Počet parciel', 'Celková potreba N', 'Celková potreba P', 'Celková potreba K']
    
    # Nutrient demand by company
    fig_nutrient_demand = go.Figure()
    
    # Add traces for N, P, K
    nutrients = ['Celková potreba N', 'Celková potreba P', 'Celková potreba K']
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
    
    for nutrient, color in zip(nutrients, colors):
        fig_nutrient_demand.add_trace(go.Bar(
            x=company_stats['Spoločnosť'],
            y=company_stats[nutrient],
            name=nutrient,
            marker_color=color
        ))
    
    fig_nutrient_demand.update_layout(
        title='Celková potreba živín podľa spoločností',
        xaxis_title='Spoločnosť',
        yaxis_title='Potreba živín',
        barmode='group'
    )
    st.plotly_chart(fig_nutrient_demand, use_container_width=True)
    
    # Crop analysis
    # Aggregate data by crop with safe numeric conversion and rounding
    crop_stats = df.groupby('crops').agg({
        'parcel_id': 'count',
        'total_demand_n': 'sum',
        'total_demand_p': 'sum',
        'total_demand_k': 'sum',
        '25_26_yield_predictions': lambda x: round(safe_convert_to_numeric(x).mean(), 2)
    }).reset_index()
    
    crop_stats.columns = ['Plodina', 'Počet parciel', 'Celková potreba N', 'Celková potreba P', 'Celková potreba K', 'Priemerná predikcia výnosov']
    
    # Nutrient demand by crop
    fig_crop_nutrient_demand = go.Figure()
    
    for nutrient, color in zip(nutrients, colors):
        fig_crop_nutrient_demand.add_trace(go.Bar(
            x=crop_stats['Plodina'],
            y=crop_stats[nutrient],
            name=nutrient,
            marker_color=color
        ))
    
    fig_crop_nutrient_demand.update_layout(
        title='Celková potreba živín podľa plodín',
        xaxis_title='Plodina',
        yaxis_title='Potreba živín',
        barmode='group'
    )
    st.plotly_chart(fig_crop_nutrient_demand, use_container_width=True)
    
    # Detailed data tables
    st.markdown("## 📋 Detailné údaje")
    
    # Company statistics table
    st.subheader("Štatistiky spoločností")
    st.dataframe(company_stats, use_container_width=True)
    
    # Crop statistics table
    st.subheader("Štatistiky plodín")
    st.dataframe(crop_stats, use_container_width=True)
