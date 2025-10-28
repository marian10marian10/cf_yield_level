import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_empty_figure(message="Žiadne dáta na zobrazenie", color="gray"):
    """Vytvorí prázdny graf s správou"""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=16, color=color)
    )
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=False, showticklabels=False),
        height=400
    )
    return fig

def create_basic_stats_cards(df):
    """Vytvorí základné štatistiky v kartách"""
    if df.empty:
        return "Žiadne dáta na zobrazenie"
    
    # Výpočet základných štatistík
    total_records = len(df)
    unique_parcels = df['parcel_id'].nunique()
    unique_crops = df['crop'].nunique()
    unique_seasons = df['season'].nunique()
    avg_yield = df['yield_ha'].mean()
    max_yield = df['yield_ha'].max()
    min_yield = df['yield_ha'].min()
    
    # Kontrola existencie stĺpca year
    if 'year' in df.columns:
        unique_years = df['year'].nunique()
    else:
        unique_years = 0
    
    # Vytvorenie metric cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📊 Celkový počet záznamov",
            value=f"{total_records:,}",
            delta=None
        )
    
    with col2:
        st.metric(
            label="🏷️ Parcel",
            value=f"{unique_parcels:,}",
            delta=None
        )
    
    with col3:
        st.metric(
            label="🌾 Plodín",
            value=f"{unique_crops:,}",
            delta=None
        )
    
    with col4:
        st.metric(
            label="📅 Rokov",
            value=f"{unique_years}",
            delta=None
        )
    
    # Druhý riadok
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="🌱 Sezón",
            value=f"{unique_seasons:,}",
            delta=None
        )
    
    with col2:
        st.metric(
            label="📏 Ø yield_ha",
            value=f"{avg_yield:.2f}",
            delta=None
        )
    
    with col3:
        st.metric(
            label="📈 Max yield",
            value=f"{max_yield:.2f}",
            delta=None
        )
    
    with col4:
        st.metric(
            label="📉 Min yield",
            value=f"{min_yield:.2f}",
            delta=None
        )

def create_seasonal_yield_trends(df, selected_crop=None):
    """Vytvorí čiarový graf vývoja výnosov podľa sezón"""
    if df.empty:
        return create_empty_figure()
    
    # Filtrovanie podľa vybranej plodiny
    if selected_crop and selected_crop != "Všetky plodiny":
        df_filtered = df[df['crop'] == selected_crop]
        if df_filtered.empty:
            return create_empty_figure(f"Žiadne dáta pre plodinu: {selected_crop}", "orange")
    else:
        df_filtered = df
    
    # Výpočet priemerného yield_ha podľa sezóny
    seasonal_avg = df_filtered.groupby('season')['yield_ha'].mean().reset_index()
    
    if seasonal_avg.empty:
        return create_empty_figure("Žiadne dáta pre zobrazenie grafu", "orange")
    
    # Vytvorenie čiarového grafu
    fig = px.line(
        seasonal_avg,
        x='season',
        y='yield_ha',
        labels={
            'season': 'Sezóna', 
            'yield_ha': 'Priemerný výnos (t/ha)'
        },
        markers=True,
        line_shape='linear'
    )
    
    fig.update_traces(
        line=dict(width=3),
        marker=dict(size=8),
        hovertemplate='Sezóna: %{x}<br>Priemerný výnos: %{y:.2f} t/ha<extra></extra>'
    )
    
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=60, b=20),
        xaxis=dict(
            showgrid=True, 
            gridcolor='#e1e5e9',
            title_font_size=14
        ),
        yaxis=dict(
            showgrid=True, 
            gridcolor='#e1e5e9',
            title_font_size=14
        ),
        height=500
    )
    
    return fig

