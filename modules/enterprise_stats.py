import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import io
import geopandas as gpd
from shapely import wkt



def create_parcel_performance_map(df):
    """Vytvorenie datovej a faktografickej mapy s výkonnosťou parciel s mriežkou a bez satelitného pozadia"""
    try:
        import folium
        from folium import plugins
        
        # Agregácia dát podľa parcele s detailnými metrikami
        parcel_stats = df.groupby(['name', 'agev_parcel_id', 'area', 'geometry']).agg({
            'yield_percentage': ['mean', 'std', 'min', 'max'],
            'yield_ha': ['mean', 'std', 'min', 'max'],
            'crop': ['count', 'nunique'],
            'year': ['min', 'max', 'nunique']
        }).reset_index()
        
        # Flatten column names
        parcel_stats.columns = [
            'name', 'agev_parcel_id', 'area', 'geometry',
            'avg_yield_percentage', 'std_yield_percentage', 'min_yield_percentage', 'max_yield_percentage',
            'avg_yield_ha', 'std_yield_ha', 'min_yield_ha', 'max_yield_ha',
            'crop_count', 'crop_unique', 'year_min', 'year_max', 'year_count'
        ]
        
        # Filtrovanie parciel s geometriou
        parcel_stats = parcel_stats.dropna(subset=['geometry'])
        
        if parcel_stats.empty:
            return None
        
        # Konverzia na GeoDataFrame
        parcel_stats['geometry'] = parcel_stats['geometry'].apply(wkt.loads)
        gdf = gpd.GeoDataFrame(parcel_stats, geometry='geometry')
        
        # Nastavenie CRS na WGS84
        gdf.set_crs(epsg=4326, inplace=True)
        
        # Výpočet bounds pre správny zoom
        bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        # Vytvorenie mapy pomocou folium s datovým vzhľadom
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=10,
            tiles='CartoDB positron',  # Čistý, datový štýl bez satelitného pozadia
            control_scale=True
        )
        
        # Dynamické nastavenie zoom levelu na základe veľkosti oblasti
        lon_range = bounds[2] - bounds[0]
        lat_range = bounds[3] - bounds[1]
        max_range = max(lon_range, lat_range)
        
        # Výpočet optimálneho zoom levelu - ešte bližšie
        if max_range > 5:  # Veľká oblasť (celé Slovensko)
            zoom_level = 10  # Zvýšené z 8 na 10
        elif max_range > 1:  # Stredná oblasť (kraj)
            zoom_level = 12  # Zvýšené z 10 na 12
        elif max_range > 0.1:  # Malá oblasť (okres)
            zoom_level = 14  # Zvýšené z 12 na 14
        else:  # Veľmi malá oblasť (obec)
            zoom_level = 16  # Zvýšené z 14 na 16
        
        # Nastavenie zoom levelu a bounds s dodatočným priblížením
        m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
        # Dodatočné priblíženie o 1-2 úrovne
        m.zoom_start = zoom_level + 1
        
        # Pridanie mriežky pre datový vzhľad
        grid_spacing = max_range / 20  # 20 riadkov/stĺpcov mriežky
        
        # Pridanie vertikálnych čiar mriežky
        for i in range(21):
            lon_pos = bounds[0] + i * grid_spacing
            folium.PolyLine(
                locations=[[bounds[1], lon_pos], [bounds[3], lon_pos]],
                color='rgba(128, 128, 128, 0.3)',
                weight=0.5,
                opacity=0.3
            ).add_to(m)
        
        # Pridanie horizontálnych čiar mriežky
        for i in range(21):
            lat_pos = bounds[1] + i * grid_spacing
            folium.PolyLine(
                locations=[[lat_pos, bounds[0]], [lat_pos, bounds[2]]],
                color='rgba(128, 128, 128, 0.3)',
                weight=0.5,
                opacity=0.3
            ).add_to(m)
        
        # Pridanie parciel s kontinuálnym farebným kódovaním
        # Výpočet min a max hodnôt pre farebné škálovanie
        min_yield = gdf['avg_yield_percentage'].min()
        max_yield = gdf['avg_yield_percentage'].max()
        
        # Funkcia pre výpočet farby na základe výnosnosti - jemnejšie, menej kriklavé farby
        def get_color(yield_percentage):
            if pd.isna(yield_percentage):
                return '#808080'  # Sivá pre chýbajúce hodnoty
            
            # Normalizácia na rozsah 0-1
            normalized = (yield_percentage - min_yield) / (max_yield - min_yield)
            
            # Jemnejšia farebná škála od červenej (nízka) cez oranžovú a žltú po zelenú (vysoká)
            if normalized <= 0.33:
                # Od červenej po oranžovú (0.0 - 0.33) - jemnejšie červené
                r = 220
                g = int(100 + 80 * (normalized * 3))
                b = int(50 + 100 * (normalized * 3))
            elif normalized <= 0.66:
                # Od oranžovej po žltú (0.33 - 0.66) - jemnejšie oranžové a žlté
                r = int(220 - 50 * ((normalized - 0.33) * 3))
                g = int(180 + 75 * ((normalized - 0.33) * 3))
                b = int(150 - 100 * ((normalized - 0.33) * 3))
            else:
                # Od žltej po zelenú (0.66 - 1.0) - jemnejšie žlté a zelené
                r = int(170 - 120 * ((normalized - 0.66) * 3))
                g = int(255 - 50 * ((normalized - 0.66) * 3))
                b = int(50 + 100 * ((normalized - 0.66) * 3))
            
            return f'#{r:02x}{g:02x}{b:02x}'
        
        # Pridanie všetkých parciel s kontinuálnymi farbami
        folium.GeoJson(
            gdf,
            style_function=lambda x: {
                'fillColor': get_color(x['properties']['avg_yield_percentage']),
                'color': '#000000',
                'weight': 1,
                'fillOpacity': 0.8
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['name', 'avg_yield_percentage', 'area'],
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
        

        
        # Pridanie fullscreen tlačidla
        plugins.Fullscreen().add_to(m)
        
        # Pridanie minimapy
        minimap = plugins.MiniMap(tile_layer='CartoDB positron', zoom_level_offset=-5)
        m.add_child(minimap)
        
        return m
        
    except Exception as e:
        st.error(f"Chyba pri vytváraní datovej mapy: {e}")
        return None

def show_enterprise_statistics(df, selected_crop):
    """Zobrazenie štatistik na úrovni podniku"""
    # Analýza výkonnosti parciel
    st.header("🏆 Výkonnosť parciel")
    
    # Top parcele podľa výnosnosti
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Top 10 parciel podľa výnosnosti")
        top_parcels = df.groupby('name')['yield_percentage'].mean().sort_values(ascending=False).head(10)
        
        # Vytvorenie atraktívneho grafu s gradientom farieb a detailnými tooltipmi
        # Zoradenie parciel od najvyššieho percenta (hore) po najnižšie (dole)
        
        # Príprava detailných tooltipov pre každú parcelu
        tooltip_data = []
        for parcel_name in top_parcels.index:
            parcel_data = df[df['name'] == parcel_name]
            yearly_percentages = parcel_data.groupby('year')['yield_percentage'].mean().round(1)
            yearly_info = []
            for year, percentage in yearly_percentages.items():
                yearly_info.append(f"{year}: {percentage}%")
            yearly_text = "<br>".join(yearly_info)
            tooltip_data.append(yearly_text)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=top_parcels.values,
            y=top_parcels.index,
            orientation='h',
            marker=dict(
                color=top_parcels.values,
                colorscale='Greens',
                showscale=True,
                colorbar=dict(title="Výnosnosť (%)")
            ),
            text=[f"{val:.1f}%" for val in top_parcels.values],
            textposition='auto',
            hovertemplate="<b>%{y}</b><br>" +
                         "Celková výnosnosť: %{x:.1f}%<br>" +
                         "<b>Výnosnosť po rokoch:</b><br>" +
                         "%{customdata}<br>" +
                         "<extra></extra>",
            customdata=tooltip_data
        ))
        
        # Nastavenie y-axis v opačnom poradí - najvyššie percento bude hore
        fig.update_layout(
            title="Top parcele podľa priemernej výnosnosti (%)",
            height=400,
            xaxis_title="Výnosnosť (%)",
            yaxis_title="Parcela",
            showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(
                autorange='reversed'  # Obráti poradie - najvyššie percento bude hore
            )
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("📉 Najhoršie parcele")
        worst_parcels = df.groupby('name')['yield_percentage'].mean().sort_values().head(10)
        
        # Vytvorenie atraktívneho grafu s gradientom farieb a detailnými tooltipmi
        # Zoradenie parciel od najvyššieho percenta (hore) po najnižšie (dole)
        # Najnižšie percento bude na spodku grafu s najsýtejšou červenou
        
        # Príprava detailných tooltipov pre každú parcelu
        tooltip_data_worst = []
        for parcel_name in worst_parcels.index:
            parcel_data = df[df['name'] == parcel_name]
            yearly_percentages = parcel_data.groupby('year')['yield_percentage'].mean().round(1)
            yearly_info = []
            for year, percentage in yearly_percentages.items():
                yearly_info.append(f"{year}: {percentage}%")
            yearly_text = "<br>".join(yearly_info)
            tooltip_data_worst.append(yearly_text)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=worst_parcels.values,
            y=worst_parcels.index,
            orientation='h',
            marker=dict(
                color=worst_parcels.values,
                colorscale='Reds_r',  # Obrátená červená škála - najnižšie percento = najsýtejšia červená
                showscale=True,
                colorbar=dict(title="Výnosnosť (%)")
            ),
            text=[f"{val:.1f}%" for val in worst_parcels.values],
            textposition='auto',
            hovertemplate="<b>%{y}</b><br>" +
                         "Celková výnosnosť: %{x:.1f}%<br>" +
                         "<b>Výnosnosť po rokoch:</b><br>" +
                         "%{customdata}<br>" +
                         "<extra></extra>",
            customdata=tooltip_data_worst
        ))
        
        # Nastavenie y-axis - najvyššie percento bude hore, najnižšie dole
        fig.update_layout(
            title="Najhoršie parcele podľa priemernej výnosnosti (%)",
            height=400,
            xaxis_title="Výnosnosť (%)",
            yaxis_title="Parcela",
            showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
            # Odstránené autorange='reversed' - teraz sa zobrazuje v normálnom poradí
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Kompaktné vysvetlenie metodiky priamo pod grafmi
    st.markdown("---")
    st.markdown("**📊 Metodika:** Percentá = (Skutočný výnos / Priemerný výnos) × 100. Priemerný výnos sa počíta ako aritmetický priemer všetkých parciel pre danú plodinu a rok. 100% = priemer, >100% = nadpriemer, <100% = podpriemer.")
    
    # Kategorizácia parciel do piatich kategórií
    st.header("🏷️ Kategorizácia parciel podľa výkonnosti")
    
    # Výpočet kategórií pre všetky parcele
    parcel_performance = df.groupby('name')['yield_percentage'].mean().sort_values(ascending=False)
    
    # Definovanie kategórií
    total_parcels = len(parcel_performance)
    category_1_count = int(total_parcels * 0.2)  # Top 20%
    category_2_count = int(total_parcels * 0.2)  # Next 20%
    category_3_count = int(total_parcels * 0.2)  # Middle 20%
    category_4_count = int(total_parcels * 0.2)  # Next 20%
    category_5_count = total_parcels - category_1_count - category_2_count - category_3_count - category_4_count  # Remaining
    
    # Rozdelenie parciel do kategórií
    category_1 = parcel_performance.head(category_1_count)
    category_2 = parcel_performance.iloc[category_1_count:category_1_count + category_2_count]
    category_3 = parcel_performance.iloc[category_1_count + category_2_count:category_1_count + category_2_count + category_3_count]
    category_4 = parcel_performance.iloc[category_1_count + category_2_count + category_3_count:category_1_count + category_2_count + category_3_count + category_4_count]
    category_5 = parcel_performance.tail(category_5_count)
    
    # Vytvorenie súhrnnej tabuľky kategórií
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Tabuľka s kategóriami
        category_summary = pd.DataFrame({
            'Kategória': ['A - Výborné', 'B - Nadpriemerné', 'C - Priemerné', 'D - Podpriemerné', 'E - Slabé'],
            'Počet parciel': [len(category_1), len(category_2), len(category_3), len(category_4), len(category_5)],
            'Percento z celku': [
                f"{len(category_1)/total_parcels*100:.1f}%",
                f"{len(category_2)/total_parcels*100:.1f}%",
                f"{len(category_3)/total_parcels*100:.1f}%",
                f"{len(category_4)/total_parcels*100:.1f}%",
                f"{len(category_5)/total_parcels*100:.1f}%"
            ],
            'Priemerná výnosnosť': [
                f"{category_1.mean():.1f}%",
                f"{category_2.mean():.1f}%",
                f"{category_3.mean():.1f}%",
                f"{category_4.mean():.1f}%",
                f"{category_5.mean():.1f}%"
            ],
            'Rozsah výnosnosti': [
                f"{category_1.min():.1f}% - {category_1.max():.1f}%",
                f"{category_2.min():.1f}% - {category_2.max():.1f}%",
                f"{category_3.min():.1f}% - {category_3.max():.1f}%",
                f"{category_4.min():.1f}% - {category_4.max():.1f}%",
                f"{category_5.min():.1f}% - {category_5.max():.1f}%"
            ]
        })
        
        st.dataframe(category_summary, use_container_width=True, hide_index=True)
    
    with col2:
        # Pie chart s kategóriami
        fig = px.pie(
            values=[len(category_1), len(category_2), len(category_3), len(category_4), len(category_5)],
            names=['A', 'B', 'C', 'D', 'E'],
            title="Rozdelenie parciel do kategórií",
            color_discrete_map={
                'A': '#2E8B57',  # Sea Green
                'B': '#32CD32',  # Lime Green
                'C': '#FFD700',  # Gold
                'D': '#FF8C00',  # Dark Orange
                'E': '#DC143C'   # Crimson
            }
        )
        fig.update_layout(height=300, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)
    
    # Detailné zobrazenie parciel v každej kategórii
    st.subheader("📋 Detailné zobrazenie kategórií")
    
    # Vytvorenie expanderov pre každú kategóriu
    with st.expander("🏆 Kategória A - Výborné parcele", expanded=False):
        st.markdown("**Kritéria:** Top 20% parciel s najvyššou výnosnosťou")
        st.markdown(f"**Počet parciel:** {len(category_1)} ({len(category_1)/total_parcels*100:.1f}%)")
        st.markdown(f"**Priemerná výnosnosť:** {category_1.mean():.1f}%")
        
        # Tabuľka s detailmi
        category_1_details = df[df['name'].isin(category_1.index)].groupby('name').agg({
            'yield_percentage': ['mean', 'std', 'min', 'max'],
            'area': 'first',
            'crop': 'nunique',
            'year': 'nunique'
        }).round(2)
        category_1_details.columns = ['Priemerná výnosnosť (%)', 'Smerodajná odchýlka', 'Minimum', 'Maximum', 'Plocha (ha)', 'Počet plodín', 'Počet rokov']
        category_1_details = category_1_details.sort_values('Priemerná výnosnosť (%)', ascending=False)
        st.dataframe(category_1_details, use_container_width=True)
    
    with st.expander("🥈 Kategória B - Nadpriemerné parcele", expanded=False):
        st.markdown("**Kritéria:** Ďalších 20% parciel s nadpriemernou výnosnosťou")
        st.markdown(f"**Počet parciel:** {len(category_2)} ({len(category_2)/total_parcels*100:.1f}%)")
        st.markdown(f"**Priemerná výnosnosť:** {category_2.mean():.1f}%")
        
        category_2_details = df[df['name'].isin(category_2.index)].groupby('name').agg({
            'yield_percentage': ['mean', 'std', 'min', 'max'],
            'area': 'first',
            'crop': 'nunique',
            'year': 'nunique'
        }).round(2)
        category_2_details.columns = ['Priemerná výnosnosť (%)', 'Smerodajná odchýlka', 'Minimum', 'Maximum', 'Plocha (ha)', 'Počet plodín', 'Počet rokov']
        category_2_details = category_2_details.sort_values('Priemerná výnosnosť (%)', ascending=False)
        st.dataframe(category_2_details, use_container_width=True)
    
    with st.expander("🥉 Kategória C - Priemerné parcele", expanded=False):
        st.markdown("**Kritéria:** Stredných 20% parciel s priemernou výnosnosťou")
        st.markdown(f"**Počet parciel:** {len(category_3)} ({len(category_3)/total_parcels*100:.1f}%)")
        st.markdown(f"**Priemerná výnosnosť:** {category_3.mean():.1f}%")
        
        category_3_details = df[df['name'].isin(category_3.index)].groupby('name').agg({
            'yield_percentage': ['mean', 'std', 'min', 'max'],
            'area': 'first',
            'crop': 'nunique',
            'year': 'nunique'
        }).round(2)
        category_3_details.columns = ['Priemerná výnosnosť (%)', 'Smerodajná odchýlka', 'Minimum', 'Maximum', 'Plocha (ha)', 'Počet plodín', 'Počet rokov']
        category_3_details = category_3_details.sort_values('Priemerná výnosnosť (%)', ascending=False)
        st.dataframe(category_3_details, use_container_width=True)
    
    with st.expander("⚠️ Kategória D - Podpriemerné parcele", expanded=False):
        st.markdown("**Kritéria:** Ďalších 20% parciel s podpriemernou výnosnosťou")
        st.markdown(f"**Počet parciel:** {len(category_4)} ({len(category_4)/total_parcels*100:.1f}%)")
        st.markdown(f"**Priemerná výnosnosť:** {category_4.mean():.1f}%")
        
        category_4_details = df[df['name'].isin(category_4.index)].groupby('name').agg({
            'yield_percentage': ['mean', 'std', 'min', 'max'],
            'area': 'first',
            'crop': 'nunique',
            'year': 'nunique'
        }).round(2)
        category_4_details.columns = ['Priemerná výnosnosť (%)', 'Smerodajná odchýlka', 'Minimum', 'Maximum', 'Plocha (ha)', 'Počet plodín', 'Počet rokov']
        category_4_details = category_4_details.sort_values('Priemerná výnosnosť (%)', ascending=False)
        st.dataframe(category_4_details, use_container_width=True)
    
    with st.expander("🚨 Kategória E - Slabé parcele", expanded=False):
        st.markdown("**Kritéria:** Posledných 20% parciel s najnižšou výnosnosťou")
        st.markdown(f"**Počet parciel:** {len(category_5)} ({len(category_5)/total_parcels*100:.1f}%)")
        st.markdown(f"**Priemerná výnosnosť:** {category_5.mean():.1f}%")
        
        category_5_details = df[df['name'].isin(category_5.index)].groupby('name').agg({
            'yield_percentage': ['mean', 'std', 'min', 'max'],
            'area': 'first',
            'crop': 'nunique',
            'year': 'nunique'
        }).round(2)
        category_5_details.columns = ['Priemerná výnosnosť (%)', 'Smerodajná odchýlka', 'Minimum', 'Maximum', 'Plocha (ha)', 'Počet plodín', 'Počet rokov']
        category_5_details = category_5_details.sort_values('Priemerná výnosnosť (%)', ascending=False)
        st.dataframe(category_5_details, use_container_width=True)
    
    # Vysvetlenie kategorizácie
    st.markdown("---")
    st.markdown("""
    **📊 Vysvetlenie kategorizácie:**
    
    - **Kategória A (Výborné):** Top 20% parciel s najvyššou výnosnosťou - ideálne pre produkciu semen a maximálne výnosy
    - **Kategória B (Nadpriemerné):** Ďalších 20% parciel s nadpriemernou výnosnosťou - vhodné pre komerčnú produkciu
    - **Kategória C (Priemerné):** Stredných 20% parciel s priemernou výnosnosťou - štandardná produkcia
    - **Kategória D (Podpriemerné):** Ďalších 20% parciel s podpriemernou výnosnosťou - potrebujú zlepšenie
    - **Kategória E (Slabé):** Posledných 20% parciel s najnižšou výnosnosťou - kritické pre optimalizáciu
    
    **🎯 Použitie:** Kategorizácia pomáha identifikovať parcele pre rôzne účely (semená, komerčná produkcia, optimalizácia) a plánovať investície do zlepšenia.
    """)
    
    # Mapa parciel - datová mapa s mriežkou
    st.header("🗺️ Datová mapa parciel")
    
    col1, col2 = st.columns([3, 1])
    with col1:
                    st.info("Táto datová mapa zobrazuje všetky parcele s mriežkou, jemným farebným kódovaním podľa výnosnosti a detailnými štatistikami. Každá parcela má unikátnu jemnú farbu od červenej (nízka) cez oranžovú a žltú po zelenú (vysoká výnosnosť).")
    
    with col2:
        if st.button("📊 Exportovať mapu", key="export_enterprise_map"):
            st.info("Funkcia exportu mapy bude implementovaná v ďalšej verzii.")
    
    with st.spinner("Generujem datovú mapu parciel s mriežkou..."):
        map_fig = create_parcel_performance_map(df)
        if map_fig:
            # Pre folium mapu používame st.components.html
            folium_static = map_fig._repr_html_()
            st.components.v1.html(folium_static, height=700)
            

        else:
            st.warning("Nepodarilo sa vytvoriť datovú mapu. Skontrolujte geometrické dáta.")
    
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
