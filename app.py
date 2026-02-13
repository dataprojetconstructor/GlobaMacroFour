import streamlit as st
import pandas as pd
from fredapi import Fred
import plotly.express as px
from datetime import datetime, timedelta
import yfinance as yf

# --- CONFIGURATION & STYLE ---
st.set_page_config(page_title="Macro Alpha Terminal Pro", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 15px; }
    .opp-card { background-color: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
    .hawk-tag { color: #238636; font-weight: bold; background: #23863622; padding: 4px 8px; border-radius: 4px; }
    h1, h2, h3 { color: #f0f6fc; font-family: 'Inter', sans-serif; }
    .text-muted { color: #8b949e; font-size: 0.85em; }
    .logic-box { background-color: #0d1117; border-left: 4px solid #58a6ff; padding: 15px; margin: 10px 0; border-radius: 4px; }
    </style>
    """, unsafe_allow_html=True)

# --- API ---
if "FRED_KEY" in st.secrets:
    API_KEY = st.secrets["FRED_KEY"]
else:
    API_KEY = 'f25835309cd5c99504970cd7f417dddd'

try:
    fred = Fred(api_key=API_KEY)
except:
    st.error("Erreur API FRED")
    st.stop()

# --- CODES SÉRIES G10 (MONÉTAIRE + MACRO) ---
central_banks = {
    'USD (Fed)': {'rate': 'FEDFUNDS', 'cpi': 'CPIAUCSL', 'liq': 'WALCL', 'gdp': 'GDP', 'debt': 'GFDEGDQ188S', 'symbol': 'USD'},
    'EUR (ECB)': {'rate': 'ECBDFR', 'cpi': 'CP0000EZ19M086NEST', 'liq': 'ECBASSETSW', 'gdp': 'CLVMEURSCAB1GQEU27', 'debt': 'DEBTTG7ZZA188S', 'symbol': 'EUR'},
    'JPY (BoJ)': {'rate': 'IRSTCI01JPM156N', 'cpi': 'JPNCPIALLMINMEI', 'liq': 'JPNASSETS', 'gdp': 'JPNNGDP', 'debt': 'DEBTTGJPZA188S', 'symbol': 'JPY'},
    'GBP (BoE)': {'rate': 'IUDSOIA', 'cpi': 'GBRCPIALLMINMEI', 'liq': 'MANMM101GBM189S', 'gdp': 'UKNGDP', 'debt': 'DEBTTGGBZA188S', 'symbol': 'GBP'},
    'CAD (BoC)': {'rate': 'IRSTCI01CAM156N', 'cpi': 'CANCPIALLMINMEI', 'liq': 'MANMM101CAM189S', 'gdp': 'CANGDP', 'debt': 'DEBTTGCAZA188S', 'symbol': 'CAD'},
    'AUD (RBA)': {'rate': 'IRSTCI01AUM156N', 'cpi': 'AUSCPIALLMINMEI', 'liq': 'MANMM101AUM189S', 'gdp': 'AUSGDP', 'debt': 'DEBTTGAUZA188S', 'symbol': 'AUD'},
    'CHF (SNB)': {'rate': 'IRSTCI01CHM156N', 'cpi': 'CHECPIALLMINMEI', 'liq': 'MABMM301CHM189S', 'gdp': 'CHNGDP', 'debt': 'DEBTTGCHZA188S', 'symbol': 'CHF'},
}

# --- BACKEND ---

def calculate_z_score(series):
    if series is None or len(series) < 5: return 0.0
    clean = series.ffill().dropna()
    return (clean.iloc[-1] - clean.mean()) / clean.std() if not clean.empty else 0.0

@st.cache_data(ttl=86400)
def fetch_macro_full():
    data = []
    start_date = datetime.now() - timedelta(days=365*10)
    for currency, codes in central_banks.items():
        row = {'Devise': currency, 'Symbol': codes['symbol'], 'Taux (%)': 0.0, 'Z-Rate': 0.0, 'Z-CPI': 0.0, 'Z-Liq': 0.0, 'Z-PIB': 0.0, 'Z-Debt': 0.0, 'Macro Score': 0.0}
        try:
            # 1. Taux
            try:
                r = fred.get_series(codes['rate'], observation_start=start_date).ffill()
                row['Taux (%)'] = r.iloc[-1]
                row['Z-Rate'] = calculate_z_score(r)
            except: pass
            # 2. CPI
            try:
                c = fred.get_series(codes['cpi'], observation_start=start_date).ffill()
                row['Z-CPI'] = calculate_z_score(c.pct_change(12))
            except: pass
            # 3. Liquidité
            try:
                l = fred.get_series(codes['liq'], observation_start=start_date).ffill()
                row['Z-Liq'] = calculate_z_score(l.pct_change(12))
            except: pass
            # 4. PIB (Croissance)
            try:
                g = fred.get_series(codes['gdp'], observation_start=start_date).ffill()
                row['Z-PIB'] = calculate_z_score(g.pct_change(4)) # Croissance annuelle (trimestriel)
            except: pass
            # 5. Dette
            try:
                d = fred.get_series(codes['debt'], observation_start=start_date).ffill()
                row['Z-Debt'] = calculate_z_score(d)
            except: pass
            
            # FORMULE FINALE : (Taux*2) + (CPI*1) + (PIB*1.5) - (Liq*1) - (Dette*0.5)
            row['Macro Score'] = (row['Z-Rate']*2.0) + (row['Z-CPI']*1.0) + (row['Z-PIB']*1.5) - (row['Z-Liq']*1.0) - (row['Z-Debt']*0.5)
            data.append(row)
        except: data.append(row)
    return pd.DataFrame(data).sort_values(by='Macro Score', ascending=False)

def fetch_price(pair):
    try:
        ticker = f"{pair}=X"
        df_p = yf.download(ticker, period="2y", interval="1d", progress=False)
        curr = df_p['Close'].iloc[-1].item()
        z = (curr - df_p['Close'].mean().item()) / df_p['Close'].std().item()
        return round(curr, 4), round(z, 2)
    except: return 0.0, 0.0

# --- UI ---
st.title("🏛️ Institutional Fundamental Terminal")
st.markdown("Analyse complète G10 : Politique Monétaire + Santé Économique + Risque Souverain")

df = fetch_macro_full()

if not df.empty:
    tab1, tab2, tab3 = st.tabs(["📊 Score Fondamental Global", "🎯 Opportunités Tactiques", "🧠 Logique de Calcul"])

    with tab1:
        st.subheader("Classement des Devises par Solidité Fondamentale")
        st.dataframe(
            df.style.map(lambda x: 'color: #238636; font-weight: bold' if isinstance(x, float) and x > 1.2 else ('color: #da3633; font-weight: bold' if isinstance(x, float) and x < -1.2 else ''), 
                         subset=['Z-Rate', 'Z-CPI', 'Z-PIB', 'Z-Debt', 'Macro Score'])
            .format("{:.2f}", subset=['Taux (%)', 'Z-Rate', 'Z-CPI', 'Z-PIB', 'Z-Debt', 'Macro Score']),
            use_container_width=True, height=400
        )
        
        col_left, col_right = st.columns(2)
        with col_left:
            st.subheader("Visualisation du Cycle (Taux vs Inflation)")
            fig_cycle = px.scatter(df, x="Z-CPI", y="Z-Rate", text="Symbol", size=[20]*len(df), color="Macro Score", color_continuous_scale='RdYlGn', template='plotly_dark')
            fig_cycle.add_hline(y=0, line_dash="dash")
            fig_cycle.add_vline(x=0, line_dash="dash")
            st.plotly_chart(fig_cycle, use_container_width=True)
        with col_right:
            st.subheader("Santé Économique (PIB vs Dette)")
            fig_health = px.scatter(df, x="Z-Debt", y="Z-PIB", text="Symbol", size=[20]*len(df), color="Macro Score", color_continuous_scale='RdYlGn', template='plotly_dark')
            fig_health.add_hline(y=0, line_dash="dash")
            fig_health.add_vline(x=0, line_dash="dash")
            st.plotly_chart(fig_health, use_container_width=True)

    with tab2:
        st.header("⚡ Top Opportunités Fondamentales")
        opps = []
        for i in range(len(df)):
            for j in range(len(df)-1, -1, -1):
                if i == j: continue
                h, d = df.iloc[i], df.iloc[j]
                div_score = h['Macro Score'] - d['Macro Score']
                if div_score > 2.0: opps.append((h, d, div_score))
        
        opps.sort(key=lambda x: x[2], reverse=True)

        for h, d, div_score in opps[:6]:
            pair_name = f"{h['Symbol']}{d['Symbol']}"
            price, z_price = fetch_price(pair_name)
            
            st.markdown(f"""
            <div class="opp-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 1.5em; font-weight: bold;">{h['Symbol']} / {d['Symbol']}</span>
                    <span class="hawk-tag">SCORE DIVERGENCE : {div_score:.2f}</span>
                </div>
                <div style="display: flex; gap: 30px; margin-top: 15px;">
                    <div><span class="text-muted">Prix</span><br><b>{price}</b></div>
                    <div><span class="text-muted">Z-Price (Technique)</span><br><b style="color: {'#238636' if z_price < 0 else '#da3633'}">{z_price}</b></div>
                    <div><span class="text-muted">PIB Relatif</span><br><b>+{h['Z-PIB']:.2f} vs {d['Z-PIB']:.2f}</b></div>
                    <div><span class="text-muted">Dette Risque</span><br><b>{h['Z-Debt']:.2f} vs {d['Z-Debt']:.2f}</b></div>
                </div>
                <div class="logic-box">
                    <b>POURQUOI CE TRADE ?</b><br>
                    Le <b>{h['Symbol']}</b> est supporté par un PIB dynamique (Z: {h['Z-PIB']:.2f}) ce qui permet à sa banque centrale de maintenir des taux à {h['Taux (%)']}%. 
                    À l'inverse, le <b>{d['Symbol']}</b> est pénalisé par {'une faible croissance' if d['Z-PIB'] < 0 else 'un risque de dette élevé'}.
                </div>
            </div>
            """, unsafe_allow_html=True)

    with tab3:
        st.header("🧠 Comprendre la Matrice Fondamentale")
        st.markdown("""
        ### 1. Pourquoi le PIB a un poids de 1.5 ?
        Le PIB est le "carburant" de la monnaie. Un pays qui croît attire naturellement les investissements étrangers. 
        Si le PIB augmente, le **Z-PIB** devient positif, ce qui booste le score.
        
        ### 2. Pourquoi la Dette a un poids de -0.5 ?
        La dette est un "frein". Un pays trop endetté (Z-Dette élevé) a moins de marge de manœuvre. 
        Le marché demande une prime de risque pour détenir la monnaie d'un pays surendetté.
        
        ### 3. Interprétation du graphique Santé (PIB vs Dette)
        - **Haut-Gauche (Idéal) :** Forte croissance et faible dette (ex: souvent le Dollar ou le Franc Suisse).
        - **Bas-Droite (Critique) :** Faible croissance et forte dette (Zone de danger pour la devise).
        """)

else:
    st.error("Échec du chargement.")
