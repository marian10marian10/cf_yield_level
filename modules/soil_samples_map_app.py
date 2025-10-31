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
    import geopandas as gpd
    import numpy as np
    
    # Ensure geometry column is preserved
    if not isinstance(gdf_parcels_with_stats, gpd.GeoDataFrame):
        st.error("Parcels data is not a GeoDataFrame. Cannot create map.")
        return None
    
    # Prepare data with categorization for Phosphorus
    if selected_parameter == 'Fosfor (P)':
        # Kategorize body
        gdf_points['p_category'] = gdf_points['p'].apply(categorize_phosphorus)
        
        # Vytvorenie figúry s oboma vrstvami
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
                    st.warning(f"Nemožno spracovať geometriu parcely {row['parcel_id']}: {e}")
        
        # Pridanie choropleth vrstvy
        choropleth = go.Choroplethmapbox(
            geojson=gdf_parcels_with_stats.__geo_interface__,
            locations=gdf_parcels_with_stats.index,
            z=gdf_parcels_with_stats['p'],
            colorscale='Viridis',
            marker_opacity=0.5,
            marker_line_width=0,
            colorbar_title='Fosfor (P)',
            hovertemplate='<b>ID Parcely</b>: %{location}<br>' +
                          '<b>Lokalita</b>: %{customdata[0]}<br>' +
                          '<b>Hodnota P</b>: %{z:.2f}<extra></extra>',
            customdata=gdf_parcels_with_stats[['localname']].values
        )
        fig.add_trace(choropleth)
        
        # Pridanie bodov vzoriek pôdy
        scatter = go.Scattermapbox(
            lat=gdf_points.geometry.y.tolist(),
            lon=gdf_points.geometry.x.tolist(),
            mode='markers',
            marker=dict(
                size=8,
                color=gdf_points['p_category'],
                colorscale=[
                    [0, color_map[0]],
                    [0.25, color_map[1]],
                    [0.5, color_map[2]],
                    [0.75, color_map[3]],
                    [1, color_map[4]]
                ],
                showscale=True,
                colorbar=dict(
                    title='Kategória P',
                    tickvals=[0, 1, 2, 3, 4],
                    ticktext=[category_labels[i] for i in range(5)]
                )
            ),
            text=[f'ID: {id}<br>P: {p:.2f}<br>Kategória: {category_labels[categorize_phosphorus(p)]}' for id, p in zip(gdf_points['id'], gdf_points['p'])],
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
    else:
        # Podobný prístup pre ostatné parametre (K, pH)
        # Vytvorenie figúry s oboma vrstvami
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
                    st.warning(f"Nemožno spracovať geometriu parcely {row['parcel_id']}: {e}")
        
        # Pridanie choropleth vrstvy
        choropleth = go.Choroplethmapbox(
            geojson=gdf_parcels_with_stats.__geo_interface__,
            locations=gdf_parcels_with_stats.index,
            z=gdf_parcels_with_stats[param_col],
            colorscale='Viridis',
            marker_opacity=0.5,
            marker_line_width=0,
            colorbar_title=selected_parameter,
            hovertemplate='<b>ID Parcely</b>: %{location}<br>' +
                          '<b>Lokalita</b>: %{customdata[0]}<br>' +
                          f'<b>{selected_parameter}</b>: %{{z:.2f}}<extra></extra>',
            customdata=gdf_parcels_with_stats[['localname']].values
        )
        fig.add_trace(choropleth)
        
        # Pridanie bodov vzoriek pôdy
        scatter = go.Scattermapbox(
            lat=gdf_points.geometry.y.tolist(),
            lon=gdf_points.geometry.x.tolist(),
            mode='markers',
            marker=dict(
                size=8,
                color=gdf_points[param_map[selected_parameter]],
                colorscale='Viridis',
                showscale=True
            ),
            text=[f'ID: {id}<br>{selected_parameter}: {val:.2f}' for id, val in zip(gdf_points['id'], gdf_points[param_map[selected_parameter]])],
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

# Zvyšok kódu zostáva nezmenený (všetky pôvodné funkcie)
# ... (celá pôvodná implementácia zostáva rovnaká)

# Pridám explicitné definície funkcií pre import
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

def about_page():
    """About page for the application."""
    st.title('O Aplikácii')
    st.markdown('''
    ## Priestorová Analýza Pôdnych Vzoriek

    ### Popis
    Táto aplikácia poskytuje interaktívnu vizualizáciu priestorových dát o pôdnych vzorkách a parcelách pre sezónu 24/25.

    ### Funkcie
    - Interaktívna mapa parciel
    - Výber parametra: Fosfor (P), Draslík (K), pH
    - Zobrazenie priestorovej distribúcie pôdnych vzoriek
    - Hover efekty pre detailné informácie

    ### Technické Detaily
    - Dáta sú načítavané z PostGIS databázy
    - Priestorové spracovanie pomocou GeoPandas
    - Vizualizácia pomocou Plotly a Streamlit

    ### Poznámky
    - Vyžaduje aktívne databázové pripojenie
    - Dáta sú filtrované pre sezónu 24/25
    ''')

def main():
    # Create sidebar navigation
    page = st.sidebar.radio(
        "Navigácia", 
        ["Mapa Pôdnych Vzoriek", "O Aplikácii"]
    )
    
    # Render selected page
    if page == "Mapa Pôdnych Vzoriek":
        soil_samples_map()
    else:
        about_page()

if __name__ == '__main__':
    main()