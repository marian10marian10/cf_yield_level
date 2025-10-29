import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import geopandas as gpd
from shapely import wkt
import folium
from folium import plugins
from modules.data_loader import (
    DB_USER_DESTINATION, 
    DB_PASSWORD_DESTINATION, 
    DB_HOST_DESTINATION, 
    DB_NAME_DESTINATION
)
from sqlalchemy import create_engine

def create_crop_timeline_charts(df, parcel_name):
    """Vytvorenie malých grafov pre časovú postupnosť úrod pre jednotlivé plodiny"""
    parcel_data = df[df['name'].astype(str) == parcel_name].copy()
    
    if parcel_data.empty:
        return None
    
    # Zoskupenie dát podľa plodiny a kontrola počtu záznamov
    crop_groups = parcel_data.groupby('crop')
    valid_crops = []
    
    for crop, crop_data in crop_groups:
        if len(crop_data) > 2:  # Iba plodiny s viac ako 2 záznamami
            valid_crops.append((crop, crop_data))
    
    if not valid_crops:
        return None
    
    # Vytvorenie stĺpcov pre grafy (max 3 grafy v riadku)
    cols_per_row = 3
    num_rows = (len(valid_crops) + cols_per_row - 1) // cols_per_row
    
    charts_container = []
    
    for i in range(num_rows):
        row_crops = valid_crops[i * cols_per_row:(i + 1) * cols_per_row]
        cols = st.columns(len(row_crops))
        
        for j, (crop, crop_data) in enumerate(row_crops):
            with cols[j]:
                # Zoradenie dát podľa roku
                crop_data_sorted = crop_data.sort_values('year')
                
                # Vytvorenie malého grafu pre plodinu
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=crop_data_sorted['year'],
                    y=crop_data_sorted['yield_ha'],
                    mode='lines+markers',
                    name=crop,
                    line=dict(width=2, color='#1f77b4'),
                    marker=dict(size=6, color='#1f77b4'),
                    hovertemplate=f'<b>{crop}</b><br>' +
                                'Rok: %{x}<br>' +
                                'Výnos: %{y:.2f} t/ha<extra></extra>'
                ))
                
                # Pridanie trendovej línie ak sú aspoň 3 body
                if len(crop_data_sorted) >= 3:
                    z = np.polyfit(crop_data_sorted['year'], crop_data_sorted['yield_ha'], 1)
                    p = np.poly1d(z)
                    fig.add_trace(go.Scatter(
                        x=crop_data_sorted['year'],
                        y=p(crop_data_sorted['year']),
                        mode='lines',
                        name='Trend',
                        line=dict(width=1, color='red', dash='dash'),
                        showlegend=False,
                        hovertemplate='Trend<extra></extra>'
                    ))
                
                # Výpočet metrík pre plodinu
                avg_yield = crop_data_sorted['yield_ha'].mean()
                yield_trend = "↗️" if len(crop_data_sorted) >= 2 and crop_data_sorted['yield_ha'].iloc[-1] > crop_data_sorted['yield_ha'].iloc[0] else "↘️"
                
                # Aktualizácia layoutu grafu
                fig.update_layout(
                    title=f"🌾 {crop}",
                    xaxis_title="Rok",
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
                        zeroline=False
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridwidth=1,
                        gridcolor='rgba(128,128,128,0.2)',
                        zeroline=False
                    )
                )
                
                # Pridanie metrík pod graf
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                
                # Zobrazenie kľúčových metrík
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Priemerný výnos", f"{avg_yield:.2f} t/ha")
                with col2:
                    st.metric("Trend", yield_trend)
                
                # Detailné informácie o plodine
                with st.expander(f"📊 Detailné údaje pre {crop}"):
                    st.write(f"**Počet záznamov:** {len(crop_data_sorted)}")
                    st.write(f"**Obdobie:** {crop_data_sorted['year'].min()} - {crop_data_sorted['year'].max()}")
                    st.write(f"**Najlepší rok:** {crop_data_sorted.loc[crop_data_sorted['yield_ha'].idxmax(), 'year']} ({crop_data_sorted['yield_ha'].max():.2f} t/ha)")
                    st.write(f"**Najhorší rok:** {crop_data_sorted.loc[crop_data_sorted['yield_ha'].idxmin(), 'year']} ({crop_data_sorted['yield_ha'].min():.2f} t/ha)")
                    
                    # Malá tabuľka s údajmi
                    display_data = crop_data_sorted[['year', 'yield_ha', 'yield_percentage']].copy()
                    display_data.columns = ['Rok', 'Výnos (t/ha)', 'Výnosnosť (%)']
                    st.dataframe(display_data, use_container_width=True, hide_index=True)
    
    return True

