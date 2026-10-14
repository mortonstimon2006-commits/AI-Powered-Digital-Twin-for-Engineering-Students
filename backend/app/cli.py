"""Operational CLI.

uv run python -m app.cli seed                    # load reference catalogue (idempotent)
uv run python -m app.cli validate-links          # check learning-resource URLs (SSRF-guarded)
uv run python -m app.cli reindex-kb              # embed knowledge base into Chroma (needs Ollama)
uv run python -m app.cli create-admin EMAIL      # create/promote an administrator (prompts for password)
uv run python -m app.cli retention               # apply data-retention policy
uv run python -m app.cli models                  # list registered model versions
uv run python -m app.cli bench-mentor            # measure local LLM latency / throughput / VRAM
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys

from sqlalchemy import select


def cmd_seed(_: argparse.Namespace) -> None:
    from app.db import system_session
    from app.seed.catalogue import seed_catalogue

    with system_session() as db:
        print(json.dumps(seed_catalogue(db)))


def cmd_validate_links(_: argparse.Namespace) -> None:
    from collections import Counter

    from app.db import system_session
    from app.services.link_checker import validate_resources

    with system_session() as db:
        report = validate_resources(db)
    print(json.dumps(Counter(r["status"] for r in report)))
    for r in report:
        if r["status"] != "verified":
            print(f"  {r['status']:10s} {r['http_status']} {r['url']} ({r['note']})")


def cmd_reindex_kb(_: argparse.Namespace) -> None:
    from app.db import system_session
    from app.services.rag.knowledge_base import reindex_global

    with system_session() as db:
        print(json.dumps(reindex_global(db), indent=2))


def cmd_create_admin(args: argparse.Namespace) -> None:
    from app.db import system_session
    from app.models import Consent, User
    from app.security.passwords import hash_password, password_problems
    from app.services import audit
    from app.services.auth_service import POLICY_VERSION

    email = args.email.strip().lower()
    with system_session() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            pw = getpass.getpass("New admin password: ")
            if pw != getpass.getpass("Repeat password: "):
                sys.exit("Passwords do not match.")
            problems = password_problems(pw, email=email)
            if problems:
                sys.exit("Weak password: " + " ".join(problems))
            user = User(email=email, password_hash=hash_password(pw), display_name=args.name or "Administrator", role="admin")
            db.add(user)
            db.flush()
            db.add(Consent(user_id=user.id, purpose="profile_processing", granted=True, policy_version=POLICY_VERSION))
        else:
            user.role = "admin"
        audit.record(db, "admin.cli.promote", actor_id=None, target_type="user", target_id=user.id)
    print(f"{email} is now an administrator.")


def cmd_retention(_: argparse.Namespace) -> None:
    from app.db import system_session
    from app.services.privacy import apply_retention

    with system_session() as db:
        print(json.dumps(apply_retention(db)))


def cmd_models(_: argparse.Namespace) -> None:
    from app.db import system_session
    from app.models import ModelVersion

    with system_session() as db:
        for m in db.scalars(select(ModelVersion).order_by(ModelVersion.created_at)):
            print(
                f"{m.id:3d} {m.status:9s} {m.version} synthetic={m.is_synthetic} pr_auc={m.metrics.get('test', {}).get('pr_auc')}"
            )


def cmd_bench_mentor(args: argparse.Namespace) -> None:
    from app.services.rag.benchmark import run_benchmark

    print(json.dumps(run_benchmark(runs=args.runs), indent=2))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed").set_defaults(fn=cmd_seed)
    sub.add_parser("validate-links").set_defaults(fn=cmd_validate_links)
    sub.add_parser("reindex-kb").set_defaults(fn=cmd_reindex_kb)
    p = sub.add_parser("create-admin")
    p.add_argument("email")
    p.add_argument("--name", default=None)
    p.set_defaults(fn=cmd_create_admin)
    sub.add_parser("retention").set_defaults(fn=cmd_retention)
    sub.add_parser("models").set_defaults(fn=cmd_models)
    b = sub.add_parser("bench-mentor")
    b.add_argument("--runs", type=int, default=3)
    b.set_defaults(fn=cmd_bench_mentor)
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
