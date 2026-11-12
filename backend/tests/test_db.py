from app.db.migrations import migrate
from app.db import repositories as repo


def test_migrate_and_product_count(tmp_db):
    assert repo.count_products(tmp_db) == 0
    migrate(tmp_db)
    assert tmp_db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()


def test_suppliers_table_exists(tmp_db):
    tables = {r[0] for r in tmp_db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "products" in tables
    assert "sales" in tables
