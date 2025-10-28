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
    """
    Získa parcely pre sezónu 25_26 a vypočíta predicted_yield na základe historických dát
    
    Args:
        df: DataFrame s historickými výnosmi z databázy
    
    Returns:
        DataFrame s predikovanými výnosmi pre sezónu 25_26
    """
    try:
        # Pripojenie k databáze
        connection_string = f"postgresql://{DB_USER_DESTINATION}:{DB_PASSWORD_DESTINATION}@{DB_HOST_DESTINATION}/{DB_NAME_DESTINATION}"
        engine = create_engine(connection_string)
        
        # Najprv skontrolujme dostupné stĺpce
        check_columns_query = """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'yield_level' 
        AND table_name = 'cf_parcel_season'
        ORDER BY ordinal_position
        """
        
        columns_df = pd.read_sql(check_columns_query, engine)
        available_columns = columns_df['column_name'].tolist()
        
        # Debug: zobraz dostupné stĺpce
        with st.expander("🔍 Debug: Dostupné stĺpce v cf_parcel_season"):
            st.dataframe(columns_df)
        
        # Preferuj "season_id"; fallback na "season"
        if 'season_id' in available_columns:
            season_column = 'season_id'
        elif 'season' in available_columns:
            season_column = 'season'
        else:
            st.error(f"Nenašiel som stĺpec 'season_id' ani 'season' v tabuľke cf_parcel_season. Dostupné stĺpce: {available_columns}")
            engine.dispose()
            return pd.DataFrame()
        
        # Načítanie parciel pre sezónu 25_26
        planning_query = f"""
        SELECT DISTINCT
            ps.parcel_id,
            ps.company,
            lc.localname
        FROM yield_level.cf_parcel_season ps
        LEFT JOIN lookups.lookup_sklpis_parcels lc ON ps.parcel_id = lc.parcel_id
        WHERE ps.{season_column} = '25_26'
        """
        
        parcels_df = pd.read_sql(planning_query, engine)
        
        # Debug: zobraz počet načítaných parciel
        st.info(f"Načítané parcely: {len(parcels_df)}")
        
        if parcels_df.empty:
            st.warning("Žiadne parcely pre sezónu 25_26")
            engine.dispose()
            return pd.DataFrame()
        
        # Načítanie plodín pre sezónu 25_26
        # V cf_parcel_season je stĺpec "crop" (nie ppa_crop_id)
        crops_query = f"""
        SELECT DISTINCT
            ps.parcel_id,
            ps.crop
        FROM yield_level.cf_parcel_season ps
        WHERE ps.{season_column} = '25_26' AND ps.crop IS NOT NULL
        """
        
        crops_df = pd.read_sql(crops_query, engine)
        
        # Spojenie parciel s plodinami
        planning_df = parcels_df.merge(crops_df, on='parcel_id', how='left')
        
        engine.dispose()
        
        if planning_df.empty:
            st.warning("Žiadne dáta pre sezónu 25_26")
            return pd.DataFrame()
        
        # Company je už načítané z query, len vyplň nan hodnoty
        if 'company' in planning_df.columns:
            planning_df['company'] = planning_df['company'].fillna('Neznáma')
        else:
            planning_df['company'] = 'Neznáma'
        
        # Vypočítanie predicted_yield pre každú parcelu
        results = []
        
        for _, row in planning_df.iterrows():
            parcel_id = row['parcel_id']
            crop = row['crop']
            company = row['company']
            name = row['localname'] if pd.notna(row['localname']) else parcel_id
            
            # Filtrovanie historických dát pre túto parcelu a plodinu
            historical_data = df[(df['parcel_id'] == parcel_id) & (df['crop'] == crop)].copy()
            
            if not historical_data.empty:
                # Predikcia = priemer z minulých výnosov
                predicted_yield = historical_data['yield_ha'].mean()
                number_of_data = len(historical_data)
            else:
                # Ak nemáme historické dáta, použijeme všeobecný priemer pre túto plodinu
                crop_data = df[df['crop'] == crop]
                if not crop_data.empty:
                    predicted_yield = crop_data['yield_ha'].mean()
                    number_of_data = 0  # 0 lebo nemáme históriu pre túto parcelu
                else:
                    predicted_yield = 0
                    number_of_data = 0
            
            results.append({
                'parcel_id': parcel_id,
                'name': name,
                'crop': crop,
                'company': company,
                'predicted_yield': predicted_yield,
                'number_of_data': number_of_data
            })
        
        result_df = pd.DataFrame(results)
        
        return result_df
        
    except Exception as e:
        st.error(f"Chyba pri načítavaní plánovacích dát: {e}")
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
    
    # Základné štatistiky
    st.subheader("📈 Prehľad predikcií")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_parcels = len(planning_df)
        st.metric("Počet parciel", f"{total_parcels}")
    
    with col2:
        avg_predicted = planning_df['predicted_yield'].mean()
        st.metric("Priemerná predikcia", f"{avg_predicted:.2f} t/ha")
    
    with col3:
        parcels_with_history = (planning_df['number_of_data'] > 0).sum()
        st.metric("Parcele s históriou", f"{parcels_with_history}")
    
    with col4:
        parcels_without_history = (planning_df['number_of_data'] == 0).sum()
        st.metric("Parcele bez histórie", f"{parcels_without_history}")
    
    st.markdown("---")
    
    # Filter podľa spoločnosti
    st.subheader("🔍 Filtre")
    
    available_companies = sorted(planning_df['company'].dropna().unique())
    
    col1, col2 = st.columns(2)
    with col1:
        selected_company = st.selectbox(
            "Filtrovať podľa spoločnosti:",
            options=['všetky'] + available_companies,
            key="planning_company_filter"
        )
    
    with col2:
        available_crops = sorted(planning_df['crop'].dropna().unique())
        selected_crop = st.selectbox(
            "Filtrovať podľa plodiny:",
            options=['všetky plodiny'] + available_crops,
            key="planning_crop_filter"
        )
    
    # Aplikovanie filtrov
    filtered_df = planning_df.copy()
    if selected_company != 'všetky':
        filtered_df = filtered_df[filtered_df['company'] == selected_company]
    if selected_crop != 'všetky plodiny':
        filtered_df = filtered_df[filtered_df['crop'] == selected_crop]
    
    st.markdown("---")
    
    # Tabuľka s predikciami
    st.subheader("📋 Predikované výnosy")
    
    # Pripravenie dát pre tabuľku
    display_df = filtered_df[['parcel_id', 'name', 'crop', 'company', 'predicted_yield', 'number_of_data']].copy()
    
    # Formátovanie
    display_df['predicted_yield'] = display_df['predicted_yield'].round(2)
    display_df['number_of_data'] = display_df['number_of_data'].astype(int)
    
    # Premenovanie stĺpcov
    display_df.columns = ['Parcela ID', 'Názov parcely', 'Plodina', 'Spoločnosť', 'Predikovaný výnos (t/ha)', 'Počet historických dát']
    
    # Zoradenie podľa predikovaného výnosu
    display_df = display_df.sort_values('Predikovaný výnos (t/ha)', ascending=False)
    
    # Zobrazenie tabuľky
    st.dataframe(
        display_df,
        use_container_width=True,
        height=500,
        hide_index=True
    )
    
    # Poznámka
    st.info("💡 **Poznámka:** Parcele s 0 počtom dát nemajú historické údaje a predikcia je založená na všeobecnom priemere pre danú plodinu.")
