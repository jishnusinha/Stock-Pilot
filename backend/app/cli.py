"""StockPilot CLI — python -m app.cli"""

from __future__ import annotations

import argparse
import json
import os
import sys

# config sets OMP/BLAS thread env
from app.core.config import settings
from app.db.connection import connect
from app.db.migrations import migrate
from app.db import repositories as repo
from app.agents.base import TrainContext
from app.agents.registry import AGENT_ORDER, get_agent, train_all
from app.ml import artifacts
from app.services.bootstrap import bootstrap, reset_demo
from app.services.inventory_history import analytics_status, build_analytics
from app.services.performance import evaluate_all
from app.services.seed import seed_demo


def _set_threads(n: int) -> None:
    n = max(1, min(2, int(n)))
    os.environ["STOCKPILOT_THREADS"] = str(n)
    os.environ["OMP_NUM_THREADS"] = str(n)
    settings.threads = n


def cmd_seed(args: argparse.Namespace) -> int:
    conn = connect()
    migrate(conn)
    info = seed_demo(
        conn,
        products=args.products,
        days=args.days,
        seed=args.seed,
        as_of=args.as_of,
    )
    conn.close()
    print(info)
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    reset_demo(confirm=args.confirm)
    print("Demo reset complete.")
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    _set_threads(args.threads)
    conn = connect()
    migrate(conn)
    ctx = TrainContext(conn=conn, fast=args.fast, threads=args.threads)
    if args.agent:
        res = get_agent(args.agent).train(ctx)
        print(res)
    else:
        results = train_all(ctx)
        for r in results:
            print(r.agent_name, r.status, r.model_version)
    conn.commit()
    conn.close()
    return 0


def cmd_model_status(_args: argparse.Namespace) -> int:
    arts = artifacts.list_agent_artifacts()
    versions = repo.list_model_versions(connect())
    print(f"Artifacts on disk: {len(arts)}")
    for a in arts:
        print(f"  {a['agent_name']} @ {a['version']}")
    print(f"DB model_versions: {len(versions)}")
    return 0


def cmd_evaluate(_args: argparse.Namespace) -> int:
    conn = connect()
    migrate(conn)
    payload = evaluate_all(conn)
    conn.close()
    print(payload)
    return 0


def cmd_analytics_status(args: argparse.Namespace) -> int:
    conn = connect()
    migrate(conn)
    try:
        payload = analytics_status(conn, seed=args.seed)
    finally:
        conn.close()
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("freshness") != "missing" else 0


def cmd_policy_replay(args: argparse.Namespace) -> int:
    from app.services.policy_replay import write_expanded_replay

    _set_threads(args.threads)
    conn = connect()
    migrate(conn)
    try:
        payload = write_expanded_replay(conn, sample=args.sample, seed=args.seed)
    finally:
        conn.close()
    print(json.dumps({k: v for k, v in payload.items() if k != "rows"}, indent=2))
    return 0


def cmd_build_analytics(args: argparse.Namespace) -> int:
    conn = connect()
    migrate(conn)
    try:
        info = build_analytics(conn, seed=args.seed, force=args.force)
    except ValueError as exc:
        print(exc)
        return 1
    finally:
        conn.close()
    print(info)
    return 0


def cmd_bootstrap(args: argparse.Namespace) -> int:
    _set_threads(args.threads)
    payload = bootstrap(
        products=args.products,
        days=args.days,
        seed=args.seed,
        threads=args.threads,
        fast=args.fast,
        force=args.force,
    )
    print(payload)
    return 0


def cmd_real_data_download(args: argparse.Namespace) -> int:
    from app.real_data.download import download_official, import_local_xlsx, write_download_sidecar

    try:
        if args.path:
            info = import_local_xlsx(args.path, force=args.force)
        else:
            info = download_official(force=args.force)
        write_download_sidecar(info)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(info, indent=2))
    return 0


def cmd_real_data_prepare(args: argparse.Namespace) -> int:
    from app.real_data.pipeline import prepare

    try:
        payload = prepare(max_products=args.max_products, seed=args.seed)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({k: v for k, v in payload.items() if k != "splits"} | {
        "splits": {
            "boundaries": payload["splits"].get("boundaries"),
            "n_selected": payload["splits"].get("sku_selection", {}).get("n_selected"),
            "train_rows": payload["splits"].get("train", {}).get("rows"),
            "validation_rows": payload["splits"].get("validation", {}).get("rows"),
            "test_rows": payload["splits"].get("test", {}).get("rows"),
        }
    }, indent=2, default=str))
    return 0


def cmd_real_data_train(args: argparse.Namespace) -> int:
    from app.real_data.train import train_models

    _set_threads(args.threads)
    try:
        meta = train_models(threads=args.threads, seed=args.seed, fast=args.fast)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "model_version": meta.get("model_version"),
        "n_train_rows": meta.get("n_train_rows"),
        "n_validation_rows": meta.get("n_validation_rows"),
        "demand_metrics": meta.get("demand_metrics"),
        "trained_at": meta.get("trained_at"),
        "models_dir": str(__import__("app.real_data.paths", fromlist=["MODELS_DIR"]).MODELS_DIR),
    }, indent=2))
    return 0


