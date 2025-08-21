import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import io
import geopandas as gpd
from shapely import wkt

def create_yield_boxplot(df, crop_name):
    """Vytvorenie boxplot grafu pre konkrétnu plodinu"""
    crop_data = df[df['crop'] == crop_name].copy()
    
    if crop_data.empty:
        return None
    
    # Výpočet celkového priemeru
    overall_avg = crop_data['yield_ha'].mean()
    
    fig = go.Figure()
    
    # Boxplot pre každý rok
    for year in sorted(crop_data['year'].unique()):
        year_data = crop_data[crop_data['year'] == year]['yield_ha']
        fig.add_trace(go.Box(
            y=year_data,
            name=str(year),
            boxpoints='outliers',
            jitter=0.3,
            pointpos=-1.8
        ))
    
    # Pridanie čiary celkového priemeru
    fig.add_hline(
        y=overall_avg,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Priemer za obdobie: {overall_avg:.3f} t/ha"
    )
    
    fig.update_layout(
        title=f"Variabilita výnosov {crop_name} v rokoch {crop_data['year'].min()}-{crop_data['year'].max()}",
        yaxis_title="Výnos (t/ha)",
        xaxis_title="Rok",
        showlegend=False,
        height=500
    )
    
    return fig

def create_yield_trend(df, crop_name):
    """Vytvorenie trendového grafu výnosov v čase"""
    crop_data = df[df['crop'] == crop_name].copy()
    
    if crop_data.empty:
        return None
    
    # Agregácia dát podľa roku
    yearly_stats = crop_data.groupby('year').agg({
        'yield_ha': ['mean', 'std', 'count']
    }).reset_index()
    
    yearly_stats.columns = ['year', 'mean_yield', 'std_yield', 'count_parcels']
    
    fig = go.Figure()
    
    # Priemerný výnos s chybovými pruhmi
    fig.add_trace(go.Scatter(
        x=yearly_stats['year'],
        y=yearly_stats['mean_yield'],
        mode='lines+markers',
        name='Priemerný výnos',
        line=dict(color='blue', width=3),
        marker=dict(size=8)
    ))
    
    # Chybové pruhy (štandardná odchýlka)
    fig.add_trace(go.Scatter(
        x=yearly_stats['year'].tolist() + yearly_stats['year'].tolist()[::-1],
        y=(yearly_stats['mean_yield'] + yearly_stats['std_yield']).tolist() + 
           (yearly_stats['mean_yield'] - yearly_stats['std_yield']).tolist()[::-1],
        fill='toself',
        fillcolor='rgba(0,100,80,0.2)',
        line=dict(color='rgba(255,255,255,0)'),
        name='±1 štandardná odchýlka'
    ))
    
    fig.update_layout(
        title=f"Trend výnosov {crop_name} v čase",
        xaxis_title="Rok",
        yaxis_title="Výnos (t/ha)",
        height=400
    )
    
    return fig

def create_parcel_performance_map(df):
    """Vytvorenie mapy s výkonnosťou parciel pomocou geopandas"""
    try:
        # Agregácia dát podľa parcele
        parcel_stats = df.groupby(['name', 'agev_parcel_id', 'area', 'geometry']).agg({
            'yield_percentage': 'mean',
            'yield_ha': 'mean',
            'crop': 'count'
        }).reset_index()
        
        parcel_stats.columns = ['name', 'agev_parcel_id', 'area', 'geometry', 'avg_yield_percentage', 'avg_yield_ha', 'crop_count']
        
        # Filtrovanie parciel s geometriou
        parcel_stats = parcel_stats.dropna(subset=['geometry'])
        
        if parcel_stats.empty:
            return None
        
        # Konverzia na GeoDataFrame
        parcel_stats['geometry'] = parcel_stats['geometry'].apply(wkt.loads)
        gdf = gpd.GeoDataFrame(parcel_stats, geometry='geometry')
        
        # Nastavenie CRS na WGS84
        gdf.set_crs(epsg=4326, inplace=True)
        
        # Vytvorenie mapy pomocou geopandas a plotly
        fig = px.choropleth_mapbox(
            gdf,
            geojson=gdf.__geo_interface__,
            locations=gdf.index,
            color='avg_yield_percentage',
            hover_name='name',
            hover_data=['area', 'crop_count'],
            color_continuous_scale='RdYlGn',
            mapbox_style="open-street-map",
            zoom=6,
            center={"lat": 48.6690, "lon": 19.6990},
            title="Výkonnosť parciel podľa priemernej výnosnosti (%)",
            labels={'avg_yield_percentage': 'Priemerná výnosnosť (%)'}
        )
        
        fig.update_layout(
            height=600,
            margin={"r":0,"t":30,"l":0,"b":0}
        )
        
        return fig
        
    except Exception as e:
        st.error(f"Chyba pri vytváraní mapy: {e}")
        return None