def create_parcel_yield_timeline(df, parcel_name):
    """Vytvorenie časovej osi výnosov pre konkrétnu parcelu"""
    parcel_data = df[df['name'].astype(str) == parcel_name].copy()
    
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
    """Porovnanie plodín na konkrétnej parcieli"""
    parcel_data = df[df['name'].astype(str) == parcel_name].copy()
    
    if parcel_data.empty:
        return None
    
    # Agregácia dát podľa plodiny
    crop_stats = parcel_data.groupby('crop').agg({
        'yield_ha': ['mean', 'std', 'count'],
        'area': 'mean'
    }).round(2)
    
    crop_stats.columns = ['priemerny_vyos', 'std_vyos', 'pocet_rokov', 'priemerna_plocha']
    crop_stats = crop_stats.reset_index()
    
    # Vytvorenie grafu
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=crop_stats['crop'],
        y=crop_stats['priemerny_vyos'],
        name='Priemerný výnos (t/ha)',
        marker_color='#1f77b4'
    ))
    
    fig.update_layout(
        title=f"Porovnanie plodín na parcieli {parcel_name}",
        xaxis_title="Plodina",
        yaxis_title="Výnos (t/ha)",
        height=400,
        showlegend=True
    )
    
    return fig

def create_parcel_performance_radar(df, parcel_name):
    """Radarový graf výkonnosti parcely"""
    parcel_data = df[df['name'].astype(str) == parcel_name].copy()
    
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
    """Vytvorenie profesionálnej mapy s vybranou parcelou pomocou geopandas a folium"""
    try:
        import folium
        from folium import plugins
        
        # Filtrovanie dát pre vybranú parcelu
        parcel_data = df[df['name'].astype(str) == selected_parcel].copy()
        
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
        
        if max_range > 0.1:  # Veľká parcela
            zoom_level = 11  # Znížené z 12 na 11 pre lepší prehľad
        elif max_range > 0.01:  # Stredná parcela
            zoom_level = 14  # Znížené z 15 na 14 pre lepší prehľad
        else:  # Malá parcela
            zoom_level = 17  # Znížené z 18 na 17 pre lepší prehľad
        
        # Nastavenie bounds s paddingom pre zobrazenie celej parcely
        padding = max_range * 0.1  # 10% padding okolo parcely
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=zoom_level,
            tiles='CartoDB positron',  # Profesionálny štýl mapy
            control_scale=True
        )
        
        # Nastavenie bounds s paddingom pre zobrazenie celej parcely
        m.fit_bounds([
            [bounds[1] - padding, bounds[0] - padding],
            [bounds[3] + padding, bounds[2] + padding]
        ])
        
        # Pridanie parcely s farebným kódovaním podľa výnosov
        if not parcel_data.empty:
            # Výpočet priemerného výnosu pre farebné kódovanie
            avg_yield = parcel_data['yield_ha'].mean()
            avg_percentage = parcel_data['yield_percentage'].mean()
            
            # Farebné kódovanie podľa výnosnosti
            if avg_percentage >= 120:
                parcel_color = '#2E8B57'  # Tmavozelená - výborná
            elif avg_percentage >= 100:
                parcel_color = '#32CD32'  # Limetkovozelená - dobrá
            elif avg_percentage >= 80:
                parcel_color = '#FFD700'  # Zlatá - priemerná
            elif avg_percentage >= 60:
                parcel_color = '#FF8C00'  # Tmavooranžová - podpriemerná
            else:
                parcel_color = '#DC143C'  # Karmínová - slabá
            
            # Pridanie parcely ako polygon
            folium.GeoJson(
                gdf,
                style_function=lambda x: {
                    'fillColor': parcel_color,
                    'color': '#000000',
                    'weight': 2,
                    'fillOpacity': 0.7
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['name'],
                    aliases=['Parcela:'],
                    localize=True,
                    sticky=False,
                    labels=True,
                    style="""
                        background-color: rgba(0, 0, 0, 0.8);
                        border: 2px solid white;
                        border-radius: 5px;
                        box-shadow: 3px;
                        color: white;
                        font-weight: bold;
                        font-size: 12px;
                        padding: 5px;
                    """
                )
            ).add_to(m)
        
        # Pridanie informačného boxu
        if not parcel_data.empty:
            # Výpočet metrík pre informačný box
            total_area = parcel_data['area'].sum()
            avg_yield = parcel_data['yield_ha'].mean()
            avg_percentage = parcel_data['yield_percentage'].mean()
            crop_count = parcel_data['crop'].nunique()
            year_range = f"{parcel_data['year'].min()} - {parcel_data['year'].max()}"
            
            # Pridanie informačného boxu
            info_html = f"""
            <div style="position: fixed; 
                        top: 10px; left: 10px; width: 300px; height: auto; 
                        background-color: white; border:2px solid grey; z-index:9999; 
                        font-size:14px; padding: 10px; border-radius: 5px;">
                <h4>Parcela: {selected_parcel}</h4>
                <p><b>Plocha:</b> {total_area:.2f} ha</p>
                <p><b>Priemerný výnos:</b> {avg_yield:.2f} t/ha</p>
                <p><b>Výnosnosť:</b> {avg_percentage:.1f}%</p>
                <p><b>Počet plodín:</b> {crop_count}</p>
                <p><b>Obdobie:</b> {year_range}</p>
            </div>
            """
            m.get_root().html.add_child(folium.Element(info_html))
        
        # Pridanie fullscreen tlačidla
        plugins.Fullscreen().add_to(m)
        
        return m
        
    except Exception as e:
        st.error(f"Chyba pri vytváraní mapy parcely: {e}")
        return None

