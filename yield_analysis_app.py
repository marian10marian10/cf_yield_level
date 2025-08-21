import streamlit as st
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Import modulov
from modules.data_loader import load_data, calculate_yield_percentage
from modules.enterprise_stats import show_enterprise_statistics
from modules.parcel_stats import show_parcel_statistics

# Konfigurácia stránky
st.set_page_config(
    page_title="Analýza výnosov DPB",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
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
    
    # Sidebar pre výber plodiny
    st.sidebar.header("Nastavenia")
    
    # Výber plodiny v sidebar s prednastavenou hodnotou
    available_crops = sorted(df['crop'].unique())
    
    # Inicializácia session state pre plodinu
    if 'selected_crop' not in st.session_state:
        # Hľadanie indexu pre PŠENICE OZ.
        if "PŠENICE OZ." in available_crops:
            st.session_state.selected_crop = "PŠENICE OZ."
            st.sidebar.success(f"Prednastavená plodina: PŠENICE OZ.")
        else:
            st.session_state.selected_crop = available_crops[0]
    
    # Výber plodiny s aktuálnou hodnotou zo session state
    selected_crop = st.sidebar.selectbox(
        "Vyberte plodinu:", 
        available_crops, 
        index=available_crops.index(st.session_state.selected_crop),
        key="crop_selector"
    )
    
    # Aktualizácia session state
    st.session_state.selected_crop = selected_crop
    
    # Menu s kartami
    st.header("📋 Menu aplikácie")
    
    # Vytvorenie dvoch stĺpcov pre menu karty
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🏢 Štatistiky na úrovni podniku", key="enterprise_tab", use_container_width=True):
            st.session_state.active_tab = "enterprise"
    
    with col2:
        if st.button("🏞️ Štatistiky na úrovni parcely", key="parcel_tab", use_container_width=True):
            st.session_state.active_tab = "parcel"
    
    # Inicializácia aktívnej karty
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = "enterprise"
    
    # Zobrazenie obsahu podľa vybranej karty
    if st.session_state.active_tab == "enterprise":
        show_enterprise_statistics(df, selected_crop)
    elif st.session_state.active_tab == "parcel":
        show_parcel_statistics(df)

if __name__ == "__main__":
    main()
