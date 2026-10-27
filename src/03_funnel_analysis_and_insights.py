from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ==========================================
# CONFIGURACIÓN DE RUTAS DEL PROYECTO
# ==========================================
BASE_DIR = Path(__file__).resolve().parent.parent
CLEAN_DIR = BASE_DIR / "data" / "clean"
ASSETS_DIR = BASE_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

print("=== PASO 3: ANÁLISIS DEL FUNNEL, REVENUE LEAKAGE Y DASHBOARD PNG ===")

# 1. Cargar datos limpios desde data/clean/
accounts = pd.read_csv(CLEAN_DIR / "clean_dim_accounts.csv", parse_dates=["signup_timestamp"])
events = pd.read_csv(CLEAN_DIR / "clean_fact_funnel_events.csv", parse_dates=["event_timestamp"])
kyb = pd.read_csv(CLEAN_DIR / "clean_fact_kyb_verifications.csv", parse_dates=["submitted_at", "resolved_at"])

stages = [
    "account_created",
    "email_verified",
    "kyb_submitted",
    "kyb_approved",
    "bank_linked",
    "first_deposit_completed",
    "first_card_transaction"
]

# 2. Pivotear matriz del funnel a nivel cuenta
funnel_pivot = (
    events[events["event_name"].isin(stages)]
    .pivot(index="account_id", columns="event_name", values="event_timestamp")[stages]
)

device_info = (
    events[events["event_name"] == "account_created"]
    [["account_id", "device_type", "app_version"]]
    .set_index("account_id")
)

bank_method = (
    events[events["event_name"] == "bank_linked"]
    [["account_id", "metadata_status"]]
    .rename(columns={"metadata_status": "bank_link_method"})
    .set_index("account_id")
)

master_df = (
    accounts.set_index("account_id")
    .join(device_info)
    .join(funnel_pivot)
    .join(bank_method)
    .join(kyb.set_index("account_id")[["kyb_vendor", "review_duration_hours", "verification_status", "rejection_reason"]])
)

# Guardar tabla maestra en data/clean/ para consumo rápido en Streamlit
master_df.reset_index().to_csv(CLEAN_DIR / "master_funnel_account_level.csv", index=False)

# 3. Resumen del Funnel y MRR Leakage
funnel_summary = []
total_accounts = len(master_df)
prev_count = total_accounts
prev_mrr = master_df["expected_plan_mrr_usd"].sum()

for idx, stage in enumerate(stages):
    reached_mask = master_df[stage].notna()
    count = int(reached_mask.sum())
    mrr_retained = float(master_df.loc[reached_mask, "expected_plan_mrr_usd"].sum())
    
    overall_conv = (count / total_accounts) * 100
    step_conv = (count / prev_count) * 100 if idx > 0 else 100.0
    step_dropoff = 100.0 - step_conv if idx > 0 else 0.0
    mrr_lost_step = prev_mrr - mrr_retained if idx > 0 else 0.0
    
    if idx > 0:
        prev_stage = stages[idx - 1]
        time_diffs = (master_df[stage] - master_df[prev_stage]).dt.total_seconds() / 3600.0
        median_hours = float(time_diffs.median())
    else:
        median_hours = 0.0
        
    funnel_summary.append({
        "step_num": idx + 1,
        "stage_name": stage,
        "accounts_count": count,
        "overall_conversion_pct": round(overall_conv, 2),
        "step_conversion_pct": round(step_conv, 2),
        "step_dropoff_pct": round(step_dropoff, 2),
        "median_hours_from_prev": round(median_hours, 2),
        "mrr_retained_usd": round(mrr_retained, 2),
        "mrr_lost_at_step_usd": round(mrr_lost_step, 2)
    })
    prev_count = count
    prev_mrr = mrr_retained

funnel_summary_df = pd.DataFrame(funnel_summary)
print("\n--- RESUMEN EJECUTIVO DEL EMBUDO ---")
print(funnel_summary_df.to_string(index=False))

# 4. Métricas de los Cuellos de Botella para Graficar
verified_df = master_df[master_df["email_verified"].notna()].copy()
verified_df["converted_to_kyb"] = verified_df["kyb_submitted"].notna()
insight1 = verified_df.groupby(["device_type", "app_version"]).agg(
    conversion_rate_pct=("converted_to_kyb", lambda s: round(s.mean() * 100, 2))
).reset_index()

kyb_app_df = master_df[master_df["kyb_approved"].notna()].copy()
kyb_app_df["converted_bank"] = kyb_app_df["bank_linked"].notna()
kyb_app_df["sla_bucket"] = pd.cut(
    kyb_app_df["review_duration_hours"],
    bins=[0, 12, 36, 500],
    labels=["1. Fast (<12h)", "2. Medium (12h-36h)", "3. Slow (>36h)"]
)
insight3 = kyb_app_df.groupby("sla_bucket", observed=False).agg(
    bank_link_conv_pct=("converted_bank", lambda s: round(s.mean() * 100, 2)),
    mrr_abandoned_usd=("expected_plan_mrr_usd", lambda s: s[~kyb_app_df.loc[s.index, "converted_bank"]].sum())
).reset_index()

