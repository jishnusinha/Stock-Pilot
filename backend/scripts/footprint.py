from pathlib import Path

root = Path(__file__).resolve().parents[2]


def du(p: Path) -> int:
    if not p.exists():
        return 0
    total = 0
    for f in p.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total


print("venv_mb", round(du(root / "backend" / ".venv") / 1e6, 1))
print("node_mb", round(du(root / "frontend" / "node_modules") / 1e6, 1))
print("db_mb", round((root / "backend" / "data" / "stockpilot.db").stat().st_size / 1e6, 2))
print("models_mb", round(du(root / "backend" / "artifacts" / "models") / 1e6, 2))
print("frontend_dist_mb", round(du(root / "frontend" / "dist") / 1e6, 2))
