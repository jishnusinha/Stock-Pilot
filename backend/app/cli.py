"""StockPilot CLI — python -m app.cli"""

from __future__ import annotations

import argparse
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
from app.services.inventory_history import build_analytics
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

    bp = sub.add_parser("bootstrap")
    bp.add_argument("--products", type=int, default=200)
    bp.add_argument("--days", type=int, default=365)
    bp.add_argument("--seed", type=int, default=settings.seed)
    bp.add_argument("--threads", type=int, default=settings.threads)
    bp.add_argument("--fast", action="store_true")
    bp.add_argument("--force", action="store_true")
    bp.set_defaults(func=cmd_bootstrap)

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
