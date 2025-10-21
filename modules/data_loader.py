import streamlit as st
import pandas as pd
import numpy as np
import re
import os
import psycopg2
from sqlalchemy import create_engine
import geopandas as gpd
from shapely import wkt
import binascii

# Database connection parameters
DB_USER_DESTINATION = 'db_admin'
DB_PASSWORD_DESTINATION = "Ybm=Zjk#sTf3#^]ybD<k"
DB_HOST_DESTINATION = 'team-pz.cyp6scadbpmv.eu-central-1.rds.amazonaws.com'
DB_NAME_DESTINATION = 'postgres'

@st.cache_data
def load_data():
    """Načítanie dát z PostgreSQL databázy"""
    try:
        # Vytvorenie connection string
        connection_string = f"postgresql://{DB_USER_DESTINATION}:{DB_PASSWORD_DESTINATION}@{DB_HOST_DESTINATION}/{DB_NAME_DESTINATION}"
        
        # Vytvorenie engine
        engine = create_engine(connection_string)
        
        # Najprv skontrolujeme dostupné stĺpce v tabuľke
        check_columns_query = """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'yield_level' 
        AND table_name = 'skeagis_yields'
        ORDER BY ordinal_position
        """
        
        columns_df = pd.read_sql(check_columns_query, engine)
        available_columns = columns_df['column_name'].tolist()
        
        # Debug informácie
        st.write("🔍 Dostupné stĺpce v tabuľke yield_level.skeagis_yields:")
        st.dataframe(columns_df)
        
        # Dynamické vytvorenie SELECT query na základe dostupných stĺpcov
        select_columns = []
        required_columns = ['parcel_id', 'yield_ha', 'season', 'ppa_crop_id']
        
        for col in required_columns:
            if col in available_columns:
                select_columns.append(col)
            else:
                st.warning(f"⚠️ Stĺpec '{col}' neexistuje v tabuľke!")
        
        # Pridanie area ak existuje
        if 'area' in available_columns:
            select_columns.append('area')
        
        # Vytvorenie SQL query
        columns_str = ', '.join(select_columns)
        query = f"""
        SELECT {columns_str}
        FROM yield_level.skeagis_yields
        WHERE yield_ha > 0
        ORDER BY season, parcel_id
        """
        
        # Načítanie dát
        df = pd.read_sql(query, engine)
        
        # Konverzia dátových typov
        df['yield_ha'] = pd.to_numeric(df['yield_ha'], errors='coerce')
        
        # Konverzia area ak existuje
        if 'area' in df.columns:
            df['area'] = pd.to_numeric(df['area'], errors='coerce')
        else:
            df['area'] = 1.0  # Default plocha
        
        # Parsovanie season do roku (napr. "19_20" -> 2019)
        df['year'] = df['season'].apply(parse_season_to_year)
        
        # Pridanie dummy stĺpca crop ak neexistuje ppa_crop_id
        if 'ppa_crop_id' not in df.columns:
            df['ppa_crop_id'] = 'Neznáma plodina'  # Default hodnota
        
        # Pre kompatibilitu s existujúcim kódom vytvoríme aj stĺpec crop
        df['crop'] = df['ppa_crop_id']
        
        # Filtrovanie len platných výnosov a rokov
        df = df[(df['yield_ha'] > 0) & (df['year'].notna())]
        
        # Skontrolujeme dostupné stĺpce v geometrické tabuľke
        geometry_columns_query = """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'yield_level' 
        AND table_name = 'cf_parcel_season'
        ORDER BY ordinal_position
        """
        
        geometry_columns_df = pd.read_sql(geometry_columns_query, engine)
        st.write("🔍 Dostupné stĺpce v tabuľke yield_level.cf_parcel_season:")
        st.dataframe(geometry_columns_df)
        
        # Načítanie geometrie z yield_level.cf_parcel_season
        geometry_query = """
        SELECT 
            parcel_id,
            geometry
        FROM yield_level.cf_parcel_season
        """
        
        geometry_df = pd.read_sql(geometry_query, engine)
        
        # Spojenie dát s geometriou
        df = df.merge(geometry_df, on='parcel_id', how='left')
        
        # Konverzia geometry na string pre kompatibilitu
        # Geometrie sú v hex formáte v EPSG:5514, musíme ich transformovať na WGS84 (EPSG:4326)
        def convert_geometry_to_wgs84(geom_data):
            try:
                if pd.isna(geom_data) or geom_data is None:
                    return None
                
                # Ak je už string, skúsime ho parsovať
                if isinstance(geom_data, str):
                    # Skontrolujeme, či je to už WKT formát
                    if geom_data.startswith(('POLYGON', 'MULTIPOLYGON', 'POINT', 'LINESTRING')):
                        try:
                            # Parsujeme geometriu
                            geom = wkt.loads(geom_data)
                            
                            # Skontrolujeme, či je geometria validná
                            if not geom.is_valid:
                                print(f"Nevalidná geometria: {geom_data[:100]}...")
                                return None
                            
                            # Vytvoríme GeoDataFrame s EPSG:5514
                            gdf = gpd.GeoDataFrame([1], geometry=[geom], crs='EPSG:5514')
                            
                            # Transformujeme na WGS84 (EPSG:4326)
                            gdf_wgs84 = gdf.to_crs('EPSG:4326')
                            
                            # Skontrolujeme výsledok
                            if gdf_wgs84.geometry.iloc[0] is None:
                                print(f"Transformácia zlyhala pre geometriu: {geom_data[:100]}...")
                                return None
                            
                            # Vrátime WKT formát
                            return gdf_wgs84.geometry.iloc[0].wkt
                        except Exception as transform_error:
                            print(f"Chyba pri transformácii geometrie: {transform_error}")
                            print(f"Problémová geometria: {geom_data[:100]}...")
                            return None
                    
                    # Ak je to hex string (začína s "01030000208A150000")
                    if geom_data.startswith('01030000208A150000') or len(geom_data) > 100:
                        try:
                            # Odstránime prípadné medzery a nové riadky
                            clean_hex = geom_data.replace(' ', '').replace('\n', '').replace('\r', '')
                            
                            # Dekódujeme hex na bytes
                            wkb_bytes = binascii.unhexlify(clean_hex)
                            
                            # Parsujeme WKB geometriu
                            geom = wkt.loads(wkb_bytes)
                            
                            # Skontrolujeme validitu
                            if not geom.is_valid:
                                print(f"Nevalidná geometria po hex dekódovaní: {geom_data[:50]}...")
                                return None
                            
                            # Vytvoríme GeoDataFrame s EPSG:5514
                            gdf = gpd.GeoDataFrame([1], geometry=[geom], crs='EPSG:5514')
                            
                            # Transformujeme na WGS84 (EPSG:4326)
                            gdf_wgs84 = gdf.to_crs('EPSG:4326')
                            
                            # Skontrolujeme výsledok
                            if gdf_wgs84.geometry.iloc[0] is None:
                                print(f"Transformácia zlyhala pre hex geometriu: {geom_data[:50]}...")
                                return None
                            
                            # Vrátime WKT formát
                            return gdf_wgs84.geometry.iloc[0].wkt
                            
                        except Exception as hex_error:
                            print(f"Chyba pri hex dekódovaní: {hex_error}")
                            print(f"Problémová hex geometria: {geom_data[:50]}...")
                            return None
                    else:
                        # Ak to nie je hex ani WKT, skúsime priamo parsovať ako WKT
                        try:
                            geom = wkt.loads(geom_data)
                            gdf = gpd.GeoDataFrame([1], geometry=[geom], crs='EPSG:5514')
                            gdf_wgs84 = gdf.to_crs('EPSG:4326')
                            return gdf_wgs84.geometry.iloc[0].wkt
                        except Exception as wkt_error:
                            print(f"Chyba pri WKT parsovaní: {wkt_error}")
                            return None
                
                # Ak je to bytes objekt
                if isinstance(geom_data, bytes):
                    try:
                        geom = wkt.loads(geom_data)
                        gdf = gpd.GeoDataFrame([1], geometry=[geom], crs='EPSG:5514')
                        gdf_wgs84 = gdf.to_crs('EPSG:4326')
                        return gdf_wgs84.geometry.iloc[0].wkt
                    except Exception as bytes_error:
                        print(f"Chyba pri bytes parsovaní: {bytes_error}")
                        return None
                
                return None
            except Exception as e:
                print(f"Chyba pri konverzii geometrie: {e}")
                return None
        
        # Aplikujeme konverziu na geometry stĺpec
        st.write("🔄 Transformujem geometrie z EPSG:5514 na WGS84 (EPSG:4326)...")
        
        # Debug - zobrazíme prvú geometriu pred transformáciou
        if not df.empty and 'geometry' in df.columns:
            first_geom = df['geometry'].iloc[0]
            st.write(f"🔍 Prvá geometria pred transformáciou: {str(first_geom)[:200]}...")
            st.write(f"🔍 Typ geometrie: {type(first_geom)}")
            st.write(f"🔍 Dĺžka geometrie: {len(str(first_geom))}")
        
        # Pokúsime sa o konverziu s lepším error handlingom
        progress_bar = st.progress(0)
        total_rows = len(df)
        
        converted_geometries = []
        for i, geom_data in enumerate(df['geometry']):
            try:
                converted_geom = convert_geometry_to_wgs84(geom_data)
                converted_geometries.append(converted_geom)
                
                # Aktualizujeme progress bar každých 100 riadkov
                if i % 100 == 0:
                    progress_bar.progress((i + 1) / total_rows)
                    
            except Exception as e:
                print(f"Chyba pri konverzii riadku {i}: {e}")
                converted_geometries.append(None)
        
        df['geometry'] = converted_geometries
        progress_bar.progress(1.0)
        
        # Debug - zobrazíme prvú geometriu po transformácii
        if not df.empty and 'geometry' in df.columns:
            first_geom_after = df['geometry'].iloc[0]
            st.write(f"🔍 Prvá geometria po transformácii: {str(first_geom_after)[:200]}...")
        
        # Zobrazíme štatistiky konverzie
        total_geometries = len(df)
        valid_geometries = df['geometry'].notna().sum()
        st.write(f"📊 Geometrie: {valid_geometries}/{total_geometries} úspešne transformované na WGS84")
        
        # Ak sa nepodarilo konvertovať žiadne geometrie, skúsime alternatívny prístup
        if valid_geometries == 0:
            st.warning("⚠️ Žiadne geometrie sa nekonvertovali. Skúšam alternatívny prístup...")
            
            # Skúsime použiť PostGIS funkcie priamo v SQL
            try:
                st.write("🔄 Skúšam konverziu pomocou PostGIS funkcií...")
                
                # SQL query s ST_Transform
                geometry_query_postgis = """
                SELECT 
                    parcel_id,
                    ST_AsText(ST_Transform(geometry, 4326)) as geometry_wgs84
                FROM yield_level.cf_parcel_season
                WHERE geometry IS NOT NULL
                """
                
                geometry_df_postgis = pd.read_sql(geometry_query_postgis, engine)
                
                if not geometry_df_postgis.empty:
                    # Spojenie s pôvodnými dátami
                    df = df.drop('geometry', axis=1, errors='ignore')
                    df = df.merge(geometry_df_postgis, on='parcel_id', how='left')
                    df['geometry'] = df['geometry_wgs84']
                    df = df.drop('geometry_wgs84', axis=1, errors='ignore')
                    
                    valid_geometries_postgis = df['geometry'].notna().sum()
                    st.success(f"✅ PostGIS konverzia úspešná: {valid_geometries_postgis}/{total_geometries} geometrií")
                else:
                    st.error("❌ PostGIS konverzia zlyhala - žiadne dáta")
                    
            except Exception as postgis_error:
                st.error(f"❌ PostGIS konverzia zlyhala: {postgis_error}")
        
        # Zobrazíme vzorku dát
        if not df.empty:
            st.write("📋 Vzorka dát:")
            sample_cols = ['parcel_id', 'yield_ha', 'season', 'ppa_crop_id', 'area']
            available_cols = [col for col in sample_cols if col in df.columns]
            st.dataframe(df[available_cols].head())
        
        # Pridanie agev_parcel_id pre kompatibilitu s existujúcim kódom
        df['agev_parcel_id'] = df['parcel_id']
        
        # Vytvorenie name stĺpca z parcel_id
        df['name'] = df['parcel_id'].astype(str)
        
        engine.dispose()
        
        return df
    except Exception as e:
        st.error(f"Chyba pri načítaní dát z databázy: {e}")
        return None

def parse_season_to_year(season_str):
    """Parsovanie season string na rok (napr. '19_20' -> 2019)"""
    try:
        if pd.isna(season_str):
            return None
        
        # Rozdelenie na dve časti (napr. "19_20" -> ["19", "20"])
        parts = str(season_str).split('_')
        if len(parts) >= 2:
            # Prvá časť je rok začiatku sezóny
            year_part = parts[0]
            # Konverzia na 4-ciferný rok
            if len(year_part) == 2:
                year = 2000 + int(year_part)
            else:
                year = int(year_part)
            return year
        return None
    except:
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