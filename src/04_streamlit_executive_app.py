from pathlib import Path
import streamlit as st
import pandas as pd

# ==========================================
# CONFIGURACIÓN DE RUTAS DEL PROYECTO
# ==========================================
BASE_DIR = Path(__file__).resolve().parent.parent
CLEAN_DIR = BASE_DIR / "data" / "clean"
ASSETS_DIR = BASE_DIR / "assets"

st.set_page_config(
    page_title="B2B SaaS Fintech Funnel",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ B2B SaaS Fintech — Product Onboarding & Revenue Leakage")
st.markdown("Análisis interactivo del embudo de activación B2B, fricciones regulatorias KYB y fuga de MRR en LATAM.")

@st.cache_data
def load_clean_data():
    master = pd.read_csv(CLEAN_DIR / "master_funnel_account_level.csv")
    return master

master_df = load_clean_data()

# Filtros laterales
st.sidebar.header("🔍 Filtros de Segmentación")
countries = ["Todos"] + sorted(master_df["country_code"].unique().tolist())
selected_country = st.sidebar.selectbox("País (ISO-2)", countries)

channels = ["Todos"] + sorted(master_df["acquisition_channel"].unique().tolist())
selected_channel = st.sidebar.selectbox("Canal de Adquisición", channels)

filtered_df = master_df.copy()
if selected_country != "Todos":
    filtered_df = filtered_df[filtered_df["country_code"] == selected_country]
if selected_channel != "Todos":
    filtered_df = filtered_df[filtered_df["acquisition_channel"] == selected_channel]

# KPIs Principales
total_acc = len(filtered_df)
activated_acc = filtered_df["first_card_transaction"].notna().sum()
activation_rate = (activated_acc / total_acc * 100) if total_acc > 0 else 0.0
total_mrr = filtered_df["expected_plan_mrr_usd"].sum()
activated_mrr = filtered_df.loc[filtered_df["first_card_transaction"].notna(), "expected_plan_mrr_usd"].sum()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Cuentas B2B (Limpio)", f"{total_acc:,}")
col2.metric("Cuentas Activadas (North Star)", f"{activated_acc:,}", f"{activation_rate:.1f}% conv.")
col3.metric("MRR Potencial Total", f"${total_mrr:,.0f} USD")
col4.metric("MRR Capturado (Activo)", f"${activated_mrr:,.0f} USD", f"-${total_mrr - activated_mrr:,.0f} Leakage")

# Tabla interactiva del Funnel para el segmento seleccionado
st.subheader("📊 Conversión Paso a Paso del Segmento Seleccionado")
stages = [
    ("1. Account Created", "account_created"),
    ("2. Email Verified", "email_verified"),
    ("3. KYB Submitted", "kyb_submitted"),
    ("4. KYB Approved", "kyb_approved"),
    ("5. Bank Linked", "bank_linked"),
    ("6. First Deposit", "first_deposit_completed"),
    ("7. Card Activated", "first_card_transaction")
]

rows = []
prev_c = total_acc
for label, col in stages:
    c = int(filtered_df[col].notna().sum())
    mrr_s = float(filtered_df.loc[filtered_df[col].notna(), "expected_plan_mrr_usd"].sum())
    rows.append({
        "Etapa": label,
        "Cuentas": c,
        "Conversión Acumulada (%)": round((c / total_acc * 100), 2) if total_acc > 0 else 0,
        "Conversión del Paso (%)": round((c / prev_c * 100), 2) if prev_c > 0 else 0,
        "MRR Retenido (USD)": f"${mrr_s:,.2f}"
    })
    prev_c = c

st.dataframe(pd.DataFrame(rows), use_container_width=True)

# Mostrar imagen ejecutiva desde assets/
dashboard_img = ASSETS_DIR / "saas_fintech_funnel_executive_dashboard.png"
if dashboard_img.exists():
    st.subheader("📈 Executive Overview (Full Dataset Benchmark)")
    st.image(str(dashboard_img), use_container_width=True)