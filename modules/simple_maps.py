import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium import plugins
import geopandas as gpd
from shapely import wkt
import io

def create_simple_map(df):
    """Vytvorí jednoduchú mapu s parcelami"""
    try:
        # Filtrovanie dát s geometriou
        df_with_geom = df.dropna(subset=['geometry'])
        
        if df_with_geom.empty:
            st.warning("⚠️ Žiadne geometrie na zobrazenie")
            return None
        
        # Skúsime parsovať geometrie
        valid_geometries = []
        for idx, row in df_with_geom.iterrows():
            try:
                if pd.notna(row['geometry']) and str(row['geometry']).startswith('POLYGON'):
                    geom = wkt.loads(row['geometry'])
                    if geom.is_valid:
                        valid_geometries.append({
                            'parcel_id': row['parcel_id'],
                            'name': row.get('name', f"Parcela {row['parcel_id']}"),
                            'yield_ha': row['yield_ha'],
                            'geometry': geom
                        })
            except Exception as e:
                continue
        
        if not valid_geometries:
            st.warning("⚠️ Žiadne validné geometrie na zobrazenie")
            return None
        
        # Vytvorenie GeoDataFrame
        gdf = gpd.GeoDataFrame(valid_geometries, geometry='geometry')
        gdf.set_crs(epsg=4326, inplace=True)
        
        # Výpočet bounds
        bounds = gdf.total_bounds
        center_lat = (bounds[1] + bounds[3]) / 2
        center_lon = (bounds[0] + bounds[2]) / 2
        
        # Vytvorenie mapy
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=10,
            tiles='CartoDB positron'
        )
        
        # Pridanie parciel
        for idx, row in gdf.iterrows():
            # Výpočet farby na základe výnosu
            yield_val = row['yield_ha']
            if yield_val > 8:
                color = 'green'
            elif yield_val > 6:
                color = 'yellow'
            elif yield_val > 4:
                color = 'orange'
            else:
                color = 'red'
            
            # Pridanie polygonu
            folium.Polygon(
                locations=[[lat, lon] for lon, lat in row['geometry'].exterior.coords],
                color='black',
                weight=2,
                fillColor=color,
                fillOpacity=0.7,
                popup=f"""
                <b>{row['name']}</b><br>
                Parcela ID: {row['parcel_id']}<br>
                Výnos: {yield_val:.2f} t/ha
                """
            ).add_to(m)
        
        return m
        
    except Exception as e:
        st.error(f"Chyba pri vytváraní mapy: {e}")
        return None

def create_plotly_map(df):
    """Vytvorí mapu pomocou Plotly"""
    try:
        # Filtrovanie dát s geometriou
        df_with_geom = df.dropna(subset=['geometry'])
        
        if df_with_geom.empty:
            return create_empty_figure("Žiadne geometrie na zobrazenie")
        
        # Skúsime parsovať geometrie
        valid_data = []
        for idx, row in df_with_geom.iterrows():
            try:
                if pd.notna(row['geometry']) and str(row['geometry']).startswith('POLYGON'):
                    geom = wkt.loads(row['geometry'])
                    if geom.is_valid:
                        # Výpočet centroidu
                        centroid = geom.centroid
                        valid_data.append({
                            'parcel_id': row['parcel_id'],
                            'name': row.get('name', f"Parcela {row['parcel_id']}"),
                            'yield_ha': row['yield_ha'],
                            'lat': centroid.y,
                            'lon': centroid.x
                        })
            except Exception as e:
                continue
        
        if not valid_data:
            return create_empty_figure("Žiadne validné geometrie na zobrazenie")
        
        # Vytvorenie DataFrame
        map_df = pd.DataFrame(valid_data)
        
        # Vytvorenie scatter mapy
        fig = px.scatter_mapbox(
            map_df,
            lat='lat',
            lon='lon',
            size='yield_ha',
            color='yield_ha',
            hover_name='name',
            hover_data={'parcel_id': True, 'yield_ha': ':.2f'},
            color_continuous_scale='RdYlGn',
            mapbox_style='open-street-map',
            zoom=10,
            height=600
        )
        
        fig.update_layout(
            title="Mapa parciel s výnosmi",
            margin=dict(l=0, r=0, t=30, b=0)
        )
        
        return fig
        
    except Exception as e:
        st.error(f"Chyba pri vytváraní Plotly mapy: {e}")
        return create_empty_figure(f"Chyba: {e}")

def create_empty_figure(message="Žiadne dáta na zobrazenie"):
    """Vytvorí prázdny graf"""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=16, color="gray")
    )
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=False, showticklabels=False),
        height=400
    )
    return fig

def show_maps(df):
    """Zobrazí mapy parciel"""
    st.header("🗺️ Mapy parciel")
    
    if df.empty:
        st.warning("⚠️ Žiadne dáta na zobrazenie")
        return
    
    # Kontrola geometrií
    geom_count = df['geometry'].notna().sum()
    st.info(f"📊 Nájdených {geom_count} geometrií z {len(df)} záznamov")
    
    # Zobrazenie vzorky geometrií
    if geom_count > 0:
        st.subheader("🔍 Vzorka geometrií")
        sample_geoms = df[df['geometry'].notna()].head(3)
        for idx, row in sample_geoms.iterrows():
            st.write(f"**Parcela {row['parcel_id']}:** {str(row['geometry'])[:100]}...")
    
    # Tab pre rôzne typy máp
    tab1, tab2 = st.tabs(["🗺️ Folium mapa", "📊 Plotly mapa"])
    
    with tab1:
        st.subheader("Interaktívna mapa (Folium)")
        folium_map = create_simple_map(df)
        if folium_map:
            # Zobrazenie mapy
            map_html = folium_map._repr_html_()
            st.components.v1.html(map_html, height=600)
        else:
            st.warning("Nepodarilo sa vytvoriť Folium mapu")
    
    with tab2:
        st.subheader("Scatter mapa (Plotly)")
        plotly_map = create_plotly_map(df)
        if plotly_map:
            st.plotly_chart(plotly_map, use_container_width=True)
        else:
            st.warning("Nepodarilo sa vytvoriť Plotly mapu")
    
    # Štatistiky
    st.subheader("📊 Štatistiky geometrií")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Celkový počet záznamov", len(df))
    
    with col2:
        st.metric("Záznamy s geometriou", geom_count)
    
    with col3:
        percentage = (geom_count / len(df) * 100) if len(df) > 0 else 0
        st.metric("Pokrytie geometriami", f"{percentage:.1f}%")
