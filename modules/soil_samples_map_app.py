# Explicitní import potřebných knihoven
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

# Konfigurace logovania
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/logs/soil_samples.log', mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Globální proměnné pro databázové připojení
DEFAULT_DB_CONFIG = {
    'host': 'team-pz.cyp6scadbpmv.eu-central-1.rds.amazonaws.com',
    'user': 'db_admin',
    'password': 'Ybm=Zjk#sTf3#^]ybD<k',
    'name': 'postgres',
    'port': '5432'
}

# Funkce pro bezpečné načítání proměnných prostředí
def safe_get_env(env_vars, default=None):
    """
    Bezpečně načte první neprázdnou proměnnou z poskytnutého seznamu
    
    Args:
        env_vars (list): Seznam názvů proměnných prostředí
        default (str, optional): Výchozí hodnota, pokud není nalezena žádná proměnná
    
    Returns:
        str: Hodnota proměnné prostředí nebo výchozí hodnota
    """
    logger.debug(f"Hledání hodnoty pro proměnné: {env_vars}")
    
    # Nejprve zkusí proměnné prostředí
    for var in env_vars:
        value = os.getenv(var)
        if value:
            logger.debug(f"Použitá proměnná prostředí: {var} = {value}")
            return value
    
    # Poté zkusí výchozí hodnoty
    logger.warning(f"Nepodařilo se najít hodnotu pro proměnné: {env_vars}")
    return default

# Parametry databázového připojení
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

# Funkce pro generování připojovacího řetězce
def get_database_connection_string():
    """
    Vygeneruje připojovací řetězec pro databázi
    
    Returns:
        str: Připojovací řetězec pro SQLAlchemy
    """
    connection_string = f"postgresql://{DB_USER_DESTINATION}:****@{DB_HOST_DESTINATION}:{DB_PORT_DESTINATION}/{DB_NAME_DESTINATION}"
    logger.debug(f"Generovaný připojovací řetězec: {connection_string}")
    return f"postgresql://{DB_USER_DESTINATION}:{DB_PASSWORD_DESTINATION}@{DB_HOST_DESTINATION}:{DB_PORT_DESTINATION}/{DB_NAME_DESTINATION}"

# Funkce pro získání databázového připojení
def get_database_connection():
    """Navázání připojení k PostgreSQL databázi."""
    try:
        connection_string = get_database_connection_string()
        logger.info(f"Připojování k databázi: {DB_HOST_DESTINATION}")
        logger.info(f"Parametry připojení: user={DB_USER_DESTINATION}, host={DB_HOST_DESTINATION}, port={DB_PORT_DESTINATION}, db={DB_NAME_DESTINATION}")
        
        engine = create_engine(connection_string, 
                               connect_args={
                                   'connect_timeout': 10,  # Přidání timeoutu
                                   'keepalives': 1,        # Udržování aktivního připojení
                                   'keepalives_idle': 30   # Interval keepalive
                               },
                               pool_size=5,               # Velikost connection pool
                               max_overflow=10,           # Maximální počet nadpočetných připojení
                               pool_timeout=30,           # Timeout pro získání připojení z pool-u
                               pool_recycle=1800)         # Recyklace připojení každých 30 minut
        return engine
    except Exception as e:
        logger.error(f"Chyba při připojování k databázi: {e}")
        st.error(f"Chyba při připojování k databázi: {e}")
        return None

# Funkce pro načítání dat parcel
def load_parcels_data():
    """Načtení dat parcel z databáze."""
    logger.info("Začátek načítání dat parcel")
    
    try:
        # Vytvoření databázového připojení
        engine = get_database_connection()
        
        if not engine:
            logger.error("Nepodařilo se vytvořit databázové připojení")
            st.error("Nepodařilo se vytvořit databázové připojení")
            return None
        
        # SQL dotaz pro načtení dat parcel
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
        
        # Načtení dat
        df = pd.read_sql(query, engine)
        
        # Konverze na GeoDataFrame
        gdf_parcels = gpd.GeoDataFrame(
            df, 
            geometry=gpd.GeoSeries.from_wkt(df['geometry_text'], crs='EPSG:4326')
        )
        
        logger.info(f"Načteno {len(gdf_parcels)} parcel")
        return gdf_parcels
    
    except Exception as e:
        logger.error(f"Chyba při načítání dat parcel: {e}")
        st.error(f"Chyba při načítání dat parcel: {e}")
        return None
    finally:
        if 'engine' in locals():
            engine.dispose()

# Funkce pro načítání dat půdních vzorků
def load_soil_samples_data():
    """Načtení dat půdních vzorků z databáze."""
    logger.info("Začátek načítání dat půdních vzorků")
    
    try:
        # Vytvoření databázového připojení
        engine = get_database_connection()
        
        if not engine:
            logger.error("Nepodařilo se vytvořit databázové připojení")
            st.error("Nepodařilo se vytvořit databázové připojení")
            return None
        
        # SQL dotaz pro načtení dat půdních vzorků
        query = """
        SELECT 
            id, 
            p, 
            k, 
            ph, 
            geom
        FROM yield_level.soil_samples_raw
        """
        
        # Načtení dat
        gdf_points = gpd.read_postgis(query, engine, geom_col='geom')
        
        logger.info(f"Načteno {len(gdf_points)} půdních vzorků")
        return gdf_points
    
    except Exception as e:
        logger.error(f"Chyba při načítání dat půdních vzorků: {e}")
        st.error(f"Chyba při načítání dat půdních vzorků: {e}")
        return None
    finally:
        if 'engine' in locals():
            engine.dispose()

# Zbytek kódu zůstává nezměněn...
# (všechny ostatní funkce jako process_spatial_data, create_map, soil_samples_map, about_page atd.)

# Explicitní export funkcí
__all__ = ['soil_samples_map', 'about_page', 'load_parcels_data', 'load_soil_samples_data']

# Hlavní spouštěcí funkce
def main():
    # Vytvoření navigace v postranním panelu
    page = st.sidebar.radio(
        "Navigace", 
        ["Mapa Půdních Vzorků", "O Aplikaci"]
    )
    
    # Vykreslení vybrané stránky
    if page == "Mapa Půdních Vzorků":
        soil_samples_map()
    else:
        about_page()

if __name__ == '__main__':
    main()