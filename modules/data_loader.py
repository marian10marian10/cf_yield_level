import streamlit as st
import pandas as pd
import numpy as np
import re
import os

@st.cache_data
def load_data():
    """Načítanie dát z CSV súboru"""
    try:
        # Získanie absolútnej cesty k CSV súboru
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        csv_path = os.path.join(parent_dir, 'yield_data.csv')
        
        # Kontrola, či súbor existuje
        if not os.path.exists(csv_path):
            # Fallback - skúsiť relatívnu cestu
            csv_path = 'yield_data.csv'
            if not os.path.exists(csv_path):
                raise FileNotFoundError(f"CSV súbor nebol nájdený na ceste: {csv_path}")
        
        # Načítanie CSV súboru
        df = pd.read_csv(csv_path, encoding='utf-8')
        
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
