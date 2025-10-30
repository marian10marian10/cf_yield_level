import streamlit as st
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Import modulov
from modules.data_loader import load_data, calculate_yield_percentage
from modules.enterprise_stats import show_enterprise_statistics
from modules.parcel_stats import show_parcel_statistics
from modules.crop_stats_db import show_crop_statistics_from_db
from modules.analyses import show_planning
from modules.simple_maps import show_maps

# Import the soil samples map function
from soil_samples_map_app import soil_samples_map, about_page

# Konfigurácia stránky
st.set_page_config(
    page_title="Analýza výnosov DPB",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"  # Zmenené na expanded pre bočné menu
)

# CSS pre lepší vzhľad
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .crop-selector {
        background-color: #e8f4fd;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .filter-container {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    /* Sidebar styling */
    .css-1d391kg {
        padding-top: 3rem;
    }
    [data-testid="stSidebar"] {
        background-image: linear-gradient(180deg, #e8f4fd 0%, #ffffff 100%);
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        font-size: 1rem;
    }
    /* Sidebar radio button styling */
    [data-testid="stSidebar"] [data-testid="stRadio"] {
        margin-top: 1rem;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        transition: all 0.2s ease;
        margin-bottom: 0.5rem;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
        background-color: #e8f4fd;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # Bočné navigačné menu
    st.sidebar.title("🌾 Analýza výnosov DPB")
    st.sidebar.markdown("---")
    
    # Menu možnosti
    menu_options = {
        "enterprise_db_prediction": {
            "title": "🏭 Štatistiky podniku (Predikcia)",
            "icon": "🏭",
            "description": "Štatistiky podniku pre sezónu 25/26"
        },
        "crop_db": {
            "title": "🌱 Štatistiky plodiny (DB)",
            "icon": "🌱",
            "description": "Detailná analýza výnosov plodín z databázy"
        },
        "parcel": {
            "title": "🏞️ Štatistiky parcely",
            "icon": "🏞️",
            "description": "Detailné štatistiky parciel"
        },
        "planning": {
            "title": "📅 Plánovanie",
            "icon": "📅",
            "description": "Predikcia výnosov pre sezónu 25_26"
        },
        "maps": {
            "title": "🗺️ Mapy",
            "icon": "🗺️",
            "description": "Interaktívne mapy výnosov"
        },
        "soil_samples": {
            "title": "🌍 Mapa Pôdnych Vzoriek",
            "icon": "🌍",
            "description": "Priestorová analýza pôdnych vzoriek"
        },
        "methodology": {
            "title": "📘 Metodika",
            "icon": "📘",
            "description": "Architektúra dát a prístup k analýze"
        }
    }
    
    # Inicializácia aktívnej karty
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = "enterprise_db_prediction"
    
    # Radiobuttony pre výber sekcie
    st.sidebar.markdown("## 📋 Navigácia")
    navigation_choice = st.sidebar.radio(
        "Vyberte sekciu:",
        options=list(menu_options.keys()),
        format_func=lambda x: menu_options[x]['title'],
        key="navigation_radio"
    )
    
    st.session_state.active_tab = navigation_choice
    st.sidebar.markdown("---")
    
    # Zobrazenie popisu aktívnej sekcie
    active_option = menu_options[st.session_state.active_tab]
    st.sidebar.markdown(f"**{active_option['icon']} {active_option['title']}**")
    st.sidebar.markdown(f"*{active_option['description']}*")
    st.sidebar.markdown("---")
    
    # Načítanie dát
    with st.spinner("Načítavam dáta z PostgreSQL databázy..."):
        df = load_data()
    
    if df is None:
        st.error("Nepodarilo sa načítať dáta z databázy. Skontrolujte pripojenie k databáze.")
        return
    
    # Výpočet percentuálnych výnosov
    df = calculate_yield_percentage(df)
    
    # Inicializácia session state pre plodinu
    available_crops = sorted(df['crop'].astype(str).dropna().unique())
    if 'selected_crop' not in st.session_state:
        # Nastavenie "Pšenica letná ozimná" ako predvolenej plodiny
        if "Pšenica letná ozimná" in available_crops:
            st.session_state.selected_crop = "Pšenica letná ozimná"
        elif "PŠENICE OZ." in available_crops:
            st.session_state.selected_crop = "PŠENICE OZ."
        else:
            st.session_state.selected_crop = available_crops[0]
    
    # Hlavný nadpis
    st.markdown('<h1 class="main-header">🌾 Analýza výnosov DPB</h1>', unsafe_allow_html=True)
    
    # Zobrazenie obsahu podľa vybranej karty
    if st.session_state.active_tab == "enterprise_db_prediction":
        # Import the new enterprise statistics function
        from modules.enterprise_stats_db_prediction import show_enterprise_stats_db_prediction
        show_enterprise_stats_db_prediction()
        
    elif st.session_state.active_tab == "crop_db":
        # Filter pre plodinu na karte plodiny z databázy
        st.markdown('<div class="filter-container">', unsafe_allow_html=True)
        st.subheader("🔍 Filtre")
        
        # Pripojenie k databáze pre štatistiky plodiny
        from sqlalchemy import create_engine
        from modules.data_loader import (
            DB_USER_DESTINATION, 
            DB_PASSWORD_DESTINATION, 
            DB_HOST_DESTINATION, 
            DB_NAME_DESTINATION
        )
        
        connection_string = f"postgresql://{DB_USER_DESTINATION}:{DB_PASSWORD_DESTINATION}@{DB_HOST_DESTINATION}/{DB_NAME_DESTINATION}"
        engine = create_engine(connection_string)
        
        # Načítanie dostupných plodín z databázy
        query = """
        SELECT DISTINCT crop 
        FROM yield_level.mv_skeagis_source 
        ORDER BY crop
        """
        available_db_crops = pd.read_sql(query, engine)['crop'].tolist()
        
        # Nastavenie indexu pre "Pšenica letná ozimná"
        default_index = 0
        if "Pšenica letná ozimná" in available_db_crops:
            default_index = available_db_crops.index("Pšenica letná ozimná")
        
        selected_crop = st.selectbox(
            "Vyberte plodinu:", 
            available_db_crops, 
            index=default_index,
            key="crop_db_selector"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        show_crop_statistics_from_db(selected_crop)
        
        # Zatvorenie databázového spojenia
        engine.dispose()
        
    elif st.session_state.active_tab == "parcel":
        # Filter pre parcelu na karte parcely
        st.markdown('<div class="filter-container">', unsafe_allow_html=True)
        st.subheader("🔍 Filtre")
        
        # Pripojenie k databáze pre načítanie lokalít
        from sqlalchemy import create_engine
        from modules.data_loader import (
            DB_USER_DESTINATION, 
            DB_PASSWORD_DESTINATION, 
            DB_HOST_DESTINATION, 
            DB_NAME_DESTINATION
        )
        
        connection_string = f"postgresql://{DB_USER_DESTINATION}:{DB_PASSWORD_DESTINATION}@{DB_HOST_DESTINATION}/{DB_NAME_DESTINATION}"
        engine = create_engine(connection_string)
        
        # Načítanie zoznamu lokalít
        query = """
        SELECT DISTINCT localname 
        FROM yield_level.mv_skeagis_source 
        ORDER BY localname
        """
        
        available_parcels = pd.read_sql(query, engine)['localname'].tolist()
        
        # Zatvorenie databázového spojenia
        engine.dispose()
        
        if not available_parcels:
            st.error("Nie sú dostupné žiadne parcely.")
            return
        
        # Výber parcely s predvolenou hodnotou
        default_index = 0
        if "Akat Velky 1" in available_parcels:
            default_index = available_parcels.index("Akat Velky 1")
            st.success(f"Predvolená parcela: Akat Velky 1")
        
        selected_parcel = st.selectbox(
            "Vyberte parcelu:",
            available_parcels,
            index=default_index,
            key="parcel_selector"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        show_parcel_statistics(df, selected_parcel)
        
    elif st.session_state.active_tab == "planning":
        show_planning(df)
        
    elif st.session_state.active_tab == "maps":
        show_maps(df)
        
    elif st.session_state.active_tab == "soil_samples":
        # Call the soil samples map function
        from soil_samples_map_app import soil_samples_map
        soil_samples_map()
        
    elif st.session_state.active_tab == "methodology":
        # Call the methodology page function
        from modules.methodology_page import show_methodology_page
        show_methodology_page()
        
    else:
        st.info("Vyberte kartu z menu vyššie.")

if __name__ == "__main__":
    main()
