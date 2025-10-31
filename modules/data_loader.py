import os
import toml
from dotenv import load_dotenv
import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import create_engine

# Load environment variables
load_dotenv()

# Funkcia na načítanie konfigurácie z railway.toml
def load_railway_config():
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'railway.toml')
        if os.path.exists(config_path):
            return toml.load(config_path)
    except Exception as e:
        st.warning(f"Chyba pri načítaní railway.toml: {e}")
    return {}

# Database connection parameters
DB_USER_DESTINATION = (
    os.getenv('DB_USER_DESTINATION') or 
    os.getenv('RAILWAY_DB_USER') or 
    load_railway_config().get('database', {}).get('user')
)
DB_PASSWORD_DESTINATION = (
    os.getenv('DB_PASSWORD_DESTINATION') or 
    os.getenv('RAILWAY_DB_PASSWORD') or 
    load_railway_config().get('database', {}).get('password')
)
DB_HOST_DESTINATION = (
    os.getenv('DB_HOST_DESTINATION') or 
    os.getenv('RAILWAY_DB_HOST') or 
    load_railway_config().get('database', {}).get('host')
)
DB_NAME_DESTINATION = (
    os.getenv('DB_NAME_DESTINATION') or 
    os.getenv('RAILWAY_DB_NAME') or 
    load_railway_config().get('database', {}).get('name', 'postgres')
)
DB_PORT_DESTINATION = (
    os.getenv('DB_PORT_DESTINATION') or 
    os.getenv('RAILWAY_DB_PORT') or 
    load_railway_config().get('database', {}).get('port', 5432)
)

# Kontrola povinných premenných
REQUIRED_VARS = [
    ('DB_USER_DESTINATION', 'Používateľské meno databázy'),
    ('DB_PASSWORD_DESTINATION', 'Heslo databázy'),
    ('DB_HOST_DESTINATION', 'Hostiteľ databázy'),
    ('DB_NAME_DESTINATION', 'Názov databázy')
]

missing_vars = [name for name, desc in REQUIRED_VARS if not locals()[name]]

if missing_vars:
    error_message = "Chýbajúce konfiguračné premenné:\n" + "\n".join(
        f"- {name}" for name in missing_vars
    )
    st.error(error_message + "\n\nSkontrolujte .env, railway.toml alebo nastavenia Railway.")
    raise ValueError(error_message)

def load_data():
    """Načítanie dát z PostgreSQL databázy"""
    try:
        # Vytvorenie connection string
        connection_string = f"postgresql://{DB_USER_DESTINATION}:{DB_PASSWORD_DESTINATION}@{DB_HOST_DESTINATION}:{DB_PORT_DESTINATION}/{DB_NAME_DESTINATION}"
        
        # Vytvorenie engine s pridanými parametrami pre lepšiu diagnostiku
        engine = create_engine(connection_string, 
                               connect_args={'connect_timeout': 10},  # Pridanie timeoutu
                               pool_size=5,  # Veľkosť connection pool
                               max_overflow=10)  # Maximálny počet nadpočetných pripojení
        
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
        except Exception as column_error:
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