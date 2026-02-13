import streamlit as st
import pandas as pd
from fredapi import Fred
import plotly.express as px
from datetime import datetime, timedelta
import yfinance as yf

# --- CONFIGURATION ---
st.set_page_config(page_title="Macro Alpha Terminal Pro", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 15px; }
    .opp-card { background-color: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
    .logic-box { background-color: #0d1117; border-left: 4px solid #58a6ff; padding: 15px; margin: 10px 0; border-radius: 4px; font-size: 0.9em; }
    h1, h2, h3 { color: #f0f6fc; }
    .text-muted { color: #8b949e; font-size: 0.85em; }
    </style>
    """, unsafe_allow_html=True)

# --- API ---
API_KEY = 'f25835309cd5c99504970cd7f417dddd'
try:
    fred = Fred(api_key=API_KEY)
except:
    st.error("Erreur API FRED")
    st.stop()

# --- CODES SÉRIES G10 (VÉRIFIÉS ET ROBUSTES) ---
# J'ai remplacé les codes par des séries OCDE standardisées (MEI) pour éviter les "0"
central_banks = {
    'USD (Fed)': {'rate': 'FEDFUNDS', 'cpi': 'CPIAUCSL', 'liq': 'WALCL', 'gdp': 'GDPC1', 'debt': 'GFDEGDQ188S', 'symbol': 'USD'},
    'EUR (ECB)': {'rate': 'ECBDFR', 'cpi': 'CP0000EZ19M086NEST', 'liq': 'ECBASSETSW', 'gdp': 'CLVMEURSCAB1GQEU19', 'debt': 'DEBTTG7ZZA188S', 'symbol': 'EUR'},
    'JPY (BoJ)': {'rate': 'IRSTCI01JPM156N', 'cpi': 'JPNCPIALLMINMEI', 'liq': 'JPNASSETS', 'gdp': 'JPNNGDP', 'debt': 'DEBTTGJPZA188S', 'symbol': 'JPY'},
    'GBP (BoE)': {'rate': 'IUDSOIA', 'cpi': 'GBRCPIALLMINMEI', 'liq': 'MANMM101GBM189S', 'gdp': 'UKNGDP', 'debt': 'DEBTTGGBZA188S', 'symbol': 'GBP'},
    'CAD (BoC)': {'rate': 'IRSTCI01CAM156N', 'cpi': 'CANCPIALLMINMEI', 'liq': 'MANMM101CAM189S', 'gdp': 'CANGDP', 'debt': 'DEBTTGCAZA188S', 'symbol': 'CAD'},
    'AUD (RBA)': {'rate': 'IRSTCI01AUM156N', 'cpi': 'AUSCPIALLMINMEI', 'liq': 'MANMM101AUM189S', 'gdp': 'AUSGDP', 'debt': 'DEBTTGAUZA188S', 'symbol': 'AUD'},
    'CHF (SNB)': {'rate': 'IRSTCI01CHM156N', 'cpi': 'CHECPIALLMINMEI', 'liq': 'MABMM301CHM189S', 'gdp': 'CHNGDP', 'debt': 'DEBTTGCHZA188S', 'symbol': 'CHF'},
}

def calculate_z_score(series):
    if series is None or len(series.dropna()) < 3: return 0.0
    clean = series.ffill().dropna()
    return (clean.iloc[-1] - clean.mean()) / clean.std()

@st.cache_data(ttl=86400)
def fetch_macro_data():
    data = []
    start_date = datetime.now() - timedelta(days=365*12) # 12 ans pour les cycles de dette
    
    for currency, codes in central_banks.items():
        row = {'Devise': currency, 'Symbol': codes['symbol'], 'Taux (%)': 0, 'Z-Rate': 0, 'Z-CPI': 0, 'Z-Liq': 0, 'Z-PIB': 0, 'Z-Debt': 0, 'Macro Score': 0}
        try:
            # 1. Taux
            r = fred.get_series(codes['rate'], observation_start=start_date).ffill()
            row['Taux (%)'] = r.iloc[-1]
            row['Z-Rate'] = calculate_z_score(r)
            
            # 2. Inflation
            c = fred.get_series(codes['cpi'], observation_start=start_date).ffill()
            row['Z-CPI'] = calculate_z_score(c.pct_change(12))
            
            # 3. Liquidité
            l = fred.get_series(codes['liq'], observation_start=start_date).ffill()
            row['Z-Liq'] = calculate_z_score(l.pct_change(12))
            
            # 4. PIB (Croissance) - On cherche la variation sur 4 trimestres
            g = fred.get_series(codes['gdp'], observation_start=start_date).ffill()
            row['Z-PIB'] = calculate_z_score(g.pct_change(4))
            
            # 5. Dette
            d = fred.get_series(codes['debt'], observation_start=start_date).ffill()
            row['Z-Debt'] = calculate_z_score(d)
            
            # CALCUL DU SCORE (Formule Équilibrée)
            row['Macro Score'] = (row['Z-Rate'] * 2.0) + (row['Z-CPI'] * 1.0) + (row['Z-PIB'] * 1.5) - (row['Z-Liq'] * 1.0) - (row['Z-Debt'] * 0.8)
            data.append(row)
        except:
            data.append(row)
    return pd.DataFrame(data).sort_values(by='Macro Score', ascending=False)

# --- ENGINE & UI ---
df = fetch_macro_data()

st.title("🏛️ Institutional Macro Terminal Pro")
st.info("Le score prend en compte : Taux (x2), Inflation (x1), Croissance (x1.5), Liquidité (-1) et Dette (-0.8).")

if not df.empty:
    # 1. TABLEAU PRINCIPAL
    st.header("1. Fundamental Health Ledger")
    st.dataframe(
        df.style.map(lambda x: 'color: #238636; font-weight: bold' if isinstance(x, float) and x > 1.2 else ('color: #da3633; font-weight: bold' if isinstance(x, float) and x < -1.2 else ''), 
                     subset=['Z-Rate', 'Z-CPI', 'Z-PIB', 'Z-Debt', 'Macro Score'])
        .format("{:.2f}", subset=['Taux (%)', 'Z-Rate', 'Z-CPI', 'Z-PIB', 'Z-Debt', 'Macro Score']),
        use_container_width=True
    )

    # 2. ANALYSE DES OPPORTUNITÉS (LOGIQUE DÉTAILLÉE)
    st.divider()
    st.header("2. Tactical Analysis")
    
    col_opps = st.columns(2)
    # On compare le top 2 contre le bottom 2
    hawks = df.iloc[:2]
    doves = df.iloc[-2:]
    
    idx = 0
    for _, h in hawks.iterrows():
        for _, d in doves.iterrows():
            spread = h['Macro Score'] - d['Macro Score']
            if spread > 2.0:
                with col_opps[idx % 2]:
                    st.markdown(f"""
                    <div class="opp-card">
                        <h3>{h['Symbol']} / {d['Symbol']}</h3>
                        <p class="hawk-tag">Divergence Globale : {spread:.2f}</p>
                        <div class="logic-box">
                            <b>ANALYSE FONDAMENTALE :</b><br>
                            • <b>Force :</b> {h['Symbol']} affiche une croissance (Z-PIB: {h['Z-PIB']:.2f}) qui valide ses taux.<br>
                            • <b>Faiblesse :</b> {d['Symbol']} présente un score de {d['Macro Score']:.2f} lié à {'une dette élevée' if d['Z-Debt'] > 1 else 'une faible croissance'}.<br>
                            • <b>Verdict :</b> Le flux de capitaux devrait favoriser {h['Symbol']} à moyen terme.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                idx += 1

    # 3. GRAPHIQUE SANTÉ ÉCONOMIQUE
    st.divider()
    st.header("3. Economic Health Map (PIB vs Dette)")
    fig = px.scatter(df, x="Z-Debt", y="Z-PIB", text="Symbol", size=[20]*len(df), color="Macro Score",
                     color_continuous_scale='RdYlGn', template='plotly_dark',
                     labels={'Z-Debt': 'Risque Dette (Z-Score)', 'Z-PIB': 'Croissance PIB (Z-Score)'})
    fig.add_hline(y=0, line_dash="dash")
    fig.add_vline(x=0, line_dash="dash")
    st.plotly_chart(fig, use_container_width=True)

st.caption("Données : FRED St-Louis. Z-Scores calculés sur une fenêtre de 12 ans.")
