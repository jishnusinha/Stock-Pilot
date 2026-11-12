import httpx

base = "http://127.0.0.1:8000"
d = httpx.get(f"{base}/api/dashboard").json()
print(
    "at_risk",
    d["kpis"]["at_risk_products"],
    "alerts",
    len(d["alerts"]),
    "top_risk",
    len(d["top_risk"]),
    "rec_qty",
    (d.get("recommendation") or {}).get("suggested_qty"),
)
print("rec", d.get("recommendation"))
