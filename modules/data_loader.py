import os
import sys
import toml
from dotenv import load_dotenv
import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import logging
import socket
import traceback

# Konfigurácia logovania
def setup_logging():
    """Nastavenie komplexného logovania"""
    # Vytvorenie adresára pre logy, ak neexistuje
    log_dir = '/tmp/logs'
    os.makedirs(log_dir, exist_ok=True)
    
    # Konfigurácia hlavného logovania
    logging.basicConfig(
        level=logging.DEBUG, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'database_connection.log'), mode='w'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Konfigurácia logovania pre SQLAlchemy
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.INFO)

# Volanie setup_logging() hneď po definícii
setup_logging()
logger = logging.getLogger(__name__)

# Pridanie funkcie na zaznamenanie všetkých environment premenných
def log_environment_variables():
    """Zaznamenanie všetkých environment premenných"""
    logger.info("--- ENVIRONMENT VARIABLES ---")
    for key, value in os.environ.items():
        # Maskuj hesla a citlivé údaje
        if any(secret in key.lower() for secret in ['password', 'secret', 'token', 'key']):
            logger.info(f"{key}: ****")
        else:
            logger.info(f"{key}: {value}")
    logger.info("--- END ENVIRONMENT VARIABLES ---")

# Prednastavené hodnoty pre databázové pripojenie
DEFAULT_DB_CONFIG = {
    'host': 'team-pz.cyp6scadbpmv.eu-central-1.rds.amazonaws.com',
    'user': 'db_admin',
    'password': 'Ybm=Zjk#sTf3#^]ybD<k',
    'name': 'postgres',
    'port': '5432'
}

# Load environment variables
load_dotenv()

# Zavolanie funkcie na zaznamenanie environment premenných
log_environment_variables()

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

def load_data():
    """Načítanie dát z PostgreSQL databázy"""
    try:
        # Vytvorenie connection string
        connection_string = get_database_connection_string()
        
        logger.info(f"Pripájanie k databáze: {DB_HOST_DESTINATION}")
        logger.info(f"Parametre pripojenia: user={DB_USER_DESTINATION}, host={DB_HOST_DESTINATION}, port={DB_PORT_DESTINATION}, db={DB_NAME_DESTINATION}")
        
        # Vytvorenie engine s pridanými parametrami pre lepšiu diagnostiku
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
        
        # Najprv skontrolujeme dostupné stĺpce v tabuľke
        with engine.connect() as connection:
            # Použitie text() pre bezpečný SQL dopyt
            columns_query = text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'yield_level' 
            AND table_name = 'skeagis_yields'
            ORDER BY ordinal_position
            """)
            
            columns_result = connection.execute(columns_query)
            available_columns = [row[0] for row in columns_result]
            logger.info(f"Dostupné stĺpce: {available_columns}")
        
        # Dynamické vytvorenie SELECT query na základe dostupných stĺpcov
        select_columns = []
        required_columns = ['parcel_id', 'yield_ha', 'season', 'ppa_crop_id']
        optional_columns = ['yield_area', 'yield_sum', 'id', 'parcel_season_id']
        
        # Pridaj požadované stĺpce
        for col in required_columns:
            if col in available_columns:
                select_columns.append(col)
            else:
                logger.warning(f"Požadovaný stĺpec '{col}' neexistuje v tabuľke!")
        
        # Pridaj voliteľné stĺpce
        for col in optional_columns:
            if col in available_columns:
                select_columns.append(col)
        
        # Vytvorenie SQL query - všetky sezóny pre výnosy
        columns_str = ', '.join(select_columns)
        
        # Samotný dopyt na načítanie dát s ochranou pred prázdnymi hodnotami
        query = text(f"""
        SELECT {columns_str}
        FROM yield_level.skeagis_yields
        WHERE 
            yield_ha IS NOT NULL 
            AND yield_ha > 0 
            AND ppa_crop_id IS NOT NULL
        LIMIT 10000  -- Pridaný limit pre istotu
        """)
        
        # Načítanie dát
        with engine.connect() as connection:
            df = pd.read_sql(query, connection)
        
        # Zatvorenie spojenia
        engine.dispose()
        
        # Kontrola načítaných dát
        if df.empty:
            logger.warning("Načítaný prázdny DataFrame")
            st.warning("Nepodarilo sa načítať žiadne dáta. Skontrolujte databázu.")
            return None
        
        logger.info(f"Načítaných riadkov: {len(df)}")
        logger.info(f"Stĺpce DataFrame: {df.columns.tolist()}")
        
        return df
    
    except Exception as e:
        logger.error(f"Chyba pri načítaní dát: {e}")
        logger.error(traceback.format_exc())  # Pridaný detailný traceback
        st.error(f"Chyba pri načítaní dát: {e}")
        st.warning("Skontrolujte pripojenie k databáze a oprávnenia.")
        return None

def calculate_yield_percentage(df):
    """
    Výpočet percentuálnych výnosov pre každú plodinu
    
    Args:
        df (pandas.DataFrame): DataFrame s výnosmi
    
    Returns:
        pandas.DataFrame: DataFrame s pridaným stĺpcom percentuálnych výnosov
    """
    if df is None or df.empty:
        st.warning("Prázdny DataFrame pre výpočet percentuálnych výnosov.")
        return df
    
    try:
        # Pridanie stĺpca 'crop' podľa ppa_crop_id
        crop_mapping = {
            1: 'Pšenica letná ozimná',
            2: 'Jačmeň jarný',
            3: 'Kukurica na zrno',
            4: 'Repka ozimná',
            # Pridajte ďalšie mapovanie podľa potreby
        }
        
        # Bezpečná konverzia ppa_crop_id na integer
        def safe_int_convert(value):
            try:
                return int(float(str(value).strip()))
            except (ValueError, TypeError):
                return None
        
        df['ppa_crop_id'] = df['ppa_crop_id'].apply(safe_int_convert)
        df['crop'] = df['ppa_crop_id'].map(crop_mapping).fillna('Iné')
        
        # Výpočet percentuálnych výnosov pre každú plodinu
        crop_yields = df.groupby('crop')['yield_ha'].agg(['mean', 'min', 'max'])
        crop_yields['range'] = crop_yields['max'] - crop_yields['min']
        
        # Pridanie percentuálnych výnosov
        def calculate_percentage(row, crop_mean):
            if pd.isna(row['yield_ha']) or pd.isna(crop_mean):
                return np.nan
            return ((row['yield_ha'] - crop_mean) / crop_mean) * 100
        
        for crop, stats in crop_yields.iterrows():
            df.loc[df['crop'] == crop, 'yield_percentage'] = df[df['crop'] == crop].apply(
                lambda row: calculate_percentage(row, stats['mean']), axis=1
            )
        
        return df
    
    except Exception as e:
        st.error(f"Chyba pri výpočte percentuálnych výnosov: {e}")
        return df