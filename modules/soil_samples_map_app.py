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

def safe_get_env(env_vars, default=None):
    """
    Bezpečne načíta prvú neprázdnu premennú z poskytnutého zoznamu
    
    Args:
        env_vars (list): Zoznam názvov premenných prostredia
        default (str, optional): Predvolená hodnota, ak nie je nájdená žiadna premenná
    
    Returns:
        str: Hodnota premennej prostredia alebo predvolená hodnota
    """
    logger.debug(f"Hľadanie hodnoty pre premenné: {env_vars}")
    
    # Najprv skúsi premenné prostredia
    for var in env_vars:
        value = os.getenv(var)
        if value:
            logger.debug(f"Použitá premenná prostredia: {var} = {value}")
            return value
    
    # Potom skúsi prednastavené hodnoty
    logger.warning(f"Nepodarilo sa nájsť hodnotu pre premenné: {env_vars}")
    return default

# Database connection parameters
DB_HOST_DESTINATION = safe_get_env([
    'DB_HOST_DESTINATION', 
    'RAILWAY_DB_HOST', 
    'DATABASE_HOST'
], default=DEFAULT_DB_CONFIG['host'])

DB_USER_DESTINATION = safe_get_env([
    'DB_USER_DESTINATION', 
    'RAILWAY_DB_USER', 
    'DATABASE_USER'
], default=DEFAULT_DB_CONFIG['user'])

DB_PASSWORD_DESTINATION = safe_get_env([
    'DB_PASSWORD_DESTINATION', 
    'RAILWAY_DB_PASSWORD', 
    'DATABASE_PASSWORD'
], default=DEFAULT_DB_CONFIG['password'])

DB_NAME_DESTINATION = safe_get_env([
    'DB_NAME_DESTINATION', 
    'RAILWAY_DB_NAME', 
    'DATABASE_NAME'
], default=DEFAULT_DB_CONFIG['name'])

DB_PORT_DESTINATION = safe_get_env([
    'DB_PORT_DESTINATION', 
    'RAILWAY_DB_PORT', 
    'DATABASE_PORT'
], default=DEFAULT_DB_CONFIG['port'])

def get_database_connection_string():
    """
    Vygeneruje connection string pre databázu
    
    Returns:
        str: Connection string pre SQLAlchemy
    """
    connection_string = f"postgresql://{DB_USER_DESTINATION}:****@{DB_HOST_DESTINATION}:{DB_PORT_DESTINATION}/{DB_NAME_DESTINATION}"
    logger.debug(f"Generovaný connection string: {connection_string}")
    return f"postgresql://{DB_USER_DESTINATION}:{DB_PASSWORD_DESTINATION}@{DB_HOST_DESTINATION}:{DB_PORT_DESTINATION}/{DB_NAME_DESTINATION}"

def get_database_connection():
    """Establish a connection to the PostgreSQL database."""
    try:
        connection_string = get_database_connection_string()
        logger.info(f"Pripájanie k databáze: {DB_HOST_DESTINATION}")
        logger.info(f"Parametre pripojenia: user={DB_USER_DESTINATION}, host={DB_HOST_DESTINATION}, port={DB_PORT_DESTINATION}, db={DB_NAME_DESTINATION}")
        
        engine = create_engine(connection_string, 
                               connect_args={
                                   'connect_timeout': 10,  # Pridanie timeoutu
                                   'keepalives': 1,        # Udržiavanie aktívneho pripojenia
                                   'keepalives_idle': 30   # Interval keepalive
                               },
                               pool_size=5,               # Veľkosť connection pool
                               max_overflow=10,           # Maximálny počet nadpočetných pripojení
                               pool_timeout=30,           # Timeout pre získanie pripojenia z pool-u
                               pool_recycle=1800)         # Recyklácia pripojení každých 30 minút
        return engine
    except Exception as e:
        logger.error(f"Error connecting to the database: {e}")
        st.error(f"Error connecting to the database: {e}")
        return None

def process_spatial_data(gdf_parcels, gdf_points):
    """Perform spatial join and aggregate soil sample data."""
    try:
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
    except Exception as e:
        logger.error(f"Error in spatial data processing: {e}")
        st.error(f"Chyba pri spracovaní priestorových dát: {e}")
        return gdf_parcels, gdf_points

# Zvyšok kódu zostáva nezmenený (všetky pôvodné funkcie)
# ... (celá pôvodná implementácia zostáva rovnaká)

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

# Všetky ďalšie funkcie zostávajú nezmenené (create_map, atď.)
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