def create_enhanced_parcel_map(df, selected_parcel):
    """Vytvorenie datovej a faktografickej mapy parcely s mriežkou a bez satelitného pozadia"""
    try:
        # Filtrovanie dát pre vybranú parcelu
        parcel_data = df[df['name'].astype(str) == selected_parcel].copy()
        
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
        bounds = gdf.total_bounds
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        # Výpočet vhodného zoom levelu
        lon_range = bounds[2] - bounds[0]
        lat_range = bounds[3] - bounds[1]
        max_range = max(lon_range, lat_range)
        
        # Nastavenie zoom levelu tak, aby parcela bola zobrazená celá s paddingom
        if max_range > 0.1:  # Veľká parcela
            zoom_level = 11  # Znížené z 12 na 11 pre lepší prehľad
        elif max_range > 0.01:  # Stredná parcela
            zoom_level = 14  # Znížené z 15 na 14 pre lepší prehľad
        else:  # Malá parcela
            zoom_level = 17  # Znížené z 18 na 17 pre lepší prehľad
        
        # Vytvorenie mapy pomocou folium s datovým vzhľadom
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=zoom_level,
            tiles='CartoDB positron',  # Čistý, datový štýl bez satelitného pozadia
            control_scale=True
        )
        
        # Nastavenie bounds s paddingom pre zobrazenie celej parcely
        padding = max_range * 0.1  # 10% padding okolo parcely
        m.fit_bounds([
            [bounds[1] - padding, bounds[0] - padding],
            [bounds[3] + padding, bounds[2] + padding]
        ])
        
        # Pridanie parcely s farebným kódovaním
        folium.GeoJson(
            gdf,
            style_function=lambda x: {
                'fillColor': parcel_color if 'parcel_color' in locals() else '#1f77b4',
                'color': '#000000',
                'weight': 3,
                'fillOpacity': 0.8
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['name'],
                aliases=['Parcela:'],
                localize=True,
                sticky=False,
                labels=True,
                style="""
                    background-color: rgba(0, 0, 0, 0.8);
                    border: 2px solid white;
                    border-radius: 5px;
                    box-shadow: 3px;
                    color: white;
                    font-weight: bold;
                    font-size: 12px;
                    padding: 5px;
                """
            )
        ).add_to(m)
        
        # Výpočet metrík pre farebné kódovanie a informácie
        if not parcel_data.empty:
            avg_percentage = parcel_data['yield_percentage'].mean()
            avg_yield = parcel_data['yield_ha'].mean()
            total_area = parcel_data['area'].sum()
            crop_count = parcel_data['crop'].nunique()
            year_range = f"{parcel_data['year'].min()} - {parcel_data['year'].max()}"
            
            # Výpočet ďalších metrík
            yield_std = parcel_data['yield_ha'].std()
            yield_cv = (yield_std / avg_yield * 100) if avg_yield > 0 else 0
            best_year = parcel_data.loc[parcel_data['yield_ha'].idxmax()]
            worst_year = parcel_data.loc[parcel_data['yield_ha'].idxmin()]
            
            # Pokročilé farebné kódovanie podľa výnosnosti
            if avg_percentage >= 130:
                parcel_color = '#006400'  # Tmavozelená - výborná
                performance_level = "Výborná"
                performance_score = "A+"
            elif avg_percentage >= 115:
                parcel_color = '#228B22'  # Forest green - veľmi dobrá
                performance_level = "Veľmi dobrá"
                performance_score = "A"
            elif avg_percentage >= 100:
                parcel_color = '#32CD32'  # Limetkovozelená - dobrá
                performance_level = "Dobrá"
                performance_score = "B+"
            elif avg_percentage >= 85:
                parcel_color = '#FFD700'  # Zlatá - priemerná
                performance_level = "Priemerná"
                performance_score = "B"
            elif avg_percentage >= 70:
                parcel_color = '#FF8C00'  # Tmavooranžová - podpriemerná
                performance_level = "Podpriemerná"
                performance_score = "C"
            else:
                parcel_color = '#DC143C'  # Karmínová - slabá
                performance_level = "Slabá"
                performance_score = "D"
        
        # Vytvorenie mapy pomocou folium s datovým vzhľadom
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=zoom_level,
            tiles='CartoDB positron',  # Čistý, datový štýl bez satelitného pozadia
            control_scale=True
        )
        
        # Pridanie parcely s farebným kódovaním
        folium.GeoJson(
            gdf,
            style_function=lambda x: {
                'fillColor': parcel_color if 'parcel_color' in locals() else '#1f77b4',
                'color': '#000000',
                'weight': 3,
                'fillOpacity': 0.8
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['name'],
                aliases=['Parcela:'],
                localize=True,
                sticky=False,
                labels=True,
                style="""
                    background-color: rgba(0, 0, 0, 0.8);
                    border: 2px solid white;
                    border-radius: 5px;
                    box-shadow: 3px;
                    color: white;
                    font-weight: bold;
                    font-size: 12px;
                    padding: 5px;
                """
            )
        ).add_to(m)
        
        # Pridanie mriežky pre datový vzhľad
        # Vytvorenie mriežky okolo parcely
        grid_spacing = max_range / 10  # 10 riadkov/stĺpcov mriežky
        
        # Pridanie vertikálnych čiar mriežky
        for i in range(11):
            lon_pos = bounds[0] + i * grid_spacing
            folium.PolyLine(
                locations=[[bounds[1], lon_pos], [bounds[3], lon_pos]],
                color='rgba(128, 128, 128, 0.3)',
                weight=1,
                opacity=0.3
            ).add_to(m)
        
        # Pridanie horizontálnych čiar mriežky
        for i in range(11):
            lat_pos = bounds[1] + i * grid_spacing
            folium.PolyLine(
                locations=[[lat_pos, bounds[0]], [lat_pos, bounds[2]]],
                color='rgba(128, 128, 128, 0.3)',
                weight=1,
                opacity=0.3
            ).add_to(m)
        
        # Pridanie súradníc mriežky
        for i in range(11):
            for j in range(11):
                lon_pos = bounds[0] + i * grid_spacing
                lat_pos = bounds[1] + j * grid_spacing
                folium.CircleMarker(
                    location=[lat_pos, lon_pos],
                    radius=2,
                    color='rgba(128, 128, 128, 0.5)',
                    fill=True,
                    fillColor='rgba(128, 128, 128, 0.5)',
                    fillOpacity=0.5
                ).add_to(m)
        
        # Pridanie hlavného informačného boxu s datami
        if not parcel_data.empty:
            info_html = f"""
            <div style="position: fixed; 
                        top: 10px; left: 10px; width: 350px; height: auto; 
                        background-color: white; border:2px solid {parcel_color if 'parcel_color' in locals() else '#1f77b4'}; z-index:9999; 
                        font-size:14px; padding: 15px; border-radius: 5px; box-shadow: 3px 3px 10px rgba(0,0,0,0.3);">
                <h4>🏞️ {selected_parcel}</h4>
                <p><b>Výkonnosť:</b> {performance_level} ({performance_score})</p>
                <p><b>Výnosnosť:</b> {avg_percentage:.1f}%</p>
                <p><b>Priemerný výnos:</b> {avg_yield:.2f} t/ha</p>
                <p><b>Celková plocha:</b> {total_area:.2f} ha</p>
                <p><b>Počet plodín:</b> {crop_count}</p>
                <p><b>Obdobie:</b> {year_range}</p>
            </div>
            """
            m.get_root().html.add_child(folium.Element(info_html))
            
            # Pridanie štatistického boxu s detailnými metrikami
            stats_html = f"""
            <div style="position: fixed; 
                        top: 10px; right: 10px; width: 350px; height: auto; 
                        background-color: white; border:2px solid rgba(0,0,0,0.5); z-index:9999; 
                        font-size:12px; padding: 15px; border-radius: 5px; box-shadow: 3px 3px 10px rgba(0,0,0,0.3);">
                <h4>📊 Štatistiky parcely:</h4>
                <p><b>Variabilita (CV):</b> {yield_cv:.1f}%</p>
                <p><b>Najlepší rok:</b> {best_year['year']} ({best_year['crop']})</p>
                <p><b>Najhorší rok:</b> {worst_year['year']} ({worst_year['crop']})</p>
                <p><b>Rozsah výnosov:</b> {worst_year['yield_ha']:.2f} - {best_year['yield_ha']:.2f} t/ha</p>
                <p><b>Počet záznamov:</b> {len(parcel_data)}</p>
            </div>
            """
            m.get_root().html.add_child(folium.Element(stats_html))
            
            # Pridanie legendy pre farebné kódovanie
            legend_html = """
            <div style="position: fixed; 
                        bottom: 10px; left: 10px; width: 300px; height: auto; 
                        background-color: white; border:2px solid rgba(0,0,0,0.3); z-index:9999; 
                        font-size:11px; padding: 15px; border-radius: 5px; box-shadow: 3px 3px 10px rgba(0,0,0,0.3);">
                <h4>🎨 Farebné kódovanie výnosnosti:</h4>
                <p>🟢 ≥130% - Výborná (A+)</p>
                <p>🟢 ≥115% - Veľmi dobrá (A)</p>
                <p>🟢 ≥100% - Dobrá (B+)</p>
                <p>🟡 ≥85% - Priemerná (B)</p>
                <p>🟠 ≥70% - Podpriemerná (C)</p>
                <p>🔴 <70% - Slabá (D)</p>
            </div>
            """
            m.get_root().html.add_child(folium.Element(legend_html))
            
            # Pridanie súradníc parcely
            coords_html = f"""
            <div style="position: fixed; 
                        bottom: 10px; right: 10px; width: 300px; height: auto; 
                        background-color: white; border:2px solid rgba(0,0,0,0.3); z-index:9999; 
                        font-size:11px; padding: 15px; border-radius: 5px; box-shadow: 3px 3px 10px rgba(0,0,0,0.3);">
                <h4>📍 Súradnice parcely:</h4>
                <p>Stred: {center_lat:.6f}°N, {center_lon:.6f}°E</p>
                <p>Rozmer: {lon_range:.6f}° × {lat_range:.6f}°</p>
                <p>Zoom: {zoom_level}</p>
            </div>
            """
            m.get_root().html.add_child(folium.Element(coords_html))
        
        # Pridanie fullscreen tlačidla
        plugins.Fullscreen().add_to(m)
        
        return m
        
    except Exception as e:
        st.error(f"Chyba pri vytváraní datovej mapy parcely: {e}")
        return None

