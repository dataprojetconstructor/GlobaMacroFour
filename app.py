import streamlit as st
import pandas as pd
from fredapi import Fred
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import yfinance as yf

# --- CONFIGURATION ET STYLE PROFESSIONNEL ---
st.set_page_config(page_title="Macro Alpha Terminal Pro", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px; }
    .opp-card { 
        background-color: #161b22; 
        border: 1px solid #30363d; 
        border-radius: 12px; 
        padding: 25px; 
        margin-bottom: 20px; 
        border-left: 6px solid #238636;
    }
    .logic-box { 
        background-color: #0d1117; 
        border: 1px solid #30363d; 
        padding: 15px; 
        margin-top: 15px; 
        border-radius: 6px; 
        color: #c9d1d9; 
        font-size: 0.95em; 
        line-height: 1.5;
    }
    .hawk-tag { color: #238636; font-weight: bold; background: #23863622; padding: 4px 12px; border-radius: 20px; border: 1px solid #238636; }
    h1, h2, h3 { color: #f0f6fc; font-family: 'Inter', sans-serif; }
    .text-muted { color: #8b949e; font-size: 0.85em; }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALISATION API ---
API_KEY = 'f25835309cd5c99504970cd7f417dddd'
try:
    fred = Fred(api_key=API_KEY)
except:
    st.error("Erreur de connexion API FRED")
    st.stop()

# --- RÉFÉRENTIEL DES SÉRIES G10 (TESTÉES POUR LA SUISSE & L'AUSTRALIE) ---
central_banks = {
    'USD (Fed)': {'rate': 'FEDFUNDS', 'cpi': 'CPIAUCSL', 'liq': 'WALCL', 'yield10y': 'GS10', 'symbol': 'USD'},
    'EUR (ECB)': {'rate': 'ECBDFR', 'cpi': 'CP0000EZ19M086NEST', 'liq': 'ECBASSETSW', 'yield10y': 'IRLTLT01EZM156N', 'symbol': 'EUR'},
    'JPY (BoJ)': {'rate': 'IRSTCI01JPM156N', 'cpi': 'JPNCPIALLMINMEI', 'liq': 'JPNASSETS', 'yield10y': 'IRLTLT01JPM156N', 'symbol': 'JPY'},
    'GBP (BoE)': {'rate': 'IUDSOIA', 'cpi': 'GBRCPIALLMINMEI', 'liq': 'MANMM101GBM189S', 'yield10y': 'IRLTLT01GBM156N', 'symbol': 'GBP'},
    'CAD (BoC)': {'rate': 'IRSTCI01CAM156N', 'cpi': 'CANCPIALLMINMEI', 'liq': 'MANMM101CAM189S', 'yield10y': 'IRLTLT01CAM156N', 'symbol': 'CAD'},
    'AUD (RBA)': {'rate': 'IRSTCI01AUM156N', 'cpi': 'AUSCPIALLMINMEI', 'liq': 'MANMM101AUM189S', 'yield10y': 'IRLTLT01AUM156N', 'symbol': 'AUD'},
    'CHF (SNB)': {'rate': 'IRSTCI01CHM156N', 'cpi': 'CHECPIALLMINMEI', 'liq': 'MABMM301CHM189S', 'yield10y': 'IRLTLT01CHM156N', 'symbol': 'CHF'},
}

# --- BACKEND : CALCULS MACRO ---

def calculate_z_score(series):
    if series is None or len(series.dropna()) < 8: return 0.0
    clean = series.ffill().dropna()
    return (clean.iloc[-1] - clean.mean()) / clean.std()

@st.cache_data(ttl=86400)
def fetch_macro_universe():
    data_list = []
    # Fenêtre de 12 ans pour stabiliser les moyennes
    start_date = datetime.now() - timedelta(days=365*12)
    
    for currency, codes in central_banks.items():
        row = {'Devise': currency, 'Symbol': codes['symbol'], 'Taux (%)': 0, 'Z-Rate': 0, 'CPI (%)': 0, 'Z-CPI': 0, 'Z-Liq': 0, '10Y (%)': 0, 'Z-Yield': 0, 'Score': 0}
        try:
            # 1. Taux Court
            r = fred.get_series(codes['rate'], observation_start=start_date).ffill()
            row['Taux (%)'] = r.iloc[-1]
            row['Z-Rate'] = calculate_z_score(r)
            
            # 2. Inflation (YoY)
            c = fred.get_series(codes['cpi'], observation_start=start_date).ffill()
            c_yoy = c.pct_change(12 if len(c)>40 else 4).dropna() * 100
            row['CPI (%)'] = c_yoy.iloc[-1]
            row['Z-CPI'] = calculate_z_score(c_yoy)
            
            # 3. Liquidité
            l = fred.get_series(codes['liq'], observation_start=start_date).ffill()
            l_yoy = l.pct_change(12).dropna() * 100
            row['Z-Liq'] = calculate_z_score(l_yoy)
            
            # 4. Taux 10 Ans (Santé Obligataire)
            y = fred.get_series(codes['yield10y'], observation_start=start_date).ffill()
            row['10Y (%)'] = y.iloc[-1]
            row['Z-Yield'] = calculate_z_score(y)
            
            # FORMULE DU MACRO SCORE (G10 Standard)
            row['Score'] = (row['Z-Rate']*2.0) + (row['Z-CPI']*1.0) + (row['Z-Yield']*1.5) - (row['Z-Liq']*1.0)
            data_list.append(row)
        except:
            data_list.append(row)
            
    return pd.DataFrame(data_list).sort_values(by='Score', ascending=False)

def get_market_execution(pair):
    try:
        ticker = f"{pair}=X"
        df_p = yf.download(ticker, period="2y", interval="1d", progress=False)
        last = df_p['Close'].iloc[-1].item()
        z = (last - df_p['Close'].mean().item()) / df_p['Close'].std().item()
        return round(last, 4), round(z, 2)
    except: return 0, 0

# --- INTERFACE UTILISATEUR ---

st.title("🏛️ Institutional Macro Terminal Pro")
st.markdown(f"**G10 Intelligence Hub** | Global Divergence Tracking | {datetime.now().strftime('%d %B %Y')}")

with st.spinner("Analyse du sentiment des banques centrales et des flux obligataires..."):
    df = fetch_macro_universe()

if not df.empty:
    # 1. TABLEAU DE BORD DÉTAILLÉ
    st.header("1. Fundamental Health Ledger")
    st.dataframe(
        df.style.map(lambda x: 'color: #238636; font-weight: bold' if isinstance(x, float) and x > 1.2 else ('color: #da3633; font-weight: bold' if isinstance(x, float) and x < -1.2 else ''), 
                     subset=['Z-Rate', 'Z-CPI', 'Z-Yield', 'Z-Liq', 'Score'])
        .format("{:.2f}", subset=['Taux (%)', 'Z-Rate', 'CPI (%)', 'Z-CPI', '10Y (%)', 'Z-Yield', 'Z-Liq', 'Score']),
        use_container_width=True, height=400
    )

    # 2. VISUALISATION DU CYCLE (SCATTER)
    st.divider()
    st.header("2. Strategic Cycle Visualization")
    
    col_fig, col_legend = st.columns([2, 1])
    
    with col_fig:
        fig = px.scatter(df, x="Z-CPI", y="Z-Rate", text="Symbol", size=[25]*len(df), color="Score",
                         color_continuous_scale='RdYlGn', template='plotly_dark',
                         labels={'Z-CPI': 'Inflation Pressure (Z)', 'Z-Rate': 'Monetary Tightness (Z)'},
                         height=600)
        
        # Quadrants explicatifs
        fig.add_hrect(y0=0, y1=4, x0=0, x1=4, fillcolor="green", opacity=0.05, layer="below", line_width=0)
        fig.add_hrect(y0=-4, y1=0, x0=0, x1=4, fillcolor="red", opacity=0.05, layer="below", line_width=0)
        fig.add_hrect(y0=-4, y1=0, x0=-4, x1=0, fillcolor="blue", opacity=0.05, layer="below", line_width=0)
        fig.add_hrect(y0=0, y1=4, x0=-4, x1=0, fillcolor="orange", opacity=0.05, layer="below", line_width=0)
        
        fig.add_hline(y=0, line_dash="solid", line_color="#444")
        fig.add_vline(x=0, line_dash="solid", line_color="#444")
        st.plotly_chart(fig, use_container_width=True)

    with col_legend:
        st.markdown("""
        ### 🧭 Comment lire le cycle ?
        - **🟢 RESTRICTIF (Haut-Droit) :** Taux hauts & Inflation forte. La monnaie attire les capitaux.
        - **🔴 BEHIND THE CURVE (Bas-Droit) :** Inflation forte & Taux bas. Risque majeur de dévaluation.
        - **🔵 ACCOMMODANT (Bas-Gauche) :** Taux bas & Inflation basse. Monnaie de financement (Carry).
        - **🟠 REFROIDISSEMENT (Haut-Gauche) :** Taux encore hauts mais inflation sous contrôle.
        """)

    # 3. OPPORTUNITÉS TACTIQUES (CARTES DÉTAILLÉES)
    st.divider()
    st.header("3. Tactical Execution & Alpha Signals")
    
    # Calcul des paires classées par divergence
    opps_list = []
    for i in range(len(df)):
        for j in range(len(df)-1, i, -1):
            h, d = df.iloc[i], df.iloc[j]
            spread = h['Score'] - d['Score']
            if spread > 1.8:
                opps_list.append((h, d, spread))
    
    opps_list.sort(key=lambda x: x[2], reverse=True)
    
    c_cards = st.columns(2)
    for idx, (h, d, spread) in enumerate(opps_list[:6]):
        target_col = c_cards[idx % 2]
        price, z_price = get_market_execution(f"{h['Symbol']}{d['Symbol']}")
        
        with target_col:
            st.markdown(f"""
            <div class="opp-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 1.6em; font-weight: bold;">{h['Symbol']} / {d['Symbol']}</span>
                    <span class="hawk-tag">DIV : {spread:.2f}</span>
                </div>
                <div style="display: flex; gap: 30px; margin-top: 15px;">
                    <div><span class="text-muted">Prix Actuel</span><br><b>{price}</b></div>
                    <div><span class="text-muted">Z-Score Prix (2y)</span><br><b style="color: {'#238636' if z_price < 0 else '#da3633'}">{z_price}</b></div>
                    <div><span class="text-muted">Confiance</span><br><b>{'🔥 Haute' if spread > 4 else '⚖️ Moyenne'}</b></div>
                </div>
                <div class="logic-box">
                    <b>THÈSE MACRO :</b><br>
                    L'achat de <b>{h['Symbol']}</b> est validé par un Z-Score de rendement 10 ans de <b>{h['Z-Yield']:.2f}</b>, 
                    indiquant une confiance du marché obligataire supérieure à celle de <b>{d['Symbol']}</b>. 
                    Le spread de divergence est de <b>{spread:.2f}</b>, suggérant une poursuite de tendance.
                </div>
            </div>
            """, unsafe_allow_html=True)

else:
    st.error("Échec de la récupération des flux FRED. Vérifiez votre clé API.")

st.caption(f"Terminal G10 Pro | Données Normalisées sur 12 ans | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
