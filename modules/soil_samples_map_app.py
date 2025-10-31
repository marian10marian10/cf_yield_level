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

# Load environment variables
load_dotenv()

# Globální proměnné pro databázové připojení
DEFAULT_DB_CONFIG = {
    'host': 'team-pz.cyp6scadbpmv.eu-central-1.rds.amazonaws.com',
    'user': 'db_admin',
    'password': 'Ybm=Zjk#sTf3#^]ybD<k',
    'name': 'postgres',
    'port': '5432'
}

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

def get_database_connection_string():
    """
    Vygeneruje připojovací řetězec pro databázi
    
    Returns:
        str: Připojovací řetězec pro SQLAlchemy
    """
    connection_string = f"postgresql://{DB_USER_DESTINATION}:****@{DB_HOST_DESTINATION}:{DB_PORT_DESTINATION}/{DB_NAME_DESTINATION}"
    logger.debug(f"Generovaný připojovací řetězec: {connection_string}")
    return f"postgresql://{DB_USER_DESTINATION}:{DB_PASSWORD_DESTINATION}@{DB_HOST_DESTINATION}:{DB_PORT_DESTINATION}/{DB_NAME_DESTINATION}"

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

def process_spatial_data(gdf_parcels, gdf_points):
    """Prostorové zpracování dat."""
    try:
        # Prostorové spojení bodů s parcelami
        gdf_points_with_parcels = gpd.sjoin(gdf_points, gdf_parcels, how='left')
        
        # Agregace dat půdních vzorků podle parcel
        parcel_soil_stats = gdf_points_with_parcels.groupby('parcel_id').agg({
            'p': 'mean',
            'k': 'mean',
            'ph': 'mean'
        }).reset_index()
        
        # Sloučení agregovaných statistik zpět do GeoDataFrame parcel
        gdf_parcels_with_stats = gdf_parcels.merge(parcel_soil_stats, on='parcel_id', how='left')
        
        # Zajištění, že stále pracujeme s GeoDataFrame
        if not isinstance(gdf_parcels_with_stats, gpd.GeoDataFrame):
            gdf_parcels_with_stats = gpd.GeoDataFrame(
                gdf_parcels_with_stats, 
                geometry=gdf_parcels.geometry, 
                crs=gdf_parcels.crs
            )
        
        return gdf_parcels_with_stats, gdf_points
    
    except Exception as e:
        logger.error(f"Chyba při prostorovém zpracování dat: {e}")
        st.error(f"Chyba při prostorovém zpracování dat: {e}")
        return gdf_parcels, gdf_points

def create_map(gdf_parcels_with_stats, gdf_points, selected_parameter):
    """Vytvoření interaktivní mapy."""
    # Mapování názvů parametrů na sloupce
    param_map = {
        'Fosfor (P)': 'p',
        'Draslík (K)': 'k',
        'pH': 'ph'
    }
    
    # Pokud nejsou potřebná data, vrátí prázdný graf
    if gdf_parcels_with_stats is None or gdf_points is None:
        logger.warning("Prázdná data pro mapu")
        return go.Figure()
    
    try:
        param_col = param_map[selected_parameter]
        
        # Vytvoření figury
        fig = go.Figure()
        
        # Přidání bodů půdních vzorků
        scatter = go.Scattermapbox(
            lat=gdf_points.geometry.y.tolist(),
            lon=gdf_points.geometry.x.tolist(),
            mode='markers',
            marker=dict(
                size=8,
                color=gdf_points[param_col],
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title=selected_parameter)
            ),
            text=[f'ID: {id}<br>{selected_parameter}: {val:.2f}' for id, val in zip(gdf_points['id'], gdf_points[param_col])],
            hoverinfo='text',
            name='Vzorky půdy'
        )
        fig.add_trace(scatter)
        
        # Aktualizace layoutu s mapou Carto Positron
        fig.update_layout(
            mapbox_style="carto-positron",
            mapbox=dict(
                center=dict(
                    lat=gdf_points.geometry.centroid.y.mean(),
                    lon=gdf_points.geometry.centroid.x.mean()
                ),
                zoom=10
            ),
            height=700,
            margin={"l":0,"r":0,"t":50,"b":0}
        )
        
        return fig
    
    except Exception as e:
        logger.error(f"Chyba při vytváření mapy: {e}")
        return go.Figure()

def soil_samples_map():
    """Stránka Streamlit pro mapu půdních vzorků."""
    st.title('Prostorová Analýza Půdních Vzorků')
    
    # Načtení dat
    gdf_parcels = load_parcels_data()
    gdf_points = load_soil_samples_data()
    
    if gdf_parcels is None or gdf_points is None:
        st.error("Nepodařilo se načíst data. Zkontrolujte databázové připojení.")
        return
    
    # Prostorové zpracování dat
    gdf_parcels_with_stats, gdf_points = process_spatial_data(gdf_parcels, gdf_points)
    
    # Výběr parametru
    selected_parameter = st.selectbox(
        'Vyberte parametr pro vizualizaci:',
        ['Fosfor (P)', 'Draslík (K)', 'pH']
    )
    
    # Vytvoření a zobrazení mapy
    fig = create_map(gdf_parcels_with_stats, gdf_points, selected_parameter)
    st.plotly_chart(fig, use_container_width=True, key='main_map')

def about_page():
    """Stránka O Aplikaci."""
    st.title('O Aplikaci')
    st.markdown('''
    ## Prostorová Analýza Půdních Vzorků

    ### Popis
    Tato aplikace poskytuje interaktivní vizualizaci prostorových dat o půdních vzorcích a parcelách pro sezónu 24/25.

    ### Funkce
    - Interaktivní mapa parcel
    - Výběr parametru: Fosfor (P), Draslík (K), pH
    - Zobrazení prostorové distribuce půdních vzorků
    - Hover efekty pro detailní informace

    ### Technické Detaily
    - Data jsou načítána z PostGIS databáze
    - Prostorové zpracování pomocí GeoPandas
    - Vizualizace pomocí Plotly a Streamlit

    ### Poznámky
    - Vyžaduje aktivní databázové připojení
    - Data jsou filtrována pro sezónu 24/25
    ''')

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

# Explicitní export funkcí
__all__ = ['soil_samples_map', 'about_page']

if __name__ == '__main__':
    main()