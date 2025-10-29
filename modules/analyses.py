"""
Plánovanie - Predikcia výnosov pre sezónu 25_26
Vypočítava predikciu na základe historických dát
"""

import streamlit as st
import pandas as pd
import numpy as np
import psycopg2
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
    
    st.header("📅 Plánovanie výnosov pre sezónu 25_26")
    
    st.markdown("""
    <div style="background-color: #e8f5e9; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
        <strong>💡 Ako to funguje:</strong><br>
        Predikované výnosy sú vypočítané ako priemer z minulých sezón pre danú parcelu a plodinu.
        Čím viac historických dát je k dispozícii, tým presnejšia je predikcia.
    </div>
    """, unsafe_allow_html=True)
    
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
            selected_crop = st.selectbox(
                "Filtrovať podľa plodiny:",
                options=['všetky plodiny'] + available_crops,
                key="planning_crop_filter"
            )
        else:
            st.warning("Stĺpec plodín nie je dostupný.")
            selected_crop = 'všetky plodiny'
    
    st.markdown("---")
    
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
    
    # Formátovanie numerických stĺpcov
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
        'prediction_counts': 'Počet predikcií',
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
    
    # Poznámka
    st.info("💡 **Poznámka:** Tabuľka zobrazuje predikcie výnosov a potreby živín pre sezónu 25_26.")
