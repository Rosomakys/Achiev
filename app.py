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
    return df_d, df_c

# --- HLAVNÍ APLIKACE ---
if check_password():
    try:
        sh = get_sheet()
        df_data, df_config = get_dataframes()
        
        # Header s metrikou
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_pts = df_data[df_data['datum'] == today_str]['body'].sum() if not df_data.empty else 0
        
        c1, c2 = st.columns([2, 1])
        c1.title(f"Vítej, {st.session_state['username']}! 👋")
        c2.metric("DNEŠNÍ SCORE", f"{today_pts} pts")

        # Rozdělení na karty podle role
        tab_list = ["🚀 Akce", "📈 Statistiky"]
        if st.session_state["user_role"] == "admin":
            tab_list.append("⚙️ Admin Panel")
        
        tabs = st.tabs(tab_list)

        # TAB 1: AKCE
        with tabs[0]:
            st.subheader("Dnešní mise")
            datum = st.date_input("Datum", datetime.now())
            
            vybrane_aktivity = []
            celkem_bodu = 0
            barvy = {"Zdraví & Vitalita": "green", "Produktivita & Růst": "blue", "Vztahy & Emoce": "orange", "Anti-Prokrastinace": "red"}
            
            for kat in df_config['Kategorie'].unique():
                barva = barvy.get(kat, "gray")
                with st.expander(f":{barva}[📂 {kat}]"):
                    kat_df = df_config[df_config['Kategorie'] == kat]
                    for _, row in kat_df.iterrows():
                        if st.checkbox(f"{row['Aktivita']} (+{row['Body']})", key=f"{row['Aktivita']}_{st.session_state['username']}"):
                            vybrane_aktivity.append(row['Aktivita'])
                            celkem_bodu += float(row['Body'])
            
            if st.button("LOGOVAT VÝKON", type="primary", use_container_width=True):
                if vybrane_aktivity:
                    sh.worksheet("Data").append_row([str(datum), ", ".join(vybrane_aktivity), celkem_bodu, st.session_state['username']])
                    get_dataframes.clear()
                    st.success("Zapsáno! Držíš linii.")
                    st.rerun()

        # TAB 2: STATISTIKY
        with tabs[1]:
            st.subheader("Performance Chart")
            # Filtrování dat podle uživatele (Admin vidí vše, User jen své)
            plot_df = df_data.copy()
            if st.session_state["user_role"] != "admin":
                # Předpokládáme, že ve sloupci 4 (index 3) je jméno uživatele
                plot_df = plot_df[plot_df['uzivatel'] == st.session_state['username']] if 'uzivatel' in plot_df.columns else plot_df

            if not plot_df.empty:
                plot_df['body'] = pd.to_numeric(plot_df['body'])
                plot_df = plot_df.groupby('datum', as_index=False)['body'].sum().sort_values('datum')
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=plot_df['datum'], y=plot_df['body'], mode='lines+markers', 
                                         line=dict(color='#00E676', width=4, shape='spline')))
                fig.update_layout(template="plotly_dark", height=300, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Zatím žádná data k zobrazení.")

        # TAB 3: ADMIN (pouze pro Admina)
        if st.session_state["user_role"] == "admin":
            with tabs[2]:
                st.subheader("Kompletní historie (všechny logs)")
                st.dataframe(df_data.tail(20), use_container_width=True)
                if st.button("Odhlásit se"):
                    del st.session_state["logged_in"]
                    st.rerun()

    except Exception as e:
        st.error(f"Systémový pád: {e}")