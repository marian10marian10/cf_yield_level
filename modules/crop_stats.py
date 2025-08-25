import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

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
        height=400,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.3,
            xanchor="center",
            x=0.5
        )
    )
    
    return fig

def show_crop_statistics(df, selected_crop):
    """Zobrazenie štatistík na úrovni plodiny"""
    st.header(f"🌱 Štatistiky na úrovni plodiny: {selected_crop}")
    
    if selected_crop:
        crop_data = df[df['crop'] == selected_crop]
        
        # Základné štatistiky pre vybranú plodinu
        st.subheader("📊 Základné štatistiky")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Počet záznamov", f"{len(crop_data):,}")
        
        with col2:
            st.metric("Počet parciel", f"{crop_data['agev_parcel_id'].nunique():,}")
        
        with col3:
            st.metric("Priemerný výnos", f"{crop_data['yield_ha'].mean():.2f} t/ha")
        
        with col4:
            st.metric("Obdobie", f"{crop_data['year'].min()} - {crop_data['year'].max()}")
        
        # Grafy pre vybranú plodinu
        st.subheader("📈 Analýza výnosov")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Variabilita výnosov**")
            boxplot_fig = create_yield_boxplot(df, selected_crop)
            if boxplot_fig:
                st.plotly_chart(boxplot_fig, use_container_width=True)
            else:
                st.warning("Nepodarilo sa vytvoriť graf variability výnosov.")
        
        with col2:
            st.markdown("**Trend výnosov**")
            trend_fig = create_yield_trend(df, selected_crop)
            if trend_fig:
                st.plotly_chart(trend_fig, use_container_width=True)
            else:
                st.warning("Nepodarilo sa vytvoriť trendový graf výnosov.")
        
        # Detailné štatistiky podľa rokov
        st.subheader("📅 Detailné štatistiky podľa rokov")
        
        yearly_stats = crop_data.groupby('year').agg({
            'yield_ha': ['count', 'mean', 'std', 'min', 'max'],
            'yield_percentage': ['mean', 'std', 'min', 'max']
        }).round(2)
        
        # Flatten column names
        yearly_stats.columns = [
            'Počet parciel', 'Priemerný výnos (t/ha)', 'Štandardná odchýlka (t/ha)', 
            'Minimálny výnos (t/ha)', 'Maximálny výnos (t/ha)',
            'Priemerná výnosnosť (%)', 'Štandardná odchýlka výnosnosti (%)',
            'Minimálna výnosnosť (%)', 'Maximálna výnosnosť (%)'
        ]
        
        st.dataframe(yearly_stats, use_container_width=True)
        
        # Vysvetlenie metodiky
        st.markdown("---")
        st.markdown("**📊 Metodika:** Percentá = (Skutočný výnos / Priemerný výnos) × 100. Priemerný výnos sa počíta ako aritmetický priemer všetkých parciel pre danú plodinu a rok. 100% = priemer, >100% = nadpriemer, <100% = podpriemer.")
