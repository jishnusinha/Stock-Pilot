from app.services.seed import seed_demo
from app.db import repositories as repo


def test_seed_demo_deterministic(tmp_db):
    a = seed_demo(tmp_db, products=20, days=60, seed=42)
    n1 = repo.count_products(tmp_db)
    sales1 = tmp_db.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    seed_demo(tmp_db, products=20, days=60, seed=42)
    n2 = repo.count_products(tmp_db)
    sales2 = tmp_db.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    assert a["products"] == 20
    assert n1 == n2 == 20
    assert sales1 == sales2 == 20 * 60
