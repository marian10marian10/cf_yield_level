import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import st_folium
import warnings
import io
import re
from shapely import wkt
from shapely.geometry import Point
import geopandas as gpd
warnings.filterwarnings('ignore')

# Konfigurácia stránky
st.set_page_config(
    page_title="Analýza výnosov DPB",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS pre lepší vzhľad
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .crop-selector {
        background-color: #e8f4fd;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    """Načítanie dát z CSV súboru"""
    try:
        # Načítanie CSV súboru
        df = pd.read_csv('yield_data.csv', encoding='utf-8')
        
        # Konverzia dátových typov
        df['year'] = pd.to_numeric(df['year'], errors='coerce')
        df['yield_ha'] = pd.to_numeric(df['yield_ha'], errors='coerce')
        df['area'] = pd.to_numeric(df['area'], errors='coerce')
        
        # Filtrovanie len platných výnosov
        df = df[df['yield_ha'] > 0]
        
        return df
    except Exception as e:
        st.error(f"Chyba pri načítaní dát: {e}")
        return None

def parse_geometry(geometry_str):
    """Parsovanie geometry string na súradnice"""
    try:
        if pd.isna(geometry_str) or geometry_str == '':
            return None, None
        
        # Hľadanie súradníc v MULTIPOLYGON string
        # Extrahujeme prvé súradnice pre zjednodušenie
        coords_match = re.search(r'\(\(([^)]+)\)', str(geometry_str))
        if coords_match:
            coords_str = coords_match.group(1)
            # Zoberieme prvú dvojicu súradníc
            first_coord = coords_str.split(',')[0].strip()
            lon, lat = map(float, first_coord.split())
            return lat, lon
        
        return None, None
    except:
        return None, None

def calculate_yield_percentage(df):
    """Výpočet výnosu v % oproti priemeru za rok a plodinu"""
    # Výpočet priemerného výnosu za rok a plodinu
    yearly_crop_avg = df.groupby(['year', 'crop'])['yield_ha'].mean().reset_index()
    yearly_crop_avg = yearly_crop_avg.rename(columns={'yield_ha': 'avg_yield_crop_year'})
    
    # Spojenie s pôvodnými dátami
    df_with_avg = df.merge(yearly_crop_avg, on=['year', 'crop'], how='left')
    
    # Výpočet percentuálneho výnosu
    df_with_avg['yield_percentage'] = (df_with_avg['yield_ha'] / df_with_avg['avg_yield_crop_year']) * 100
    
    return df_with_avg

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
        
        # Vytvorenie mapy - centrum Slovenska
        center_lat, center_lon = 48.6690, 19.6990
        m = folium.Map(location=[center_lat, center_lon], zoom_start=7)
        
        # Pridanie parciel na mapu
        for idx, row in gdf.iterrows():
            try:
                # Farba podľa výkonnosti
                if row['avg_yield_percentage'] < 80:
                    color = 'red'
                elif row['avg_yield_percentage'] < 100:
                    color = 'orange'
                else:
                    color = 'green'
                
                # Vykreslenie hraníc parcele
                folium.GeoJson(
                    row['geometry'],
                    style_function=lambda x: {
                        'fillColor': color,
                        'color': 'black',
                        'weight': 1,
                        'fillOpacity': 0.3
                    },
                    popup=folium.Popup(f"""
                    <b>{row['name']}</b><br>
                    Priemerný výnos: {row['avg_yield_percentage']:.1f}%<br>
                    Plocha: {row['area']:.2f} ha<br>
                    Počet plodín: {row['crop_count']}
                    """, max_width=300)
                ).add_to(m)
                
            except Exception as e:
                continue
        
        return m
        
    except Exception as e:
        st.error(f"Chyba pri vytváraní mapy: {e}")
        return None

def main():
    st.markdown('<h1 class="main-header">🌾 Analýza výnosov DPB</h1>', unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.header("Nastavenia")
    
    # Načítanie dát
    with st.spinner("Načítavam dáta z CSV súboru..."):
        df = load_data()
    
    if df is None:
        st.error("Nepodarilo sa načítať dáta. Skontrolujte, či existuje súbor 'yield_data.csv'.")
        return
    
    # Výpočet percentuálnych výnosov
    df = calculate_yield_percentage(df)
    
    # Výber plodiny v sidebar
    available_crops = sorted(df['crop'].unique())
    default_crop = "PŠENICE OZ" if "PŠENICE OZ" in available_crops else available_crops[0]
    selected_crop = st.sidebar.selectbox("Vyberte plodinu:", available_crops, index=available_crops.index(default_crop))
    
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
        
        # Štatistiky pre vybranú plodinu
        col1, col2, col3 = st.columns(3)
        
        with col1:
            avg_yield = crop_data['yield_ha'].mean()
            st.metric(f"Priemerný výnos {selected_crop}", f"{avg_yield:.2f} t/ha")
        
        with col2:
            total_area = crop_data['area'].sum()
            st.metric("Celková plocha", f"{total_area:.1f} ha")
        
        with col3:
            avg_percentage = crop_data['yield_percentage'].mean()
            st.metric("Priemerná výnosnosť", f"{avg_percentage:.1f}%")
        
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
    
    # Mapa parciel
    st.header("🗺️ Mapa parciel")
    
    if st.button("Zobraziť mapu"):
        with st.spinner("Generujem mapu..."):
            map_fig = create_parcel_performance_map(df)
            if map_fig:
                st_folium(map_fig, width=800, height=600)
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

if __name__ == "__main__":
    main()
