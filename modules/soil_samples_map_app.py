import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import geopandas as gpd
import psycopg2
import pandas as pd
from sqlalchemy import create_engine

# Import database connection parameters
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection parameters
DB_USER_DESTINATION = os.getenv('DB_USER_DESTINATION', 'db_admin')
DB_PASSWORD_DESTINATION = os.getenv('DB_PASSWORD_DESTINATION', '')
DB_HOST_DESTINATION = os.getenv('DB_HOST_DESTINATION', 'localhost')
DB_NAME_DESTINATION = os.getenv('DB_NAME_DESTINATION', 'postgres')

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
        
        # Update layout with Carto Positron light map
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
        
        # Update layout with Carto Positron light map
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

def create_additional_visualizations(gdf_parcels_with_stats, gdf_points):
    """Create additional visualizations for soil sample data."""
    import plotly.graph_objs as go
    import plotly.express as px
    import numpy as np
    import pandas as pd
    
    # 1. Box Plot: Distribution of Soil Nutrients
    fig_boxplot = go.Figure()
    nutrients = ['p', 'k', 'ph']
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']  # Blue, Orange, Green
    
    for i, nutrient in enumerate(nutrients):
        fig_boxplot.add_trace(go.Box(
            y=gdf_points[nutrient],
            name=nutrient.upper(),
            marker_color=colors[i]
        ))
    
    fig_boxplot.update_layout(
        title='Distribúcia Živín v Pôdnych Vzorkách',
        yaxis_title='Hodnota',
        height=300,
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    # 2. Scatter Matrix: Correlation between Nutrients
    scatter_matrix_data = gdf_points[['p', 'k', 'ph']].copy()
    scatter_matrix_data.columns = ['Fosfor (P)', 'Draslík (K)', 'pH']
    
    fig_scatter_matrix = px.scatter_matrix(
        scatter_matrix_data, 
        dimensions=['Fosfor (P)', 'Draslík (K)', 'pH'],
        title='Korelácie medzi Živinami',
        height=400,
        color_discrete_sequence=['#1f77b4']
    )
    
    # 3. Histogram: Frequency of Nutrient Levels
    fig_histogram = go.Figure()
    
    for i, nutrient in enumerate(nutrients):
        fig_histogram.add_trace(go.Histogram(
            x=gdf_points[nutrient],
            name=nutrient.upper(),
            opacity=0.7,
            marker_color=colors[i]
        ))
    
    fig_histogram.update_layout(
        title='Frekvencia Úrovní Živín',
        xaxis_title='Hodnota',
        yaxis_title='Početnosť',
        barmode='overlay',
        height=300,
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    # 4. Pie Chart: Parcel Distribution by Nutrient Categories
    def categorize_nutrient(nutrient, values):
        if nutrient == 'p':
            categories = [
                (0, 50, 'Nízky'),
                (51, 80, 'Vyhovujúci'),
                (81, 115, 'Dobrý'),
                (116, 185, 'Vysoký'),
                (186, float('inf'), 'Veľmi vysoký')
            ]
        elif nutrient == 'k':
            categories = [
                (0, 50, 'Nízky'),
                (51, 100, 'Stredný'),
                (101, 200, 'Dobrý'),
                (201, 300, 'Vysoký'),
                (301, float('inf'), 'Veľmi vysoký')
            ]
        else:  # pH
            categories = [
                (0, 5.5, 'Silne kyslé'),
                (5.5, 6.5, 'Kyslé'),
                (6.5, 7.2, 'Neutrálne'),
                (7.2, 8.5, 'Alkalické'),
                (8.5, float('inf'), 'Silne alkalické')
            ]
        
        for low, high, label in categories:
            if low <= values < high:
                return label
        return 'Neurčené'
    
    nutrient_pie_data = {}
    for nutrient in nutrients:
        nutrient_categories = gdf_points[nutrient].apply(lambda x: categorize_nutrient(nutrient, x))
        nutrient_counts = nutrient_categories.value_counts()
        nutrient_pie_data[nutrient] = nutrient_counts
    
    # Create pie charts
    fig_pie = go.Figure()
    for i, (nutrient, counts) in enumerate(nutrient_pie_data.items()):
        fig_pie.add_trace(go.Pie(
            labels=counts.index, 
            values=counts.values,
            name=nutrient.upper(),
            title=f'Kategórie {nutrient.upper()}',
            domain={'row': i // 2, 'column': i % 2}
        ))
    
    fig_pie.update_layout(
        title='Distribúcia Kategórií Živín',
        grid={'rows': 2, 'columns': 2},
        height=600,
        margin=dict(l=50, r=50, t=100, b=50)
    )
    
    # 5. Dummy figure to match the 5-value unpacking
    fig_dummy = go.Figure()
    fig_dummy.update_layout(
        title='Dummy Figure',
        height=300,
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    return fig_boxplot, fig_scatter_matrix, fig_histogram, fig_pie, fig_dummy

def create_company_visualizations(gdf_parcels_with_stats, gdf_points):
    """Create visualizations based on company data."""
    import plotly.graph_objs as go
    import plotly.express as px
    import pandas as pd
    import geopandas as gpd
    
    # Ensure parcels DataFrame is a GeoDataFrame with geometry
    if not isinstance(gdf_parcels_with_stats, gpd.GeoDataFrame):
        gdf_parcels_with_stats = gpd.GeoDataFrame(
            gdf_parcels_with_stats, 
            geometry=gdf_parcels_with_stats.geometry, 
            crs=gdf_points.crs
        )
    
    # Create a GeoDataFrame for parcels with only the required columns
    parcels_subset = gdf_parcels_with_stats[['parcel_id', 'company', 'geometry']].copy()
    
    # Spatial join to get company information
    try:
        # Use spatial join to match points to parcels
        gdf_points_with_company = gpd.sjoin(
            gdf_points, 
            parcels_subset, 
            how='left', 
            predicate='within'
        )
    except Exception as e:
        # Fallback to attribute join if spatial join fails
        st.warning(f"Spatial join failed. Falling back to attribute join: {e}")
        # Merge based on parcel_id if available
        if 'parcel_id' in gdf_points.columns and 'parcel_id' in gdf_parcels_with_stats.columns:
            gdf_points_with_company = gdf_points.merge(
                gdf_parcels_with_stats[['parcel_id', 'company']], 
                on='parcel_id', 
                how='left'
            )
            # Convert back to GeoDataFrame
            gdf_points_with_company = gpd.GeoDataFrame(
                gdf_points_with_company, 
                geometry=gdf_points.geometry, 
                crs=gdf_points.crs
            )
        else:
            st.error("Cannot join points with parcels. No common identifier found.")
            return None, None, None
    
    # Remove rows with no company information
    gdf_points_with_company = gdf_points_with_company.dropna(subset=['company'])
    
    # Nutrients (excluding pH)
    nutrients = ['p', 'k']
    colors = ['#1f77b4', '#ff7f0e']  # Blue, Orange
    
    # 1. Box Plot: Nutrient Levels by Company
    fig_company_boxplot = go.Figure()
    
    for i, nutrient in enumerate(nutrients):
        # Group data by company
        company_groups = [
            gdf_points_with_company[gdf_points_with_company['company'] == company][nutrient] 
            for company in gdf_points_with_company['company'].unique()
        ]
        company_labels = list(gdf_points_with_company['company'].unique())
        
        # Create box plot
        fig_company_boxplot.add_trace(go.Box(
            y=company_groups,
            name=nutrient.upper(),
            boxpoints='outliers',
            marker_color=colors[i],
            x=company_labels
        ))
    
    fig_company_boxplot.update_layout(
        title='Distribúcia Živín (P, K) podľa Spoločností',
        xaxis_title='Spoločnosť',
        yaxis_title='Hodnota',
        height=400,
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    # 2. Bar Chart: Average Nutrient Levels by Company
    company_avg_nutrients = gdf_points_with_company.groupby('company')[nutrients].mean().reset_index()
    
    fig_company_avg = go.Figure()
    for i, nutrient in enumerate(nutrients):
        fig_company_avg.add_trace(go.Bar(
            x=company_avg_nutrients['company'],
            y=company_avg_nutrients[nutrient],
            name=nutrient.upper(),
            marker_color=colors[i]
        ))
    
    fig_company_avg.update_layout(
        title='Priemerné Úrovne Živín (P, K) podľa Spoločností',
        xaxis_title='Spoločnosť',
        yaxis_title='Priemerná Hodnota',
        barmode='group',
        height=400,
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    # 3. Pie Chart: Nutrient Category Distribution by Company
    def categorize_nutrient(nutrient, values):
        if nutrient == 'p':
            categories = [
                (0, 50, 'Nízky'),
                (51, 80, 'Vyhovujúci'),
                (81, 115, 'Dobrý'),
                (116, 185, 'Vysoký'),
                (186, float('inf'), 'Veľmi vysoký')
            ]
        elif nutrient == 'k':
            categories = [
                (0, 50, 'Nízky'),
                (51, 100, 'Stredný'),
                (101, 200, 'Dobrý'),
                (201, 300, 'Vysoký'),
                (301, float('inf'), 'Veľmi vysoký')
            ]
        
        for low, high, label in categories:
            if low <= values < high:
                return label
        return 'Neurčené'
    
    # Pie Charts for P and K
    fig_company_pie = go.Figure()
    companies = gdf_points_with_company['company'].unique()
    
    for i, nutrient in enumerate(nutrients):
        # Prepare data for pie chart
        nutrient_categories = gdf_points_with_company.groupby('company').apply(
            lambda x: x[nutrient].apply(lambda val: categorize_nutrient(nutrient, val)).value_counts()
        )
        
        # Create subplot for each company
        for j, company in enumerate(companies):
            fig_company_pie.add_trace(go.Pie(
                labels=nutrient_categories[company].index, 
                values=nutrient_categories[company].values,
                name=f'{company} - {nutrient.upper()}',
                title=f'{company} - Kategórie {nutrient.upper()}',
                domain={'row': (i * len(companies) + j) // 3, 'column': (i * len(companies) + j) % 3}
            ))
    
    fig_company_pie.update_layout(
        title='Distribúcia Kategórií Živín (P, K) podľa Spoločností',
        grid={'rows': len(nutrients), 'columns': 3},
        height=900,
        margin=dict(l=50, r=50, t=100, b=50)
    )
    
    # 4. pH-specific Visualizations
    # Box Plot for pH
    fig_ph_boxplot = go.Figure()
    
    company_groups_ph = [
        gdf_points_with_company[gdf_points_with_company['company'] == company]['ph'] 
        for company in gdf_points_with_company['company'].unique()
    ]
    company_labels_ph = list(gdf_points_with_company['company'].unique())
    
    fig_ph_boxplot.add_trace(go.Box(
        y=company_groups_ph,
        name='pH',
        boxpoints='outliers',
        marker_color='#2ca02c',  # Green
        x=company_labels_ph
    ))
    
    fig_ph_boxplot.update_layout(
        title='Distribúcia pH podľa Spoločností',
        xaxis_title='Spoločnosť',
        yaxis_title='pH Hodnota',
        height=400,
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    # Pie Chart for pH Categories
    def categorize_ph(value):
        """
        Categorize pH values based on soil reaction:
        - do 4,5 extrémne kyslá
        - 4,6 - 5,0 silne kyslá
        - 5,1 - 5,5 kyslá
        - 5,6 - 6,5 slabo kyslá
        - 6,6 - 7,2 neutrálna
        - 7,3 - 7,7 alkalická
        - nad 7,7 silne alkalická
        """
        if value <= 4.5:
            return 'Extrémne kyslá'
        elif 4.6 <= value <= 5.0:
            return 'Silne kyslá'
        elif 5.1 <= value <= 5.5:
            return 'Kyslá'
        elif 5.6 <= value <= 6.5:
            return 'Slabo kyslá'
        elif 6.6 <= value <= 7.2:
            return 'Neutrálna'
        elif 7.3 <= value <= 7.7:
            return 'Alkalická'
        else:
            return 'Silne alkalická'
    
    # Pie Chart for pH Categories by Company
    fig_ph_pie = go.Figure()
    
    # Prepare data for pH pie chart
    ph_categories = gdf_points_with_company.groupby('company').apply(
        lambda x: x['ph'].apply(categorize_ph).value_counts()
    )
    
    # Create subplot for each company
    for j, company in enumerate(companies):
        fig_ph_pie.add_trace(go.Pie(
            labels=ph_categories[company].index, 
            values=ph_categories[company].values,
            name=f'{company} - pH',
            title=f'{company} - Kategórie pH',
            domain={'row': j // 3, 'column': j % 3}
        ))
    
    fig_ph_pie.update_layout(
        title='Distribúcia Kategórií pH podľa Spoločností',
        grid={'rows': (len(companies) + 2) // 3, 'columns': 3},
        height=900,
        margin=dict(l=50, r=50, t=100, b=50)
    )
    
    return fig_company_boxplot, fig_company_avg, fig_company_pie, fig_ph_boxplot, fig_ph_pie

def categorize_ph(value):
    """
    Categorize pH values based on soil reaction:
    - do 4,5 extrémne kyslá
    - 4,6 - 5,0 silne kyslá
    - 5,1 - 5,5 kyslá
    - 5,6 - 6,5 slabo kyslá
    - 6,6 - 7,2 neutrálna
    - 7,3 - 7,7 alkalická
    - nad 7,7 silne alkalická
    """
    if value <= 4.5:
        return 'Extrémne kyslá'
    elif 4.6 <= value <= 5.0:
        return 'Silne kyslá'
    elif 5.1 <= value <= 5.5:
        return 'Kyslá'
    elif 5.6 <= value <= 6.5:
        return 'Slabo kyslá'
    elif 6.6 <= value <= 7.2:
        return 'Neutrálna'
    elif 7.3 <= value <= 7.7:
        return 'Alkalická'
    else:
        return 'Silne alkalická'

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
    
    # Create additional visualizations
    st.markdown("## Doplňujúce Analýzy Pôdnych Vzoriek")
    
    # Create visualization columns
    col1, col2 = st.columns(2)
    
    with col1:
        # Box Plot
        st.markdown("### Distribúcia Živín")
        fig_boxplot, _, _, _, _ = create_additional_visualizations(gdf_parcels_with_stats, gdf_points)
        st.plotly_chart(fig_boxplot, use_container_width=True, key='boxplot')
        
        # Histogram
        st.markdown("### Frekvencia Úrovní Živín")
        _, _, fig_histogram, _, _ = create_additional_visualizations(gdf_parcels_with_stats, gdf_points)
        st.plotly_chart(fig_histogram, use_container_width=True, key='histogram')
    
    with col2:
        # Scatter Matrix
        st.markdown("### Korelácie medzi Živinami")
        _, fig_scatter_matrix, _, _, _ = create_additional_visualizations(gdf_parcels_with_stats, gdf_points)
        st.plotly_chart(fig_scatter_matrix, use_container_width=True, key='scatter_matrix')
        
        # Pie Charts
        st.markdown("### Kategórie Živín")
        _, _, _, fig_pie, _ = create_additional_visualizations(gdf_parcels_with_stats, gdf_points)
        st.plotly_chart(fig_pie, use_container_width=True, key='pie_chart')
    
    # Company-based Visualizations
    st.markdown("## Analýzy Podľa Spoločností")
    
    # Create visualization columns for company data
    col3, col4 = st.columns(2)
    
    with col3:
        # Company Box Plot
        st.markdown("### Distribúcia Živín (P, K)")
        fig_company_boxplot, _, _, _, _ = create_company_visualizations(gdf_parcels_with_stats, gdf_points)
        st.plotly_chart(fig_company_boxplot, use_container_width=True, key='company_boxplot')
    
    with col4:
        # Company Average Nutrients
        st.markdown("### Priemerné Úrovne Živín (P, K)")
        _, fig_company_avg, _, _, _ = create_company_visualizations(gdf_parcels_with_stats, gdf_points)
        st.plotly_chart(fig_company_avg, use_container_width=True, key='company_avg')
    
    # Company Pie Charts for P and K
    st.markdown("### Kategórie Živín (P, K) podľa Spoločností")
    _, _, fig_company_pie, _, _ = create_company_visualizations(gdf_parcels_with_stats, gdf_points)
    st.plotly_chart(fig_company_pie, use_container_width=True, key='company_pie')
    
    # pH-specific Visualizations
    st.markdown("## Analýzy pH")
    
    # pH Box Plot
    st.markdown("### Distribúcia pH podľa Spoločností")
    _, _, _, _, fig_ph_boxplot = create_company_visualizations(gdf_parcels_with_stats, gdf_points)
    st.plotly_chart(fig_ph_boxplot, use_container_width=True, key='ph_boxplot')
    
    # pH Pie Charts
    st.markdown("### Kategórie pH podľa Spoločností")
    _, _, _, _, fig_ph_pie = create_company_visualizations(gdf_parcels_with_stats, gdf_points)
    st.plotly_chart(fig_ph_pie, use_container_width=True, key='ph_pie')

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
