from app.db.connection import connect
from app.db import repositories as repo

conn = connect()
print("risk product 1", dict(conn.execute("SELECT * FROM product_risk_cache WHERE product_id=1").fetchone() or {}))
print("high sample:")
for r in conn.execute(
    """
    SELECT p.id, p.sku, p.stock_on_hand, c.days_of_supply, c.risk_level, r.suggested_qty
    FROM product_risk_cache c
    JOIN products p ON p.id=c.product_id
    LEFT JOIN recommendations r ON r.product_id=p.id AND r.status='open'
    WHERE c.risk_level='high'
    ORDER BY c.days_of_supply ASC
    LIMIT 5
    """
).fetchall():
    print(dict(r))
print("open recs top:")
for r in repo.get_open_recommendations(conn, 5):
    print(r["id"], r["sku"], r.get("risk_level"), r.get("days_of_supply"), r["suggested_qty"])
conn.close()
