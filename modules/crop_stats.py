import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
from modules.data_loader import (
    DB_USER_DESTINATION, 
    DB_PASSWORD_DESTINATION, 
    DB_HOST_DESTINATION, 
    DB_NAME_DESTINATION
)

def show_crop_statistics(data, selected_crop):
    """Zobrazenie štatistík plodiny z materialized view"""
    st.header("🌾 Štatistiky plodiny")
    
    try:
        # Determine if input is a DataFrame or SQLAlchemy engine
        if isinstance(data, pd.DataFrame):
            # If it's a DataFrame, filter for the selected crop
            crop_data = data[data['crop'] == selected_crop]
        elif hasattr(data, 'connect'):  # SQLAlchemy engine check
            # Príprava SQL dotazu pre štatistiky plodiny
            query = text("""
            SELECT * 
            FROM yield_level.mv_skeagis_source 
            WHERE crop = :crop_name
            ORDER BY season_id
            """)
            
            # Načítanie dát pre vybranú plodinu
            with data.connect() as connection:
                crop_data = pd.read_sql(
                    query, 
                    connection, 
                    params={'crop_name': selected_crop}
                )
        else:
            raise ValueError("Input must be a pandas DataFrame or SQLAlchemy engine")
        
        if crop_data.empty:
            st.error(f"Pre plodinu {selected_crop} nie sú dostupné žiadne dáta.")
            return
        
        # Základné informácie o plodine
        st.subheader(f"📋 Informácie o plodine: {selected_crop}")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Počet záznamov", f"{len(crop_data):,}")
        
        with col2:
            st.metric("Počet parciel", f"{crop_data['parcel_label'].nunique()}")
        
        with col3:
            st.metric("Sezóny", f"{crop_data['season_id'].min()} - {crop_data['season_id'].max()}")
        
        with col4:
            st.metric("Priemerná plocha", f"{crop_data['area_ha'].mean():.2f} ha")
        
        # Agregácia dát podľa spoločnosti
        company_stats = crop_data.groupby('company').agg({
            'sk_yield_ha': ['mean', 'std', 'count'],
            'area_ha': 'mean'
        }).round(2)
        
        company_stats.columns = ['priemerny_vyos', 'std_vyos', 'pocet_zaznamov', 'priemerna_plocha']
        company_stats = company_stats.reset_index()
        
        # Výpočet celkového priemerného výnosu pre porovnanie
        total_avg_yield = crop_data['sk_yield_ha'].mean()
        
        # Porovnanie s celkovým priemerom
        company_stats['odchylka_od_priemeru'] = ((company_stats['priemerny_vyos'] - total_avg_yield) / total_avg_yield * 100).round(2)
        
        # Graf porovnania spoločností
        st.subheader("🏢 Porovnanie spoločností")
        
        # Bar chart s priemerným výnosom
        fig_companies = px.bar(
            company_stats, 
            x='company', 
            y='priemerny_vyos', 
            color='odchylka_od_priemeru',
            color_continuous_scale='RdYlGn',
            title='Priemerné výnosy podľa spoločností',
            labels={'company': 'Spoločnosť', 'priemerny_vyos': 'Priemerný výnos (t/ha)'}
        )
        st.plotly_chart(fig_companies, use_container_width=True)
        
        # Tabuľka s porovnaním spoločností
        st.subheader("📊 Detailné porovnanie spoločností")
        
        st.dataframe(
            company_stats.drop(columns=['std_vyos', 'priemerna_plocha', 'odchylka_od_priemeru']),
            use_container_width=True
        )
        
        # Časový vývoj výnosov
        st.subheader("📈 Vývoj výnosov v čase")
        
        # Agregácia podľa sezóny
        seasonal_stats = crop_data.groupby('season_id')['sk_yield_ha'].agg(['mean', 'std']).reset_index()
        
        # Líniový graf vývoja výnosov
        fig_seasonal = go.Figure()
        
        # Priemerný výnos
        fig_seasonal.add_trace(go.Scatter(
            x=seasonal_stats['season_id'], 
            y=seasonal_stats['mean'], 
            mode='lines+markers',
            name='Priemerný výnos',
            line=dict(color='blue', width=2),
            marker=dict(size=8)
        ))
        
        # Interval spoľahlivosti (štandardná odchýlka)
        fig_seasonal.add_trace(go.Scatter(
            x=seasonal_stats['season_id'],
            y=seasonal_stats['mean'] + seasonal_stats['std'],
            mode='lines',
            name='Horná hranica (±σ)',
            line=dict(color='rgba(0,100,80,0.2)', width=0),
            showlegend=True
        ))
        
        fig_seasonal.add_trace(go.Scatter(
            x=seasonal_stats['season_id'],
            y=seasonal_stats['mean'] - seasonal_stats['std'],
            mode='lines',
            name='Dolná hranica (±σ)',
            line=dict(color='rgba(0,100,80,0.2)', width=0),
            fill='tonexty',
            fillcolor='rgba(0,100,80,0.1)',
            showlegend=True
        ))
        
        fig_seasonal.update_layout(
            title='Vývoj priemerného výnosu v čase',
            xaxis_title='Sezóna',
            yaxis_title='Priemerný výnos (t/ha)',
            hovermode='x unified'
        )
        
        st.plotly_chart(fig_seasonal, use_container_width=True)
        
        # Detailná história plodiny
        st.subheader("📋 Detailná história plodiny")
        st.dataframe(
            crop_data.sort_values('season_id', ascending=False).drop(columns=['parcel_season_id', 'geometry']),
            use_container_width=True
        )
    
    except Exception as e:
        st.error(f"Chyba pri spracovaní dát plodiny: {e}")
        # Debug information
        st.write("Input type:", type(data))
        if isinstance(data, pd.DataFrame):
            st.write("DataFrame columns:", list(data.columns))
