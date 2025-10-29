import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from modules.data_loader import (
    DB_USER_DESTINATION, 
    DB_PASSWORD_DESTINATION, 
    DB_HOST_DESTINATION, 
    DB_NAME_DESTINATION
)
from sqlalchemy import create_engine

def create_crop_timeline_charts(df, crop_name):
    """Vytvorenie malých grafov pre časovú postupnosť úrod pre jednotlivé roky/sezóny danej plodiny"""
    crop_data = df[df['crop'].astype(str) == crop_name].copy()
    
    if crop_data.empty:
        return None
    
    # Použitie season_id ako roku, ak 'year' nie je prítomný
    if 'year' not in crop_data.columns:
        st.warning("Stĺpec 'year' nebol nájdený. Používam 'season_id' namiesto roku.")
        crop_data['year'] = crop_data['season_id']
    
    # Zoskupenie dát podľa roku a kontrola počtu záznamov
    year_groups = crop_data.groupby('year')
    valid_years = []
    
    for year, year_data in year_groups:
        if len(year_data) > 2:  # Iba roky s viac ako 2 záznamami
            valid_years.append((year, year_data))
    
    if not valid_years:
        return None
    
    # Vytvorenie stĺpcov pre grafy (max 3 grafy v riadku)
    cols_per_row = 3
    num_rows = (len(valid_years) + cols_per_row - 1) // cols_per_row
    
    charts_container = []
    
    for i in range(num_rows):
        row_years = valid_years[i * cols_per_row:(i + 1) * cols_per_row]
        cols = st.columns(len(row_years))
        
        for j, (year, year_data) in enumerate(row_years):
            with cols[j]:
                # Zoradenie dát podľa parciel
                year_data_sorted = year_data.sort_values('parcel_label')
                
                # Vytvorenie malého grafu pre rok
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=year_data_sorted['parcel_label'],
                    y=year_data_sorted['sk_yield_ha'],
                    mode='lines+markers',
                    name=str(year),
                    line=dict(width=2, color='#1f77b4'),
                    marker=dict(size=6, color='#1f77b4'),
                    hovertemplate=f'<b>{year}</b><br>' +
                                'Parcela: %{x}<br>' +
                                'Výnos: %{y:.2f} t/ha<extra></extra>'
                ))
                
                # Pridanie trendovej línie ak sú aspoň 3 body
                if len(year_data_sorted) >= 3:
                    z = np.polyfit(range(len(year_data_sorted)), year_data_sorted['sk_yield_ha'], 1)
                    p = np.poly1d(z)
                    fig.add_trace(go.Scatter(
                        x=year_data_sorted['parcel_label'],
                        y=p(range(len(year_data_sorted))),
                        mode='lines',
                        name='Trend',
                        line=dict(width=1, color='red', dash='dash'),
                        showlegend=False,
                        hovertemplate='Trend<extra></extra>'
                    ))
                
                # Výpočet metrík pre rok
                avg_yield = year_data_sorted['sk_yield_ha'].mean()
                yield_trend = "↗️" if len(year_data_sorted) >= 2 and year_data_sorted['sk_yield_ha'].iloc[-1] > year_data_sorted['sk_yield_ha'].iloc[0] else "↘️"
                
                # Aktualizácia layoutu grafu
                fig.update_layout(
                    title=f"🌾 {year}",
                    xaxis_title="Parcela",
                    yaxis_title="Výnos (t/ha)",
                    height=250,
                    margin=dict(l=40, r=40, t=60, b=40),
                    showlegend=False,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(
                        showgrid=True,
                        gridwidth=1,
                        gridcolor='rgba(128,128,128,0.2)',
                        zeroline=False,
                        tickangle=-45  # Otočenie štítkov parciel
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridwidth=1,
                        gridcolor='rgba(128,128,128,0.2)',
                        zeroline=False
                    )
                )
                
                # Pridanie grafu
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                
                # Pridanie metrík pod graf
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Priemerný výnos", f"{avg_yield:.2f} t/ha")
                with col2:
                    st.metric("Trend", yield_trend)
                
                # Detailné informácie o roku
                with st.expander(f"📊 Detailné údaje pre {year}"):
                    st.write(f"**Počet parciel:** {len(year_data_sorted)}")
                    st.write(f"**Najlepšia parcela:** {year_data_sorted.loc[year_data_sorted['sk_yield_ha'].idxmax(), 'parcel_label']} ({year_data_sorted['sk_yield_ha'].max():.2f} t/ha)")
                    st.write(f"**Najhoršia parcela:** {year_data_sorted.loc[year_data_sorted['sk_yield_ha'].idxmin(), 'parcel_label']} ({year_data_sorted['sk_yield_ha'].min():.2f} t/ha)")
                    
                    # Malá tabuľka s údajmi
                    display_data = year_data_sorted[['parcel_label', 'sk_yield_ha', 'area_ha']].copy()
                    display_data.columns = ['Parcela', 'Výnos (t/ha)', 'Plocha (ha)']
                    st.dataframe(display_data, use_container_width=True, hide_index=True)
    
    return True

