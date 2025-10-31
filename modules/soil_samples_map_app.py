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

# Zvyšok kódu zostáva nezmenený (všetky funkcie soil_samples_map(), about_page(), main() atď.)
# ... (celá pôvodná implementácia zostáva rovnaká)