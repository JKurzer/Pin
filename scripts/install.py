#!/usr/bin/env python3
"""Install the context-pins skill (and optionally the code-puppy adapter).

    python scripts/install.py                      # skill + adapter into ~/.code_puppy
    python scripts/install.py --dest <dir>         # same, into a custom home (testing)
    python scripts/install.py --vendor <proj-dir>  # drop tools/pin/scripts/pin.py into a project

Idempotent: files are copied when they differ; existing identical files are
left alone and reported as such. Stdlib only, like everything else here.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL_FILES = [("SKILL.md", "SKILL.md"), ("scripts/pin.py", "scripts/pin.py")]
ADAPTER_SRC = REPO / "pinning" / "adapters" / "code-puppy" / "context_pins"


def copy_tree(src: Path, dst: Path) -> tuple[int, int]:
    """Copy src tree over dst. Returns (written, unchanged) counts."""
    written = unchanged = 0
    for p in src.rglob("*"):
        if p.is_dir():
            continue
        rel = p.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() == p.read_bytes():
            unchanged += 1
            continue
        shutil.copyfile(p, target)
        written += 1
        print(f"  wrote {target}")
    return written, unchanged


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", default="~/.code_puppy", help="agent home (default ~/.code_puppy)")
    ap.add_argument("--vendor", metavar="DIR", help="vendor pin.py into a project at tools/pin/scripts/")
    ap.add_argument("--no-adapter", action="store_true", help="skill only, skip the code-puppy adapter")
    args = ap.parse_args()

    if args.vendor:
        proj = Path(args.vendor).resolve()
        dst = proj / "tools" / "pin" / "scripts"
        dst.mkdir(parents=True, exist_ok=True)
        w, u = copy_tree(REPO / "scripts", dst)
        print(f"vendored pin.py into {dst} ({w} written, {u} already current)")
        print(f"re-pin footer for this project's card: `python tools/pin/scripts/pin.py pin RULES.md`")
        return

    home = Path(args.dest).expanduser().resolve()
    skill_dir = home / "skills" / "context-pins"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "scripts").mkdir(exist_ok=True)

    for rel, _ in SKILL_FILES:
        src = REPO / rel
        if not src.exists():
            sys.exit(f"error: {src} missing -- run from the Pin repo (scripts/install.py)")
    w = u = 0
    for rel, _ in SKILL_FILES:
        src = REPO / rel
        target = skill_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() == src.read_bytes():
            u += 1
            continue
        shutil.copyfile(src, target)
        w += 1
        print(f"  wrote {target}")

    print(f"skill installed at {skill_dir} ({w} written, {u} already current)")

    if not args.no_adapter:
        if not ADAPTER_SRC.exists():
            sys.exit(f"error: adapter not found at {ADAPTER_SRC}")
        w2, u2 = copy_tree(ADAPTER_SRC, home / "plugins" / "context_pins")
        print(f"adapter installed at {home / 'plugins' / 'context_pins'} ({w2} written, {u2} already current)")

    print("\nper project, pin a rules card once:")
    print(f"  python {skill_dir / 'scripts' / 'pin.py'} pin RULES.md")
    print("then forget about it -- the adapter injects the floor every run.")


if __name__ == "__main__":
    main()
