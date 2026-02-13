import streamlit as st
import pandas as pd
from fredapi import Fred
import plotly.express as px
from datetime import datetime, timedelta
import yfinance as yf

# --- CONFIGURATION DE L'INTERFACE ---
st.set_page_config(page_title="Macro Alpha Terminal Pro", layout="wide")

# Style "Bloomberg Dark Mode"
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 15px; }
    .opp-card { background-color: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 25px; margin-bottom: 20px; }
    .logic-box { background-color: #0d1117; border-left: 4px solid #58a6ff; padding: 15px; margin: 10px 0; border-radius: 4px; color: #c9d1d9; font-size: 0.95em; }
    .hawk-tag { color: #238636; font-weight: bold; background: #23863622; padding: 4px 12px; border-radius: 20px; border: 1px solid #238636; }
    h1, h2, h3 { color: #f0f6fc; font-family: 'Inter', sans-serif; }
    .text-muted { color: #8b949e; font-size: 0.85em; }
    </style>
    """, unsafe_allow_html=True)

# --- API FRED ---
API_KEY = 'f25835309cd5c99504970cd7f417dddd'
try:
    fred = Fred(api_key=API_KEY)
except:
    st.error("Erreur de connexion API FRED.")
    st.stop()

# --- RÉFÉRENTIEL DES SÉRIES G10 (MONÉTAIRE + MACRO + DETTE) ---
central_banks = {
    'USD (Fed)': {'rate': 'FEDFUNDS', 'cpi': 'CPIAUCSL', 'liq': 'WALCL', 'gdp': 'GDPC1', 'debt': 'GFDEGDQ188S', 'symbol': 'USD'},
    'EUR (ECB)': {'rate': 'ECBDFR', 'cpi': 'CP0000EZ19M086NEST', 'liq': 'ECBASSETSW', 'gdp': 'CLVMEURSCAB1GQEU19', 'debt': 'DEBTTG7ZZA188S', 'symbol': 'EUR'},
    'JPY (BoJ)': {'rate': 'IRSTCI01JPM156N', 'cpi': 'JPNCPIALLMINMEI', 'liq': 'JPNASSETS', 'gdp': 'JPNNGDP', 'debt': 'DEBTTGJPZA188S', 'symbol': 'JPY'},
    'GBP (BoE)': {'rate': 'IUDSOIA', 'cpi': 'GBRCPIALLMINMEI', 'liq': 'MANMM101GBM189S', 'gdp': 'UKNGDP', 'debt': 'DEBTTGGBZA188S', 'symbol': 'GBP'},
    'CAD (BoC)': {'rate': 'IRSTCI01CAM156N', 'cpi': 'CANCPIALLMINMEI', 'liq': 'MANMM101CAM189S', 'gdp': 'CANGDP', 'debt': 'DEBTTGCAZA188S', 'symbol': 'CAD'},
    'AUD (RBA)': {'rate': 'IRSTCI01AUM156N', 'cpi': 'AUSCPIALLMINMEI', 'liq': 'MANMM101AUM189S', 'gdp': 'AUSGDP', 'debt': 'DEBTTGAUZA188S', 'symbol': 'AUD'},
    'CHF (SNB)': {'rate': 'IRSTCI01CHM156N', 'cpi': 'CHECPIALLMINMEI', 'liq': 'MABMM301CHM189S', 'gdp': 'CHNGDP', 'debt': 'DEBTTGCHZA188S', 'symbol': 'CHF'},
}

# --- FONCTIONS DE CALCUL ---

def calculate_z_score(series):
    """Calcule l'écart à la moyenne sur l'historique disponible"""
    if series is None or len(series.dropna()) < 5: return 0.0
    clean = series.ffill().dropna()
    return (clean.iloc[-1] - clean.mean()) / clean.std()

@st.cache_data(ttl=86400)
def fetch_all_macro():
    """Récupère et calcule tous les piliers fondamentaux"""
    data_list = []
    # On remonte à 12 ans pour capturer les cycles de dette et de PIB
    start_date = datetime.now() - timedelta(days=365*12)
    
    for currency, codes in central_banks.items():
        row = {'Devise': currency, 'Symbol': codes['symbol'], 'Taux (%)': 0, 
               'Z-Rate': 0, 'Z-CPI': 0, 'Z-Liq': 0, 'Z-PIB': 0, 'Z-Debt': 0, 'Score': 0}
        try:
            # 1. Taux (Monétaire)
            try:
                r = fred.get_series(codes['rate'], observation_start=start_date).ffill()
                row['Taux (%)'] = r.iloc[-1]
                row['Z-Rate'] = calculate_z_score(r)
            except: pass
            
            # 2. CPI (Inflation)
            try:
                c = fred.get_series(codes['cpi'], observation_start=start_date).ffill()
                row['Z-CPI'] = calculate_z_score(c.pct_change(12))
            except: pass
            
            # 3. Liquidité (Masse monétaire ou Bilan)
            try:
                l = fred.get_series(codes['liq'], observation_start=start_date).ffill()
                row['Z-Liq'] = calculate_z_score(l.pct_change(12))
            except: pass
            
            # 4. PIB (Croissance) - Variation annuelle du PIB
            try:
                g = fred.get_series(codes['gdp'], observation_start=start_date).ffill()
                row['Z-PIB'] = calculate_z_score(g.pct_change(4))
            except: pass
            
            # 5. Dette (Dette Publique / PIB)
            try:
                d = fred.get_series(codes['debt'], observation_start=start_date).ffill()
                row['Z-Debt'] = calculate_z_score(d)
            except: pass
            
            # FORMULE DU FONDAMENTAL SCORE
            # (Taux*2) + (Inflation*1) + (Croissance*1.5) - (Impression Monétaire*1) - (Dette*0.8)
            row['Score'] = (row['Z-Rate']*2.0) + (row['Z-CPI']*1.0) + (row['Z-PIB']*1.5) - (row['Z-Liq']*1.0) - (row['Z-Debt']*0.8)
            data_list.append(row)
        except:
            data_list.append(row)
            
    return pd.DataFrame(data_list).sort_values(by='Score', ascending=False)

def get_price_analysis(pair):
    """Analyse technique du prix via Yahoo Finance"""
    try:
        ticker = f"{pair}=X"
        df_p = yf.download(ticker, period="2y", interval="1d", progress=False)
        curr_price = df_p['Close'].iloc[-1].item()
        z_price = (curr_price - df_p['Close'].mean().item()) / df_p['Close'].std().item()
        return round(curr_price, 4), round(z_price, 2)
    except:
        return 0, 0

# --- INTERFACE UTILISATEUR ---

st.title("🏛️ Institutional Fundamental Terminal")
st.markdown(f"**Analyse Macro G10** | Mise à jour : {datetime.now().strftime('%d %B %Y')}")

with st.spinner("Analyse des cycles économiques en cours..."):
    df = fetch_all_macro()

if not df.empty:
    # 1. TABLEAU DE BORD (LEDGER)
    st.header("1. Fundamental Health Ledger")
    st.markdown("Comparaison normalisée (Z-Score) de tous les piliers de puissance d'une devise.")
    
    # Stylisage pro
    st.dataframe(
        df.style.map(lambda x: 'color: #238636; font-weight: bold' if isinstance(x, float) and x > 1.2 else ('color: #da3633; font-weight: bold' if isinstance(x, float) and x < -1.2 else ''), 
                     subset=['Z-Rate', 'Z-CPI', 'Z-PIB', 'Z-Debt', 'Score'])
        .format("{:.2f}", subset=['Taux (%)', 'Z-Rate', 'Z-CPI', 'Z-PIB', 'Z-Debt', 'Score']),
        use_container_width=True
    )

    # 2. VISUALISATION DES CYCLES
    st.divider()
    st.header("2. Market Visualization")
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Cycle Monétaire (Taux vs Inflation)")
        fig1 = px.scatter(df, x="Z-CPI", y="Z-Rate", text="Symbol", size=[20]*len(df), color="Score", color_continuous_scale='RdYlGn', template='plotly_dark')
        fig1.add_hline(y=0, line_dash="dash")
        fig1.add_vline(x=0, line_dash="dash")
        st.plotly_chart(fig1, use_container_width=True)
        
    with c2:
        st.subheader("Santé Structurelle (PIB vs Dette)")
        fig2 = px.scatter(df, x="Z-Debt", y="Z-PIB", text="Symbol", size=[20]*len(df), color="Score", color_continuous_scale='RdYlGn', template='plotly_dark')
        fig2.add_hline(y=0, line_dash="dash")
        fig2.add_vline(x=0, line_dash="dash")
        st.plotly_chart(fig2, use_container_width=True)

    # 3. ANALYSE TACTIQUE (OPPORTUNITÉS)
    st.divider()
    st.header("3. Tactical Opportunities")
    
    # On sélectionne les paires avec le spread le plus élevé
    col_opps = st.columns(2)
    top_hawks = df.iloc[:2]
    top_doves = df.iloc[-2:]
    
    idx = 0
    for _, h in top_hawks.iterrows():
        for _, d in top_doves.iterrows():
            spread = h['Score'] - d['Score']
            pair = f"{h['Symbol']}{d['Symbol']}"
            price, z_price = get_price_analysis(pair)
            
            with col_opps[idx % 2]:
                st.markdown(f"""
                <div class="opp-card">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="font-size: 1.6em; font-weight: bold;">{h['Symbol']} / {d['Symbol']}</span>
                        <span class="hawk-tag">DIVERGENCE : {spread:.2f}</span>
                    </div>
                    <div style="display: flex; gap: 30px; margin-top: 15px;">
                        <div><span class="text-muted">Prix Actuel</span><br><b>{price}</b></div>
                        <div><span class="text-muted">Z-Score Prix (2y)</span><br><b style="color: {'#238636' if z_price < 0 else '#da3633'}">{z_price}</b></div>
                        <div><span class="text-muted">Croissance Relat.</span><br><b>+{h['Z-PIB'] - d['Z-PIB']:.2f}</b></div>
                    </div>
                    <div class="logic-box">
                        <b>LOGIQUE DE CONVICTION :</b><br>
                        • <b>Achat {h['Symbol']} :</b> Soutenu par une croissance (Z-PIB: {h['Z-PIB']:.2f}) qui permet de maintenir des taux élevés.<br>
                        • <b>Vente {d['Symbol']} :</b> Pénalisé par {'un endettement excessif' if d['Z-Debt'] > 1 else 'une économie stagnante'}.<br>
                        • <b>Timing :</b> Le prix est actuellement <b>{'bon marché' if z_price < 0 else 'cher'}</b> par rapport à sa moyenne de 2 ans.
                    </div>
                </div>
                """, unsafe_allow_html=True)
            idx += 1

    # 4. MÉTHODOLOGIE (ÉDUCATION)
    with st.expander("📝 Comprendre la Méthodologie"):
        st.markdown("""
        ### Comment interpréter les scores ?
        Le **Z-Score** indique à combien d'écarts-types la valeur actuelle se situe par rapport à sa moyenne sur 12 ans.
        
        1. **Z-Rate (Taux) :** Mesure si la banque centrale rémunère le capital. Plus il est haut, plus la monnaie est attractive.
        2. **Z-CPI (Inflation) :** Mesure la pression sur les prix. Une inflation haute force la banque centrale à rester agressive.
        3. **Z-PIB (Croissance) :** C'est le moteur. Une forte croissance permet de supporter des taux élevés sans casser l'économie.
        4. **Z-Liq (Liquidité) :** Mesure l'impression monétaire. Plus on injecte de liquidité, plus on dilue la valeur de la monnaie.
        5. **Z-Debt (Dette) :** Mesure le risque fiscal. Une dette qui explose fragilise la monnaie à long terme.
        
        **L'opportunité parfaite :** Acheter une devise avec un Score élevé (Hawk) et un Z-Score de Prix négatif (sous-évalué).
        """)

else:
    st.error("Impossible de charger les données. Vérifiez votre clé API FRED.")
