import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import geopandas as gpd
from shapely import wkt

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
    """Porovnanie plodín na konkrétnej parcele"""
    parcel_data = df[df['name'].astype(str) == parcel_name].copy()
    
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
    """Vytvorenie profesionálnej mapy s vybranou parcelou pomocou geopandas a plotly"""
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
        
        # Vytvorenie profesionálnej mapy pomocou plotly
        fig = go.Figure()
        
        # Pridanie parcely ako polygon s profesionálnym vzhľadom
        fig.add_trace(go.Scattermapbox(
            lon=[],
            lat=[],
            mode='markers',
            marker=dict(size=0),
            showlegend=False,
            hoverinfo='skip'
        ))
        
        # Pridanie parcely ako polygon s farebným kódovaním podľa výnosov
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
            fig.add_trace(go.Scattermapbox(
                lon=[],
                lat=[],
                mode='markers',
                marker=dict(size=0),
                showlegend=False,
                hoverinfo='skip'
            ))
        
        # Nastavenie layoutu mapy
        fig.update_layout(
            mapbox=dict(
                style="carto-positron",  # Profesionálny štýl mapy
                center=dict(lat=center_lat, lon=center_lon),
                zoom=zoom_level,
                layers=[
                    {
                        "sourcetype": "geojson",
                        "source": gdf.__geo_interface__,
                        "type": "fill",
                        "color": parcel_color if 'parcel_color' in locals() else '#1f77b4',
                        "opacity": 0.7,
                        "filloutline": {
                            "color": "#000000",
                            "width": 2
                        }
                    }
                ]
            ),
            height=600,
            margin={"r": 0, "t": 0, "l": 0, "b": 0},
            showlegend=False
        )
        
        # Pridanie informačného boxu
        if not parcel_data.empty:
            # Výpočet metrík pre informačný box
            total_area = parcel_data['area'].sum()
            avg_yield = parcel_data['yield_ha'].mean()
            avg_percentage = parcel_data['yield_percentage'].mean()
            crop_count = parcel_data['crop'].nunique()
            year_range = f"{parcel_data['year'].min()} - {parcel_data['year'].max()}"
            
            # Pridanie anotácie s informáciami o parcele
            fig.add_annotation(
                x=0.02,
                y=0.98,
                xref="paper",
                yref="paper",
                text=f"<b>Parcela: {selected_parcel}</b><br>" +
                     f"Plocha: {total_area:.2f} ha<br>" +
                     f"Priemerný výnos: {avg_yield:.2f} t/ha<br>" +
                     f"Výnosnosť: {avg_percentage:.1f}%<br>" +
                     f"Počet plodín: {crop_count}<br>" +
                     f"Obdobie: {year_range}",
                showarrow=False,
                bgcolor="rgba(255, 255, 255, 0.9)",
                bordercolor="rgba(0, 0, 0, 0.5)",
                borderwidth=1,
                font=dict(size=12, color="black"),
                align="left"
            )
        
        return fig
        
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
        
        if max_range > 0.1:
            zoom_level = 12
        elif max_range > 0.01:
            zoom_level = 15
        else:
            zoom_level = 18
        
        # Vytvorenie mapy pomocou plotly s datovým vzhľadom
        fig = go.Figure()
        
        # Pridanie parcely ako polygon s datovým vzhľadom
        fig.add_trace(go.Scattermapbox(
            lon=[],
            lat=[],
            mode='markers',
            marker=dict(size=0),
            showlegend=False,
            hoverinfo='skip'
        ))
        
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
        
        # Nastavenie layoutu mapy s datovým vzhľadom
        fig.update_layout(
            mapbox=dict(
                style="carto-positron",  # Čistý, datový štýl bez satelitného pozadia
                center=dict(lat=center_lat, lon=center_lon),
                zoom=zoom_level,
                layers=[
                    {
                        "sourcetype": "geojson",
                        "source": gdf.__geo_interface__,
                        "type": "fill",
                        "color": parcel_color if 'parcel_color' in locals() else '#1f77b4',
                        "opacity": 0.8,
                        "filloutline": {
                            "color": "#000000",
                            "width": 3
                        }
                    }
                ]
            ),
            height=700,
            margin={"r": 0, "t": 0, "l": 0, "b": 0},
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        # Pridanie mriežky pre datový vzhľad
        # Vytvorenie mriežky okolo parcely
        grid_spacing = max_range / 10  # 10 riadkov/stĺpcov mriežky
        
        # Pridanie vertikálnych čiar mriežky
        for i in range(11):
            lon_pos = bounds[0] + i * grid_spacing
            fig.add_trace(go.Scattermapbox(
                lon=[lon_pos, lon_pos],
                lat=[bounds[1], bounds[3]],
                mode='lines',
                line=dict(color='rgba(128, 128, 128, 0.3)', width=1),
                showlegend=False,
                hoverinfo='skip'
            ))
        
        # Pridanie horizontálnych čiar mriežky
        for i in range(11):
            lat_pos = bounds[1] + i * grid_spacing
            fig.add_trace(go.Scattermapbox(
                lon=[bounds[0], bounds[2]],
                lat=[lat_pos, lat_pos],
                mode='lines',
                line=dict(color='rgba(128, 128, 128, 0.3)', width=1),
                showlegend=False,
                hoverinfo='skip'
            ))
        
        # Pridanie súradníc mriežky
        for i in range(11):
            for j in range(11):
                lon_pos = bounds[0] + i * grid_spacing
                lat_pos = bounds[1] + j * grid_spacing
                fig.add_trace(go.Scattermapbox(
                    lon=[lon_pos],
                    lat=[lat_pos],
                    mode='markers',
                    marker=dict(size=2, color='rgba(128, 128, 128, 0.5)'),
                    showlegend=False,
                    hoverinfo='skip'
                ))
        
        # Pridanie hlavného informačného boxu s datami
        if not parcel_data.empty:
            fig.add_annotation(
                x=0.02,
                y=0.98,
                xref="paper",
                yref="paper",
                text=f"<b>🏞️ {selected_parcel}</b><br>" +
                     f"<b>Výkonnosť:</b> {performance_level} ({performance_score})<br>" +
                     f"<b>Výnosnosť:</b> {avg_percentage:.1f}%<br>" +
                     f"<b>Priemerný výnos:</b> {avg_yield:.2f} t/ha<br>" +
                     f"<b>Celková plocha:</b> {total_area:.2f} ha<br>" +
                     f"<b>Počet plodín:</b> {crop_count}<br>" +
                     f"<b>Obdobie:</b> {year_range}",
                showarrow=False,
                bgcolor="rgba(255, 255, 255, 0.95)",
                bordercolor=parcel_color if 'parcel_color' in locals() else '#1f77b4',
                borderwidth=2,
                font=dict(size=13, color="black"),
                align="left",
                xanchor="left",
                yanchor="top"
            )
            
            # Pridanie štatistického boxu s detailnými metrikami
            fig.add_annotation(
                x=0.98,
                y=0.98,
                xref="paper",
                yref="paper",
                text=f"<b>📊 Štatistiky parcely:</b><br>" +
                     f"<b>Variabilita (CV):</b> {yield_cv:.1f}%<br>" +
                     f"<b>Najlepší rok:</b> {best_year['year']} ({best_year['crop']})<br>" +
                     f"<b>Najhorší rok:</b> {worst_year['year']} ({worst_year['crop']})<br>" +
                     f"<b>Rozsah výnosov:</b> {worst_year['yield_ha']:.2f} - {best_year['yield_ha']:.2f} t/ha<br>" +
                     f"<b>Počet záznamov:</b> {len(parcel_data)}",
                showarrow=False,
                bgcolor="rgba(255, 255, 255, 0.95)",
                bordercolor="rgba(0, 0, 0, 0.5)",
                borderwidth=1,
                font=dict(size=11, color="black"),
                align="right",
                xanchor="right",
                yanchor="top"
            )
            
            # Pridanie legendy pre farebné kódovanie
            fig.add_annotation(
                x=0.02,
                y=0.02,
                xref="paper",
                yref="paper",
                text="<b>🎨 Farebné kódovanie výnosnosti:</b><br>" +
                     "🟢 ≥130% - Výborná (A+)<br>" +
                     "🟢 ≥115% - Veľmi dobrá (A)<br>" +
                     "🟢 ≥100% - Dobrá (B+)<br>" +
                     "🟡 ≥85% - Priemerná (B)<br>" +
                     "🟠 ≥70% - Podpriemerná (C)<br>" +
                     "🔴 <70% - Slabá (D)",
                showarrow=False,
                bgcolor="rgba(255, 255, 255, 0.9)",
                bordercolor="rgba(0, 0, 0, 0.3)",
                borderwidth=1,
                font=dict(size=11, color="black"),
                align="left",
                xanchor="left",
                yanchor="bottom"
            )
            
            # Pridanie súradníc parcely
            fig.add_annotation(
                x=0.98,
                y=0.02,
                xref="paper",
                yref="paper",
                text=f"<b>📍 Súradnice parcely:</b><br>" +
                     f"Stred: {center_lat:.6f}°N, {center_lon:.6f}°E<br>" +
                     f"Rozmer: {lon_range:.6f}° × {lat_range:.6f}°<br>" +
                     f"Zoom: {zoom_level}",
                showarrow=False,
                bgcolor="rgba(255, 255, 255, 0.9)",
                bordercolor="rgba(0, 0, 0, 0.3)",
                borderwidth=1,
                font=dict(size=11, color="black"),
                align="right",
                xanchor="right",
                yanchor="bottom"
            )
        
        return fig
        
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
        
        # Agregácia dát podľa parcele s detailnými metrikami
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
        
        # Vytvorenie GeoDataFrame pre všetky parcele
        gdf = gpd.GeoDataFrame(parcel_stats)
        gdf['geometry'] = all_geometries[:len(parcel_stats)]
        gdf.set_crs(epsg=4326, inplace=True)
        
        # Výpočet bounds
        bounds = gdf.total_bounds
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        # Vytvorenie mapy s datovým vzhľadom
        fig = go.Figure()
        
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
            fig.add_trace(go.Scattermapbox(
                lon=[],
                lat=[],
                mode='markers',
                marker=dict(size=0),
                showlegend=False,
                hoverinfo='skip'
            ))
        
        # Nastavenie layoutu mapy s datovým vzhľadom
        fig.update_layout(
            mapbox=dict(
                style="carto-positron",  # Čistý, datový štýl bez satelitného pozadia
                center=dict(lat=center_lat, lon=center_lon),
                zoom=10,
                layers=[
                    {
                        "sourcetype": "geojson",
                        "source": gdf.__geo_interface__,
                        "type": "fill",
                        "color": gdf['avg_yield_percentage'].apply(lambda x: 
                            '#006400' if x >= 130 else
                            '#228B22' if x >= 115 else
                            '#32CD32' if x >= 100 else
                            '#FFD700' if x >= 85 else
                            '#FF8C00' if x >= 70 else '#DC143C'
                        ).tolist(),
                        "opacity": 0.7,
                        "filloutline": {
                            "color": "#000000",
                            "width": 1
                        }
                    }
                ]
            ),
            height=700,
            margin={"r": 0, "t": 0, "l": 0, "b": 0},
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        # Pridanie mriežky pre datový vzhľad
        # Výpočet rozmerov oblasti
        lon_range = bounds[2] - bounds[0]
        lat_range = bounds[3] - bounds[1]
        grid_spacing = max(lon_range, lat_range) / 20  # 20 riadkov/stĺpcov mriežky
        
        # Pridanie vertikálnych čiar mriežky
        for i in range(21):
            lon_pos = bounds[0] + i * grid_spacing
            fig.add_trace(go.Scattermapbox(
                lon=[lon_pos, lon_pos],
                lat=[bounds[1], bounds[3]],
                mode='lines',
                line=dict(color='rgba(128, 128, 128, 0.2)', width=0.5),
                showlegend=False,
                hoverinfo='skip'
            ))
        
        # Pridanie horizontálnych čiar mriežky
        for i in range(21):
            lat_pos = bounds[1] + i * grid_spacing
            fig.add_trace(go.Scattermapbox(
                lon=[bounds[0], bounds[2]],
                lat=[lat_pos, lat_pos],
                mode='lines',
                line=dict(color='rgba(128, 128, 128, 0.2)', width=0.5),
                showlegend=False,
                hoverinfo='skip'
            ))
        
        # Pridanie súradníc mriežky (menej husté pre prehľadnosť)
        for i in range(0, 21, 2):  # Každý druhý bod
            for j in range(0, 21, 2):
                lon_pos = bounds[0] + i * grid_spacing
                lat_pos = bounds[1] + j * grid_spacing
                fig.add_trace(go.Scattermapbox(
                    lon=[lon_pos],
                    lat=[lat_pos],
                    mode='markers',
                    marker=dict(size=1, color='rgba(128, 128, 128, 0.3)'),
                    showlegend=False,
                    hoverinfo='skip'
                ))
        
        # Pridanie hlavnej legendy s farebným kódovaním
        fig.add_annotation(
            x=0.98,
            y=0.98,
            xref="paper",
            yref="paper",
            text="<b>🎨 Farebné kódovanie parciel:</b><br>" +
                 "🟢 ≥130% - Výborná (A+)<br>" +
                 "🟢 ≥115% - Veľmi dobrá (A)<br>" +
                 "🟢 ≥100% - Dobrá (B+)<br>" +
                 "🟡 ≥85% - Priemerná (B)<br>" +
                 "🟠 ≥70% - Podpriemerná (C)<br>" +
                 "🔴 <70% - Slabá (D)",
            showarrow=False,
            bgcolor="rgba(255, 255, 255, 0.95)",
            bordercolor="rgba(0, 0, 0, 0.5)",
            borderwidth=2,
            font=dict(size=12, color="black"),
            align="right",
            xanchor="right",
            yanchor="top"
        )
        
        # Pridanie detailných štatistík všetkých parciel
        total_parcels = len(parcel_stats)
        avg_performance = parcel_stats['avg_yield_percentage'].mean()
        best_parcel = parcel_stats.loc[parcel_stats['avg_yield_percentage'].idxmax()]
        worst_parcel = parcel_stats.loc[parcel_stats['avg_yield_percentage'].idxmin()]
        
        fig.add_annotation(
            x=0.02,
            y=0.98,
            xref="paper",
            yref="paper",
            text=f"<b>📊 Prehľad všetkých parciel:</b><br>" +
                 f"Celkový počet: {total_parcels}<br>" +
                 f"Priemerná výnosnosť: {avg_performance:.1f}%<br>" +
                 f"Rozsah rokov: {parcel_stats['year_min'].min()} - {parcel_stats['year_max'].max()}<br>" +
                 f"Celková plocha: {parcel_stats['total_area'].sum():.1f} ha",
            showarrow=False,
            bgcolor="rgba(255, 255, 255, 0.95)",
            bordercolor="rgba(0, 0, 0, 0.5)",
            borderwidth=2,
            font=dict(size=12, color="black"),
            align="left",
            xanchor="left",
            yanchor="top"
        )
        
        # Pridanie informácií o najlepšej a najhoršej parcele
        fig.add_annotation(
            x=0.02,
            y=0.02,
            xref="paper",
            yref="paper",
            text=f"<b>🏆 Najlepšia parcela:</b> {best_parcel['name']}<br>" +
                 f"Výnosnosť: {best_parcel['avg_yield_percentage']:.1f}%<br>" +
                 f"<b>⚠️ Najhoršia parcela:</b> {worst_parcel['name']}<br>" +
                 f"Výnosnosť: {worst_parcel['avg_yield_percentage']:.1f}%",
            showarrow=False,
            bgcolor="rgba(255, 255, 255, 0.9)",
            bordercolor="rgba(0, 0, 0, 0.3)",
            borderwidth=1,
            font=dict(size=11, color="black"),
            align="left",
            xanchor="left",
            yanchor="bottom"
        )
        
        # Pridanie súradníc oblasti
        fig.add_annotation(
            x=0.98,
            y=0.02,
            xref="paper",
            yref="paper",
            text=f"<b>📍 Súradnice oblasti:</b><br>" +
                 f"Stred: {center_lat:.6f}°N, {center_lon:.6f}°E<br>" +
                 f"Rozmer: {lon_range:.6f}° × {lat_range:.6f}°<br>" +
                 f"Zoom: 10",
            showarrow=False,
            bgcolor="rgba(255, 255, 255, 0.9)",
            bordercolor="rgba(0, 0, 0, 0.3)",
            borderwidth=1,
            font=dict(size=11, color="black"),
            align="right",
            xanchor="right",
            yanchor="bottom"
        )
        
        return fig
        
    except Exception as e:
        st.error(f"Chyba pri vytváraní datovej mapy všetkých parciel: {e}")
        return None

def show_parcel_statistics(df):
    """Zobrazenie štatistík na úrovni parcely"""
    st.header("🏞️ Štatistiky na úrovni parcely")
    
    # Sidebar pre výber parcely
    st.sidebar.header("Výber parcely")
    
    # Získanie zoznamu parciel
    # Vyčistenie a konverzia na string pre správne triedenie
    available_parcels = sorted([str(parcel) for parcel in df['name'].unique() if pd.notna(parcel)])
    
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
    # Konverzia na string pre správne porovnanie
    parcel_data = df[df['name'].astype(str) == selected_parcel].copy()
    
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
    
    # Mapa všetkých parciel
    st.subheader("🗺️ Datová mapa všetkých parciel")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info("Táto datová mapa zobrazuje všetky parcele s mriežkou, farebným kódovaním podľa výnosnosti a detailnými štatistikami. Zelené parcele majú vyššiu výnosnosť, červené nižšiu.")
    
    with col2:
        if st.button("📊 Exportovať mapu", key="export_all_parcels_map"):
            st.info("Funkcia exportu mapy bude implementovaná v ďalšej verzii.")
    
    with st.spinner("Generujem datovú mapu všetkých parciel s mriežkou..."):
        all_parcels_map = create_all_parcels_map(df)
        if all_parcels_map:
            st.plotly_chart(all_parcels_map, use_container_width=True)
            
            # Štatistiky parciel
            parcels_with_geometry = df[df['geometry'].notna()].copy()
            if not parcels_with_geometry.empty:
                parcel_performance = parcels_with_geometry.groupby('name')['yield_percentage'].mean()
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Celkový počet parciel", len(parcel_performance))
                with col2:
                    st.metric("Priemerná výnosnosť", f"{parcel_performance.mean():.1f}%")
                with col3:
                    st.metric("Najlepšia parcela", f"{parcel_performance.max():.1f}%")
                with col4:
                    st.metric("Najhoršia parcela", f"{parcel_performance.min():.1f}%")
        else:
            st.warning("Nepodarilo sa vytvoriť prehľadovú mapu parciel.")
    
    # Mapa parcely
    st.subheader("🗺️ Datová mapa vybranej parcely")
    
    # Výber typu mapy
    map_type = st.radio(
        "Vyberte typ mapy:",
        ["Datová mapa s mriežkou (odporúčané)", "Základná mapa"],
        horizontal=True,
        key="map_type_selector"
    )
    
    # Informácie o vybranej parcele
    if not parcel_data.empty:
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            st.info(f"**Parcela:** {selected_parcel}")
        with col2:
            st.info(f"**Výnosnosť:** {parcel_data['yield_percentage'].mean():.1f}%")
        with col3:
            if st.button("📊 Exportovať mapu", key="export_parcel_map"):
                st.info("Funkcia exportu mapy bude implementovaná v ďalšej verzii.")
    
    with st.spinner("Generujem datovú mapu parcely s mriežkou..."):
        if map_type == "Datová mapa s mriežkou (odporúčané)":
            map_fig = create_enhanced_parcel_map(df, selected_parcel)
        else:
            map_fig = create_parcel_map(df, selected_parcel)
            
        if map_fig:
            st.plotly_chart(map_fig, use_container_width=True)
            
            # Pridanie informácií o mape
            if map_type == "Datová mapa s mriežkou (odporúčané)":
                st.success("""
                **🎯 Datová mapa s mriežkou obsahuje:**
                - Farebné kódovanie podľa výnosnosti parcely s hodnotením A+ až D
                - Detailné informácie o parcele a štatistiky
                - Mriežku pre presné určenie polohy
                - Súradnice parcely a rozmerov
                - Variabilitu výnosov a trendové údaje
                - Čistý, datový vzhľad bez satelitného pozadia
                """)
            else:
                st.info("Základná mapa zobrazuje parcela s minimálnymi informáciami.")
        else:
            st.warning("Nepodarilo sa vytvoriť mapu parcely. Skontrolujte, či sú dostupné geometrické dáta.")
    
    # Základné metriky parcely
    st.subheader("📊 Základné metriky parcely")
    
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
