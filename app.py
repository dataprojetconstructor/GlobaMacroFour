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
    .opp-card { background-color: #1c2128; border: 1px solid #30363d; border-radius: 12px; padding: 25px; margin-bottom: 20px; border-left: 5px solid #238636; }
    .logic-box { background-color: #0d1117; padding: 15px; margin-top: 10px; border-radius: 6px; color: #c9d1d9; font-size: 0.95em; border: 1px solid #30363d; }
    h1, h2, h3 { color: #f0f6fc; }
    </style>
    """, unsafe_allow_html=True)

# --- API ---
API_KEY = 'f25835309cd5c99504970cd7f417dddd'
try:
    fred = Fred(api_key=API_KEY)
except:
    st.error("Erreur API FRED")
    st.stop()

# --- CODES SÉRIES G10 (OPTIMISÉS POUR L'AUSTRALIE) ---
central_banks = {
    'USD (Fed)': {'rate': 'FEDFUNDS', 'cpi': 'CPIAUCSL', 'liq': 'WALCL', 'yield10y': 'GS10', 'symbol': 'USD'},
    'EUR (ECB)': {'rate': 'ECBDFR', 'cpi': 'CP0000EZ19M086NEST', 'liq': 'ECBASSETSW', 'yield10y': 'IRLTLT01EZM156N', 'symbol': 'EUR'},
    'JPY (BoJ)': {'rate': 'IRSTCI01JPM156N', 'cpi': 'JPNCPIALLMINMEI', 'liq': 'JPNASSETS', 'yield10y': 'IRLTLT01JPM156N', 'symbol': 'JPY'},
    'GBP (BoE)': {'rate': 'IUDSOIA', 'cpi': 'GBRCPIALLMINMEI', 'liq': 'MANMM101GBM189S', 'yield10y': 'IRLTLT01GBM156N', 'symbol': 'GBP'},
    'CAD (BoC)': {'rate': 'IRSTCI01CAM156N', 'cpi': 'CANCPIALLMINMEI', 'liq': 'MANMM101CAM189S', 'yield10y': 'IRLTLT01CAM156N', 'symbol': 'CAD'},
    'AUD (RBA)': {'rate': 'IRSTCI01AUM156N', 'cpi': 'AUSCPIALLMINMEI', 'liq': 'MANMM101AUM189S', 'yield10y': 'IRLTLT01AUM156N', 'symbol': 'AUD'},
    'CHF (SNB)': {'rate': 'IRSTCI01CHM156N', 'cpi': 'CHECPIALLMINMEI', 'liq': 'MABMM301CHM189S', 'yield10y': 'IRLTLT01CHM156N', 'symbol': 'CHF'},
}

def calculate_z_score(series):
    if series is None or len(series.dropna()) < 3: return 0.0
    clean = series.ffill().dropna()
    return (clean.iloc[-1] - clean.mean()) / clean.std()

@st.cache_data(ttl=86400)
def fetch_macro_data():
    data = []
    start_date = datetime.now() - timedelta(days=365*12)
    for currency, codes in central_banks.items():
        row = {'Devise': currency, 'Symbol': codes['symbol'], 'Taux (%)': 0, 'Z-Rate': 0, 'Z-CPI': 0, 'Z-Liq': 0, '10Y Yield': 0, 'Z-Yield': 0, 'Score': 0}
        try:
            r = fred.get_series(codes['rate'], observation_start=start_date).ffill()
            row['Taux (%)'] = r.iloc[-1]
            row['Z-Rate'] = calculate_z_score(r)
            
            c = fred.get_series(codes['cpi'], observation_start=start_date).ffill()
            # Variation annuelle (12 mois ou 4 trimestres selon la série)
            c_yoy = c.pct_change(12 if len(c) > 40 else 4).dropna() * 100
            row['Z-CPI'] = calculate_z_score(c_yoy)
            
            l = fred.get_series(codes['liq'], observation_start=start_date).ffill()
            l_yoy = l.pct_change(12).dropna() * 100
            row['Z-Liq'] = calculate_z_score(l_yoy)
            
            y = fred.get_series(codes['yield10y'], observation_start=start_date).ffill()
            row['10Y Yield'] = y.iloc[-1]
            row['Z-Yield'] = calculate_z_score(y)
            
            row['Score'] = (row['Z-Rate']*2.0) + (row['Z-CPI']*1.0) + (row['Z-Yield']*1.5) - (row['Z-Liq']*1.0)
            data.append(row)
        except:
            data.append(row)
    return pd.DataFrame(data).sort_values(by='Score', ascending=False)

def get_price_info(pair):
    try:
        ticker = f"{pair}=X"
        df_p = yf.download(ticker, period="2y", interval="1d", progress=False)
        curr = df_p['Close'].iloc[-1].item()
        z = (curr - df_p['Close'].mean().item()) / df_p['Close'].std().item()
        return round(curr, 4), round(z, 2)
    except: return 0, 0

# --- UI ---
st.title("🏛️ Institutional Macro Terminal Pro")
df = fetch_macro_data()

if not df.empty:
    # 1. TABLEAU LEDGER
    st.header("1. Fundamental Health Ledger")
    st.dataframe(
        df.style.map(lambda x: 'color: #238636; font-weight: bold' if isinstance(x, float) and x > 1.2 else ('color: #da3633; font-weight: bold' if isinstance(x, float) and x < -1.2 else ''), 
                     subset=['Z-Rate', 'Z-CPI', 'Z-Yield', 'Z-Liq', 'Score'])
        .format("{:.2f}", subset=['Taux (%)', 'Z-Rate', 'Z-CPI', '10Y Yield', 'Z-Yield', 'Z-Liq', 'Score']),
        use_container_width=True
    )

    # 2. OPPORTUNITÉS
    st.divider()
    st.header("2. Tactical Opportunities (Alpha Search)")
    
    col1, col2 = st.columns(2)
    # On compare les paires à plus forte divergence
    opps = []
    for i in range(len(df)):
        for j in range(len(df)-1, i, -1):
            h, d = df.iloc[i], df.iloc[j]
            spread = h['Score'] - d['Score']
            if spread > 1.5: opps.append((h, d, spread))
    
    opps.sort(key=lambda x: x[2], reverse=True)

    for idx, (h, d, spread) in enumerate(opps[:6]):
        target_col = col1 if idx % 2 == 0 else col2
        price, z_price = get_price_info(f"{h['Symbol']}{d['Symbol']}")
        
        with target_col:
            st.markdown(f"""
            <div class="opp-card">
                <div style="display: flex; justify-content: space-between;">
                    <span style="font-size: 1.4em; font-weight: bold;">{h['Symbol']} / {d['Symbol']}</span>
                    <span style="color: #238636; font-weight: bold;">SPREAD : {spread:.2f}</span>
                </div>
                <div style="display: flex; gap: 20px; margin-top: 10px;">
                    <div><span style="color:#8b949e; font-size:0.8em;">Prix</span><br><b>{price}</b></div>
                    <div><span style="color:#8b949e; font-size:0.8em;">Z-Price</span><br><b style="color:{'#238636' if z_price < 0 else '#da3633'}">{z_price}</b></div>
                </div>
                <div class="logic-box">
                    <b>ANALYSE :</b> Achat de {h['Symbol']} supporté par une force cyclique de {h['Score']:.2f} contre {d['Symbol']} ({d['Score']:.2f}). 
                    Différentiel de rendement 10 ans : <b>{h['Z-Yield'] - d['Z-Yield']:.2f}</b>.
                </div>
            </div>
            """, unsafe_allow_html=True)

    # 3. GRAPHIQUE DU CYCLE
    st.divider()
    st.header("3. Monetary Cycle Map")
    fig = px.scatter(df, x="Z-CPI", y="Z-Rate", text="Symbol", size=[20]*len(df), color="Score",
                     color_continuous_scale='RdYlGn', template='plotly_dark',
                     labels={'Z-CPI': 'Inflation (Z-Score)', 'Z-Rate': 'Taux (Z-Score)'})
    fig.add_hline(y=0, line_dash="dash")
    fig.add_vline(x=0, line_dash="dash")
    st.plotly_chart(fig, use_container_width=True)

st.caption("Données : FRED St-Louis & Yahoo Finance. Z-Scores calculés sur 12 ans d'historique.")
