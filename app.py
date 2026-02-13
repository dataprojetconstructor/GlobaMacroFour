import streamlit as st
import pandas as pd
from fredapi import Fred
import plotly.express as px
from datetime import datetime, timedelta
import yfinance as yf

# --- CONFIGURATION ---
st.set_page_config(page_title="Institutional Macro Terminal Pro", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 15px; }
    .opp-card { background-color: #1c2128; border-radius: 12px; padding: 25px; margin-bottom: 20px; border-left: 5px solid #58a6ff; border: 1px solid #30363d; }
    .logic-box { background-color: #0d1117; border: 1px solid #30363d; padding: 15px; margin-top: 10px; border-radius: 6px; color: #c9d1d9; font-size: 0.95em; }
    .hawk-tag { color: #238636; font-weight: bold; background: #23863622; padding: 4px 12px; border-radius: 20px; border: 1px solid #238636; }
    h1, h2, h3 { color: #f0f6fc; font-family: 'Inter', sans-serif; }
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
    if series is None or len(series.dropna()) < 5: return 0.0
    clean = series.ffill().dropna()
    return (clean.iloc[-1] - clean.mean()) / clean.std()

@st.cache_data(ttl=86400)
def fetch_macro_universe():
    data_list = []
    # On remonte à 15 ans pour bien calculer les moyennes de dette
    start_date = datetime.now() - timedelta(days=365*15)
    
    for currency, codes in central_banks.items():
        row = {'Devise': currency, 'Symbol': codes['symbol'], 'Taux (%)': 0, 
               'Z-Rate': 0, 'Z-CPI': 0, 'Z-Liq': 0, 'Z-PIB': 0, 'Z-Debt': 0, 'Score': 0}
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
            
            # 4. PIB (Variation annuelle)
            g = fred.get_series(codes['gdp'], observation_start=start_date).ffill()
            row['Z-PIB'] = calculate_z_score(g.pct_change(4))
            
            # 5. Dette (Ratio Dette/PIB)
            d = fred.get_series(codes['debt'], observation_start=start_date).ffill()
            row['Z-Debt'] = calculate_z_score(d)
            
            # FORMULE MACRO : (Rate*2) + (CPI*1) + (GDP*1.5) - (Liq*1) - (Debt*0.8)
            row['Score'] = (row['Z-Rate']*2.0) + (row['Z-CPI']*1.0) + (row['Z-PIB']*1.5) - (row['Z-Liq']*1.0) - (row['Z-Debt']*0.8)
            data_list.append(row)
        except:
            data_list.append(row)
            
    return pd.DataFrame(data_list).sort_values(by='Score', ascending=False)

def fetch_price_analysis(pair):
    try:
        ticker = f"{pair}=X"
        df_p = yf.download(ticker, period="2y", interval="1d", progress=False)
        curr = df_p['Close'].iloc[-1].item()
        z = (curr - df_p['Close'].mean().item()) / df_p['Close'].std().item()
        return round(curr, 4), round(z, 2)
    except: return 0, 0

# --- INTERFACE ---
st.title("🏛️ Institutional Macro Terminal Pro")
st.markdown(f"**Analyse Fondamentale G10** | Mise à jour : {datetime.now().strftime('%d %B %Y')}")

with st.spinner("Analyse des cycles en cours..."):
    df = fetch_macro_universe()

if not df.empty:
    # Tableau Ledger
    st.header("1. Fundamental Health Ledger")
    st.dataframe(
        df.style.map(lambda x: 'color: #238636; font-weight: bold' if isinstance(x, float) and x > 1.2 else ('color: #da3633; font-weight: bold' if isinstance(x, float) and x < -1.2 else ''), 
                     subset=['Z-Rate', 'Z-CPI', 'Z-PIB', 'Z-Debt', 'Score'])
        .format("{:.2f}", subset=['Taux (%)', 'Z-Rate', 'Z-CPI', 'Z-PIB', 'Z-Debt', 'Score']),
        use_container_width=True
    )

    # Opportunités
    st.divider()
    st.header("2. Tactical Opportunities")
    col1, col2 = st.columns(2)
    hawks = df.iloc[:2]
    doves = df.iloc[-2:]
    
    idx = 0
    for _, h in hawks.iterrows():
        for _, d in doves.iterrows():
            spread = h['Score'] - d['Score']
            price, z_price = fetch_price_analysis(f"{h['Symbol']}{d['Symbol']}")
            with (col1 if idx % 2 == 0 else col2):
                st.markdown(f"""
                <div class="opp-card">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="font-size: 1.5em; font-weight: bold;">{h['Symbol']} / {d['Symbol']}</span>
                        <span class="hawk-tag">DIVERGENCE : {spread:.2f}</span>
                    </div>
                    <div style="display: flex; gap: 25px; margin-top: 10px;">
                        <div><span style="color:#8b949e; font-size:0.8em;">Prix</span><br><b>{price}</b></div>
                        <div><span style="color:#8b949e; font-size:0.8em;">Z-Price</span><br><b style="color:{'#238636' if z_price < 0 else '#da3633'}">{z_price}</b></div>
                        <div><span style="color:#8b949e; font-size:0.8em;">Diff PIB</span><br><b>{h['Z-PIB'] - d['Z-PIB']:.2f}</b></div>
                    </div>
                    <div class="logic-box">
                        <b>THÈSE :</b> Achat de {h['Symbol']} supporté par une croissance robuste (Z-PIB: {h['Z-PIB']:.2f}) 
                        contre {d['Symbol']} pénalisé par {'un risque fiscal élevé' if d['Z-Debt'] > 1 else 'une économie stagnante'}.
                    </div>
                </div>
                """, unsafe_allow_html=True)
            idx += 1

    # Graphiques
    st.divider()
    st.header("3. Strategic Landscapes")
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Monétaire (Taux vs Inflation)")
        st.plotly_chart(px.scatter(df, x="Z-CPI", y="Z-Rate", text="Symbol", size=[20]*len(df), color="Score", color_continuous_scale='RdYlGn', template='plotly_dark').add_hline(y=0).add_vline(x=0), use_container_width=True)
    with g2:
        st.subheader("Structurel (PIB vs Dette)")
        st.plotly_chart(px.scatter(df, x="Z-Debt", y="Z-PIB", text="Symbol", size=[20]*len(df), color="Score", color_continuous_scale='RdYlGn', template='plotly_dark').add_hline(y=0).add_vline(x=0), use_container_width=True)
