"""Command line entry point: ``python -m aos.cli run|report <path>``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="aos")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="execute an experiment config")
    r.add_argument("config", type=Path)
    r.add_argument("--out", type=Path, default=None)
    r.add_argument("--workers", type=int, default=None)

    p = sub.add_parser("report", help="build tables and figures from results")
    p.add_argument("results", type=Path)
    p.add_argument("--out", type=Path, default=None)

    args = ap.parse_args(argv)

    if args.cmd == "run":
        from .runner import ExperimentConfig, run_experiment

        cfg = ExperimentConfig.load(args.config)
        out = args.out or Path("results") / cfg.name
        run_experiment(cfg, out, workers=args.workers)
        return 0

    from .report import build_report

    build_report(args.results, args.out or args.results / "report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
