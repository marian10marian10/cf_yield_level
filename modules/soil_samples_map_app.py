import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import geopandas as gpd
import psycopg2
import pandas as pd
from sqlalchemy import create_engine, text
import os
import sys
import logging
from dotenv import load_dotenv

# Konfigurácia logovania
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/logs/soil_samples.log', mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Prednastavené hodnoty pre databázové pripojenie
DEFAULT_DB_CONFIG = {
    'host': 'team-pz.cyp6scadbpmv.eu-central-1.rds.amazonaws.com',
    'user': 'db_admin',
    'password': 'Ybm=Zjk#sTf3#^]ybD<k',
    'name': 'postgres',
    'port': '5432'
}

# Všetky predchádzajúce funkcie zostávajú nezmenené...

def create_map(gdf_parcels_with_stats, gdf_points, selected_parameter):
    """Create interactive map with Plotly."""
    # Mapping parameter names to column names
    param_map = {
        'Fosfor (P)': 'p',
        'Draslík (K)': 'k',
        'pH': 'ph'
    }
    
    # Ak nie sú potrebné dáta, vráť prázdny graf
    if gdf_parcels_with_stats is None or gdf_points is None:
        logger.warning("Prázdne dáta pre mapu")
        return go.Figure()
    
    try:
        param_col = param_map[selected_parameter]
        
        # Custom color scale and category function for Phosphorus
        def categorize_phosphorus(value):
            if value <= 50:
                return 0  # Nízky
            elif 51 <= value <= 80:
                return 1  # Vyhovujúci
            elif 81 <= value <= 115:
                return 2  # Dobrý
            elif 116 <= value <= 185:
                return 3  # Vysoký
            else:
                return 4  # Veľmi vysoký
        
        # Color mapping for categories
        color_map = {
            0: '#FF0000',    # Nízky - Red
            1: '#FFA500',    # Vyhovujúci - Orange
            2: '#FFFF00',    # Dobrý - Yellow
            3: '#90EE90',    # Vysoký - Light Green
            4: '#008000'     # Veľmi vysoký - Dark Green
        }
        
        category_labels = {
            0: 'Nízky',
            1: 'Vyhovujúci', 
            2: 'Dobrý', 
            3: 'Vysoký', 
            4: 'Veľmi vysoký'
        }
        
        # Ensure we're working with a GeoDataFrame
        if not isinstance(gdf_parcels_with_stats, gpd.GeoDataFrame):
            logger.error("Parcels data is not a GeoDataFrame. Cannot create map.")
            return go.Figure()
        
        # Vytvorenie figúry
        fig = go.Figure()
        
        # Pridanie hraníc parciel ako líniové stopy
        for idx, row in gdf_parcels_with_stats.iterrows():
            # Extrakcia súradníc hraníc
            if not row.geometry.is_empty:
                try:
                    # Získanie vonkajších súradníc polygónu
                    boundary_lons, boundary_lats = row.geometry.exterior.xy
                    
                    # Konverzia na zoznam pre spracovanie
                    boundary_lons = list(boundary_lons)
                    boundary_lats = list(boundary_lats)
                    
                    # Pridanie línie hranice parcely
                    fig.add_trace(go.Scattermapbox(
                        mode="lines",
                        lon=boundary_lons,
                        lat=boundary_lats,
                        line=dict(color='black', width=1),
                        opacity=0.7,
                        showlegend=False,
                        hoverinfo='none'
                    ))
                except Exception as e:
                    logger.warning(f"Nemožno spracovať geometriu parcely {row['parcel_id']}: {e}")
        
        # Pridanie bodov vzoriek pôdy
        scatter = go.Scattermapbox(
            lat=gdf_points.geometry.y.tolist(),
            lon=gdf_points.geometry.x.tolist(),
            mode='markers',
            marker=dict(
                size=8,
                color=gdf_points[param_col],
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title=selected_parameter)
            ),
            text=[f'ID: {id}<br>{selected_parameter}: {val:.2f}' for id, val in zip(gdf_points['id'], gdf_points[param_col])],
            hoverinfo='text',
            name='Vzorky pôdy'
        )
        fig.add_trace(scatter)
        
        # Aktualizácia layoutu s mapou Carto Positron
        fig.update_layout(
            mapbox_style="carto-positron",
            mapbox=dict(
                center=dict(
                    lat=gdf_parcels_with_stats.geometry.centroid.y.mean(),
                    lon=gdf_parcels_with_stats.geometry.centroid.x.mean()
                ),
                zoom=10
            ),
            height=700,
            margin={"l":0,"r":0,"t":50,"b":0}
        )
        
        return fig
    
    except Exception as e:
        logger.error(f"Chyba pri vytváraní mapy: {e}")
        return go.Figure()

# Zvyšok kódu zostáva nezmenený (všetky pôvodné funkcie)
# ... (celá pôvodná implementácia zostáva rovnaká)

def soil_samples_map():
    """Streamlit page for soil samples map."""
    st.title('Priestorová Analýza Pôdnych Vzoriek')
    
    # Load data
    gdf_parcels = load_parcels_data()
    gdf_points = load_soil_samples_data()
    
    if gdf_parcels is None or gdf_points is None:
        st.error("Nepodarilo sa načítať dáta. Skontrolujte databázové pripojenie.")
        return
    
    # Process spatial data
    gdf_parcels_with_stats, gdf_points = process_spatial_data(gdf_parcels, gdf_points)
    
    # Parameter selection
    selected_parameter = st.selectbox(
        'Vyberte parameter na vizualizáciu:',
        ['Fosfor (P)', 'Draslík (K)', 'pH']
    )
    
    # Create and display map
    fig = create_map(gdf_parcels_with_stats, gdf_points, selected_parameter)
    st.plotly_chart(fig, use_container_width=True, key='main_map')
    
    # Zvyšok funkcie zostáva nezmenený
    # ... (celá pôvodná implementácia zostáva rovnaká)

# Zvyšok kódu zostáva nezmenený
# ... (celá pôvodná implementácia zostáva rovnaká)