import streamlit as st
import base64
import os
import graphviz

def show_methodology_page():
    """Display a visual, diagram-based methodology page"""
    st.markdown("# 🌱 Cesta Dát: Od Poľa po Analýzu")
    
    # Introduction
    st.markdown("""
    ## 🚜 Náš Príbeh Dát
    Každý údaj má svoju cestu. Tu je, ako premieňame surové poľnohospodárske dáta na užitočné insights.
    """)
    
    # Data Flow Diagram using Graphviz
    def create_data_flow_diagram():
        dot = graphviz.Digraph('data_flow', filename='data_flow.gv', 
                                node_attr={'shape': 'box', 'style': 'filled', 'fillcolor': 'lightblue'})
        
        # Nodes
        dot.node('farm', 'Poľnohospodárske Podniky\n🚜', fillcolor='lightgreen')
        dot.node('csv', 'CSV Súbory\n📄', fillcolor='lightyellow')
        dot.node('database', 'PostgreSQL Databáza\n🗄️', fillcolor='lightpink')
        dot.node('cleaning', 'Čistenie Dát\n🧹', fillcolor='lightcoral')
        dot.node('transform', 'Transformácia\n🔄', fillcolor='lightsalmon')
        dot.node('analysis', 'Streamlit Dashboard\n📊', fillcolor='lightblue')
        dot.node('insights', 'Analytické Insights\n💡', fillcolor='lightcyan')
        
        # Edges
        dot.edges([
            ('farm', 'csv'),
            ('csv', 'cleaning'),
            ('cleaning', 'transform'),
            ('transform', 'database'),
            ('database', 'analysis'),
            ('analysis', 'insights')
        ])
        
        return dot
    
    # Render Data Flow Diagram
    data_flow_diagram = create_data_flow_diagram()
    st.graphviz_chart(data_flow_diagram)
    
    # Detailed Stages
    st.markdown("## 🔍 Kľúčové Etapy Spracovania Dát")
    
    # Create columns for stages
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        ### 🚜 Zber Dát
        - Priamo z poľnohospodárskych podnikov
        - Ročné záznamy o výnosoch
        - Presné GPS súradnice parciel
        """)
    
    with col2:
        st.markdown("""
        ### 🧹 Čistenie Dát
        - Odstránenie duplicít
        - Kontrola rozsahov hodnôt
        - Štandardizácia formátov
        - Dopĺňanie chýbajúcich údajov
        """)
    
    with col3:
        st.markdown("""
        ### 🔄 Transformácia
        - Prepojenie súvisiacich tabuliek
        - Priestorové transformácie
        - Výpočet agregovaných ukazovateľov
        - Príprava pre analýzu
        """)
    
    # Raw Data Architecture Image
    st.markdown("## 🖼️ Architektúra Surových Dát")
    
    # Load and display the first image
    image_path1 = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        'media', 
        'skeagis_csv.png'
    )
    
    try:
        with open(image_path1, "rb") as image_file:
            encoded_image1 = base64.b64encode(image_file.read()).decode()
        
        st.markdown(f"""
        <div style="text-align: center;">
            <img src="data:image/png;base64,{encoded_image1}" style="max-width: 100%; height: auto;">
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Nepodarilo sa načítať prvý obrázok: {e}")
    
    # Database Table Preview Image
    st.markdown("## 📊 Databázová Tabuľka: Náhľad")
    
    # Load and display the second image (database table preview)
    image_path2 = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        'media', 
        'db_image.png'
    )
    
    try:
        with open(image_path2, "rb") as image_file:
            encoded_image2 = base64.b64encode(image_file.read()).decode()
        
        st.markdown(f"""
        <div style="text-align: center;">
            <img src="data:image/png;base64,{encoded_image2}" style="max-width: 100%; height: auto;">
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Nepodarilo sa načítať druhý obrázok: {e}")
    
    # Database Structure Image
    st.markdown("## 🗄️ Štruktúra Databázových Tabuliek")
    
    # Load and display the third image (database structure)
    image_path3 = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        'media', 
        'db_structure.png'
    )
    
    try:
        with open(image_path3, "rb") as image_file:
            encoded_image3 = base64.b64encode(image_file.read()).decode()
        
        st.markdown(f"""
        <div style="text-align: center;">
            <img src="data:image/png;base64,{encoded_image3}" style="max-width: 100%; height: auto;">
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Nepodarilo sa načítať tretí obrázok: {e}")
    
    # Database and Visualization
    st.markdown("## 🌐 Databáza a Vizualizácia")
    
    col4, col5 = st.columns(2)
    
    with col4:
        st.markdown("""
        ### 🗄️ PostgreSQL
        - Priestorové dáta (PostGIS)
        - Rýchle agregácie
        - Komplexné priestorové dotazy
        """)
    
    with col5:
        st.markdown("""
        ### 📊 Streamlit Dashboard
        - Interaktívne grafy
        - Priestorové mapy
        - Dynamické filtre
        - Predikčné modely
        """)
    
    # Conclusion
    st.markdown("## 🚀 Náš Cieľ")
    st.markdown("""
    Premeniť surové poľnohospodárské dáta na zmysluplné insights, 
    ktoré pomôžu poľnohospodárom robiť lepšie rozhodnutia.
    """)