def create_yield_heatmap(df, selected_crop=None):
    """Vytvorí heatmapu výnosov"""
    if df.empty:
        return create_empty_figure()
    
    # Filtrovanie podľa vybranej plodiny
    if selected_crop and selected_crop != "Všetky plodiny":
        df_filtered = df[df['crop'] == selected_crop]
        if df_filtered.empty:
            return create_empty_figure(f"Žiadne dáta pre plodinu: {selected_crop}", "orange")
    else:
        df_filtered = df
    
    # Výpočet priemerného yield_ha podľa sezóny a roku
    if 'year' in df_filtered.columns:
        heatmap_data = df_filtered.groupby(['year', 'season'])['yield_ha'].mean().reset_index()
        
        # Vytvorenie pivot tabuľky pre heatmapu
        pivot_table = heatmap_data.pivot(index='year', columns='season', values='yield_ha')
        
        if pivot_table.empty:
            return create_empty_figure("Žiadne dáta pre zobrazenie heatmapy", "orange")
        
        # Vytvorenie heatmapy
        fig = px.imshow(
            pivot_table.values,
            x=[f"Sezóna {col}" for col in pivot_table.columns],
            y=pivot_table.index,
            labels=dict(x="Sezóna", y="Rok", color="Výnos (t/ha)"),
            color_continuous_scale='RdYlGn',
            aspect='auto'
        )
        
        # Pridanie hodnôt do buniek heatmapy
        fig.update_traces(
            text=pivot_table.values.round(1),
            texttemplate="%{text}",
            textfont={"size": 10},
            hovertemplate='Rok: %{y}<br>%{x}<br>Výnos: %{z:.2f} t/ha<extra></extra>'
        )
    else:
        # Ak nemáme year stĺpec, použijeme len season
        seasonal_avg = df_filtered.groupby('season')['yield_ha'].mean().reset_index()
        
        fig = px.bar(
            seasonal_avg,
            x='season',
            y='yield_ha',
            labels={'season': 'Sezóna', 'yield_ha': 'Priemerný výnos (t/ha)'},
            color='yield_ha',
            color_continuous_scale='RdYlGn'
        )
    
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        title_x=0.5,
        title_font_size=16,
        margin=dict(l=20, r=20, t=60, b=20),
        xaxis=dict(
            title_font_size=14,
            tickangle=45
        ),
        yaxis=dict(
            title_font_size=14
        ),
        coloraxis_colorbar=dict(
            title="Výnos (t/ha)",
            title_font_size=12
        ),
        height=600
    )
    
    return fig

def create_yield_boxplot(df, selected_crop=None):
    """Vytvorí box plot výnosov podľa sezón"""
    if df.empty:
        return create_empty_figure()
    
    # Filtrovanie podľa vybranej plodiny
    if selected_crop and selected_crop != "Všetky plodiny":
        df_filtered = df[df['crop'] == selected_crop]
        if df_filtered.empty:
            return create_empty_figure(f"Žiadne dáta pre plodinu: {selected_crop}", "orange")
    else:
        df_filtered = df
    
    # Vyčistíme NaN hodnoty
    df_filtered = df_filtered.dropna(subset=['yield_ha', 'season'])
    
    if df_filtered.empty:
        return create_empty_figure("Žiadne platné dáta pre zobrazenie box plotu", "orange")
    
    # Vytvorenie box plotu
    fig = go.Figure()
    
    seasons = sorted(df_filtered['season'].unique())
    
    for season in seasons:
        season_data = df_filtered[df_filtered['season'] == season]['yield_ha']
        
        fig.add_trace(go.Box(
            y=season_data,
            name=str(season),
            boxpoints='outliers',
            jitter=0.3,
            pointpos=0,
            hovertemplate=f'Sezóna: {season}<br>Výnos: %{{y:.2f}} t/ha<extra></extra>'
        ))
    
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=60, b=20),
        xaxis=dict(
            title="Sezóna",
            showgrid=True, 
            gridcolor='#e1e5e9',
            title_font_size=14,
            tickangle=45
        ),
        yaxis=dict(
            title="Výnos (t/ha)",
            showgrid=True, 
            gridcolor='#e1e5e9',
            title_font_size=14
        ),
        height=500
    )
    
    return fig