def cmd_real_data_evaluate(_args: argparse.Namespace) -> int:
    from app.real_data.evaluate import evaluate

    try:
        payload = evaluate()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "ml": payload.get("ml"),
        "baselines": payload.get("baselines"),
        "interval": payload.get("interval"),
        "best_wape_method": payload.get("best_wape_method"),
        "n_test_rows": payload.get("n_test_rows"),
        "evaluation_mode": payload.get("evaluation_mode"),
    }, indent=2))
    return 0


def cmd_real_data_status(_args: argparse.Namespace) -> int:
    from app.real_data.pipeline import status

    print(json.dumps(status(), indent=2))
    return 0


def cmd_real_data_all(args: argparse.Namespace) -> int:
    from app.real_data.pipeline import run_all

    _set_threads(args.threads)
    try:
        payload = run_all(
            max_products=args.max_products,
            seed=args.seed,
            threads=args.threads,
            fast=args.fast,
            force_download=args.force,
            skip_download=args.skip_download,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    summary = {
        "download_status": (payload.get("download") or {}).get("status"),
        "selected_skus": payload.get("prepare", {}).get("splits", {}).get("sku_selection", {}).get("n_selected"),
        "ml": (payload.get("evaluate") or {}).get("ml"),
        "best_wape_method": (payload.get("evaluate") or {}).get("best_wape_method"),
        "ready_for_ui": (payload.get("status") or {}).get("ready_for_ui"),
    }
    print(json.dumps(summary, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="stockpilot")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("seed")
    sp.add_argument("--products", type=int, default=200)
    sp.add_argument("--days", type=int, default=365)
    sp.add_argument("--seed", type=int, default=settings.seed)
    sp.add_argument("--as-of", default=settings.demo_date)
    sp.set_defaults(func=cmd_seed)

    rp = sub.add_parser("reset-demo")
    rp.add_argument("--confirm", action="store_true")
    rp.set_defaults(func=cmd_reset)

    tp = sub.add_parser("train")
    tp.add_argument("--all", action="store_true")
    tp.add_argument("--agent", choices=AGENT_ORDER)
    tp.add_argument("--fast", action="store_true")
    tp.add_argument("--threads", type=int, default=settings.threads)
    tp.set_defaults(func=cmd_train)

    sub.add_parser("model-status").set_defaults(func=cmd_model_status)
    sub.add_parser("evaluate").set_defaults(func=cmd_evaluate)

    ap = sub.add_parser("build-analytics")
    ap.add_argument("--seed", type=int, default=settings.seed)
    ap.add_argument("--force", action="store_true")
    ap.set_defaults(func=cmd_build_analytics)

    st = sub.add_parser("analytics-status")
    st.add_argument("--seed", type=int, default=None)
    st.set_defaults(func=cmd_analytics_status)

    pp = sub.add_parser("policy-replay")
    pp.add_argument("--sample", type=int, default=50)
    pp.add_argument("--seed", type=int, default=settings.seed)
    pp.add_argument("--threads", type=int, default=settings.threads)
    pp.set_defaults(func=cmd_policy_replay)

    bp = sub.add_parser("bootstrap")
    bp.add_argument("--products", type=int, default=200)
    bp.add_argument("--days", type=int, default=365)
    bp.add_argument("--seed", type=int, default=settings.seed)
    bp.add_argument("--threads", type=int, default=settings.threads)
    bp.add_argument("--fast", action="store_true")
    bp.add_argument("--force", action="store_true")
    bp.set_defaults(func=cmd_bootstrap)

    rdd = sub.add_parser("real-data-download", help="Download or import official UCI Online Retail XLSX")
    rdd.add_argument("--path", default=None, help="Optional local official XLSX to import")
    rdd.add_argument("--force", action="store_true")
    rdd.set_defaults(func=cmd_real_data_download)

    rdp = sub.add_parser("real-data-prepare", help="Clean, aggregate, and chronologically split real data")
    rdp.add_argument("--max-products", type=int, default=100)
    rdp.add_argument("--seed", type=int, default=42)
    rdp.set_defaults(func=cmd_real_data_prepare)

    rdt = sub.add_parser("real-data-train", help="Train REAL_RETAIL_UCI models (isolated artifacts)")
    rdt.add_argument("--threads", type=int, default=settings.threads)
    rdt.add_argument("--seed", type=int, default=42)
    rdt.add_argument("--fast", action="store_true")
    rdt.set_defaults(func=cmd_real_data_train)

    sub.add_parser("real-data-evaluate", help="Evaluate real-data models vs baselines on holdout").set_defaults(
        func=cmd_real_data_evaluate
    )
    sub.add_parser("real-data-status", help="Show real-data experiment readiness").set_defaults(
        func=cmd_real_data_status
    )

    rda = sub.add_parser("real-data-all", help="Download → prepare → train → evaluate")
    rda.add_argument("--max-products", type=int, default=100)
    rda.add_argument("--seed", type=int, default=42)
    rda.add_argument("--threads", type=int, default=settings.threads)
    rda.add_argument("--fast", action="store_true")
    rda.add_argument("--force", action="store_true", help="Re-download raw workbook")
    rda.add_argument("--skip-download", action="store_true")
    rda.set_defaults(func=cmd_real_data_all)

    return p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "cmd", None) == "train" and not args.all and not args.agent:
        parser.error("train requires --all or --agent")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
