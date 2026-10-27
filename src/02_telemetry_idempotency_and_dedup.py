from pathlib import Path
import pandas as pd

# ==========================================
# CONFIGURACIÓN DE RUTAS DEL PROYECTO
# ==========================================
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
CLEAN_DIR = BASE_DIR / "data" / "clean"

print("=== PASO 2: IDEMPOTENCIA Y DEDUPLICACIÓN DE TELEMETRÍA ===")

# 1. Cargar telemetría cruda y padrón limpio de cuentas
events_raw = pd.read_csv(RAW_DIR / "fact_funnel_events.csv")
accounts_clean = pd.read_csv(CLEAN_DIR / "clean_dim_accounts.csv")

events_raw["event_timestamp"] = pd.to_datetime(events_raw["event_timestamp"])
valid_account_ids = set(accounts_clean["account_id"])

# 2. Filtrar eventos de cuentas de QA (Integridad Referencial)
events_valid_accounts = events_raw[events_raw["account_id"].isin(valid_account_ids)].copy()
qa_events_removed = len(events_raw) - len(events_valid_accounts)

# 3. Auditar colisiones antes de deduplicar
dup_count = events_valid_accounts.duplicated(subset=["account_id", "event_name"], keep="first").sum()
print(f"[!] Eventos de cuentas QA eliminados: {qa_events_removed}")
print(f"[!] Eventos duplicados por reintento de red detectados: {dup_count}")

# 4. Deduplicación determinística conservando el primer timestamp (MIN)
events_dedup = (
    events_valid_accounts
    .sort_values(by=["account_id", "event_name", "event_timestamp"], ascending=[True, True, True])
    .drop_duplicates(subset=["account_id", "event_name"], keep="first")
    .reset_index(drop=True)
)

# 5. Data Quality Gates (Validaciones de producción)
assert events_dedup.duplicated(subset=["account_id", "event_name"]).sum() == 0, \
    "ERROR: Aún existen eventos duplicados."
assert (events_dedup["metadata_status"] == "success_retry_duplicate").sum() == 0, \
    "ERROR: Quedaron registros con flag success_retry_duplicate."

# 6. Guardar en data/clean/
events_dedup.to_csv(CLEAN_DIR / "clean_fact_funnel_events.csv", index=False)
print(f"[OK] clean_fact_funnel_events.csv guardado con éxito ({len(events_dedup):,} eventos únicos)\n")