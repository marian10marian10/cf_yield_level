import os
import toml
from dotenv import load_dotenv
import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import logging

# Konfigurácia logovania
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Funkcia na načítanie konfigurácie z railway.toml
def load_railway_config():
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'railway.toml')
        if os.path.exists(config_path):
            return toml.load(config_path)
    except Exception as e:
        logger.warning(f"Chyba pri načítaní railway.toml: {e}")
    return {}

# Funkcia na bezpečné načítanie premennej prostredia
def safe_get_env(env_vars, default=None):
    """
    Bezpečne načíta prvú neprázdnu premennú z poskytnutého zoznamu
    
    Args:
        env_vars (list): Zoznam názvov premenných prostredia
        default (str, optional): Predvolená hodnota, ak nie je nájdená žiadna premenná
    
    Returns:
        str: Hodnota premennej prostredia alebo predvolená hodnota
    """
    railway_config = load_railway_config().get('database', {})
    
    for var in env_vars:
        # Najprv skúsi premenné prostredia
        value = os.getenv(var)
        if value:
            logger.info(f"Použitá premenná prostredia: {var}")
            return value
    
    # Potom skúsi railway.toml
    for var_name, config_key in [
        ('DB_HOST_DESTINATION', 'host'),
        ('DB_USER_DESTINATION', 'user'),
        ('DB_PASSWORD_DESTINATION', 'password'),
        ('DB_NAME_DESTINATION', 'name'),
        ('DB_PORT_DESTINATION', 'port')
    ]:
        value = railway_config.get(config_key)
        if value:
            logger.info(f"Použitá hodnota z railway.toml: {config_key}")
            return value
    
    # Ak nič nenájde, vráti predvolenú hodnotu
    logger.warning(f"Nepodarilo sa nájsť hodnotu pre premenné: {env_vars}")
    return default

# Database connection parameters
DB_HOST_DESTINATION = safe_get_env([
    'DB_HOST_DESTINATION', 
    'RAILWAY_DB_HOST', 
    'DATABASE_HOST'
], default='localhost')

DB_USER_DESTINATION = safe_get_env([
    'DB_USER_DESTINATION', 
    'RAILWAY_DB_USER', 
    'DATABASE_USER'
], default='db_admin')

DB_PASSWORD_DESTINATION = safe_get_env([
    'DB_PASSWORD_DESTINATION', 
    'RAILWAY_DB_PASSWORD', 
    'DATABASE_PASSWORD'
], default='')

DB_NAME_DESTINATION = safe_get_env([
    'DB_NAME_DESTINATION', 
    'RAILWAY_DB_NAME', 
    'DATABASE_NAME'
], default='postgres')

DB_PORT_DESTINATION = safe_get_env([
    'DB_PORT_DESTINATION', 
    'RAILWAY_DB_PORT', 
    'DATABASE_PORT'
], default='5432')

# Kontrola povinných premenných
def validate_db_config():
    """
    Validácia konfigurácie databázy
    
    Raises:
        ValueError: Ak chýbajú kritické konfiguračné parametre
    """
    missing_params = []
    
    if not DB_HOST_DESTINATION:
        missing_params.append("Hostiteľ databázy (DB_HOST_DESTINATION)")
    
    if not DB_USER_DESTINATION:
        missing_params.append("Používateľ databázy (DB_USER_DESTINATION)")
    
    if not DB_PASSWORD_DESTINATION:
        missing_params.append("Heslo databázy (DB_PASSWORD_DESTINATION)")
    
    if not DB_NAME_DESTINATION:
        missing_params.append("Názov databázy (DB_NAME_DESTINATION)")
    
    if missing_params:
        error_message = "Chýbajúce konfiguračné parametre databázy:\n" + "\n".join(
            f"- {param}" for param in missing_params
        )
        logger.error(error_message)
        st.error(error_message + "\n\nSkontrolujte .env, railway.toml alebo nastavenia Railway.")
        raise ValueError(error_message)

# Vykonanie validácie
validate_db_config()

def load_data():
    """Načítanie dát z PostgreSQL databázy"""
    try:
        # Vytvorenie connection string
        connection_string = f"postgresql://{DB_USER_DESTINATION}:{DB_PASSWORD_DESTINATION}@{DB_HOST_DESTINATION}:{DB_PORT_DESTINATION}/{DB_NAME_DESTINATION}"
        
        logger.info(f"Pripájanie k databáze: {DB_HOST_DESTINATION}")
        
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
        check_columns_query = """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'yield_level' 
        AND table_name = 'skeagis_yields'
        ORDER BY ordinal_position
        """
        
        try:
            columns_df = pd.read_sql(check_columns_query, engine)
            available_columns = columns_df['column_name'].tolist()
            logger.info(f"Dostupné stĺpce: {available_columns}")
        except Exception as column_error:
            logger.error(f"Chyba pri načítaní stĺpcov: {column_error}")
            st.error(f"Chyba pri načítaní stĺpcov: {column_error}")
            st.warning("Skontrolujte pripojenie k databáze a oprávnenia.")
            return None
        
        # Dynamické vytvorenie SELECT query na základe dostupných stĺpcov
        select_columns = []
        required_columns = ['parcel_id', 'yield_ha', 'season', 'ppa_crop_id']
        
        for col in required_columns:
            if col in available_columns:
                select_columns.append(col)
            else:
                st.warning(f"Stĺpec '{col}' neexistuje v tabuľke!")
        
        # Pridanie area ak existuje
        if 'area' in available_columns:
            select_columns.append('area')
        
        # Vytvorenie SQL query - všetky sezóny pre výnosy
        columns_str = ', '.join(select_columns)
        
        # Samotný dopyt na načítanie dát
        query = f"SELECT {columns_str} FROM yield_level.skeagis_yields"
        
        # Načítanie dát
        df = pd.read_sql(query, engine)
        
        # Zatvorenie spojenia
        engine.dispose()
        
        return df
    
    except Exception as e:
        logger.error(f"Chyba pri načítaní dát: {e}")
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