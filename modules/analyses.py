"""
Plánovanie - Predikcia výnosov pre sezónu 25_26
Vypočítava predikciu na základe historických dát
"""

import streamlit as st
import pandas as pd
import numpy as np
import psycopg2
import plotly.express as px
from sqlalchemy import create_engine

# Database connection parameters
DB_USER_DESTINATION = 'db_admin'
DB_PASSWORD_DESTINATION = "Ybm=Zjk#sTf3#^]ybD<k"
DB_HOST_DESTINATION = 'team-pz.cyp6scadbpmv.eu-central-1.rds.amazonaws.com'
DB_NAME_DESTINATION = 'postgres'


def get_planning_data(df):
    """Načítanie plánovacích dát z PostgreSQL databázy"""
    try:
        # Vytvorenie connection string
        connection_string = f"postgresql://{DB_USER_DESTINATION}:{DB_PASSWORD_DESTINATION}@{DB_HOST_DESTINATION}/{DB_NAME_DESTINATION}"
        
        # Vytvorenie engine
        engine = create_engine(connection_string)
        
        # Komplexnejší SQL dopyt pre načítanie dát vrátane potreby N
        planning_query = """
        SELECT * 
        FROM yield_level.mv_25_26_prediction_demand
        """
        
        # Vykonanie dopytu a načítanie dát
        planning_df = pd.read_sql(planning_query, engine)
        
        # Zatvorenie spojenia
        engine.dispose()
        
        if planning_df.empty:
            st.warning("Žiadne dáta pre sezónu 25_26")
            return pd.DataFrame()
        
        # Nahradenie prázdnych hodnôt pre numerické stĺpce
        numeric_columns = [
            '25_26_yield_predictions', 
            'prediction_counts', 
            'total_demand_n', 
            'total_demand_p', 
            'total_demand_k', 
            'total_demand_n_80', 
            'total_demand_p_80', 
            'total_demand_k_80'
        ]
        
        # Dynamicky nahradenie prázdnych hodnôt pre existujúce numerické stĺpce
        for col in numeric_columns:
            if col in planning_df.columns:
                planning_df[col] = pd.to_numeric(planning_df[col], errors='coerce').fillna(0)
        
        return planning_df
    
    except Exception as e:
        st.error(f"Chyba pri načítaní plánovacích dát: {e}")
        import traceback
        st.error(traceback.format_exc())
        return pd.DataFrame()


