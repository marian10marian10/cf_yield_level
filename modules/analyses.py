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
import io
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection parameters
DB_USER_DESTINATION = os.getenv('DB_USER_DESTINATION', 'db_admin')
DB_PASSWORD_DESTINATION = os.getenv('DB_PASSWORD_DESTINATION', '')
DB_HOST_DESTINATION = os.getenv('DB_HOST_DESTINATION', 'localhost')
DB_NAME_DESTINATION = os.getenv('DB_NAME_DESTINATION', 'postgres')


def get_planning_data(df):
    """Načítanie plánovacích dát z PostgreSQL databázy"""
    try:
        # Vytvorenie connection string
        connection_string = f"postgresql://{DB_USER_DESTINATION}:{DB_PASSWORD_DESTINATION}@{DB_HOST_DESTINATION}/{DB_NAME_DESTINATION}"
        
        # Vytvorenie engine
        engine = create_engine(connection_string)
        
        # Komplexnejší SQL dopyt pre načítanie dát vrátane potreby N
        planning_query = """
        SELECT localname, company, crops, "25_26_yield_predictions", 
               total_demand_n, total_demand_n_90, total_demand_p, total_demand_k
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
            'total_demand_n', 
            'total_demand_n_90', 
            'total_demand_p', 
            'total_demand_k'
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
    
    st.header("📅 Plánovanie potreby živín pre sezónu 25/26")
    
    # Načítanie plánovacích dát
    with st.spinner("Načítavam dáta pre plánovanie..."):
        planning_df = get_planning_data(df)
    
    if planning_df.empty:
        st.warning("Žiadne dáta pre plánovanie.")
        return
    
    # Filtre
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
    
    # Premenovanie stĺpcov pre lepšiu čitateľnosť
    column_mapping = {
        'localname': 'Lokalita',
        'company': 'Spoločnosť',
        'crops': 'Plodina',
        '25_26_yield_predictions': 'Predikovaný výnos (t/ha)',
        'total_demand_n': 'Potreba N',
        'total_demand_n_90': 'Potreba N (90%)',
        'total_demand_p': 'Potreba P',
        'total_demand_k': 'Potreba K'
    }
    
    # Pripravenie dát pre tabuľku
    display_df = filtered_df.copy()
    
    # Premenovanie len existujúcich stĺpcov
    rename_dict = {old: new for old, new in column_mapping.items() if old in display_df.columns}
    display_df.rename(columns=rename_dict, inplace=True)
    
    # Zobrazenie tabuľky
    if not display_df.empty:
        # Zobrazenie tabuľky
        st.dataframe(display_df, use_container_width=True)
        
        # Export buttons pod tabuľkou
        st.markdown("""
        <style>
        /* Kontajner pre tlačidlá bez medzier */
        .export-buttons-container {
            display: inline-flex;
            width: 100%;
            justify-content: center;
            align-items: center;
            margin: -15px 0 0 0 !important;
            padding: 0 !important;
        }
        
        /* Úprava tlačidiel */
        .export-buttons-container .stDownloadButton {
            margin: 0 !important;
            padding: 0 !important;
            display: inline-block;
        }
        
        .export-buttons-container .stDownloadButton > button {
            width: 30px !important;
            height: 30px !important;
            min-width: 30px !important;
            min-height: 30px !important;
            padding: 0 !important;
            margin: 0 !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            font-size: 16px !important;
            background-color: transparent !important;
            border: 1px solid #e0e0e0 !important;
            color: #666 !important;
        }
        
        .export-buttons-container .stDownloadButton > button:hover {
            background-color: #f0f0f0 !important;
        }
        
        /* Odstránenie medzery pod tabuľkou */
        .stDataFrame {
            margin-bottom: 0 !important;
            padding-bottom: 0 !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Kontajner pre export tlačidlá
        st.markdown('<div class="export-buttons-container">', unsafe_allow_html=True)
        
        # CSV download
        csv = display_df.to_csv(index=False)
        st.download_button(
            label="📄",  # Simple document icon
            data=csv,
            file_name="planning_data.csv",
            mime="text/csv",
            help="Stiahnuť CSV",
            key="csv_download_planning",
            type="secondary"
        )
        
        # Excel download
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            display_df.to_excel(writer, index=False, sheet_name='Plánovanie')
        excel_buffer.seek(0)
        
        st.download_button(
            label="📊",  # Spreadsheet/chart icon
            data=excel_buffer,
            file_name="planning_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Stiahnuť Excel",
            key="excel_download_planning",
            type="secondary"
        )
        
        # Uzavretie kontajnera
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.warning("Po aplikovaní filtrov nie sú k dispozícii žiadne dáta.")
    
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
