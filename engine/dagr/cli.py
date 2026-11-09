#!/usr/bin/env python3
"""dagr command line. Run as `python -B engine/dagr/cli.py <cmd>` (no install) or
`python -m dagr.cli <cmd>` with `engine/` on the path.

    scan | ports | doctor | plan | go | run | status | apply | uninstall

Exit codes: 0 ok, 1 doctor found errors, 2 refused or invalid input, 3 another runner is
active, 4 run stuck, 5 run finished with held or failed tickets (--strict-exit only).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if __package__ in (None, ""):   # run as a script: make the `dagr` package importable
    _here = Path(__file__).resolve().parent
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != _here]
    sys.path.insert(0, str(_here.parent))

from dagr import apply as apply_mod, compose, config, graphcore, runner, scaffold, scan as scan_mod  # noqa: E402
from dagr import status as status_mod  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="dagr", description="Turn your ICM folders into a DAG of agent work.",
        epilog="exit codes: 0 ok | 1 doctor found errors | 2 refused or invalid input | "
        "3 another runner is active | 4 run stuck | 5 run finished with held or failed "
        "tickets (--strict-exit only). `doctor` with no contracts yet exits 0.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def root_arg(p):
        p.add_argument("--root", help="your tree's root (default: the folder holding .dagr/, "
                       "found by walking up from the current folder)")

    p = sub.add_parser("scan", help="inventory your tree -> .dagr/scan.json + scan.md")
    root_arg(p)
    p = sub.add_parser("ports", help="list declared ports, unbound inputs, mismatches")
    root_arg(p)
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("doctor", help="contracts vs disk drift, parse errors, cycles")
    root_arg(p)
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("plan", help="request or workflow id -> a map of tickets")
    root_arg(p)
    p.add_argument("request", help="free text, or a workflow id")
    p.add_argument("--map", dest="slug", help="map folder name (default: date + request)")
    p.add_argument("--stages", action="store_true",
                   help="one ticket per stage instead of one per workflow")
    p.add_argument("--no-model", action="store_true",
                   help="never call a model; match keywords only")
    p.add_argument("--also", action="append", default=[], metavar="WORKFLOW_ID",
                   help="add this workflow to the plan; repeat it (or name one the plan "
                   "already has) to run the same workflow more than once, e.g. episodes 1 "
                   "and 2: `plan video-script --also video-script`")
    p = sub.add_parser("go", help="approve a map (writes GO.md)")
    root_arg(p)
    p.add_argument("slug")
    p.add_argument("--scope", help="e.g. T01,T02-T05 (default: all)")
    p.add_argument("--who", help="your name, recorded in GO.md")
    p = sub.add_parser("run", help="run an approved map")
    root_arg(p)
    p.add_argument("slug")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--strict-exit", action="store_true")
    p.add_argument("--worker", choices=["claude", "codex", "opencode", "custom"])
    p.add_argument("--reviewer-model")
    p.add_argument("--no-review", action="store_true")
    p.add_argument("--max-budget-usd", type=float)
    p.add_argument("--max-minutes", type=float)
    p.add_argument("--stall-minutes", type=float)
    p.add_argument("--max-turns", type=int)
    p.add_argument("--poll", type=float, default=5.0)
    p.add_argument("--backoff-scale", type=float, default=1.0, help=argparse.SUPPRESS)
    p.add_argument("--max-rate-retries", type=int, default=5)
    p = sub.add_parser("status", help="write and print STATUS.md for a map")
    root_arg(p)
    p.add_argument("slug")
    p = sub.add_parser("apply", help="apply the approved items of .dagr/PROPOSAL.md "
                       "(backs up first; refuses, exit 2, if any diff does not apply)")
    root_arg(p)
    p.add_argument("--items", help="item numbers `1,2,5-7` or `all` (default: the approved "
                   "list in .dagr/approval.md)")
    p.add_argument("--dry-run", action="store_true",
                   help="check every selected diff applies; write nothing")
    p = sub.add_parser("uninstall", help="restore backed-up files, remove what dagr added")
    root_arg(p)
    p.add_argument("--yes", action="store_true", help="do not ask first")
    return ap


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    a = build_parser().parse_args(argv)
    root = config.find_root(a.root)
    try:
        if a.cmd == "scan":
            s = scan_mod.run_scan(root)
            st = s["stats"]
            print(f"scan: {st['context_files']} CONTEXT.md, {st['workflow_candidates']} "
                  f"workflow-looking folder(s), {st['contracts_declared']} declared contract(s) "
                  "-> .dagr/scan.json, .dagr/scan.md")
            return 0
        if a.cmd == "apply":
            return apply_mod.run_apply(root, a.items, a.dry_run)
        if a.cmd == "uninstall":
            return scaffold.uninstall(root, yes=a.yes)
        cfg = config.load_config(root)
        if a.cmd == "ports":
            return compose.cmd_ports(root, cfg, a.json)
        if a.cmd == "doctor":
            return compose.cmd_doctor(root, cfg, a.json)
        if a.cmd == "plan":
            return compose.plan_request(root, cfg, a.request, a.slug,
                                        use_model=not a.no_model, expand_stages=a.stages,
                                        also=a.also)
        if a.cmd == "go":
            return compose.cmd_go(root, cfg, a.slug, a.scope, a.who)
        if a.cmd == "run":
            return runner.run_slug(
                a.slug, root, dry_run=a.dry_run, strict_exit=a.strict_exit, worker=a.worker,
                reviewer_model=a.reviewer_model, no_review=a.no_review,
                max_budget_usd=a.max_budget_usd, max_minutes=a.max_minutes,
                stall_minutes=a.stall_minutes, max_turns=a.max_turns, poll=a.poll,
                backoff_scale=a.backoff_scale, max_rate_retries=a.max_rate_retries)
        if a.cmd == "status":
            return status_mod.run_status(a.slug, root)
    except (config.ConfigError, graphcore.GraphError) as e:
        print(f"ERROR: {e}")
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