def create_yield_scatter_plot(df, selected_crop=None):
    """Vytvorí scatter plot jednotlivých výnosov"""
    if df.empty:
        return create_empty_figure()
    
    # Filtrovanie podľa vybranej plodiny
    if selected_crop and selected_crop != "Všetky plodiny":
        df_filtered = df[df['crop'] == selected_crop]
        if df_filtered.empty:
            return create_empty_figure(f"Žiadne dáta pre plodinu: {selected_crop}", "orange")
    else:
        df_filtered = df
    
    # Odstránenie NaN hodnôt
    df_filtered = df_filtered.dropna(subset=['yield_ha', 'season'])
    
    if df_filtered.empty:
        return create_empty_figure("Žiadne platné dáta pre zobrazenie scatter plotu", "orange")
    
    # Získanie unikátnych sezón
    seasons = sorted(df_filtered['season'].unique())
    
    # Vytvorenie mapovania sezón na čísla pre X-os
    season_mapping = {season: i+1 for i, season in enumerate(seasons)}
    df_filtered['season_order'] = df_filtered['season'].map(season_mapping)
    
    # Vytvorenie scatter plotu
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df_filtered['season_order'],
        y=df_filtered['yield_ha'],
        mode='markers',
        name='Výnosy',
        marker=dict(
            color='#1f77b4',
            size=8,
            opacity=0.7,
            line=dict(width=1, color='white')
        ),
        hovertemplate='Sezóna: %{x}<br>Výnos: %{y:.2f} t/ha<br>Parcela: %{text}<extra></extra>',
        text=df_filtered['parcel_id']
    ))
    
    # Nastavenie layoutu
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=60, b=20),
        xaxis=dict(
            title="Sezóna",
            showgrid=True,
            gridcolor='#e1e5e9',
            title_font_size=14,
            tickmode='array',
            tickvals=list(range(1, len(seasons) + 1)),
            ticktext=seasons,
            tickangle=45
        ),
        yaxis=dict(
            title="Výnos (t/ha)",
            showgrid=True,
            gridcolor='#e1e5e9',
            title_font_size=14
        ),
        height=500
    )
    
    return fig

def show_advanced_analytics(df):
    """Zobrazí pokročilé analýzy výnosov"""
    st.header("📈 Pokročilé analýzy výnosov")
    
    # Základné štatistiky
    st.subheader("📊 Základné štatistiky")
    create_basic_stats_cards(df)
    
    # Filter pre plodiny
    st.subheader("🔍 Filter")
    available_crops = sorted(df['crop'].unique())
    selected_crop = st.selectbox(
        "Vyberte plodinu:",
        ["Všetky plodiny"] + available_crops,
        index=0
    )
    
    # Čiarový graf vývoja výnosov
    st.subheader("📈 Vývoj priemerného výnosu na hektár podľa sezón")
    with st.expander("ℹ️ Informácie o grafe", expanded=False):
        st.markdown("""
        **Čiarový graf vývoja výnosov:**
        - Čiary ukazujú trend výnosov v čase
        - Body = priemerné výnosy za sezónu
        - Stúpajúca čiara = zlepšovanie výnosov
        - Klesajúca čiara = zhoršovanie výnosov
        """)
    
    trend_fig = create_seasonal_yield_trends(df, selected_crop)
    st.plotly_chart(trend_fig, use_container_width=True)
    
    # Heatmapa výnosov
    st.subheader("🔥 Heatmapa výnosov (t/ha)")
    with st.expander("ℹ️ Informácie o heatmape", expanded=False):
        st.markdown("""
        **Heatmapa výnosov:**
        - Farba = intenzita výnosu
        - Zelená = vysoké výnosy
        - Červená = nízke výnosy
        - Žltá = stredné výnosy
        - Porovnajte výnosy medzi sezónami
        """)
    
    heatmap_fig = create_yield_heatmap(df, selected_crop)
    st.plotly_chart(heatmap_fig, use_container_width=True)
    
    # Box plot
    st.subheader("📦 Box plot výnosov podľa sezón")
    boxplot_fig = create_yield_boxplot(df, selected_crop)
    st.plotly_chart(boxplot_fig, use_container_width=True)
    
    # Scatter plot
    st.subheader("🔍 Scatter plot jednotlivých výnosov")
    scatter_fig = create_yield_scatter_plot(df, selected_crop)
    st.plotly_chart(scatter_fig, use_container_width=True)
    
    # Detailné štatistiky podľa sezón
    st.subheader("📅 Detailné štatistiky podľa sezón")
    
    if selected_crop != "Všetky plodiny":
        df_filtered = df[df['crop'] == selected_crop]
    else:
        df_filtered = df
    
    seasonal_stats = df_filtered.groupby('season').agg({
        'yield_ha': ['count', 'mean', 'std', 'min', 'max'],
        'parcel_id': 'nunique'
    }).round(2)
    
    # Flatten column names
    seasonal_stats.columns = [
        'Počet záznamov', 'Priemerný výnos (t/ha)', 'Štandardná odchýlka (t/ha)', 
        'Minimálny výnos (t/ha)', 'Maximálny výnos (t/ha)', 'Počet parciel'
    ]
    
    st.dataframe(seasonal_stats, use_container_width=True)
