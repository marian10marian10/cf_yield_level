import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import geopandas as gpd
from shapely import wkt

def create_parcel_yield_timeline(df, parcel_name):
    """Vytvorenie časovej osi výnosov pre konkrétnu parcelu"""
    parcel_data = df[df['name'] == parcel_name].copy()
    
    if parcel_data.empty:
        return None
    
    # Zoradenie podľa roku a plodiny
    parcel_data = parcel_data.sort_values(['year', 'crop'])
    
    fig = go.Figure()
    
    # Pre každú plodinu vytvoríme líniu
    for crop in parcel_data['crop'].unique():
        crop_data = parcel_data[parcel_data['crop'] == crop]
        fig.add_trace(go.Scatter(
            x=crop_data['year'],
            y=crop_data['yield_ha'],
            mode='lines+markers',
            name=crop,
            line=dict(width=3),
            marker=dict(size=8)
        ))
    
    fig.update_layout(
        title=f"Výnosy parcely {parcel_name} v čase",
        xaxis_title="Rok",
        yaxis_title="Výnos (t/ha)",
        height=400,
        hovermode='x unified'
    )
    
    return fig

def create_parcel_crop_comparison(df, parcel_name):
    """Porovnanie plodín na konkrétnej parcele"""
    parcel_data = df[df['name'] == parcel_name].copy()
    
    if parcel_data.empty:
        return None
    
    # Agregácia dát podľa plodiny
    crop_stats = parcel_data.groupby('crop').agg({
        'yield_ha': ['mean', 'std', 'count'],
        'yield_percentage': 'mean',
        'area': 'mean'
    }).round(2)
    
    crop_stats.columns = ['priemerny_vyos', 'std_vyos', 'pocet_rokov', 'priemerna_vyosnost', 'priemerna_plocha']
    crop_stats = crop_stats.reset_index()
    
    # Vytvorenie grafu
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=crop_stats['crop'],
        y=crop_stats['priemerny_vyos'],
        name='Priemerný výnos (t/ha)',
        yaxis='y'
    ))
    
    fig.add_trace(go.Scatter(
        x=crop_stats['crop'],
        y=crop_stats['priemerna_vyosnost'],
        name='Priemerná výnosnosť (%)',
        yaxis='y2'
    ))
    
    fig.update_layout(
        title=f"Porovnanie plodín na parcele {parcel_name}",
        xaxis_title="Plodina",
        yaxis=dict(title="Výnos (t/ha)", side="left"),
        yaxis2=dict(title="Výnosnosť (%)", side="right", overlaying="y"),
        height=400,
        barmode='group'
    )
    
    return fig

def create_parcel_performance_radar(df, parcel_name):
    """Radarový graf výkonnosti parcely"""
    parcel_data = df[df['name'] == parcel_name].copy()
    
    if parcel_data.empty:
        return None
    
    # Výpočet metrík
    metrics = {
        'Priemerná výnosnosť (%)': parcel_data['yield_percentage'].mean(),
        'Stabilita výnosov': 100 - parcel_data['yield_ha'].std() / parcel_data['yield_ha'].mean() * 100,
        'Počet plodín': parcel_data['crop'].nunique(),
        'Priemerná plocha': parcel_data['area'].mean(),
        'Trend výnosov': parcel_data.groupby('year')['yield_ha'].mean().pct_change().mean() * 100
    }
    
    # Normalizácia hodnôt na 0-100
    max_values = {
        'Priemerná výnosnosť (%)': 150,
        'Stabilita výnosov': 100,
        'Počet plodín': 10,
        'Priemerná plocha': 20,
        'Trend výnosov': 20
    }
    
    normalized_values = []
    for metric, value in metrics.items():
        normalized = min(100, max(0, (value / max_values[metric]) * 100))
        normalized_values.append(normalized)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=normalized_values,
        theta=list(metrics.keys()),
        fill='toself',
        name='Výkonnosť parcely'
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100]
            )),
        title=f"Radarový graf výkonnosti parcely {parcel_name}",
        height=500
    )
    
    return fig

def create_parcel_map(df, selected_parcel):
    """Vytvorenie mapy s vybranou parcelou pomocou geopandas"""
    try:
        # Filtrovanie dát pre vybranú parcelu
        parcel_data = df[df['name'] == selected_parcel].copy()
        
        if parcel_data.empty or parcel_data['geometry'].isna().all():
            return None
        
        # Získanie geometrie parcely
        geometry_str = parcel_data['geometry'].iloc[0]
        if pd.isna(geometry_str):
            return None
        
        # Konverzia na GeoDataFrame
        parcel_geometry = wkt.loads(geometry_str)
        gdf = gpd.GeoDataFrame([{'name': selected_parcel, 'geometry': parcel_geometry}])
        gdf.set_crs(epsg=4326, inplace=True)
        
        # Výpočet bounds pre správny zoom
        bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        # Výpočet vhodného zoom levelu na základe veľkosti parcely
        lon_range = bounds[2] - bounds[0]
        lat_range = bounds[3] - bounds[1]
        max_range = max(lon_range, lat_range)
        
        # Nastavenie zoom levelu na základe veľkosti parcely
        if max_range > 0.1:  # Veľká parcela
            zoom_level = 12
        elif max_range > 0.01:  # Stredná parcela
            zoom_level = 15
        else:  # Malá parcela
            zoom_level = 18
        
        # Vytvorenie mapy pomocou geopandas a plotly
        fig = px.choropleth_mapbox(
            gdf,
            geojson=gdf.__geo_interface__,
            locations=gdf.index,
            color_discrete_sequence=['blue'],
            mapbox_style="open-street-map",
            zoom=zoom_level,
            center={"lat": center_lat, "lon": center_lon},
            title=f"Parcela: {selected_parcel}",
            hover_name='name'
        )
        
        fig.update_layout(
            height=500,
            margin={"r":0,"t":30,"l":0,"b":0}
        )
        
        return fig
        
    except Exception as e:
        st.error(f"Chyba pri vytváraní mapy parcely: {e}")
        return None

