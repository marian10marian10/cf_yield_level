import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

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

def create_yield_distribution(df, crop_name):
    """Vytvorenie histogramu distribúcie výnosov pre konkrétnu plodinu"""
    crop_data = df[df['crop'] == crop_name].copy()
    
    if crop_data.empty:
        return None
    
    # Výpočet mediánu
    median_yield = crop_data['yield_ha'].median()
    
    # Vytvorenie histogramu
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=crop_data['yield_ha'],
        nbinsx=20,
        marker_color='lightblue',
        opacity=0.8,
        name='Počet parciel'
    ))
    
    # Pridanie čiary mediánu
    fig.add_vline(
        x=median_yield,
        line_dash="dash",
        line_color="orange",
        annotation_text=f"Medián: {median_yield:.2f} t/ha",
        annotation_position="top right"
    )
    
    fig.update_layout(
        title=f"Distribúcia výnosov {crop_name}",
        xaxis_title="Výnos (t/ha)",
        yaxis_title="Počet parciel",
        height=400,
        showlegend=False,
        bargap=0.1
    )
    
    return fig

def create_yield_percentiles(df, crop_name):
    """Vytvorenie histogramu s percentilmi výnosov pre konkrétnu plodinu"""
    crop_data = df[df['crop'] == crop_name].copy()
    
    if crop_data.empty:
        return None
    
    # Výpočet percentilov
    percentiles = {
        '10%': crop_data['yield_ha'].quantile(0.10),
        '25%': crop_data['yield_ha'].quantile(0.25),
        '50%': crop_data['yield_ha'].quantile(0.50),
        '75%': crop_data['yield_ha'].quantile(0.75),
        '90%': crop_data['yield_ha'].quantile(0.90),
        '95%': crop_data['yield_ha'].quantile(0.95)
    }
    
    # Vytvorenie histogramu
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=crop_data['yield_ha'],
        nbinsx=20,
        marker_color='lightgreen',
        opacity=0.8,
        name='Počet parciel'
    ))
    
    # Pridanie percentilových čiar s farebnými bodkami
    colors = ['red', 'orange', 'blue', 'yellow', 'brown', 'black']
    for i, (percentile, value) in enumerate(percentiles.items()):
        fig.add_vline(
            x=value,
            line_dash="dot",
            line_color=colors[i],
            line_width=2,
            annotation_text=f"{percentile}: {value:.2f} t/ha",
            annotation_position="bottom"
        )
    
    fig.update_layout(
        title=f"Analýza percentilov výnosov {crop_name}",
        xaxis_title="Výnos (t/ha)",
        yaxis_title="Počet parciel",
        height=400,
        showlegend=False,
        bargap=0.1
    )
    
    return fig

def create_yield_heatmap(df, crop_name):
    """Vytvorenie heatmapy výnosov pre konkrétnu plodinu"""
    crop_data = df[df['crop'] == crop_name].copy()
    
    if crop_data.empty:
        return None
    
    # Vytvorenie výnosových kategórií pre lepšiu prehľadnosť
    # Použijeme 10 kategórií od minimálneho po maximálny výnos
    min_yield = crop_data['yield_ha'].min()
    max_yield = crop_data['yield_ha'].max()
    
    # Vytvorenie kategórií s rovnakou šírkou
    yield_bins = np.linspace(min_yield, max_yield, 11)
    yield_labels = [f"{yield_bins[i]:.1f}-{yield_bins[i+1]:.1f}" for i in range(len(yield_bins)-1)]
    
    # Pridanie kategórií do dát
    crop_data['yield_category'] = pd.cut(crop_data['yield_ha'], bins=yield_bins, labels=yield_labels, include_lowest=True)
    
    # Agregácia dát podľa roku a výnosovej kategórie
    heatmap_data = crop_data.groupby(['year', 'yield_category']).size().unstack(fill_value=0)
    
    # Preusporiadanie stĺpcov podľa výnosu (od najnižšieho po najvyšší)
    heatmap_data = heatmap_data.reindex(columns=yield_labels)
    
    # Vytvorenie heatmapy
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data.values,
        x=heatmap_data.columns,
        y=heatmap_data.index,
        colorscale='RdYlGn_r',  # Červená (nízke výnosy) -> Zelená (vysoké výnosy)
        text=heatmap_data.values,
        texttemplate="%{text}",
        textfont={"size": 10},
        hoverongaps=False,
        hovertemplate='Rok: %{y}<br>Výnos: %{x}<br>Počet parciel: %{z}<extra></extra>'
    ))
    
    fig.update_layout(
        title=f"Heatmapa výnosov {crop_name} - Počet parciel podľa roku a výnosu",
        xaxis_title="Výnosová kategória (t/ha)",
        yaxis_title="Rok",
        height=500,
        xaxis={'side': 'bottom'},
        yaxis={'side': 'left'},
        annotations=[
            dict(
                text="Tmavšie farby = viac parciel",
                showarrow=False,
                xref="paper", yref="paper",
                x=0, y=1.05,
                xanchor='left', yanchor='bottom',
                font=dict(size=12, color="gray")
            )
        ]
    )
    
    return fig

def show_crop_statistics(df, selected_crop):
    """Zobrazenie štatistik na úrovni plodiny"""
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
        
        # Nové grafy - Distribúcia a percentily výnosov
        st.subheader("📊 Distribúcia a percentily výnosov")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Distribúcia výnosov**")
            dist_fig = create_yield_distribution(df, selected_crop)
            if dist_fig:
                st.plotly_chart(dist_fig, use_container_width=True)
            else:
                st.warning("Nepodarilo sa vytvoriť graf distribúcie výnosov.")
        
        with col2:
            st.markdown("**Analýza percentilov**")
            perc_fig = create_yield_percentiles(df, selected_crop)
            if perc_fig:
                st.plotly_chart(perc_fig, use_container_width=True)
            else:
                st.warning("Nepodarilo sa vytvoriť graf percentilov výnosov.")
        
        # Heatmapa výnosov
        st.subheader("🗺️ Heatmapa výnosov")
        st.markdown("**Prehľad výnosov podľa rokov a výnosových kategórií**")
        
        heatmap_fig = create_yield_heatmap(df, selected_crop)
        if heatmap_fig:
            st.plotly_chart(heatmap_fig, use_container_width=True)
        else:
            st.warning("Nepodarilo sa vytvoriť heatmapu výnosov.")
        
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
