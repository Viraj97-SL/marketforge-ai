"""
MarketForge AI -- Deployment Sync Script
=========================================
Copies changed files from the main working directory (marketforge-ai)
to the publishable backend and frontend repos.

Usage:
    python sync.py              # copy + show git status
    python sync.py --push       # copy + git add/commit/push both repos
    python sync.py --dry-run    # show what would be copied, nothing written

Repos (siblings of this directory):
    ../marketforge-backend   -- FastAPI + Python source
    ../marketforge-frontend  -- Next.js frontend
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Paths
ROOT     = Path(__file__).parent          # marketforge-ai/
BACKEND  = ROOT.parent / "marketforge-backend"
FRONTEND = ROOT.parent / "marketforge-frontend"

# Files to sync to backend (source relative to ROOT, dest relative to BACKEND)
# Use None as dest to mean "same path"
BACKEND_FILES: list[tuple[str, str | None]] = [
    ("api/main.py",      None),
    ("api/security.py",  None),
    ("pyproject.toml",   None),
    ("README.md",        None),
    ("worker.py",        None),
]

BACKEND_DIRS: list[tuple[str, str | None]] = [
    ("src/marketforge/cv",              None),
    ("src/marketforge/agents/security", None),
    ("src/marketforge/config",          None),
    ("src/marketforge/memory",          None),
    ("src/marketforge/nlp",             None),
    ("src/marketforge/models",          None),
    ("src/marketforge/utils",           None),
    ("tests/test_cv",                   None),
    ("tests/load",                      None),
]

# Frontend files live IN the frontend repo -- just verify they exist
FRONTEND_FILES: list[str] = [
    "src/lib/api.ts",
    "src/app/career/page.tsx",
    "src/app/jobs/page.tsx",
    "src/app/market/page.tsx",
    "src/app/page.tsx",
    "src/components/nav.tsx",
]


def _copy_file(src: Path, dst: Path, dry: bool) -> bool:
    """Copy src to dst. Returns True if the file actually changed."""
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and dst.read_bytes() == src.read_bytes():
        return False   # identical -- skip
    if not dry:
        shutil.copy2(src, dst)
    tag = "[dry]" if dry else "[copy]"
    try:
        rel = src.relative_to(ROOT)
    except ValueError:
        rel = src
    print(f"  {tag} {rel}")
    return True


def _copy_dir(src: Path, dst: Path, dry: bool) -> int:
    """Recursively copy a directory. Returns number of changed files."""
    if not src.exists():
        return 0
    changed = 0
    for f in src.rglob("*"):
        if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc":
            changed += _copy_file(f, dst / f.relative_to(src), dry)
    return changed


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True
    )
    return result.stdout.strip()


def sync(dry: bool = False, push: bool = False) -> None:
    SEP = "-" * 60
    changed_backend = 0

    # Backend
    print(f"\n{SEP}")
    print(f"Backend  ->  {BACKEND}")
    print(SEP)

    for rel_src, rel_dst in BACKEND_FILES:
        src = ROOT / rel_src
        dst = BACKEND / (rel_dst or rel_src)
        changed_backend += _copy_file(src, dst, dry)

    for rel_src, rel_dst in BACKEND_DIRS:
        src = ROOT / rel_src
        dst = BACKEND / (rel_dst or rel_src)
        changed_backend += _copy_dir(src, dst, dry)

    if changed_backend == 0:
        print("  (no changes)")

    # Frontend (files are edited in-place inside FRONTEND repo)
    print(f"\n{SEP}")
    print(f"Frontend ->  {FRONTEND}")
    print(SEP)
    for rel in FRONTEND_FILES:
        p = FRONTEND / rel
        if p.exists():
            print(f"  [in-place] {rel}")
    print("  (frontend files are edited directly in the frontend repo)")

    # Git status
    print(f"\n{SEP}")
    print("Git status")
    print(SEP)
    for label, repo in [("backend", BACKEND), ("frontend", FRONTEND)]:
        status = _git(repo, "status", "--short")
        print(f"\n  [{label}]")
        if status:
            for line in status.splitlines():
                print(f"    {line}")
        else:
            print("    (clean -- nothing to push)")

    # Auto push
    if push and not dry:
        print(f"\n{SEP}")
        print("Pushing")
        print(SEP)
        for label, repo in [("backend", BACKEND), ("frontend", FRONTEND)]:
            status = _git(repo, "status", "--short")
            if not status:
                print(f"  [{label}] nothing to commit")
                continue
            _git(repo, "add", "-A")
            msg = input(f"  [{label}] commit message (blank = skip): ").strip()
            if not msg:
                print(f"  [{label}] skipped")
                continue
            _git(repo, "commit", "-m", msg)
            out = _git(repo, "push")
            print(f"  [{label}] pushed -> {out or 'ok'}")

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Sync marketforge-ai -> backend + frontend repos"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be copied, write nothing"
    )
    parser.add_argument(
        "--push", action="store_true",
        help="git add + commit + push after sync"
    )
    args = parser.parse_args()
    sync(dry=args.dry_run, push=args.push)