def show_crop_statistics_from_db(selected_crop):
    """Zobrazenie štatistík plodiny z databázy"""
    st.header("🌾 Štatistiky plodiny")
    
    # Pripojenie k databáze
    connection_string = f"postgresql://{DB_USER_DESTINATION}:{DB_PASSWORD_DESTINATION}@{DB_HOST_DESTINATION}/{DB_NAME_DESTINATION}"
    engine = create_engine(connection_string)
    
    try:
        from sqlalchemy.sql import text
        
        # Príprava SQL dotazu pre štatistiky plodiny
        query = text("""
        SELECT * 
        FROM yield_level.mv_skeagis_source 
        WHERE crop = :crop_name
        ORDER BY season_id
        """)
        
        # Načítanie dát pre vybranú plodinu
        with engine.connect() as connection:
            crop_data = pd.read_sql(
                query, 
                connection, 
                params={'crop_name': selected_crop}
            )
        
        if crop_data.empty:
            st.error(f"Pre plodinu {selected_crop} nie sú dostupné žiadne dáta.")
            
            # Zobrazenie dostupných plodín pre kontrolu
            query_available = text("""
            SELECT DISTINCT crop 
            FROM yield_level.mv_skeagis_source 
            ORDER BY crop 
            LIMIT :limit_count
            """)
            
            with engine.connect() as connection:
                available_crops = pd.read_sql(
                    query_available, 
                    connection, 
                    params={'limit_count': 20}
                )
            
            st.warning("Dostupné plodiny:")
            st.dataframe(available_crops, use_container_width=True)
            
            return
        
        # Pridanie stĺpca 'year' z 'season_id', ak neexistuje
        if 'year' not in crop_data.columns:
            st.warning("Stĺpec 'year' nebol nájdený. Používam 'season_id' namiesto roku.")
            crop_data['year'] = crop_data['season_id']
        
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
        
        # Definovanie presného poradia sezón
        season_order = [
            "13_14", "14_15", "15_16", "16_17", "17_18", "18_19", 
            "19_20", "20_21", "21_22", "22_23", "23_24", "24_25"
        ]
        
        # Agregácia podľa sezóny a spoločnosti
        seasonal_company_stats = crop_data.groupby(['season_id', 'company'])['sk_yield_ha'].mean().reset_index()
        
        # Vytvorenie kategorického poradia pre sezóny
        seasonal_company_stats['season_order'] = seasonal_company_stats['season_id'].map({
            season: index for index, season in enumerate(season_order)
        })
        
        # Zoradenie podľa definovaného poradia
        seasonal_company_stats = seasonal_company_stats.sort_values('season_order')
        
        # Líniový graf vývoja výnosov
        fig_seasonal = go.Figure()
        
        # Pridanie línie pre každú spoločnosť
        for company in seasonal_company_stats['company'].unique():
            company_data = seasonal_company_stats[seasonal_company_stats['company'] == company]
            
            fig_seasonal.add_trace(go.Scatter(
                x=company_data['season_id'], 
                y=company_data['sk_yield_ha'], 
                mode='lines+markers',
                name=company,
                line=dict(width=2),
                marker=dict(size=8)
            ))
        
        # Nastavenie layoutu grafu
        fig_seasonal.update_layout(
            title='Vývoj priemerného výnosu v čase podľa spoločností',
            xaxis_title='Sezóna',
            yaxis_title='Priemerný výnos (t/ha)',
            hovermode='x unified',
            legend_title_text='Spoločnosti'
        )
        
        # Pridanie mriežky a nastavenie poradia na osi X
        fig_seasonal.update_xaxes(
            showgrid=True, 
            gridwidth=1, 
            gridcolor='rgba(128,128,128,0.2)',
            categoryorder='array',
            categoryarray=season_order
        )
        fig_seasonal.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
        
        st.plotly_chart(fig_seasonal, use_container_width=True)
        
        # Detailná história plodiny
        st.subheader("📋 Detailná história plodiny")
        st.dataframe(
            crop_data.sort_values('season_id', ascending=False).drop(columns=['parcel_season_id', 'geometry']),
            use_container_width=True
        )
        
        # Vytvorenie grafov pre jednotlivé roky
        st.subheader("🌱 Detailný pohľad na jednotlivé roky")
        create_crop_timeline_charts(crop_data, selected_crop)
    
    except Exception as e:
        st.error(f"Chyba pri spracovaní dát plodiny: {e}")
        st.write("Detaily chyby:", str(e))
    
    finally:
        # Zatvorenie databázového spojenia
        engine.dispose()
