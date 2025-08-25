# 🌾 Analýza výnosov DPB - Streamlit Aplikácia

Komplexná Streamlit aplikácia pre analýzu výnosov poľnohospodárskych parciel s pokročilými vizualizáciami a štatistickými analýzami.

## 🚀 Funkcie

### 📊 Hlavné funkcie
- **Prehľad dát**: Základné štatistiky a metriky
- **Analýza podľa plodiny**: Detailné grafy a štatistiky pre každú plodinu
- **Výkonnosť parciel**: Porovnanie parciel podľa výnosnosti
- **Mapové zobrazenie**: Interaktívna mapa s výkonnosťou parciel
- **Porovnanie plodín**: Štatistické porovnanie medzi rôznymi plodinami
- **Štatistická analýza**: ANOVA testy a pokročilé analýzy
- **Export dát**: Možnosť exportu do CSV a Excel

### 📈 Grafy a vizualizácie
- **Boxplot grafy**: Variabilita výnosov v čase (inšpirované vašimi obrázkami)
- **Trendové grafy**: Vývoj výnosov s chybovými pruhmi
- **Bar grafy**: Porovnanie parciel a plodín
- **Interaktívne mapy**: Folium mapy s výkonnosťou parciel

### 🔬 Pokročilé analýzy
- **Percentuálne výnosy**: Výpočet výnosu v % oproti priemeru za rok a plodinu
- **Štatistické testy**: ANOVA testy pre porovnanie plodín
- **Agregované dáta**: Rôzne úrovne agregácie podľa potreby

## 🛠️ Inštalácia

### Lokálne spustenie
```bash
# Klonovanie repozitára
git clone <your-repo>
cd yield-analysis-app

# Vytvorenie virtuálneho prostredia
python -m venv venv
source venv/bin/activate  # Linux/Mac
# alebo
venv\Scripts\activate  # Windows

# Inštalácia závislostí
pip install -r requirements.txt

# Spustenie aplikácie
streamlit run yield_analysis_app.py
```

### Nasadenie na Railway

1. **Vytvorenie Railway účtu** na [railway.app](https://railway.app)
2. **Pripojenie GitHub repozitára**
3. **Nastavenie environment variables**:
   - `DATABASE_URL`: PostgreSQL connection string
4. **Automatické nasadenie** po push do main branch

## ⚙️ Konfigurácia

### Databázové pripojenie
Aplikácia používa `st.secrets["DATABASE_URL"]` pre pripojenie k PostgreSQL databáze.

**Formát connection string:**
```
postgresql://username:password@host:port/database
```

### Nastavenie Streamlit
Aplikácia je nakonfigurovaná pre:
- **Wide layout** pre lepšie využitie priestoru
- **Caching** pre rýchlejšie načítanie dát
- **Responsive design** pre rôzne veľkosti obrazoviek

## 📁 Štruktúra projektu

```
yield-analysis-app/
├── yield_analysis_app.py    # Hlavná aplikácia
├── requirements.txt         # Python závislosti
├── Procfile               # Railway deployment
├── README.md              # Dokumentácia
└── .streamlit/            # Streamlit konfigurácia (voliteľné)
```

## 🔧 Úprava aplikácie

### Pridanie nových grafov
```python
def create_new_chart(df, crop_name):
    # Váš kód pre nový graf
    return fig

# Použitie v main()
new_chart = create_new_chart(df, selected_crop)
st.plotly_chart(new_chart, use_container_width=True)
```

### Pridanie nových analýz
```python
# V main() funkcii
if st.checkbox("Nová analýza"):
    # Váš kód pre novú analýzu
    pass
```

## 🚀 Nasadenie na Railway

### Automatické nasadenie
1. Push kódu do GitHub
2. Railway automaticky detekuje zmeny
3. Aplikácia sa nasadí automaticky

### Manuálne nasadenie
```bash
# Railway CLI
railway login
railway init
railway up
```

## 📊 Použitie aplikácie

### 1. Prehľad dát
- Zobrazenie základných štatistík
- Počet záznamov, parciel, plodín
- Obdobie dát

### 2. Analýza plodiny
- Výber konkrétnej plodiny
- Boxplot grafy variability
- Trendové grafy v čase
- Detailné dáta

### 3. Výkonnosť parciel
- Top 10 parciel podľa výnosnosti
- Najhoršie parcele
- Interaktívna mapa

### 4. Porovnanie plodín
- Priemerné výnosy
- Percentuálna výnosnosť
- Štatistické testy

## 🔍 Riešenie problémov

### Chyba pri načítaní dát
- Skontrolujte `DATABASE_URL` v Railway secrets
- Overte pripojenie k databáze
- Skontrolujte SQL query

### Problémy s mapou
- Overte formát `geometry` stĺpca
- Upravte súradnice v `create_parcel_performance_map()`

### Pomalé načítanie
- Použite caching s `@st.cache_data`
- Optimalizujte SQL query
- Filtrujte dáta pred spracovaním

## 📈 Rozšírenia

### Možné vylepšenia
- **Filtrovanie podľa roku**: Výber konkrétneho obdobia
- **Export grafov**: Uloženie grafov ako obrázky
- **Alert systém**: Upozornenia na nízke výnosy
- **Prediktívne modely**: ML modely pre predpoveď výnosov
- **Real-time dáta**: Automatické aktualizácie

## 🤝 Príspevky

1. Fork repozitára
2. Vytvorte feature branch
3. Commit zmeny
4. Push do branch
5. Vytvorte Pull Request

## 📄 Licencia

Tento projekt je pod MIT licenciou.

## 📞 Kontakt

Pre otázky a podporu kontaktujte autora aplikácie.

---

**Poznámka**: Aplikácia je navrhnutá pre analýzu poľnohospodárskych dát a môže byť upravená podľa špecifických potrieb vašej organizácie.