def show_parcel_statistics(df):
    """Zobrazenie štatistík na úrovni parcely"""
    st.header("🏞️ Štatistiky na úrovni parcely")
    
    # Sidebar pre výber parcely
    st.sidebar.header("Výber parcely")
    
    # Získanie zoznamu parciel
    available_parcels = sorted(df['name'].unique())
    
    if not available_parcels:
        st.error("Nie sú dostupné žiadne parcele.")
        return
    
    # Výber parcely
    selected_parcel = st.sidebar.selectbox(
        "Vyberte parcelu:",
        available_parcels,
        index=0
    )
    
    if not selected_parcel:
        st.info("Vyberte parcelu z ľavého panelu.")
        return
    
    # Filtrovanie dát pre vybranú parcelu
    parcel_data = df[df['name'] == selected_parcel].copy()
    
    if parcel_data.empty:
        st.error(f"Pre parcelu {selected_parcel} nie sú dostupné žiadne dáta.")
        return
    
    # Základné informácie o parcele
    st.subheader(f"📋 Informácie o parcele: {selected_parcel}")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Počet záznamov", f"{len(parcel_data):,}")
    
    with col2:
        st.metric("Počet plodín", f"{parcel_data['crop'].nunique()}")
    
    with col3:
        st.metric("Obdobie", f"{parcel_data['year'].min()} - {parcel_data['year'].max()}")
    
    with col4:
        st.metric("Priemerná plocha", f"{parcel_data['area'].mean():.2f} ha")
    
    # Časová os výnosov
    st.subheader("📈 Časová os výnosov")
    timeline_fig = create_parcel_yield_timeline(df, selected_parcel)
    if timeline_fig:
        st.plotly_chart(timeline_fig, use_container_width=True)
    
    # Porovnanie plodín
    st.subheader("🌾 Porovnanie plodín")
    crop_comparison_fig = create_parcel_crop_comparison(df, selected_parcel)
    if crop_comparison_fig:
        st.plotly_chart(crop_comparison_fig, use_container_width=True)
    
    # Detailné dáta parcely
    st.subheader("📊 Detailné dáta parcely")
    
    # Agregované dáta podľa roku a plodiny
    parcel_summary = parcel_data.groupby(['year', 'crop']).agg({
        'yield_ha': 'mean',
        'yield_percentage': 'mean',
        'area': 'mean'
    }).round(2).reset_index()
    
    st.dataframe(
        parcel_summary.sort_values(['year', 'crop'], ascending=[False, True]),
        use_container_width=True
    )
    
    # Radarový graf výkonnosti
    st.subheader("🎯 Radarový graf výkonnosti")
    radar_fig = create_parcel_performance_radar(df, selected_parcel)
    if radar_fig:
        st.plotly_chart(radar_fig, use_container_width=True)
    
    # Mapa parcely
    st.subheader("🗺️ Mapa parcely")
    
    with st.spinner("Generujem mapu parcely pomocou geopandas..."):
        map_fig = create_parcel_map(df, selected_parcel)
        if map_fig:
            st.plotly_chart(map_fig, use_container_width=True)
        else:
            st.warning("Nepodarilo sa vytvoriť mapu parcely.")
    
    # Štatistická analýza parcely
    st.subheader("🔬 Štatistická analýza parcely")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Variabilita výnosov
        yield_variability = parcel_data['yield_ha'].std() / parcel_data['yield_ha'].mean() * 100
        st.metric("Variabilita výnosov (CV)", f"{yield_variability:.1f}%")
        
        # Najlepší rok
        best_year = parcel_data.loc[parcel_data['yield_ha'].idxmax()]
        st.metric("Najlepší rok", f"{best_year['year']} ({best_year['crop']})")
    
    with col2:
        # Priemerná výnosnosť
        avg_performance = parcel_data['yield_percentage'].mean()
        st.metric("Priemerná výnosnosť", f"{avg_performance:.1f}%")
        
        # Najhorší rok
        worst_year = parcel_data.loc[parcel_data['yield_ha'].idxmin()]
        st.metric("Najhorší rok", f"{worst_year['year']} ({worst_year['crop']})")
    
    # Odporúčania pre parcelu
    st.subheader("💡 Odporúčania pre parcelu")
    
    # Analýza výkonnosti
    if avg_performance < 80:
        st.warning("Parcela má podpriemernú výnosnosť. Odporúčame:")
        st.write("- Analýzu pôdnych podmienok")
        st.write("- Optimalizáciu agrotechniky")
        st.write("- Zváženie zmeny plodín")
    elif avg_performance < 100:
        st.info("Parcela má priemernú výnosnosť. Možnosti zlepšenia:")
        st.write("- Jemné doladenie agrotechniky")
        st.write("- Optimalizácia termínov sejby a zberu")
    else:
        st.success("Parcela má výbornú výnosnosť! Pokračujte v súčasnom prístupe.")
    
    # Export dát parcely
    st.subheader("💾 Export dát parcely")
    
    if st.button("Export CSV pre parcelu"):
        csv = parcel_data.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="Stiahnuť CSV",
            data=csv,
            file_name=f"parcela_{selected_parcel.replace(' ', '_')}_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