def create_all_parcels_map(df):
    """Vytvorenie datovej a faktografickej mapy všetkých parciel s mriežkou a bez satelitného pozadia"""
    try:
        # Filtrovanie dát s geometriou
        parcels_with_geometry = df[df['geometry'].notna()].copy()
        
        if parcels_with_geometry.empty:
            return None
        
        # Agregácia dát podľa parciel s detailnými metrikami
        parcel_stats = parcels_with_geometry.groupby('name').agg({
            'yield_percentage': ['mean', 'std', 'min', 'max'],
            'yield_ha': ['mean', 'std', 'min', 'max'],
            'area': ['sum', 'mean'],
            'crop': 'nunique',
            'year': ['min', 'max', 'nunique']
        }).round(2)
        
        # Flatten column names
        parcel_stats.columns = [
            'avg_yield_percentage', 'std_yield_percentage', 'min_yield_percentage', 'max_yield_percentage',
            'avg_yield_ha', 'std_yield_ha', 'min_yield_ha', 'max_yield_ha',
            'total_area', 'avg_area', 'crop_count', 'year_min', 'year_max', 'year_count'
        ]
        parcel_stats = parcel_stats.reset_index()
        
        # Výpočet celkových bounds
        all_geometries = []
        for _, row in parcels_with_geometry.iterrows():
            try:
                geom = wkt.loads(row['geometry'])
                all_geometries.append(geom)
            except:
                continue
        
        if not all_geometries:
            return None
        
        # Vytvorenie GeoDataFrame pre všetky parcely
        gdf = gpd.GeoDataFrame(parcel_stats)
        gdf['geometry'] = all_geometries[:len(parcel_stats)]
        gdf.set_crs(epsg=4326, inplace=True)
        
        # Výpočet bounds
        bounds = gdf.total_bounds
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        # Vytvorenie mapy pomocou folium s datovým vzhľadom
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=10,
            tiles='CartoDB positron',  # Čistý, datový štýl bez satelitného pozadia
            control_scale=True
        )
        
        # Pridanie všetkých parciel s farebným kódovaním
        for idx, row in gdf.iterrows():
            # Farebné kódovanie podľa výnosnosti
            if row['avg_yield_percentage'] >= 130:
                color = '#006400'  # Tmavozelená
            elif row['avg_yield_percentage'] >= 115:
                color = '#228B22'  # Forest green
            elif row['avg_yield_percentage'] >= 100:
                color = '#32CD32'  # Limetkovozelená
            elif row['avg_yield_percentage'] >= 85:
                color = '#FFD700'  # Zlatá
            elif row['avg_yield_percentage'] >= 70:
                color = '#FF8C00'  # Tmavooranžová
            else:
                color = '#DC143C'  # Karmínová
            
            # Pridanie parcely
            folium.GeoJson(
                gdf.iloc[[idx]],
                style_function=lambda x: {
                    'fillColor': color,
                    'color': '#000000',
                    'weight': 1,
                    'fillOpacity': 0.7
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['name', 'avg_yield_percentage', 'total_area'],
                    aliases=['Parcela:', 'Výnosnosť (%):', 'Plocha (ha):'],
                    localize=True,
                    sticky=False,
                    labels=True,
                    style="""
                        background-color: rgba(0, 0, 0, 0.8);
                        border: 2px solid white;
                        border-radius: 5px;
                        box-shadow: 3px;
                        color: white;
                        font-weight: bold;
                        font-size: 12px;
                        padding: 5px;
                    """
                )
            ).add_to(m)
        
        # Vytvorenie mapy pomocou folium s datovým vzhľadom
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=10,
            tiles='CartoDB positron',  # Čistý, datový štýl bez satelitného pozadia
            control_scale=True
        )
        
        # Pridanie všetkých parciel s farebným kódovaním
        for idx, row in gdf.iterrows():
            # Farebné kódovanie podľa výnosnosti
            if row['avg_yield_percentage'] >= 130:
                color = '#006400'  # Tmavozelená
            elif row['avg_yield_percentage'] >= 115:
                color = '#228B22'  # Forest green
            elif row['avg_yield_percentage'] >= 100:
                color = '#32CD32'  # Limetkovozelená
            elif row['avg_yield_percentage'] >= 85:
                color = '#FFD700'  # Zlatá
            elif row['avg_yield_percentage'] >= 70:
                color = '#FF8C00'  # Tmavooranžová
            else:
                color = '#DC143C'  # Karmínová
            
            # Pridanie parcely
            folium.GeoJson(
                gdf.iloc[[idx]],
                style_function=lambda x: {
                    'fillColor': color,
                    'color': '#000000',
                    'weight': 1,
                    'fillOpacity': 0.7
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['name', 'avg_yield_percentage', 'total_area'],
                    aliases=['Parcela:', 'Výnosnosť (%):', 'Plocha (ha):'],
                    localize=True,
                    sticky=False,
                    labels=True,
                    style="""
                        background-color: rgba(0, 0, 0, 0.8);
                        border: 2px solid white;
                        border-radius: 5px;
                        box-shadow: 3px;
                        color: white;
                        font-weight: bold;
                        font-size: 12px;
                        padding: 5px;
                    """
                )
            ).add_to(m)
        
        # Pridanie mriežky pre datový vzhľad
        # Výpočet rozmerov oblasti
        lon_range = bounds[2] - bounds[0]
        lat_range = bounds[3] - bounds[1]
        grid_spacing = max(lon_range, lat_range) / 20  # 20 riadkov/stĺpcov mriežky
        
        # Pridanie vertikálnych čiar mriežky
        for i in range(21):
            lon_pos = bounds[0] + i * grid_spacing
            folium.PolyLine(
                locations=[[bounds[1], lon_pos], [bounds[3], lon_pos]],
                color='rgba(128, 128, 128, 0.2)',
                weight=0.5,
                opacity=0.2
            ).add_to(m)
        
        # Pridanie horizontálnych čiar mriežky
        for i in range(21):
            lat_pos = bounds[1] + i * grid_spacing
            folium.PolyLine(
                locations=[[lat_pos, bounds[0]], [lat_pos, bounds[2]]],
                color='rgba(128, 128, 128, 0.2)',
                weight=0.5,
                opacity=0.2
            ).add_to(m)
        
        # Pridanie súradníc mriežky (menej husté pre prehľadnosť)
        for i in range(0, 21, 2):  # Každý druhý bod
            for j in range(0, 21, 2):
                lon_pos = bounds[0] + i * grid_spacing
                lat_pos = bounds[1] + j * grid_spacing
                folium.CircleMarker(
                    location=[lat_pos, lon_pos],
                    radius=1,
                    color='rgba(128, 128, 128, 0.3)',
                    fill=True,
                    fillColor='rgba(128, 128, 128, 0.3)',
                    fillOpacity=0.3
                ).add_to(m)
        
        # Pridanie hlavnej legendy s farebným kódovaním
        legend_html = """
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 300px; height: auto; 
                    background-color: white; border:2px solid rgba(0,0,0,0.5); z-index:9999; 
                    font-size:12px; padding: 15px; border-radius: 5px; box-shadow: 3px 3px 10px rgba(0,0,0,0.3);">
            <h4>🎨 Farebné kódovanie parciel:</h4>
            <p>🟢 ≥130% - Výborná (A+)</p>
            <p>🟢 ≥115% - Veľmi dobrá (A)</p>
            <p>🟢 ≥100% - Dobrá (B+)</p>
            <p>🟡 ≥85% - Priemerná (B)</p>
            <p>🟠 ≥70% - Podpriemerná (C)</p>
            <p>🔴 <70% - Slabá (D)</p>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Pridanie detailných štatistík všetkých parciel
        total_parcels = len(parcel_stats)
        avg_performance = parcel_stats['avg_yield_percentage'].mean()
        best_parcel = parcel_stats.loc[parcel_stats['avg_yield_percentage'].idxmax()]
        worst_parcel = parcel_stats.loc[parcel_stats['avg_yield_percentage'].idxmin()]
        
        stats_html = f"""
        <div style="position: fixed; 
                    top: 10px; left: 10px; width: 350px; height: auto; 
                    background-color: white; border:2px solid rgba(0,0,0,0.5); z-index:9999; 
                    font-size:12px; padding: 15px; border-radius: 5px; box-shadow: 3px 3px 10px rgba(0,0,0,0.3);">
            <h4>📊 Prehľad všetkých parciel:</h4>
            <p>Celkový počet: {total_parcels}</p>
            <p>Priemerná výnosnosť: {avg_performance:.1f}%</p>
            <p>Rozsah rokov: {parcel_stats['year_min'].min()} - {parcel_stats['year_max'].max()}</p>
            <p>Celková plocha: {parcel_stats['total_area'].sum():.1f} ha</p>
        </div>
        """
        m.get_root().html.add_child(folium.Element(stats_html))
        
        # Pridanie informácií o najlepšej a najhoršej parcieli
        best_worst_html = f"""
        <div style="position: fixed; 
                    bottom: 10px; left: 10px; width: 350px; height: auto; 
                    background-color: white; border:2px solid rgba(0,0,0,0.3); z-index:9999; 
                    font-size:11px; padding: 15px; border-radius: 5px; box-shadow: 3px 3px 10px rgba(0,0,0,0.3);">
                         <h4>📊 Najlepšia parcela: {best_parcel['name']}</h4>
            <p>Výnosnosť: {best_parcel['avg_yield_percentage']:.1f}%</p>
            <h4>⚠️ Najhoršia parcela: {worst_parcel['name']}</h4>
            <p>Výnosnosť: {worst_parcel['avg_yield_percentage']:.1f}%</p>
        </div>
        """
        m.get_root().html.add_child(folium.Element(best_worst_html))
        
        # Pridanie súradníc oblasti
        coords_html = f"""
        <div style="position: fixed; 
                    bottom: 10px; right: 10px; width: 300px; height: auto; 
                    background-color: white; border:2px solid rgba(0,0,0,0.3); z-index:9999; 
                    font-size:11px; padding: 15px; border-radius: 5px; box-shadow: 3px 3px 10px rgba(0,0,0,0.3);">
            <h4>📍 Súradnice oblasti:</h4>
            <p>Stred: {center_lat:.6f}°N, {center_lon:.6f}°E</p>
            <p>Rozmer: {lon_range:.6f}° × {lat_range:.6f}°</p>
            <p>Zoom: 10</p>
        </div>
        """
        m.get_root().html.add_child(folium.Element(coords_html))
        
        # Pridanie fullscreen tlačidla
        plugins.Fullscreen().add_to(m)
        
        return m
        
    except Exception as e:
        st.error(f"Chyba pri vytváraní datovej mapy všetkých parciel: {e}")
        return None

def show_parcel_statistics(df, selected_parcel):
    """Zobrazenie štatistík parcely z materialized view"""
    st.header("🏞️ Štatistiky parcely")
    
    # Pripojenie k databáze
    connection_string = f"postgresql://{DB_USER_DESTINATION}:{DB_PASSWORD_DESTINATION}@{DB_HOST_DESTINATION}/{DB_NAME_DESTINATION}"
    engine = create_engine(connection_string)
    
    try:
        from sqlalchemy.sql import text
        
        # Príprava rôznych vyhľadávacích reťazcov
        search_variants = [
            selected_parcel,  # Presný reťazec
            selected_parcel.strip(),  # Bez medzier
            selected_parcel.replace('_', ''),  # Bez podtržítek
            selected_parcel.replace(' ', ''),  # Bez medzier
        ]
        
        # Načítanie dát pre vybranú parcelu
        query = text("""
        SELECT * 
        FROM yield_level.mv_skeagis_source 
        WHERE 
            REPLACE(REPLACE(TRIM(localname), '_', ''), ' ', '') = 
            REPLACE(REPLACE(TRIM(:parcel_name), '_', ''), ' ', '')
        ORDER BY season_id
        """)
        
        # Skúšame rôzne varianty vyhľadávania
        parcel_data = None
        for variant in search_variants:
            with engine.connect() as connection:
                result = pd.read_sql(
                    query, 
                    connection, 
                    params={'parcel_name': variant}
                )
                
                if not result.empty:
                    parcel_data = result
                    break
        
        # Ak stále nemáme dáta, skúsime čiastočnú zhodu
        if parcel_data is None or parcel_data.empty:
            query_partial = text("""
            SELECT * 
            FROM yield_level.mv_skeagis_source 
            WHERE 
                REPLACE(REPLACE(TRIM(localname), '_', ''), ' ', '') 
                ILIKE 
                REPLACE(REPLACE(TRIM(:parcel_pattern), '_', ''), ' ', '')
            ORDER BY season_id
            """)
            
            with engine.connect() as connection:
                parcel_data = pd.read_sql(
                    query_partial, 
                    connection, 
                    params={'parcel_pattern': f'%{selected_parcel}%'}
                )
        
        if parcel_data is None or parcel_data.empty:
            st.error(f"Pre parcelu {selected_parcel} nie sú dostupné žiadne dáta.")
            
            # Zobrazenie dostupných parciel pre kontrolu
            query_available = text("""
            SELECT DISTINCT localname 
            FROM yield_level.mv_skeagis_source 
            ORDER BY localname 
            LIMIT :limit_count
            """)
            
            with engine.connect() as connection:
                available_parcels = pd.read_sql(
                    query_available, 
                    connection, 
                    params={'limit_count': 20}
                )
            
            st.warning("Dostupné parcely:")
            st.dataframe(available_parcels, use_container_width=True)
            
            return
        
        # Základné informácie o parcele
        st.subheader(f"📋 Informácie o parcele: {selected_parcel}")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Počet záznamov", f"{len(parcel_data):,}")
        
        with col2:
            st.metric("Počet plodín", f"{parcel_data['crop'].nunique()}")
        
        with col3:
            st.metric("Sezóny", f"{parcel_data['season_id'].min()} - {parcel_data['season_id'].max()}")
        
        with col4:
            st.metric("Priemerná plocha", f"{parcel_data['area_ha'].mean():.2f} ha")
        
        # Agregácia dát podľa plodiny
        crop_stats = parcel_data.groupby('crop').agg({
            'sk_yield_ha': ['mean', 'std', 'count'],
            'area_ha': 'mean'
        }).round(2)
        
        crop_stats.columns = ['priemerny_vyos', 'std_vyos', 'pocet_rokov', 'priemerna_plocha']
        crop_stats = crop_stats.reset_index()
        
        # Výpočet celkového priemerného výnosu pre porovnanie
        total_avg_yield = parcel_data['sk_yield_ha'].mean()
        
        # Porovnanie s celkovým priemerom
        crop_stats['odchylka_od_priemeru'] = ((crop_stats['priemerny_vyos'] - total_avg_yield) / total_avg_yield * 100).round(2)
        
        # Graf porovnania plodín
        st.subheader("🌾 Porovnanie plodín")
        
        # Bar chart s priemerným výnosom
        fig_crops = px.bar(
            crop_stats, 
            x='crop', 
            y='priemerny_vyos', 
            color='odchylka_od_priemeru',
            color_continuous_scale='RdYlGn',
            title='Priemerné výnosy podľa plodín',
            labels={'crop': 'Plodina', 'priemerny_vyos': 'Priemerný výnos (t/ha)'}
        )
        st.plotly_chart(fig_crops, use_container_width=True)
        
        # Tabuľka s porovnaním plodín
        st.subheader("📊 Detailné porovnanie plodín")
        
        st.dataframe(
            crop_stats.drop(columns=['std_vyos', 'priemerna_plocha', 'odchylka_od_priemeru']),
            use_container_width=True
        )
        
        # Detailná história parcely
        st.subheader("📈 História parcely")
        st.dataframe(
            parcel_data.sort_values('season_id', ascending=False).drop(columns=['parcel_season_id', 'parcel_id', 'geometry']),
            use_container_width=True
        )
        
        # Histogram výnosov
        # Removed distribution of yields section
        
        # Mapa parcely
        st.subheader("🗺️ Lokalizácia parcely")
        
        # Kontrola dostupnosti geometrie
        if 'geometry' in parcel_data.columns and not parcel_data['geometry'].isna().all():
            # Použitie prvej dostupnej geometrie
            geometry_str = parcel_data['geometry'].dropna().iloc[0]
            
            try:
                # Konverzia geometrie
                from shapely import wkt
                import geopandas as gpd
                import folium
                from shapely.wkb import loads as wkb_loads
                import binascii
                
                # Pokus o konverziu WKB
                try:
                    # Odstránenie medzier a konverzia na bytes
                    geometry_str = geometry_str.replace(' ', '')
                    parcel_geometry = wkb_loads(binascii.unhexlify(geometry_str))
                except Exception as wkb_err:
                    # Ak WKB zlyhá, skúsiť WKT
                    try:
                        parcel_geometry = wkt.loads(geometry_str)
                    except Exception as wkt_err:
                        raise ValueError(f"Nepodarilo sa spracovať geometriu: WKB chyba: {wkb_err}, WKT chyba: {wkt_err}")
                
                # Vytvorenie GeoDataFrame so správnym súradnicovým systémom
                gdf = gpd.GeoDataFrame([{'name': selected_parcel, 'geometry': parcel_geometry}])
                gdf.set_crs(epsg=5514, inplace=True)  # Nastavenie pôvodného súradnicového systému
                
                # Transformácia do WGS84 (EPSG:4326) pre mapu
                gdf_wgs84 = gdf.to_crs(epsg=4326)
                
                # Výpočet stredu a bounds pre mapu
                bounds = gdf_wgs84.total_bounds
                center_lon = (bounds[0] + bounds[2]) / 2
                center_lat = (bounds[1] + bounds[3]) / 2
                
                # Vytvorenie mapy
                m = folium.Map(
                    location=[center_lat, center_lon],
                    zoom_start=14,
                    tiles='CartoDB positron'
                )
                
                # Pridanie parcely
                folium.GeoJson(
                    gdf_wgs84,
                    style_function=lambda x: {
                        'fillColor': '#3498db',
                        'color': '#000000',
                        'weight': 2,
                        'fillOpacity': 0.5
                    }
                ).add_to(m)
                
                # Zobrazenie mapy
                folium_static = m._repr_html_()
                st.components.v1.html(folium_static, height=500)
            
            except Exception as e:
                st.warning(f"Nepodarilo sa zobraziť mapu parcely: {e}")
                # Pridať debug informácie
                st.text(f"Pôvodná geometria: {geometry_str}")
                st.text(f"Typ geometrie: {type(geometry_str)}")
                st.text(f"Dĺžka geometrie: {len(geometry_str)}")
        else:
            st.warning("Pre túto parcelu nie sú dostupné geometrické údaje.")
    
    except Exception as e:
        st.error(f"Chyba pri spracovaní dát parcely: {e}")
    
    finally:
        # Zatvorenie databázového spojenia
        engine.dispose()
