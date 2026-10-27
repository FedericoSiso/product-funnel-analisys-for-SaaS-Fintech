from pathlib import Path
import pandas as pd

# ==========================================
# CONFIGURACIÓN DE RUTAS DEL PROYECTO
# ==========================================
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
CLEAN_DIR = BASE_DIR / "data" / "clean"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

# 1. Carga de datos crudos desde data/raw/
accounts_raw = pd.read_csv(RAW_DIR / "dim_accounts.csv")
kyb_raw = pd.read_csv(RAW_DIR / "fact_kyb_verifications.csv")
tx_raw = pd.read_csv(RAW_DIR / "fact_onboarding_transactions.csv")

print("=== PASO 1: AUDITORÍA Y LIMPIEZA DE DIMENSIONES Y TRANSACCIONES ===")

# 2. Identificar cuentas internas de QA para aislamiento en cascada
qa_mask = accounts_raw["admin_email"].str.contains("fintech-internal-qa.io", case=False, na=False)
qa_account_ids = set(accounts_raw.loc[qa_mask, "account_id"])
print(f"[!] Cuentas internas de QA detectadas y aisladas: {len(qa_account_ids)}")

accounts_clean = accounts_raw[~accounts_raw["account_id"].isin(qa_account_ids)].copy()

# 3. Normalizar country_code a estándar ISO-2
country_mapping = {
    "MX": "MX", "mx": "MX", "Mexico": "MX",
    "BR": "BR", "br": "BR", "Brazil": "BR",
    "CO": "CO", "co": "CO", "Colombia": "CO",
    "AR": "AR", "ar": "AR", "Argentina": "AR",
    "CL": "CL", "cl": "CL", "Chile": "CL",
    "PE": "PE", "pe": "PE", "Peru": "PE"
}
accounts_clean["country_code"] = (
    accounts_clean["country_code"]
    .astype(str).str.strip()
    .map(country_mapping)
    .fillna("UNKNOWN")
)

# 4. Estandarizar canales de adquisición sin atribución
accounts_clean["acquisition_channel"] = (
    accounts_clean["acquisition_channel"]
    .replace({"(not set)": "Unattributed / Direct", "unknown": "Unattributed / Direct"})
    .fillna("Unattributed / Direct")
)
accounts_clean["signup_timestamp"] = pd.to_datetime(accounts_clean["signup_timestamp"])

# 5. Limpiar KYB y Transacciones en cascada (excluir QA)
kyb_clean = kyb_raw[~kyb_raw["account_id"].isin(qa_account_ids)].copy()
kyb_clean["submitted_at"] = pd.to_datetime(kyb_clean["submitted_at"])
kyb_clean["resolved_at"] = pd.to_datetime(kyb_clean["resolved_at"])
kyb_clean["rejection_reason"] = kyb_clean["rejection_reason"].fillna("APPROVED_NO_REJECTION")

tx_clean = tx_raw[~tx_raw["account_id"].isin(qa_account_ids)].copy()
tx_clean["transaction_timestamp"] = pd.to_datetime(tx_clean["transaction_timestamp"])

# 6. Guardar en data/clean/
accounts_clean.to_csv(CLEAN_DIR / "clean_dim_accounts.csv", index=False)
kyb_clean.to_csv(CLEAN_DIR / "clean_fact_kyb_verifications.csv", index=False)
tx_clean.to_csv(CLEAN_DIR / "clean_fact_onboarding_transactions.csv", index=False)

print(f"[OK] clean_dim_accounts.csv guardado ({len(accounts_clean):,} filas)")
print(f"[OK] clean_fact_kyb_verifications.csv guardado ({len(kyb_clean):,} filas)")
print(f"[OK] clean_fact_onboarding_transactions.csv guardado ({len(tx_clean):,} filas)\n")