import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import geopandas as gpd
import psycopg2
import pandas as pd
from sqlalchemy import create_engine

# Import database connection parameters
from modules.data_loader import (
    DB_USER_DESTINATION, 
    DB_PASSWORD_DESTINATION, 
    DB_HOST_DESTINATION, 
    DB_NAME_DESTINATION
)

# Add custom CSS for better map layout
st.markdown("""
<style>
    /* Increase map container height */
    .stPlotlyChart {
        height: 700px !important;
    }
    
    /* Ensure full width and remove unnecessary padding */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    /* Style for parameter selection */
    .stSelectbox {
        width: 100%;
        max-width: 400px;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

def get_database_connection():
    """Establish a connection to the PostgreSQL database."""
    try:
        connection_string = f"postgresql://{DB_USER_DESTINATION}:{DB_PASSWORD_DESTINATION}@{DB_HOST_DESTINATION}/{DB_NAME_DESTINATION}"
        engine = create_engine(connection_string)
        return engine
    except Exception as e:
        st.error(f"Error connecting to the database: {e}")
        return None

def load_parcels_data():
    """Load parcels data from the database."""
    query = """
    SELECT 
        ps.parcel_season_id,
        ps.parcel_id, 
        ps.season_id,
        ps.crop,
        ps.area_ha,
        ps.company,
        ps.parcel_label,
        ST_AsText(ST_Transform(ps.geometry, 4326)) AS geometry_text,
        ST_Transform(ps.geometry, 4326) AS geom,
        lp.localname
    FROM yield_level.cf_parcel_season ps
    LEFT JOIN lookups.lookup_sklpis_parcels lp ON ps.parcel_id = lp.parcel_id
    WHERE ps.season_id = '24_25'
    """
    
    engine = get_database_connection()
    if not engine:
        return None
    
    try:
        # Read the data as a DataFrame first
        df = pd.read_sql(query, engine)
        
        # Convert to GeoDataFrame
        gdf_parcels = gpd.GeoDataFrame(
            df, 
            geometry=gpd.GeoSeries.from_wkt(df['geometry_text'], crs='EPSG:4326')
        )
        
        return gdf_parcels
    except Exception as e:
        st.error(f"Error loading parcels data: {e}")
        return None
    finally:
        engine.dispose()

def load_soil_samples_data():
    """Load soil samples data from the database."""
    query = """
    SELECT 
        id, 
        p, 
        k, 
        ph, 
        geom
    FROM yield_level.soil_samples_raw
    """
    
    engine = get_database_connection()
    if not engine:
        return None
    
    try:
        gdf_points = gpd.read_postgis(query, engine, geom_col='geom')
        return gdf_points
    except Exception as e:
        st.error(f"Error loading soil samples data: {e}")
        return None
    finally:
        engine.dispose()

def process_spatial_data(gdf_parcels, gdf_points):
    """Perform spatial join and aggregate soil sample data."""
    # Spatial join to assign points to parcels
    gdf_points_with_parcels = gpd.sjoin(gdf_points, gdf_parcels, how='left')
    
    # Aggregate soil sample data by parcel
    parcel_soil_stats = gdf_points_with_parcels.groupby('parcel_id').agg({
        'p': 'mean',
        'k': 'mean',
        'ph': 'mean'
    }).reset_index()
    
    # Merge aggregated stats back to parcels GeoDataFrame
    gdf_parcels_with_stats = gdf_parcels.merge(parcel_soil_stats, on='parcel_id', how='left')
    
    # Ensure we're still working with a GeoDataFrame
    if not isinstance(gdf_parcels_with_stats, gpd.GeoDataFrame):
        gdf_parcels_with_stats = gpd.GeoDataFrame(
            gdf_parcels_with_stats, 
            geometry=gdf_parcels.geometry, 
            crs=gdf_parcels.crs
        )
    
    return gdf_parcels_with_stats, gdf_points

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
        # Categorize points
        gdf_points['p_category'] = gdf_points['p'].apply(categorize_phosphorus)
        
        # Create figure with both choropleth and line traces for parcel boundaries
        fig = go.Figure()
        
        # Add parcel boundaries as line traces
        for idx, row in gdf_parcels_with_stats.iterrows():
            # Extract boundary coordinates
            if not row.geometry.is_empty:
                try:
                    # Get exterior coordinates of the polygon
                    boundary_lons, boundary_lats = row.geometry.exterior.xy
                    
                    # Convert to list to handle array.array
                    boundary_lons = list(boundary_lons)
                    boundary_lats = list(boundary_lats)
                    
                    # Add boundary line trace
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
                    st.warning(f"Could not process geometry for parcel {row['parcel_id']}: {e}")
        
        # Add choropleth layer
        choropleth = go.Choroplethmapbox(
            geojson=gdf_parcels_with_stats.__geo_interface__,
            locations=gdf_parcels_with_stats.index,
            z=gdf_parcels_with_stats['p'],
            colorscale='Viridis',
            marker_opacity=0.5,
            marker_line_width=0,
            colorbar_title='Fosfor (P)',
            hovertemplate='<b>Parcel ID</b>: %{location}<br>' +
                          '<b>Lokalita</b>: %{customdata[0]}<br>' +
                          '<b>Hodnota P</b>: %{z:.2f}<extra></extra>',
            customdata=gdf_parcels_with_stats[['localname']].values
        )
        fig.add_trace(choropleth)
        
        # Add soil sample points
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
        
        # Update layout
        fig.update_layout(
            mapbox_style="open-street-map",
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
        # Similar approach for other parameters (K, pH)
        # Create figure with both choropleth and line traces for parcel boundaries
        fig = go.Figure()
        
        # Add parcel boundaries as line traces
        for idx, row in gdf_parcels_with_stats.iterrows():
            # Extract boundary coordinates
            if not row.geometry.is_empty:
                try:
                    # Get exterior coordinates of the polygon
                    boundary_lons, boundary_lats = row.geometry.exterior.xy
                    
                    # Convert to list to handle array.array
                    boundary_lons = list(boundary_lons)
                    boundary_lats = list(boundary_lats)
                    
                    # Add boundary line trace
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
                    st.warning(f"Could not process geometry for parcel {row['parcel_id']}: {e}")
        
        # Add choropleth layer
        choropleth = go.Choroplethmapbox(
            geojson=gdf_parcels_with_stats.__geo_interface__,
            locations=gdf_parcels_with_stats.index,
            z=gdf_parcels_with_stats[param_col],
            colorscale='Viridis',
            marker_opacity=0.5,
            marker_line_width=0,
            colorbar_title=selected_parameter,
            hovertemplate='<b>Parcel ID</b>: %{location}<br>' +
                          '<b>Lokalita</b>: %{customdata[0]}<br>' +
                          f'<b>{selected_parameter}</b>: %{{z:.2f}}<extra></extra>',
            customdata=gdf_parcels_with_stats[['localname']].values
        )
        fig.add_trace(choropleth)
        
        # Add soil sample points
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
        
        # Update layout
        fig.update_layout(
            mapbox_style="open-street-map",
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
    st.plotly_chart(fig, use_container_width=True)

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
    # Set page configuration
    st.set_page_config(
        page_title="Priestorová Analýza Pôdnych Vzoriek",
        page_icon="🌍",
        layout="wide"
    )
    
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
