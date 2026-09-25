#!/usr/bin/env python3
"""Self-contained checks for snip.py. Builds its own fixtures in a temp
dir; asserts the fail-loud paths as first-class expectations; exits 0
only when everything passes. Zero errors accepted."""

import subprocess
import sys
import tempfile
from pathlib import Path

SNIP = Path(__file__).with_name("snip.py")

CARD = """# test card

## keep me one.
##
## @snip-begin demo
## demo line one
## demo line two with unicode — dash
## @snip-end demo
##
## ADHOC-START
## ad hoc payload
## ADHOC-END
##
## keep me two.
"""


def run_snip(*args):
    return subprocess.run(
        [sys.executable, str(SNIP), *args], capture_output=True, text=True
    )


def main() -> int:
    checks = []

    def check(name, fn):
        try:
            fn()
            checks.append((name, True, ""))
        except AssertionError as exc:
            checks.append((name, False, str(exc)))

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        card = tmp / "card.md"

        def fresh_card():
            card.write_text(CARD, encoding="utf-8")

        def t_slug_extract():
            fresh_card()
            dest = tmp / "demo.md"
            r = run_snip("extract", str(card), "--slug", "demo", "--to", str(dest))
            assert r.returncode == 0, r.stderr
            assert dest.read_text(encoding="utf-8") == (
                "## demo line one\n## demo line two with unicode — dash\n"
            ), "payload not byte-exact"
            src = card.read_text(encoding="utf-8")
            assert "## @snip:archived demo ->" in src, "pointer missing"
            assert "@snip-begin" not in src and "@snip-end" not in src, "markers left"
            assert "keep me one" in src and "keep me two" in src, "neighbors disturbed"

        def t_adhoc_anchors():
            fresh_card()
            dest = tmp / "adhoc.md"
            r = run_snip(
                "extract", str(card),
                "--start", "## ADHOC-START", "--end", "## ADHOC-END",
                "--to", str(dest),
            )
            assert r.returncode == 0, r.stderr
            assert "ad hoc payload" in dest.read_text(encoding="utf-8")

        def t_dry_run():
            fresh_card()
            dest = tmp / "dry.md"
            r = run_snip("extract", str(card), "--slug", "demo", "--to", str(dest), "--dry-run")
            assert r.returncode == 0, r.stderr
            assert not dest.exists(), "dry-run wrote a file"

        def t_missing_anchor():
            fresh_card()
            r = run_snip("extract", str(card), "--slug", "nope", "--to", str(tmp / "x.md"))
            assert r.returncode == 1, "expected exit 1"
            assert "begin anchor not found" in r.stderr

        def t_nonunique_anchor():
            dup = tmp / "dup.md"
            dup.write_text("## MARK\nx\n## MARK\ny\n", encoding="utf-8")
            r = run_snip("extract", str(dup), "--start", "## MARK", "--end", "y", "--to", str(tmp / "y.md"))
            assert r.returncode == 1, "expected exit 1"
            assert "not unique" in r.stderr

        def t_dest_exists():
            fresh_card()
            dest = tmp / "exists.md"
            dest.write_text("old", encoding="utf-8")
            r = run_snip("extract", str(card), "--slug", "demo", "--to", str(dest))
            assert r.returncode == 1, "expected exit 1"
            assert "exists" in r.stderr
            assert dest.read_text(encoding="utf-8") == "old", "dest clobbered"

        def t_keep_mode():
            fresh_card()
            dest = tmp / "keepcopy.md"
            r = run_snip(
                "extract", str(card), "--slug", "demo",
                "--to", str(dest), "--keep", "--no-backup",
            )
            assert r.returncode == 0, r.stderr
            assert "## demo line one" in card.read_text(encoding="utf-8"), "span removed in keep mode"

        def t_crlf_preserved():
            crlf = tmp / "crlf.md"
            raw = ("## head\r\n## @snip-begin d\r\n## payload one\r\n"
                   "## payload two\r\n## @snip-end d\r\n## tail\r\n")
            crlf.write_bytes(raw.encode("utf-8"))
            dest = tmp / "d.md"
            r = run_snip("extract", str(crlf), "--slug", "d", "--to", str(dest))
            assert r.returncode == 0, r.stderr
            src = crlf.read_bytes()
            assert b"## head\r\n" in src and b"## tail\r\n" in src, "CRLF rewritten in untouched region"
            # 6 raw EOLs - 4 moved (begin,payload x2,end) + 1 pointer = 3
            assert src.count(b"\r\n") == raw.count("\r\n") - 3, "line endings disturbed"
            assert dest.read_bytes() == b"## payload one\r\n## payload two\r\n", "payload not byte-exact"
            assert b"-> " in src and b"\r\n" in src.split(b"@snip:archived")[-1][:200], "pointer EOL mismatch"

        def t_empty_span():
            empty = tmp / "empty.md"
            empty.write_text("## @snip-begin z\n## @snip-end z\n", encoding="utf-8")
            r = run_snip("extract", str(empty), "--slug", "z", "--to", str(tmp / "z.md"))
            assert r.returncode == 1, "expected exit 1"
            assert "empty" in r.stderr

        tests = [
            ("slug extract: byte-exact payload, pointer, markers consumed", t_slug_extract),
            ("ad-hoc anchors extract", t_adhoc_anchors),
            ("dry-run writes nothing", t_dry_run),
            ("missing anchor fails loud", t_missing_anchor),
            ("non-unique anchor fails loud", t_nonunique_anchor),
            ("existing dest refused without --overwrite", t_dest_exists),
            ("--keep copies without removing", t_keep_mode),
            ("CRLF file: untouched bytes + payload + pointer EOL preserved", t_crlf_preserved),
            ("empty span fails loud", t_empty_span),
        ]
        for name, fn in tests:
            check(name, fn)

    for name, ok, err in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {err}" if err else ""))
    failed = [n for n, ok, _ in checks if not ok]
    print(f"{len(checks) - len(failed)}/{len(checks)} PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