# 5. Generar Dashboard en assets/
plt.rcParams["figure.facecolor"] = "#0F1117"
plt.rcParams["axes.facecolor"] = "#181B24"
plt.rcParams["axes.edgecolor"] = "#303646"
plt.rcParams["text.color"] = "#F0F4F8"
plt.rcParams["axes.labelcolor"] = "#D9E2EC"
plt.rcParams["xtick.color"] = "#BCCCDC"
plt.rcParams["ytick.color"] = "#BCCCDC"

fig, axes = plt.subplots(2, 2, figsize=(16, 11), dpi=140)
fig.suptitle("B2B SaaS Fintech — Product Onboarding Funnel & Revenue Leakage (LATAM 2026)",
             fontsize=16, fontweight="bold", color="#FFFFFF", y=0.97)

# Panel 1
ax1 = axes[0, 0]
stage_labels = ["1. Account Created", "2. Email Verified", "3. KYB Submitted", "4. KYB Approved",
                "5. Bank Linked", "6. First Deposit", "7. Card Activated"]
counts = funnel_summary_df["accounts_count"].values[::-1]
pcts = funnel_summary_df["overall_conversion_pct"].values[::-1]
colors_1 = ["#FF3B5C" if x in ["3. KYB Submitted", "4. KYB Approved"] else "#FF9F1C" if x == "7. Card Activated" else "#3B82F6" for x in stage_labels[::-1]]
bars1 = ax1.barh(stage_labels[::-1], counts, color=colors_1, height=0.62)
ax1.set_title("1. Embudo General de Activación B2B", fontsize=12, fontweight="bold", color="#FF9F1C")
ax1.set_xlim(0, 10200)
for bar, pct, cnt in zip(bars1, pcts, counts):
    ax1.text(bar.get_width() + 180, bar.get_y() + bar.get_height()/2, f"{cnt:,} ({pct:.1f}%)", va="center", fontweight="bold")

# Panel 2
ax2 = axes[0, 1]
insight1["segment"] = insight1["device_type"] + " (" + insight1["app_version"] + ")"
insight1 = insight1.sort_values("conversion_rate_pct", ascending=True)
colors_2 = ["#FF3B5C" if "v2.4.2-buggy" in s and "Android" in s else "#486581" for s in insight1["segment"]]
bars2 = ax2.barh(insight1["segment"], insight1["conversion_rate_pct"], color=colors_2, height=0.58)
ax2.set_title("2. Conversión a KYB Submitted por Versión de App", fontsize=12, fontweight="bold", color="#FF3B5C")
ax2.set_xlim(0, 100)
for bar, val in zip(bars2, insight1["conversion_rate_pct"]):
    ax2.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2, f"{val:.1f}%", va="center", fontweight="bold")

# Panel 3
ax3 = axes[1, 0]
sla_labels = ["Rápido (<12h)\n[IdentityFlow AI]", "Medio (12h–36h)\n[Mixto]", "Lento (>36h)\n[LegacyCheck LATAM]"]
bars3 = ax3.bar(sla_labels, insight3["bank_link_conv_pct"].values, color=["#10B981", "#F59E0B", "#FF3B5C"], width=0.5)
ax3.set_title("3. Impacto del SLA de KYB en Vinculación Bancaria", fontsize=12, fontweight="bold", color="#F59E0B")
ax3.set_ylim(0, 105)
for bar, val, mrr_lost in zip(bars3, insight3["bank_link_conv_pct"].values, insight3["mrr_abandoned_usd"].values):
    ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2.5, f"{val:.1f}%\n(-${mrr_lost:,.0f} MRR)", ha="center", fontweight="bold")

# Panel 4
ax4 = axes[1, 1]
drop_stages = ["2. Verify Email", "3. Submit KYB", "4. Approve KYB", "5. Link Bank", "6. First Deposit", "7. Card Spend"]
mrr_lost_vals = funnel_summary_df["mrr_lost_at_step_usd"].values[1:] / 1000.0
colors_4 = ["#FF3B5C" if v > 160 else "#FF9F1C" if v > 80 else "#3B82F6" for v in mrr_lost_vals]
bars4 = ax4.bar(drop_stages, mrr_lost_vals, color=colors_4, width=0.55)
ax4.set_title("4. Fuga de MRR Potencial por Etapa ($K USD)", fontsize=12, fontweight="bold", color="#FF9F1C")
ax4.set_ylim(0, 215)
ax4.tick_params(axis="x", rotation=20)
for bar, val in zip(bars4, mrr_lost_vals):
    ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 4, f"${val:,.1f}K", ha="center", fontweight="bold")

plt.tight_layout(rect=[0, 0.01, 1, 0.94])
output_img = ASSETS_DIR / "saas_fintech_funnel_executive_dashboard.png"
plt.savefig(output_img, dpi=140)
plt.close()
print(f"\n[OK] Gráfico exportado exitosamente en: {output_img}\n")