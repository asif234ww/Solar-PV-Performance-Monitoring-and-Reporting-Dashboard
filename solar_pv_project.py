"""
Solar PV Performance Monitoring and Reporting
---------------------------------------------
Run on REAL data (Kaggle "Solar Power Generation Data", Plant 1 files):
    python solar_pv_project.py --gen Plant_1_Generation_Data.csv --weather Plant_1_Weather_Sensor_Data.csv
Run a DEMO on synthetic data (to test the code only, never report demo numbers as real results):
    python solar_pv_project.py --demo
Outputs go to ./output_solar/
"""
import argparse, os
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FAULT_DAY_RATIO = 0.80      
UNDERPERFORM_RATIO = 0.90   
def load_demo(seed=2):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-05-15", periods=34 * 96, freq="15min")
    sun = np.clip(np.sin((idx.hour + idx.minute / 60 - 6) / 12 * np.pi), 0, None)
    cloud = np.repeat(rng.uniform(0.6, 1.0, 34), 96)
    irr = sun * cloud * 1.0
    w = pd.DataFrame({"DATE_TIME": idx, "AMBIENT_TEMPERATURE": 25 + 8 * sun, "MODULE_TEMPERATURE": 27 + 20 * sun, "IRRADIATION": irr})
    rows = []
    for i in range(22):
        k = f"INV{i+1:02d}"; f = 0.78 if i in (4, 13) else rng.normal(1, 0.02)
        dc = irr * 12000 * f * rng.normal(1, 0.03, len(idx)); ac = dc * 0.097
        df = pd.DataFrame({"DATE_TIME": idx, "SOURCE_KEY": k, "DC_POWER": dc, "AC_POWER": ac})
        df["DAILY_YIELD"] = df.groupby(df.DATE_TIME.dt.date).AC_POWER.cumsum() * 0.25
        df = df.drop(df.sample(frac=0.02, random_state=i).index)       
        df.loc[df.sample(frac=0.003, random_state=i + 50).index, "AC_POWER"] = -5   
        rows.append(df)
    return pd.concat(rows, ignore_index=True), w

def load_real(gen, weather):
    g = pd.read_csv(gen); w = pd.read_csv(weather)
    g["DATE_TIME"] = pd.to_datetime(g["DATE_TIME"], dayfirst=True)  
    w["DATE_TIME"] = pd.to_datetime(w["DATE_TIME"])
    return g, w

def clean(g, w):
    log = {"rows_in": len(g), "faulty_negative": int((g.AC_POWER < 0).sum()), "duplicates": int(g.duplicated(["DATE_TIME", "SOURCE_KEY"]).sum())}
    g = g.drop_duplicates(["DATE_TIME", "SOURCE_KEY"]).copy()
    g.loc[g.AC_POWER < 0, "AC_POWER"] = np.nan
    g = g.dropna(subset=["AC_POWER"])
    full = g.DATE_TIME.nunique() * g.SOURCE_KEY.nunique()
    log["missing_timestamp_slots"] = int(full - len(g))
    m = g.merge(w[["DATE_TIME", "IRRADIATION", "MODULE_TEMPERATURE"]].drop_duplicates("DATE_TIME"), on="DATE_TIME", how="left")
    return m, log

