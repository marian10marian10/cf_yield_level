import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
import os
import logging
import sys
from dotenv import load_dotenv

# Konfigurácia logovania
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/logs/enterprise_stats.log', mode='w'),
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

def load_prediction_demand_data():
    """Load data from yield_level.mv_25_26_prediction_demand materialized view"""
    try:
        # Create database connection
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
        
        # Load data from the materialized view
        query = text("SELECT * FROM yield_level.mv_25_26_prediction_demand")
        
        with engine.connect() as connection:
            df = pd.read_sql(query, connection)
        
        # Close the connection
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
        logger.error(sys.exc_info()[2])
        st.error(f"Chyba pri načítaní dát: {e}")
        return None

def show_enterprise_stats_db_prediction():
    """Display enterprise statistics using prediction and demand data"""
    st.markdown('<h1 class="main-header">🏭 Štatistiky podniku (Predikcia 25/26)</h1>', unsafe_allow_html=True)
    
    # Load data
    df = load_prediction_demand_data()
    
    if df is None:
        st.error("Nepodarilo sa načítať dáta.")
        return
    
    # Convert yield predictions to numeric, handling potential non-numeric values
    def safe_convert_to_numeric(series):
        try:
            # Try to convert to numeric, coercing errors to NaN
            return pd.to_numeric(series, errors='coerce')
        except:
            # If conversion fails, return NaN
            return pd.Series([float('nan')] * len(series))
    
    # Aggregate data by company
    company_stats = df.groupby('company').agg({
        'parcel_id': 'count',
        'total_demand_n': 'sum',
        'total_demand_p': 'sum',
        'total_demand_k': 'sum',
    }).reset_index()
    
    company_stats.columns = ['Spoločnosť', 'Počet parciel', 'Celková potreba N', 'Celková potreba P', 'Celková potreba K']
    
    # Nutrient demand by company
    fig_nutrient_demand = go.Figure()
    
    # Add traces for N, P, K
    nutrients = ['Celková potreba N', 'Celková potreba P', 'Celková potreba K']
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
    
    for nutrient, color in zip(nutrients, colors):
        fig_nutrient_demand.add_trace(go.Bar(
            x=company_stats['Spoločnosť'],
            y=company_stats[nutrient],
            name=nutrient,
            marker_color=color
        ))
    
    fig_nutrient_demand.update_layout(
        title='Celková potreba živín podľa spoločností',
        xaxis_title='Spoločnosť',
        yaxis_title='Potreba živín',
        barmode='group'
    )
    st.plotly_chart(fig_nutrient_demand, use_container_width=True)
    
    # Crop analysis
    # Aggregate data by crop with safe numeric conversion and rounding
    crop_stats = df.groupby('crops').agg({
        'parcel_id': 'count',
        'total_demand_n': 'sum',
        'total_demand_p': 'sum',
        'total_demand_k': 'sum',
        '25_26_yield_predictions': lambda x: round(safe_convert_to_numeric(x).mean(), 2)
    }).reset_index()
    
    crop_stats.columns = ['Plodina', 'Počet parciel', 'Celková potreba N', 'Celková potreba P', 'Celková potreba K', 'Priemerná predikcia výnosov']
    
    # Nutrient demand by crop
    fig_crop_nutrient_demand = go.Figure()
    
    for nutrient, color in zip(nutrients, colors):
        fig_crop_nutrient_demand.add_trace(go.Bar(
            x=crop_stats['Plodina'],
            y=crop_stats[nutrient],
            name=nutrient,
            marker_color=color
        ))
    
    fig_crop_nutrient_demand.update_layout(
        title='Celková potreba živín podľa plodín',
        xaxis_title='Plodina',
        yaxis_title='Potreba živín',
        barmode='group'
    )
    st.plotly_chart(fig_crop_nutrient_demand, use_container_width=True)
    
    # Detailed data tables
    st.markdown("## 📋 Detailné údaje")
    
    # Company statistics table
    st.subheader("Štatistiky spoločností")
    st.dataframe(company_stats, use_container_width=True)
    
    # Crop statistics table
    st.subheader("Štatistiky plodín")
    st.dataframe(crop_stats, use_container_width=True)