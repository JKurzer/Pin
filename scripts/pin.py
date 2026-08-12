#!/usr/bin/env python3
"""Deterministic context pinning for the artillery-guns skill.

Why this exists: model attention over context is U-shaped (primacy/recency).
A markdown instruction like "re-read GUARDRAILS.md every subturn" sits in the
low-attention middle and decays as the window fills. Tool OUTPUT lands at the
recency end every time. So instead of trusting the model to remember, this
script mechanically replays pinned files verbatim on demand.

Workflow:
    python pin.py pin GUARDRAILS.md     # one-time setup (per state file)
    python pin.py emit                  # run at the START of every subturn
    python pin.py check --extract draft.txt   # optional: fidelity self-check
    python pin.py wrap -- <command>     # pinned shell: replay pins, run command,
                                        # pass through its exit code. Cross-platform.
                                        # Thin shims for bare-name use: pinning/adapters/shell/

State: JSON list resolved from $CONTEXT_PINS, $ARTILLERY_GUNS_PINS (legacy),
~/.context-pins.json, or ~/.artillery-guns-pins.json (legacy), first match wins.
Pins store abspath + sha256-at-pin-time; emit flags content changed since pin.

Portability: pin.py is the framework-agnostic core (stdlib only). Framework
adapters (claude-code hooks, code-puppy plugin, static render) implement only
the render path against the same state file. See pinning/README.md.

check verifies that claim-shaped passages actually appear in the pinned corpus
(algorithm adapted from the verbatim plugin, claude-plugins/verbatim). It is
the ONLY subcommand that needs rapidfuzz; pin/emit/list stay stdlib-only.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MAX_FILE_BYTES = 16 * 1024        # per-file pin cap; guardrails are ~2 KB
MAX_EMIT_BYTES = 64 * 1024        # total replay cap per emit
MAX_PINS = 16

TOKENS_PER_BYTE = 0.25            # rough chars/4 estimate


def state_path() -> Path:
    for env in ("CONTEXT_PINS", "ARTILLERY_GUNS_PINS"):
        override = os.environ.get(env)
        if override:
            return Path(override)
    for name in (".context-pins.json", ".artillery-guns-pins.json"):
        candidate = Path.home() / name
        if candidate.exists():
            return candidate
    return Path.home() / ".context-pins.json"


def load_state() -> list:
    p = state_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_state(pins: list) -> None:
    state_path().write_text(json.dumps(pins, indent=2), encoding="utf-8")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_pin(pins: list, abspath: str):
    return next((p for p in pins if p["path"] == abspath), None)


def cmd_pin(args) -> int:
    pins = load_state()
    rc = 0
    for raw in args.files:
        path = Path(raw).resolve()
        if not path.is_file():
            print(f"error: {path} is not a file", file=sys.stderr)
            rc = 1
            continue
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            print(f"error: {path} is {size} B > {MAX_FILE_BYTES} B cap; "
                  f"pin only small hot-loop files", file=sys.stderr)
            rc = 1
            continue
        if find_pin(pins, str(path)):
            print(f"already pinned: {path}")
            continue
        if len(pins) >= MAX_PINS:
            print(f"error: pin limit {MAX_PINS} reached; unpin something first",
                  file=sys.stderr)
            rc = 1
            continue
        pins.append({"path": str(path), "sha256": sha256_of(path), "bytes": size})
        print(f"pinned: {path} ({size} B)")
    save_state(pins)
    return rc


def cmd_unpin(args) -> int:
    pins = load_state()
    rc = 0
    for raw in args.files:
        abspath = str(Path(raw).resolve())
        pin = find_pin(pins, abspath)
        if pin is None:
            print(f"error: not pinned: {abspath}", file=sys.stderr)
            rc = 1
            continue
        pins.remove(pin)
        print(f"unpinned: {abspath}")
    save_state(pins)
    return rc


def cmd_clear(_args) -> int:
    save_state([])
    print("cleared all pins")
    return 0


def cmd_list(_args) -> int:
    pins = load_state()
    if not pins:
        print(f"(no pins; state: {state_path()})")
        return 0
    for i, p in enumerate(pins, 1):
        print(f"{i}. {p['path']} ({p['bytes']} B, sha256:{p['sha256'][:12]})")
    total = sum(p["bytes"] for p in pins)
    print(f"{len(pins)} pins, {total} B, ~{int(total * TOKENS_PER_BYTE)} tokens per emit")
    return 0


def _emit_body(pins, quiet: bool) -> int:
    """Render all pins. Shared by cmd_emit and cmd_wrap."""
    emitted, total_bytes, missing = 0, 0, 0
    for i, p in enumerate(pins, 1):
        path = Path(p["path"])
        if not path.is_file():
            print(f"!!! PINNED {i}/{len(pins)} MISSING: {path}\n")
            missing += 1
            continue
        size = path.stat().st_size
        if total_bytes + size > MAX_EMIT_BYTES:
            print(f"!!! PINNED {i}/{len(pins)} SKIPPED (emit cap {MAX_EMIT_BYTES} B): "
                  f"{path}\n")
            continue
        current_hash = sha256_of(path)
        drift = "" if current_hash == p["sha256"] else " [CHANGED since pinned]"
        print(f"=== PINNED {i}/{len(pins)}: {path} ({size} B, "
              f"sha256:{current_hash[:12]}{drift}) ===")
        content = path.read_text(encoding="utf-8", errors="replace")
        sys.stdout.write(content)
        if not content.endswith("\n"):
            print()
        print(f"=== END PINNED {i}/{len(pins)} ===\n")
        emitted += 1
        total_bytes += size
    if not quiet:
        print(f"--- pin.py: emitted {emitted}/{len(pins)}"
              f"{f', {missing} MISSING' if missing else ''}, "
              f"{total_bytes} B, ~{int(total_bytes * TOKENS_PER_BYTE)} tokens ---")
    return 0


def cmd_emit(_args) -> int:
    pins = load_state()
    if not pins:
        print(f"error: no pins (state: {state_path()}). "
              f"e.g.: python pin.py pin GUARDRAILS.md", file=sys.stderr)
        return 1
    return _emit_body(pins, getattr(_args, "quiet", False))


def cmd_wrap(args) -> int:
    """Pinned shell: replay pins, run the command, pass through its exit code."""
    pins = load_state()
    if pins:
        _emit_body(pins, quiet=True)
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    return subprocess.call(" ".join(command), shell=True) if command else 0


# --- check: claim fidelity against the pinned corpus ----------------------
# Adapted from the verbatim plugin (claude-plugins/verbatim). Same algorithm:
# whitespace-canonicalize, exact-substring fast path, then partial-ratio
# alignment + Damerau-Levenshtein within tolerance.

_WS = re.compile(r"\s+")
_FENCED = re.compile(r"```.*?```", re.DOTALL)
_URL = re.compile(r"\bhttps?://\S+")
_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}")
MIN_CLAIM_LEN = 30
MIN_ALPHA_RATIO = 0.7


def _canon(s: str) -> str:
    return _WS.sub(" ", s).strip()


def _load_rapidfuzz():
    try:
        from rapidfuzz import fuzz
        from rapidfuzz.distance import DamerauLevenshtein
        return fuzz, DamerauLevenshtein
    except ImportError:
        pass
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                        "rapidfuzz"], check=True, timeout=60)
        from rapidfuzz import fuzz
        from rapidfuzz.distance import DamerauLevenshtein
        return fuzz, DamerauLevenshtein
    except Exception:
        return None, None


def extract_claims(text: str) -> list:
    """Pull claim-shaped passages (verbatim's candidate_claims)."""
    text = _URL.sub("", _FENCED.sub("", text))
    out = []
    for chunk in _SPLIT.split(text):
        chunk = chunk.strip().strip('"\'>` ').strip()
        if len(chunk) < MIN_CLAIM_LEN:
            continue
        if sum(c.isalpha() or c.isspace() for c in chunk) / len(chunk) < MIN_ALPHA_RATIO:
            continue
        out.append(chunk)
    return out


def load_claims(raw: str) -> list:
    """verbatim's load_claims: JSON array, JSONL {'claim': ...}, or plain lines."""
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith("["):
        return json.loads(raw)
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("{"):
            out.append(json.loads(line)["claim"])
        elif line.startswith('"'):
            out.append(json.loads(line))
        else:
            out.append(line)
    return out


def _verify_one(source_canon: str, claim_canon: str, tolerance: int, fuzz, dl):
    """Returns (matched, distance) of claim against one canonicalized source."""
    if not claim_canon:
        return True, 0
    if source_canon.find(claim_canon) >= 0:
        return True, 0
    align = fuzz.partial_ratio_alignment(claim_canon, source_canon, score_cutoff=0)
    if align is None:
        return False, -1
    dist = dl.distance(claim_canon, source_canon[align.dest_start:align.dest_end])
    return dist <= tolerance, dist


def cmd_check(args) -> int:
    pins = load_state()
    if not pins:
        print(f"error: no pins (state: {state_path()}); nothing to check against",
              file=sys.stderr)
        return 2
    corpus = {}
    for p in pins:
        path = Path(p["path"])
        if path.is_file():
            corpus[str(path)] = _canon(path.read_text(encoding="utf-8", errors="replace"))
    if not corpus:
        print("error: all pinned files are missing", file=sys.stderr)
        return 2

    if args.extract is not None:
        raw = (sys.stdin.read() if args.extract == "-"
               else Path(args.extract).read_text(encoding="utf-8", errors="replace"))
        claims = extract_claims(raw)
    else:
        raw = (sys.stdin.read() if args.claims == "-"
               else Path(args.claims).read_text(encoding="utf-8"))
        claims = load_claims(raw)
    if not claims:
        print("error: no claims to verify", file=sys.stderr)
        return 2

    fuzz, dl = _load_rapidfuzz()
    if fuzz is None:
        print("error: rapidfuzz unavailable (pip install rapidfuzz, or use uv)",
              file=sys.stderr)
        return 2

    results, failures = [], 0
    for claim in claims:
        claim_canon = _canon(claim)
        best = min(((_verify_one(src, claim_canon, args.tolerance, fuzz, dl), name)
                    for name, src in corpus.items()), key=lambda r: (r[0][1] < 0, r[0][1]))
        (matched, dist), source = best
        failures += 0 if matched else 1
        results.append({"claim": claim[:80] + ("..." if len(claim) > 80 else ""),
                        "matched": matched, "distance": dist, "source": source})
    print(json.dumps({"tolerance": args.tolerance, "failures": failures,
                      "results": results}, indent=2))
    print(f"--- pin.py check: {len(results) - failures}/{len(results)} claims matched "
          f"pinned corpus ---")
    return 1 if failures else 0


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Replay pinned files verbatim into recent context. "
                    "Default action (no args) is emit.")
    sub = parser.add_subparsers(dest="subcommand")
    for name, help_text in [("pin", "add files to the pin list"),
                            ("unpin", "remove files from the pin list")]:
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("files", nargs="+", help="files (resolved to abspaths)")
    sub.add_parser("list", help="show pins with size/hash")
    sub.add_parser("clear", help="remove all pins")
    sp = sub.add_parser("emit", help="replay all pinned files verbatim (default)")
    sp.add_argument("--quiet", action="store_true",
                    help="suppress the trailing summary line (for static includes)")
    sp = sub.add_parser("check", help="verify claims appear in the pinned corpus "
                                      "(needs rapidfuzz; exit 1 on any failure)")
    src = sp.add_mutually_exclusive_group(required=True)
    src.add_argument("--claims", help="claims file (JSON array/JSONL/lines), or - for stdin")
    src.add_argument("--extract", help="extract claim-shaped passages from file, or - for stdin")
    sp.add_argument("--tolerance", type=int, default=2,
                    help="max Damerau-Levenshtein distance (default 2)")
    sp = sub.add_parser("wrap", help="pinned shell: replay pins, run command, "
                                     "pass through exit code")
    sp.add_argument("command", nargs=argparse.REMAINDER,
                    help="command to run, after --")
    args = parser.parse_args()

    handlers = {"pin": cmd_pin, "unpin": cmd_unpin, "list": cmd_list,
                "clear": cmd_clear, "emit": cmd_emit, "check": cmd_check,
                "wrap": cmd_wrap, None: cmd_emit}
    return handlers[args.subcommand](args)


if __name__ == "__main__":
    sys.exit(main())