def analyse(m):
    m["date"] = m.DATE_TIME.dt.date
    day = m.groupby(["SOURCE_KEY", "date"]).DAILY_YIELD.max().reset_index()
    day["date"] = pd.to_datetime(day["date"])
    peak = m[m.DC_POWER > m.DC_POWER.quantile(0.5)]
    eff = (peak.groupby("SOURCE_KEY").AC_POWER.sum() / peak.groupby("SOURCE_KEY").DC_POWER.sum() * 100).rename("efficiency_pct")
    inv = day.groupby("SOURCE_KEY").DAILY_YIELD.mean().rename("mean_daily_yield_kwh").to_frame().join(eff).reset_index()
    med = inv.mean_daily_yield_kwh.median()
    inv["vs_fleet_median_pct"] = (inv.mean_daily_yield_kwh / med - 1) * 100
    inv["underperforming"] = inv.mean_daily_yield_kwh < UNDERPERFORM_RATIO * med
    ndays = day.date.nunique()
    inv["lost_kwh_period"] = np.where(inv.underperforming, (med - inv.mean_daily_yield_kwh) * ndays, 0.0)
    return day, inv.sort_values("mean_daily_yield_kwh"), med

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen"); ap.add_argument("--weather"); ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    g, w = load_demo() if a.demo else load_real(a.gen, a.weather)
    m, log = clean(g, w); day, inv, med = analyse(m)
    out = "output_solar"; os.makedirs(out, exist_ok=True)
    day.to_csv(f"{out}/daily_yield_by_inverter.csv", index=False); inv.to_csv(f"{out}/inverter_summary.csv", index=False)

    tot = day.groupby("date").DAILY_YIELD.sum()
    fig, ax = plt.subplots(figsize=(9, 4)); ax.plot(tot.index, tot / 1000, color="#1F3864", marker="o", ms=3)
    ax.set(title="Total daily plant generation", ylabel="MWh/day"); fig.autofmt_xdate()
    fig.tight_layout(); fig.savefig(f"{out}/daily_generation.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4)); cols = np.where(inv.underperforming, "red", "#1F3864")
    ax.bar(inv.SOURCE_KEY.astype(str).str[-6:], inv.mean_daily_yield_kwh, color=cols); ax.axhline(med, color="grey", ls="--", label="Fleet median")
    ax.set(title="Mean daily yield per inverter (red = underperforming)", ylabel="kWh/day"); ax.legend(); plt.xticks(rotation=70, fontsize=7)
    fig.tight_layout(); fig.savefig(f"{out}/inverter_yield.png", dpi=130); plt.close(fig)

    s = m.dropna(subset=["IRRADIATION"]).sample(min(20000, len(m)), random_state=1)
    fig, ax = plt.subplots(figsize=(6, 4)); ax.scatter(s.IRRADIATION, s.AC_POWER, s=2, alpha=0.3)
    ax.set(title="AC power vs irradiation", xlabel="Irradiation", ylabel="AC power"); fig.tight_layout(); fig.savefig(f"{out}/power_vs_irradiation.png", dpi=130); plt.close(fig)

    u = inv[inv.underperforming]
    
    day["day_median"] = day.groupby("date").DAILY_YIELD.transform("median")
    fd = day[(day.DAILY_YIELD < FAULT_DAY_RATIO * day.day_median) & (day.day_median > 1000)].copy()
    fd["lost_kwh"] = fd.day_median - fd.DAILY_YIELD
    fd.sort_values("lost_kwh", ascending=False).to_csv(f"{out}/low_output_inverter_days.csv", index=False)
    low = inv.iloc[0]
    summary = [f"Mode: {'DEMO (synthetic data)' if a.demo else 'REAL data'}",
               f"Rows read: {log['rows_in']:,} | faulty (negative) readings: {log['faulty_negative']:,} | duplicates: {log['duplicates']:,} | missing timestamp slots: {log['missing_timestamp_slots']:,}",
               f"Inverters: {len(inv)} | days: {day.date.nunique()} | fleet median yield: {med:,.0f} kWh/day",
               f"Underperforming inverters (<{UNDERPERFORM_RATIO:.0%} of median): {len(u)} -> {', '.join(u.SOURCE_KEY.astype(str))}",
               f"Estimated lost output over the period: {u.lost_kwh_period.sum():,.0f} kWh",
               f"Lowest inverter: {low.SOURCE_KEY} at {low.vs_fleet_median_pct:+.1f}% vs fleet median",
               f"Low-output inverter-days (<{FAULT_DAY_RATIO:.0%} of that day's median): {len(fd)} across {fd.SOURCE_KEY.nunique()} inverters | estimated lost output: {fd.lost_kwh.sum():,.0f} kWh"]
    open(f"{out}/summary.txt", "w").write("\n".join(summary)); print("\n".join(summary))

if __name__ == "__main__":
    main()