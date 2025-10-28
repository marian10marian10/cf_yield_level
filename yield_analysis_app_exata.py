import streamlit as st
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Import modulov
from modules.data_loader import load_data, calculate_yield_percentage
from modules.enterprise_stats import show_enterprise_statistics
from modules.parcel_stats import show_parcel_statistics
from modules.crop_stats import show_crop_statistics
from modules.advanced_analytics import show_advanced_analytics
from modules.analyses import show_planning
from modules.simple_maps import show_maps

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
        "enterprise": {
            "title": "🏢 Štatistiky podniku",
            "icon": "🏢",
            "description": "Prehľad štatistík na úrovni podniku"
        },
        "crop": {
            "title": "🌱 Štatistiky plodiny",
            "icon": "🌱",
            "description": "Analýza výnosov podľa plodiny"
        },
        "parcel": {
            "title": "🏞️ Štatistiky parcely",
            "icon": "🏞️",
            "description": "Detailné štatistiky parciel"
        },
        "advanced": {
            "title": "📈 Pokročilé analýzy",
            "icon": "📈",
            "description": "Komplexné analytické nástroje"
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
        }
    }
    
    # Inicializácia aktívnej karty
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = "enterprise"
    
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
    available_crops = sorted(df['crop'].unique())
    if 'selected_crop' not in st.session_state:
        # Hľadanie indexu pre PŠENICE OZ.
        if "PŠENICE OZ." in available_crops:
            st.session_state.selected_crop = "PŠENICE OZ."
        else:
            st.session_state.selected_crop = available_crops[0]
    
    # Hlavný nadpis
    st.markdown('<h1 class="main-header">🌾 Analýza výnosov DPB</h1>', unsafe_allow_html=True)
    
    # Zobrazenie obsahu podľa vybranej karty
    if st.session_state.active_tab == "enterprise":
        show_enterprise_statistics(df, st.session_state.selected_crop)
        
    elif st.session_state.active_tab == "crop":
        # Filter pre plodinu na karte plodiny
        st.markdown('<div class="filter-container">', unsafe_allow_html=True)
        st.subheader("🔍 Filtre")
        selected_crop = st.selectbox(
            "Vyberte plodinu:", 
            available_crops, 
            index=available_crops.index(st.session_state.selected_crop),
            key="crop_crop_selector"
        )
        st.session_state.selected_crop = selected_crop
        st.markdown('</div>', unsafe_allow_html=True)
        
        show_crop_statistics(df, selected_crop)
        
    elif st.session_state.active_tab == "parcel":
        # Filter pre parcelu na karte parcely
        st.markdown('<div class="filter-container">', unsafe_allow_html=True)
        st.subheader("🔍 Filtre")
        
        # Získanie zoznamu parciel
        available_parcels = sorted([str(parcel) for parcel in df['name'].unique() if pd.notna(parcel)])
        
        if not available_parcels:
            st.error("Nie sú dostupné žiadne parcely.")
            return
        
        # Výber parcely s predvolenou hodnotou "Akat Velky 1"
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
        
    elif st.session_state.active_tab == "advanced":
        show_advanced_analytics(df)
        
    elif st.session_state.active_tab == "planning":
        show_planning(df)
        
    elif st.session_state.active_tab == "maps":
        show_maps(df)
        
    else:
        st.info("Vyberte kartu z menu vyššie.")

if __name__ == "__main__":
    main()
