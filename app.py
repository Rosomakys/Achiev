import streamlit as st
import pandas as pd
import gspread
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
import os
import json

# --- KONFIGURACE ---
st.set_page_config(page_title="Alpha Tracker Pro", layout="centered")

SHEET_ID = "10iaHG09CdNfeOxI5kYEYWH9V3BHTddgvMdAAaji0Vd4"
JSON_FILE = "denni-rozspis-0787b08cb57c.json"

# --- LOGIN SYSTÉM ---
def check_password():
    if "logged_in" not in st.session_state:
        st.title("🔐 Alpha Access")
        user = st.text_input("Uživatel")
        password = st.text_input("Heslo", type="password")
        if st.button("Vstoupit", use_container_width=True):
            if "passwords" in st.secrets and user in st.secrets["passwords"] and password == st.secrets["passwords"][user]:
                st.session_state["logged_in"] = True
                st.session_state["user_role"] = "admin" if user == "admin" else "user"
                st.session_state["username"] = user
                st.rerun()
            else:
                st.error("Nesprávné jméno nebo heslo.")
        return False
    return True

# --- DATOVÉ FUNKCE ---
@st.cache_resource
def get_sheet():
    if os.path.exists(JSON_FILE):
        gc = gspread.service_account(filename=JSON_FILE)
    else:
        creds_dict = json.loads(st.secrets["gspread_creds"])
        gc = gspread.service_account_from_dict(creds_dict)
    return gc.open_by_key(SHEET_ID)

@st.cache_data(ttl=60)
def get_dataframes():
    sh = get_sheet()
    df_d = pd.DataFrame(sh.worksheet("Data").get_all_records())
    df_c = pd.DataFrame(sh.worksheet("List1").get_all_records())
    # Načtení milníků s novými sloupci
    try:
        df_m = pd.DataFrame(sh.worksheet("Milníky").get_all_records())
    except:
        df_m = pd.DataFrame(columns=["Oblast", "Kategorie", "Aktivita", "Body", "Splněno"])
    return df_d, df_c, df_m

# --- HLAVNÍ APLIKACE ---
if check_password():
    try:
        sh = get_sheet()
        df_data, df_config, df_milniky = get_dataframes()
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # Header
        today_pts = df_data[df_data['datum'] == today_str]['body'].sum() if not df_data.empty else 0
        c1, c2 = st.columns([2, 1])
        c1.title(f"Alpha Tracker")
        c2.metric("DNES", f"{today_pts} pts")

        # Karty
        tab_list = ["🚀 Akce", "🏆 Milníky", "📈 Statistiky"]
        if st.session_state["user_role"] == "admin":
            tab_list.append("⚙️ Admin")
        
        tabs = st.tabs(tab_list)

        # TAB 1: DENNÍ AKCE
        with tabs[0]:
            st.subheader("Dnešní cíle")
            datum = st.date_input("Datum", datetime.now())
            vybrane_aktivity = []
            celkem_bodu = 0
            
            # Mapování barev na tvoje nové kategorie
            barvy = {
                "Trading Disciplína": "red",
                "Biohacking": "blue",
                "Produktivita": "orange",
                "Zdraví & Vitalita": "green"
            }
            
            for kat in df_config['Kategorie'].unique():
                barva = barvy.get(kat, "gray") # Pokud není v seznamu, bude šedá
                with st.expander(f":{barva}[📂 {kat}]"):
                    kat_df = df_config[df_config['Kategorie'] == kat]
                    for _, row in kat_df.iterrows():
                        if st.checkbox(f"{row['Aktivita']} (+{row['Body']})", key=f"d_{row['Aktivita']}"):
                            vybrane_aktivity.append(row['Aktivita'])
                            celkem_bodu += float(row['Body'])
            
            if st.button("LOGOVAT VÝKON", type="primary", use_container_width=True):
                if vybrane_aktivity:
                    sh.worksheet("Data").append_row([str(datum), ", ".join(vybrane_aktivity), celkem_bodu, st.session_state['username']])
                    get_dataframes.clear()
                    st.success("Dnešní progres zapsán!")
                    st.rerun()

       # TAB 2: MILNÍKY (Globální cíle)
        with tabs[1]:
            st.subheader("Jednorázové úspěchy")
            milniky_ws = sh.worksheet("Milníky")

            if not df_milniky.empty:
                # 1. Filtr na Oblast (ČR / Svět)
                oblasti = df_milniky['Oblast'].unique()
                vybrana_oblast = st.radio("Lokalita", oblasti, horizontal=True)

                # 2. Filtr na Kategorie (Hory / Památky...) podle vybrané oblasti
                kat_v_oblasti = df_milniky[df_milniky['Oblast'] == vybrana_oblast]['Kategorie'].unique()
                vybrana_kat = st.selectbox("Kategorie", kat_v_oblasti)

                # Filtrovaná data pro zobrazení
                df_filtrovane = df_milniky[(df_milniky['Oblast'] == vybrana_oblast) & (df_milniky['Kategorie'] == vybrana_kat)]

                for i, row in df_filtrovane.iterrows():
                    if row['Splněno'] == 0:
                        if st.checkbox(f"🚩 {row['Aktivita']} (+{row['Body']} pts)", key=f"m_{i}"):
                            # Zápis do logu (Data)
                            sh.worksheet("Data").append_row([today_str, f"MILNÍK: {row['Aktivita']}", row['Body'], st.session_state['username']])
                            
                            # KLÍČOVÁ ZMĚNA: Index 5 znamená sloupec E (Splněno)
                            milniky_ws.update_cell(i + 2, 5, 1) 
                            
                            get_dataframes.clear()
                            st.success(f"Dosaženo: {row['Aktivita']}")
                            st.rerun()
                    else:
                        st.write(f"✅ ~~{row['Aktivita']}~~")
            else:
                st.info("V Excelu zatím nejsou žádné milníky.")

        # TAB 3: STATISTIKY
        with tabs[2]:
            st.subheader("Performance")
            plot_df = df_data.copy()
            if st.session_state["user_role"] != "admin" and 'uzivatel' in plot_df.columns:
                plot_df = plot_df[plot_df['uzivatel'] == st.session_state['username']]
            
            if not plot_df.empty:
                plot_df['body'] = pd.to_numeric(plot_df['body'])
                plot_df = plot_df.groupby('datum', as_index=False)['body'].sum().sort_values('datum')
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=plot_df['datum'], y=plot_df['body'], mode='lines+markers', line=dict(color='#00E676', width=4)))
                fig.update_layout(template="plotly_dark", height=300)
                st.plotly_chart(fig, use_container_width=True)

        # TAB 4: ADMIN
        if st.session_state["user_role"] == "admin":
            with tabs[3]:
                st.write(f"Přihlášen: {st.session_state['username']}")
                st.dataframe(df_data.tail(15), use_container_width=True)
                if st.button("Odhlásit"):
                    del st.session_state["logged_in"]
                    st.rerun()

    except Exception as e:
        st.error(f"Chyba: {e}")