def show_enterprise_statistics(df, selected_crop):
    """Zobrazenie štatistík na úrovni podniku"""
    # Základné štatistiky
    st.header("📊 Prehľad dát")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Celkový počet záznamov", f"{len(df):,}")
    
    with col2:
        st.metric("Počet parciel", f"{df['agev_parcel_id'].nunique():,}")
    
    with col3:
        st.metric("Počet plodín", f"{df['crop'].nunique()}")
    
    with col4:
        st.metric("Obdobie", f"{df['year'].min()} - {df['year'].max()}")
    
    # Analýza vybranej plodiny
    st.header(f"🌱 Analýza plodiny: {selected_crop}")
    
    if selected_crop:
        crop_data = df[df['crop'] == selected_crop]
        
        # Grafy pre vybranú plodinu
        col1, col2 = st.columns(2)
        
        with col1:
            boxplot_fig = create_yield_boxplot(df, selected_crop)
            if boxplot_fig:
                st.plotly_chart(boxplot_fig, use_container_width=True)
        
        with col2:
            trend_fig = create_yield_trend(df, selected_crop)
            if trend_fig:
                st.plotly_chart(trend_fig, use_container_width=True)
    
    # Analýza výkonnosti parciel
    st.header("🏆 Výkonnosť parciel")
    
    # Top parcele podľa výnosnosti
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Top 10 parciel podľa výnosnosti")
        top_parcels = df.groupby('name')['yield_percentage'].mean().sort_values(ascending=False).head(10)
        
        fig = px.bar(
            x=top_parcels.values,
            y=top_parcels.index,
            orientation='h',
            title="Top parcele podľa priemernej výnosnosti (%)"
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Najhoršie parcele")
        worst_parcels = df.groupby('name')['yield_percentage'].mean().sort_values().head(10)
        
        fig = px.bar(
            x=worst_parcels.values,
            y=worst_parcels.index,
            orientation='h',
            title="Najhoršie parcele podľa priemernej výnosnosti (%)"
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    # Mapa parciel - zobrazuje sa automaticky pomocou geopandas
    st.header("🗺️ Mapa parciel")
    
    with st.spinner("Generujem mapu pomocou geopandas..."):
        map_fig = create_parcel_performance_map(df)
        if map_fig:
            st.plotly_chart(map_fig, use_container_width=True)
        else:
            st.warning("Nepodarilo sa vytvoriť mapu. Skontrolujte geometrické dáta.")
    
    # Štatistická analýza
    st.header("🔬 Štatistická analýza")
    
    # ANOVA test pre porovnanie plodín
    if st.checkbox("Zobraziť štatistické testy"):
        from scipy import stats
        
        # Filtrovanie plodín s dostatočnými dátami
        crop_counts = df['crop'].value_counts()
        valid_crops = crop_counts[crop_counts >= 5].index
        
        if len(valid_crops) >= 2:
            # ANOVA test
            crop_groups = [df[df['crop'] == crop]['yield_ha'].values for crop in valid_crops]
            
            try:
                f_stat, p_value = stats.f_oneway(*crop_groups)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("F-štatistika", f"{f_stat:.4f}")
                
                with col2:
                    st.metric("P-hodnota", f"{p_value:.4f}")
                
                if p_value < 0.05:
                    st.success("Existuje štatisticky významný rozdiel medzi výnosmi plodín (p < 0.05)")
                else:
                    st.info("Nie je štatisticky významný rozdiel medzi výnosmi plodín (p ≥ 0.05)")
                
            except Exception as e:
                st.warning(f"Nepodarilo sa vykonať štatistický test: {e}")
    
    # Export dát
    st.header("💾 Export dát")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Export CSV"):
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="Stiahnuť CSV",
                data=csv,
                file_name=f"vynosy_analyza_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    
    with col2:
        if st.button("Export Excel"):
            # Vytvorenie Excel súboru
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Výnosy', index=False)
            output.seek(0)
            
            st.download_button(
                label="Stiahnuť Excel",
                data=output.getvalue(),
                file_name=f"vynosy_analyza_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
