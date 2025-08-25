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

# Konfigurácia stránky
st.set_page_config(
    page_title="Analýza výnosov DPB",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed"  # Zmenené na collapsed
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
    .menu-tab {
        background-color: #f8f9fa;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    .menu-tab:hover {
        background-color: #e9ecef;
        transform: translateY(-2px);
    }
    .menu-tab.active {
        background-color: #1f77b4;
        color: white;
    }
    .filter-container {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

def main():
    st.markdown('<h1 class="main-header">🌾 Analýza výnosov DPB</h1>', unsafe_allow_html=True)
    
    # Načítanie dát
    with st.spinner("Načítavam dáta z CSV súboru..."):
        df = load_data()
    
    if df is None:
        st.error("Nepodarilo sa načítať dáta. Skontrolujte, či existuje súbor 'yield_data.csv'.")
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
    
    # Menu s kartami
    st.header("📋 Menu aplikácie")
    
    # Vytvorenie troch stĺpcov pre menu karty
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🏢 Štatistiky na úrovni podniku", key="enterprise_tab", use_container_width=True):
            st.session_state.active_tab = "enterprise"
    
    with col2:
        if st.button("🌱 Štatistiky na úrovni plodiny", key="crop_tab", use_container_width=True):
            st.session_state.active_tab = "crop"
    
    with col3:
        if st.button("🏞️ Štatistiky na úrovni parcely", key="parcel_tab", use_container_width=True):
            st.session_state.active_tab = "parcel"
    
    # Inicializácia aktívnej karty
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = "enterprise"
    
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

if __name__ == "__main__":
    main()
