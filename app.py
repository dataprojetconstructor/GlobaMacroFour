import streamlit as st
import pandas as pd
from fredapi import Fred
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import yfinance as yf

# --- CONFIGURATION DE L'INTERFACE ---
st.set_page_config(page_title="Macro Alpha Terminal Pro", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 15px; }
    .opp-card { background-color: #1c2128; border: 1px solid #30363d; border-radius: 12px; padding: 25px; margin-bottom: 20px; border-left: 5px solid #58a6ff; }
    .logic-box { background-color: #0d1117; border: 1px solid #30363d; padding: 15px; margin-top: 10px; border-radius: 6px; color: #c9d1d9; font-size: 0.92em; line-height: 1.4; }
    .hawk-tag { color: #238636; font-weight: bold; background: #23863622; padding: 4px 12px; border-radius: 20px; border: 1px solid #238636; font-size: 0.8em; }
    h1, h2, h3 { color: #f0f6fc; font-family: 'Inter', sans-serif; }
    .text-muted { color: #8b949e; font-size: 0.85em; }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALISATION API ---
API_KEY = 'f25835309cd5c99504970cd7f417dddd'
try:
    fred = Fred(api_key=API_KEY)
except:
    st.error("Erreur de connexion à l'API FRED.")
    st.stop()

# --- RÉFÉRENTIEL DES SÉRIES G10 (MONÉTAIRE + PIB + DETTE) ---
# Sélection de séries homogènes pour éviter les données manquantes (Source : BRI & OCDE via FRED)
central_banks = {
    'USD (Fed)': {'rate': 'FEDFUNDS', 'cpi': 'CPIAUCSL', 'liq': 'WALCL', 'gdp': 'GDPC1', 'debt': 'GFDEGDQ188S', 'symbol': 'USD'},
    'EUR (ECB)': {'rate': 'ECBDFR', 'cpi': 'CP0000EZ19M086NEST', 'liq': 'ECBASSETSW', 'gdp': 'CLVMEURSCAB1GQEU19', 'debt': 'DEBTTG7ZZA188S', 'symbol': 'EUR'},
    'JPY (BoJ)': {'rate': 'IRSTCI01JPM156N', 'cpi': 'JPNCPIALLMINMEI', 'liq': 'JPNASSETS', 'gdp': 'JPNNGDP', 'debt': 'DEBTTGJPZA188S', 'symbol': 'JPY'},
    'GBP (BoE)': {'rate': 'IUDSOIA', 'cpi': 'GBRCPIALLMINMEI', 'liq': 'MANMM101GBM189S', 'gdp': 'UKNGDP', 'debt': 'DEBTTGGBZA188S', 'symbol': 'GBP'},
    'CAD (BoC)': {'rate': 'IRSTCI01CAM156N', 'cpi': 'CANCPIALLMINMEI', 'liq': 'MANMM101CAM189S', 'gdp': 'CANGDP', 'debt': 'DEBTTGCAZA188S', 'symbol': 'CAD'},
    'AUD (RBA)': {'rate': 'IRSTCI01AUM156N', 'cpi': 'AUSCPIALLMINMEI', 'liq': 'MANMM101AUM189S', 'gdp': 'AUSGDP', 'debt': 'DEBTTGAUZA188S', 'symbol': 'AUD'},
    'CHF (SNB)': {'rate': 'IRSTCI01CHM156N', 'cpi': 'CHECPIALLMINMEI', 'liq': 'MABMM301CHM189S', 'gdp': 'CHNGDP', 'debt': 'DEBTTGCHZA188S', 'symbol': 'CHF'},
}

# --- LOGIQUE DE CALCUL ---

def calculate_z_score(series):
    """Calcule la position statistique actuelle par rapport à l'historique."""
    if series is None or len(series.dropna()) < 8: return 0.0
    clean = series.ffill().dropna()
    return (clean.iloc[-1] - clean.mean()) / clean.std()

@st.cache_data(ttl=86400)
def fetch_macro_universe():
    data_list = []
    # Fenêtre de 12 ans pour capturer les cycles longs de dette
    start_date = datetime.now() - timedelta(days=365*12)
    
    for currency, codes in central_banks.items():
        row = {'Devise': currency, 'Symbol': codes['symbol'], 'Taux (%)': 0, 
               'Z-Rate': 0, 'Z-CPI': 0, 'Z-Liq': 0, 'Z-PIB': 0, 'Z-Debt': 0, 'Score': 0}
        try:
            # 1. Taux (Politique Monétaire)
            r = fred.get_series(codes['rate'], observation_start=start_date).ffill()
            row['Taux (%)'] = r.iloc[-1]
            row['Z-Rate'] = calculate_z_score(r)
            
            # 2. CPI (Pression Inflationniste)
            c = fred.get_series(codes['cpi'], observation_start=start_date).ffill()
            row['Z-CPI'] = calculate_z_score(c.pct_change(12))
            
            # 3. Liquidité (Impression Monétaire)
            l = fred.get_series(codes['liq'], observation_start=start_date).ffill()
            row['Z-Liq'] = calculate_z_score(l.pct_change(12))
            
            # 4. PIB (Dynamisme Économique)
            g = fred.get_series(codes['gdp'], observation_start=start_date).ffill()
            row['Z-PIB'] = calculate_z_score(g.pct_change(4)) # Croissance annuelle
            
            # 5. Dette (Risque de Solvabilité)
            d = fred.get_series(codes['debt'], observation_start=start_date).ffill()
            row['Z-Debt'] = calculate_z_score(d)
            
            # FORMULE DU SCORE FONDAMENTAL GLOBAL
            # On privilégie les Taux et la Croissance. On pénalise la Dette et l'Impression Monétaire.
            row['Score'] = (row['Z-Rate']*2.0) + (row['Z-CPI']*1.0) + (row['Z-PIB']*1.5) - (row['Z-Liq']*1.0) - (row['Z-Debt']*0.8)
            data_list.append(row)
        except:
            data_list.append(row)
            
    return pd.DataFrame(data_list).sort_values(by='Score', ascending=False)

def fetch_pair_details(pair):
    """Analyse technique rapide du prix"""
    try:
        ticker = f"{pair}=X"
        df_p = yf.download(ticker, period="2y", interval="1d", progress=False)
        last_price = df_p['Close'].iloc[-1].item()
        z_price = (last_price - df_p['Close'].mean().item()) / df_p['Close'].std().item()
        return round(last_price, 4), round(z_price, 2)
    except:
        return 0, 0

# --- INTERFACE UTILISATEUR ---

st.title("🏛️ Institutional Fundamental Terminal")
st.markdown(f"**Global Macro Surveillance** | G10 Universe | {datetime.now().strftime('%d %B %Y')}")

with st.spinner("Analyse approfondie des piliers macro-économiques..."):
    df = fetch_macro_universe()

if not df.empty:
    # 1. TABLEAU DE BORD DÉTAILLÉ
    st.header("1. Fundamental Health Ledger")
    st.markdown("Comparaison normalisée des indicateurs de puissance et de risque.")
    
    st.dataframe(
        df.style.map(lambda x: 'color: #238636; font-weight: bold' if isinstance(x, float) and x > 1.2 else ('color: #da3633; font-weight: bold' if isinstance(x, float) and x < -1.2 else ''), 
                     subset=['Z-Rate', 'Z-CPI', 'Z-PIB', 'Z-Debt', 'Score'])
        .format("{:.2f}", subset=['Taux (%)', 'Z-Rate', 'Z-CPI', 'Z-PIB', 'Z-Debt', 'Score']),
        use_container_width=True, height=400
    )

    # 2. ANALYSE VISUELLE DES CYCLES
    st.divider()
    st.header("2. Strategic Mapping")
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Monetary Cycle (Rates vs Inflation)")
        fig1 = px.scatter(df, x="Z-CPI", y="Z-Rate", text="Symbol", size=[25]*len(df), color="Score", color_continuous_scale='RdYlGn', template='plotly_dark')
        fig1.add_hline(y=0, line_dash="dash", line_color="#444")
        fig1.add_vline(x=0, line_dash="dash", line_color="#444")
        st.plotly_chart(fig1, use_container_width=True)
        
    with c2:
        st.subheader("Structural Health (Growth vs Debt)")
        fig2 = px.scatter(df, x="Z-Debt", y="Z-PIB", text="Symbol", size=[25]*len(df), color="Score", color_continuous_scale='RdYlGn', template='plotly_dark')
        fig2.add_hline(y=0, line_dash="dash", line_color="#444")
        fig2.add_vline(x=0, line_dash="dash", line_color="#444")
        st.plotly_chart(fig2, use_container_width=True)

    # 3. OPPORTUNITÉS TACTIQUES (ALGORITHME DE DIVERGENCE)
    st.divider()
    st.header("3. Tactical Opportunities")
    
    # Génération des paires par ordre de divergence fondamentale
    opps_list = []
    for i in range(len(df)):
        for j in range(len(df)-1, i, -1):
            h, d = df.iloc[i], df.iloc[j]
            div = h['Score'] - d['Score']
            if div > 1.5:
                opps_list.append((h, d, div))
    
    opps_list.sort(key=lambda x: x[2], reverse=True)
    
    col_cards = st.columns(2)
    for idx, (h, d, spread) in enumerate(opps_list[:6]):
        target_col = col_cards[idx % 2]
        price, z_price = fetch_pair_details(f"{h['Symbol']}{d['Symbol']}")
        
        with target_col:
            st.markdown(f"""
            <div class="opp-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 1.6em; font-weight: bold;">{h['Symbol']} / {d['Symbol']}</span>
                    <span class="hawk-tag">DIVERGENCE : {spread:.2f}</span>
                </div>
                <div style="display: flex; gap: 30px; margin-top: 15px;">
                    <div><span class="text-muted">Prix Market</span><br><b>{price}</b></div>
                    <div><span class="text-muted">Z-Price (2y)</span><br><b style="color: {'#238636' if z_price < 0 else '#da3633'}">{z_price}</b></div>
                    <div><span class="text-muted">Diff. PIB (Z)</span><br><b>{h['Z-PIB'] - d['Z-PIB']:.2f}</b></div>
                </div>
                <div class="logic-box">
                    <b>THÈSE D'INVESTISSEMENT :</b><br>
                    • <b>FORCE :</b> Le {h['Symbol']} bénéficie d'une croissance solide (Z-PIB: {h['Z-PIB']:.2f}) validant son rendement de {h['Taux (%)']}%.<br>
                    • <b>FAIBLESSE :</b> Le {d['Symbol']} est pénalisé par {'un endettement excessif' if d['Z-Debt'] > 1 else 'une croissance atone'}.<br>
                    • <b>TIMING :</b> Le prix est actuellement <b>{'favorable (Value)' if z_price < 0 else 'cher (Momentum)'}</b>.
                </div>
            </div>
            """, unsafe_allow_html=True)

    # 4. MÉTHODOLOGIE DÉTAILLÉE
    with st.expander("📝 Guide d'interprétation des données"):
        st.markdown("""
        ### Comment lire ce terminal ?
        Cet outil utilise le **Z-Score** pour comparer des pays aux structures différentes. Le Z-score indique l'écart à la moyenne sur les 12 dernières années.
        
        1. **Z-Rate (2.0) :** Attraction des capitaux. Plus il est haut, plus la devise est recherchée (Carry Trade).
        2. **Z-PIB (1.5) :** Le moteur économique. Une croissance forte justifie des taux élevés sans risque de récession.
        3. **Z-CPI (1.0) :** La pression inflationniste. Force la banque centrale à rester agressive.
        4. **Z-Liq (-1.0) :** L'impression monétaire. Plus la liquidité augmente, plus la monnaie se dévalue.
        5. **Z-Debt (-0.8) :** Le risque fiscal. Une dette élevée bride la banque centrale et fait fuir les investisseurs de long terme.
        
        **L'Opportunité d'Or :** Une paire avec une divergence élevée (> 3.0) et un Z-Price négatif (Prix bas).
        """)

else:
    st.error("Impossible de charger les données. Vérifiez votre connexion FRED.")