def show_planning(df):
    """Zobrazí plánovanie výnosov s predikciami"""
    
    # Pridanie vlastného CSS pre väčší font a responzívne stĺpce
    st.markdown("""
    <style>
    /* Výrazné zvýšenie základnej veľkosti písma */
    body, .stMarkdown, .stDataFrame, .stSelectbox, .stRadio, .stText {
        font-size: 22px !important;
    }
    
    /* Responzívne stĺpce v DataFrames */
    .stDataFrame {
        width: 100% !important;
        max-width: 100% !important;
    }
    .stDataFrame th, .stDataFrame td {
        padding: 12px 16px !important;
        font-size: 24px !important;
        line-height: 1.5 !important;
        word-wrap: break-word !important;
        white-space: normal !important;
        vertical-align: middle !important;
    }
    
    /* Zvýraznenie hlavičky tabuľky */
    .stDataFrame th {
        text-align: left !important;
        background-color: #e6f2ff !important;
        font-weight: bold !important;
        color: #1a1a1a !important;
        font-size: 26px !important;
    }
    
    /* Zarovnanie buniek */
    .stDataFrame td {
        text-align: left !important;
    }
    
    /* Responzívne nastavenia pre mobilné zariadenia */
    @media (max-width: 768px) {
        .stDataFrame th, .stDataFrame td {
            font-size: 20px !important;
            padding: 8px 12px !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Odstraňujem debug text
    
    st.header("📅 Plánovanie potreby živín pre sezónu 25/26")
    
    # Načítanie plánovacích dát
    with st.spinner("Načítavam dáta pre plánovanie..."):
        planning_df = get_planning_data(df)
    
    if planning_df.empty:
        st.warning("Žiadne dáta pre plánovanie.")
        return
    
    # Filtre
    st.subheader("🔍 Filtre")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Bezpečné načítanie spoločností
        company_col = 'company'
        if company_col in planning_df.columns:
            available_companies = sorted(planning_df[company_col].dropna().unique())
            selected_company = st.selectbox(
                "Filtrovať podľa spoločnosti:",
                options=['všetky'] + available_companies,
                key="planning_company_filter"
            )
        else:
            st.warning("Stĺpec spoločnosti nie je dostupný.")
            selected_company = 'všetky'
    
    with col2:
        # Bezpečné načítanie plodín
        crop_col = 'crops'
        if crop_col in planning_df.columns:
            available_crops = sorted(planning_df[crop_col].dropna().unique())
            
            # Nastavenie default hodnoty na "Pšenica letná ozimná"
            default_index = 0
            if "Pšenica letná ozimná" in available_crops:
                default_index = available_crops.index("Pšenica letná ozimná")
            
            selected_crop = st.selectbox(
                "Filtrovať podľa plodiny:",
                options=['všetky plodiny'] + available_crops,
                index=default_index + 1,  # +1 because of 'všetky plodiny' option
                key="planning_crop_filter"
            )
        else:
            st.warning("Stĺpec plodín nie je dostupný.")
            selected_crop = 'všetky plodiny'
    
    # Aplikovanie filtrov
    filtered_df = planning_df.copy()
    
    if selected_company != 'všetky' and company_col in filtered_df.columns:
        filtered_df = filtered_df[filtered_df[company_col] == selected_company]
    
    if selected_crop != 'všetky plodiny' and crop_col in filtered_df.columns:
        filtered_df = filtered_df[filtered_df[crop_col] == selected_crop]
    
    # Tabuľka s predikciami
    st.subheader("📋 Predikované výnosy a potreby živín")
    
    # Pripravenie dát pre tabuľku
    display_df = filtered_df.copy()
    
    # Odobratie stĺpca prediction_counts
    if 'prediction_counts' in display_df.columns:
        display_df = display_df.drop(columns=['prediction_counts'])
    
    # Formátovanie numerických stĺpcov
    numeric_columns = [
        '25_26_yield_predictions', 
        'total_demand_n', 
        'total_demand_p', 
        'total_demand_k', 
        'total_demand_n_80', 
        'total_demand_p_80', 
        'total_demand_k_80'
    ]
    
    for col in numeric_columns:
        if col in display_df.columns:
            # Bezpečná konverzia na numerické hodnoty
            numeric_series = pd.to_numeric(display_df[col], errors='coerce')
            
            # Nahradenie NaN a nekonečných hodnôt nulou
            numeric_series = numeric_series.fillna(0)
            numeric_series = numeric_series.replace([np.inf, -np.inf], 0)
            
            if col.startswith('total_demand_'):
                # Zaokrúhli demand stĺpce na celé čísla
                display_df[col] = numeric_series.round(0).astype('Int64')
            else:
                # Ostatné numerické stĺpce zaokrúhli na 2 desatinné miesta
                display_df[col] = numeric_series.round(2)
    
    # Premenovanie stĺpcov pre lepšiu čitateľnosť
    column_mapping = {
        'parcel_id': 'Parcela ID',
        'crops': 'Plodina',
        'localname': 'Lokalita',
        'company': 'Spoločnosť',
        '25_26_yield_predictions': 'Predikovaný výnos (t/ha)',
        'total_demand_n': 'Potreba N',
        'total_demand_p': 'Potreba P',
        'total_demand_k': 'Potreba K',
        'total_demand_n_80': 'Potreba N (80%)',
        'total_demand_p_80': 'Potreba P (80%)',
        'total_demand_k_80': 'Potreba K (80%)'
    }
    
    # Premenovanie len existujúcich stĺpcov
    rename_dict = {old: new for old, new in column_mapping.items() if old in display_df.columns}
    display_df.rename(columns=rename_dict, inplace=True)
    
    # Zoradenie podľa predikovaného výnosu, ak je stĺpec dostupný
    if 'Predikovaný výnos (t/ha)' in display_df.columns:
        display_df = display_df.sort_values('Predikovaný výnos (t/ha)', ascending=False)
    
    # Pridanie vlastného CSS pre atraktívnejšiu tabuľku
    st.markdown("""
    <style>
    /* Moderný a atraktívny dizajn tabuľky */
    .stDataFrame {
        border-collapse: separate !important;
        border-spacing: 0 !important;
        border-radius: 15px !important;
        overflow: hidden !important;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1), 0 6px 10px rgba(0,0,0,0.05) !important;
        background-color: white !important;
        background: linear-gradient(to right, #f4f6f7 0%, #ffffff 100%) !important;
        border: 1px solid rgba(0,0,0,0.05) !important;
    }
    
    .stDataFrame th {
        background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%) !important;
        color: white !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        border-bottom: 2px solid rgba(255,255,255,0.2) !important;
        padding: 15px 20px !important;
        font-size: 19px !important;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.2) !important;
    }
    
    .stDataFrame td {
        border-bottom: 1px solid #e9ecef !important;
        padding: 12px 20px !important;
        transition: all 0.3s ease !important;
        font-size: 17px !important;
    }
    
    .stDataFrame tr:nth-child(even) {
        background-color: rgba(41, 128, 185, 0.05) !important;
    }
    
    .stDataFrame tr:hover {
        background-color: rgba(41, 128, 185, 0.1) !important;
        transform: scale(1.01) !important;
        box-shadow: 0 5px 15px rgba(0,0,0,0.05) !important;
        transition: all 0.3s ease !important;
    }
    
    /* Zvýraznenie stĺpca predikovaného výnosu */
    .stDataFrame td:nth-child(5) {
        font-weight: bold !important;
        color: #2c3e50 !important;
        background-color: rgba(46, 204, 113, 0.1) !important;
    }
    
    /* Gradient pre dôležité hodnoty */
    .stDataFrame td:nth-child(6), 
    .stDataFrame td:nth-child(7), 
    .stDataFrame td:nth-child(8) {
        background: linear-gradient(to right, #f6d365 0%, #fda085 100%) !important;
        color: white !important;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.3) !important;
        font-weight: 600 !important;
    }
    
    /* Responzívne nastavenia */
    @media (max-width: 768px) {
        .stDataFrame th, .stDataFrame td {
            font-size: 16px !important;
            padding: 10px 15px !important;
        }
    }
    
    /* Animácie */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .stDataFrame {
        animation: fadeIn 0.5s ease-out !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Zobrazenie tabuľky
    st.dataframe(
        display_df,
        height=500,
        hide_index=True,
        use_container_width=True,
        column_config={
            col: st.column_config.TextColumn(
                label=col,
                help=f"Stĺpec {col}",
                width="small"
            ) for col in display_df.columns
        }
    )
    
    # Grafy pre súhrn dát
    st.markdown("---")
    st.subheader("📊 Súhrnné vizualizácie")
    
    # Príprava dát pre grafy
    numeric_columns = [
        'Predikovaný výnos (t/ha)', 
        'Potreba N', 
        'Potreba P', 
        'Potreba K'
    ]
    
    # Rozloženie stĺpcov pre grafy
    col1, col2 = st.columns(2)
    
    with col1:
        # Histogram predikovaného výnosu
        st.markdown("#### Distribúcia predikovaného výnosu")
        fig_yield = px.histogram(
            display_df, 
            x='Predikovaný výnos (t/ha)', 
            title='Rozloženie predikovaných výnosov',
            labels={'Predikovaný výnos (t/ha)': 'Výnos (t/ha)'},
            color_discrete_sequence=['#3498db'],
            opacity=0.7
        )
        fig_yield.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(size=14)
        )
        st.plotly_chart(fig_yield, use_container_width=True)
    
    with col2:
        # Krabicový graf pre potreby živín
        st.markdown("#### Potreby živín")
        fig_nutrients = px.box(
            display_df, 
            y=['Potreba N', 'Potreba P', 'Potreba K'],
            title='Rozloženie potrieb živín',
            labels={'value': 'Potreba', 'variable': 'Živina'},
            color_discrete_sequence=['#2ecc71', '#e74c3c', '#f39c12']
        )
        fig_nutrients.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(size=14)
        )
        st.plotly_chart(fig_nutrients, use_container_width=True)
