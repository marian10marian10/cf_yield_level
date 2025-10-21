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
        # Geometrie sú v WKB formáte, musíme ich konvertovať na WKT
        def convert_wkb_to_wkt(wkb_data):
            try:
                if pd.isna(wkb_data) or wkb_data is None:
                    return None
                
                # Ak je už string, skúsime ho parsovať ako WKB
                if isinstance(wkb_data, str):
                    # Skontrolujeme, či je to už WKT formát
                    if wkb_data.startswith('POLYGON') or wkb_data.startswith('MULTIPOLYGON'):
                        return wkb_data
                    # Ak nie, pokúsime sa dekódovať z hex
                    try:
                        # Odstránime prípadné medzery
                        clean_hex = wkb_data.replace(' ', '').replace('\n', '')
                        wkb_bytes = binascii.unhexlify(clean_hex)
                        geom = wkt.loads(wkb_bytes)
                        return geom.wkt
                    except Exception as hex_error:
                        # Ak hex dekódovanie zlyhá, skúsime priamo parsovať ako WKT
                        try:
                            geom = wkt.loads(wkb_data)
                            return geom.wkt
                        except:
                            return None
                
                # Ak je to bytes objekt
                if isinstance(wkb_data, bytes):
                    geom = wkt.loads(wkb_data)
                    return geom.wkt
                
                return None
            except Exception as e:
                print(f"Chyba pri konverzii geometrie: {e}")
                return None
        
        # Aplikujeme konverziu na geometry stĺpec
        st.write("🔄 Konvertujem geometrie z WKB na WKT formát...")
        df['geometry'] = df['geometry'].apply(convert_wkb_to_wkt)
        
        # Zobrazíme štatistiky konverzie
        total_geometries = len(df)
        valid_geometries = df['geometry'].notna().sum()
        st.write(f"📊 Geometrie: {valid_geometries}/{total_geometries} úspešne konvertované")
        
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
