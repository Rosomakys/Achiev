import streamlit as st
import pandas as pd
import gspread
import plotly.graph_objects as go
import numpy as np
from datetime import datetime

# 1. Konfigurace a Styl
st.set_page_config(page_title="Alpha Tracker", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #0E1117; }
    div[data-testid="stMetricValue"] { font-size: 32px; color: #00E676; }
    .stRadio [role=radiogroup] { margin-top: -20px; }
    </style>
    """, unsafe_allow_html=True)

SHEET_ID = "10iaHG09CdNfeOxI5kYEYWH9V3BHTddgvMdAAaji0Vd4"
JSON_FILE = "denni-rozspis-0787b08cb57c.json"

# --- CACHING (Ochrana proti 429 Erroru) ---

@st.cache_resource
def get_sheet():
    # 1. Zkusíme, jestli jsme v cloudu (mobilu) a máme "Secrets"
    if "gspread_creds" in st.secrets:
        import json
        creds_dict = json.loads(st.secrets["gspread_creds"])
        gc = gspread.service_account_from_dict(creds_dict)
    # 2. Pokud ne, zkusíme to postaru přes soubor (jen pro tvůj počítač)
    else:
        gc = gspread.service_account(filename=JSON_FILE)
    
    return gc.open_by_key(SHEET_ID)

@st.cache_data(ttl=60) 
def get_dataframes():
    # Stáhne data z tabulky a pamatuje si je 60 vteřin
    sh = get_sheet()
    df_d = pd.DataFrame(sh.worksheet("Data").get_all_records())
    df_c = pd.DataFrame(sh.worksheet("List1").get_all_records())
    return df_d, df_c

try:
    # Načtení z cache
    sh = get_sheet()
    df_data, df_config = get_dataframes()

    # --- BODY NAHORU ---
    col1, col2 = st.columns(2)
    with col1:
        st.title("Alpha Tracker")
    with col2:
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_pts = df_data[df_data['datum'] == today_str]['body'].sum() if not df_data.empty else 0
        st.metric("DNEŠNÍ SKÓRE", f"{today_pts} pts")

    # Menu
    stranka = st.radio("Navigace", ["🚀 Akce", "📈 Trading View", "📜 Historie"], horizontal=True, label_visibility="collapsed")

    if stranka == "🚀 Akce":
        st.subheader("Dnešní cíle")
        datum = st.date_input("Datum", datetime.now())
        
        vybrane_aktivity = []
        celkem_bodu = 0
        barvy = {"Zdraví & Vitalita": "green", "Produktivita & Růst": "blue", "Vztahy & Emoce": "orange", "Anti-Prokrastinace": "red"}
        
        for kat in df_config['Kategorie'].unique():
            barva = barvy.get(kat, "gray")
            with st.expander(f":{barva}[📂 {kat}]"):
                kat_df = df_config[df_config['Kategorie'] == kat]
                for _, row in kat_df.iterrows():
                    if st.checkbox(f"{row['Aktivita']} ({row['Body']} b)", key=f"{row['Aktivita']}_{kat}"):
                        vybrane_aktivity.append(row['Aktivita'])
                        celkem_bodu += float(row['Body'])
        
        if st.button("LOGOVAT VÝKON", use_container_width=True):
            if vybrane_aktivity:
                data_ws = sh.worksheet("Data")
                data_ws.append_row([str(datum), ", ".join(vybrane_aktivity), celkem_bodu])
                
                # Smazání paměti, aby se hned načetla čerstvá data do grafu!
                get_dataframes.clear() 
                
                st.success("Data zapsána do blockchainu tabulky.")
                st.rerun()

    elif stranka == "📈 Trading View":
        st.subheader("Performance Chart")
        if len(df_data) > 0:
            df_data['body'] = pd.to_numeric(df_data['body'])
            df_data = df_data.groupby('datum', as_index=False)['body'].sum()
            df_data = df_data.sort_values('datum')
            
            fig = go.Figure()
            
            # Hlavní neonová čára (zaoblená - spline)
            fig.add_trace(go.Scatter(
                x=df_data['datum'], 
                y=df_data['body'], 
                mode='lines+markers', 
                name='Denní body', 
                line=dict(color='#00E676', width=4, shape='spline'),
                marker=dict(size=8, color='#00E676', line=dict(width=2, color='white'))
            ))
            
            # Žlutá/Oranžová Trendovka
            if len(df_data) > 1: 
                y = df_data['body'].values
                x = np.arange(len(y))
                z = np.polyfit(x, y, 1)
                p = np.poly1d(z)
                fig.add_trace(go.Scatter(
                    x=df_data['datum'], 
                    y=p(x), 
                    mode='lines', 
                    name='Trend', 
                    line=dict(color='#FFB300', width=2, dash='dash')
                ))

            # Styling aby to vypadalo jako v ukázce
            fig.update_layout(
                template="plotly_dark", 
                plot_bgcolor='#161A25', 
                paper_bgcolor='rgba(0,0,0,0)', 
                margin=dict(l=20, r=20, t=30, b=20),
                xaxis=dict(showgrid=True, gridcolor='#2D3342', gridwidth=1),
                yaxis=dict(showgrid=True, gridcolor='#2D3342', gridwidth=1, title="Body")
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nahraj aspoň 2 dny dat pro zobrazení trendu.")

    elif stranka == "📜 Historie":
        st.subheader("Poslední záznamy")
        st.dataframe(df_data.tail(10), use_container_width=True)

except Exception as e:
    st.error(f"Error: {e}")