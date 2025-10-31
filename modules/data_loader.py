import os
import toml
from dotenv import load_dotenv
import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import logging

# Konfigurácia logovania
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

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
    for var in env_vars:
        value = os.getenv(var)
        if value:
            logger.info(f"Použitá premenná prostredia: {var}")
            return value
    
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
        query = text(f"SELECT {columns_str} FROM yield_level.skeagis_yields")
        
        # Načítanie dát
        with engine.connect() as connection:
            df = pd.read_sql(query, connection)
        
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