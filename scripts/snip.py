#!/usr/bin/env python3
"""snip -- anchor-exact span extraction/moving for card files.

Moves (or copies) a byte-exact span out of a markdown card into its own
file, leaving a pointer token behind. Models wibble when they transcribe
state by hand; this tool moves bytes, not opinions.

Two ways to address a span:
  --slug NAME            fixed markers:  '## @snip-begin NAME' .. '## @snip-end NAME'
                         (payload = lines BETWEEN the markers)
  --start TEXT --end TEXT  ad-hoc unique anchors (end is exclusive)

Fixed token grammar (reserved, greppable):
  ## @snip-begin <slug>            opens a movable span
  ## @snip-end <slug>              closes it
  ## @snip:archived <slug> -> <p>  pointer left behind by a move (default)

Usage:
  snip.py extract SRC --slug NAME --to DEST [--pointer TEXT]
            [--header-file F] [--keep] [--dry-run] [--overwrite] [--no-backup]
  snip.py extract SRC --start TEXT --end TEXT --to DEST [same options]

Line endings are normalized to \\n on read and write (deterministic bytes).
"""

import argparse
import sys
from pathlib import Path

BEGIN = "## @snip-begin "
END = "## @snip-end "
POINTER_FMT = "## @snip:archived {slug} -> {dest}\n"


def fail(msg: str) -> "SystemExit":
    print(f"snip: error: {msg}", file=sys.stderr)
    raise SystemExit(1)


def read_text(path: Path) -> str:
    """Raw text, NO normalization. A move must never rewrite a byte it
    did not mean to move: untouched regions keep their exact bytes
    (line endings included) because we splice on the raw text."""
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write_text(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def eol_of(text: str) -> str:
    """The file's own line ending, so the inserted pointer matches it."""
    return "\r\n" if "\r\n" in text else "\n"


def find_unique(text: str, anchor: str, label: str) -> int:
    """Index of the ONLY occurrence of anchor; fail loud on 0 or >1."""
    count = text.count(anchor)
    if count == 0:
        fail(f"{label} anchor not found: {anchor!r}")
    if count > 1:
        fail(f"{label} anchor not unique ({count} matches): {anchor!r}")
    return text.index(anchor)


def locate_span(text: str, slug, start, end):
    """Return (span, remove_start, remove_end) — payload and the byte range
    a move should replace with the pointer."""
    if slug:
        b = find_unique(text, BEGIN + slug, "begin")
        content_start = text.index("\n", b) + 1
        e = find_unique(text, END + slug, "end")
        remove_end = text.index("\n", e) + 1  # consume the end-marker line too
        return text[content_start:e], b, remove_end
    if not (start and end):
        fail("address the span with --slug or with both --start and --end")
    s = find_unique(text, start, "start")
    e = find_unique(text, end, "end")
    return text[s:e], s, e


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["extract"])
    parser.add_argument("src")
    parser.add_argument("--slug")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--to", required=True)
    parser.add_argument("--header-file", help="file whose text prepends the payload")
    parser.add_argument("--pointer", help="override the default pointer token")
    parser.add_argument("--keep", action="store_true", help="copy, leaving the span in place")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    src = Path(args.src)
    dest = Path(args.to)
    text = read_text(src)
    span, remove_start, remove_end = locate_span(text, args.slug, args.start, args.end)
    if not span.strip():
        fail("span is empty")

    slug = args.slug or dest.stem
    eol = eol_of(text)
    if args.pointer is not None:
        pointer = args.pointer
    else:
        pointer = POINTER_FMT.format(slug=slug, dest=dest).replace("\n", eol)

    print(f"span: {len(span)} chars, {span.count(chr(10))} lines")
    print(f"dest: {dest} ({'overwrite' if args.overwrite else 'new'})")
    if not args.keep:
        print(f"pointer: {pointer.splitlines()[0]!r}")
    if args.dry_run:
        print("dry run; no files written")
        return 0

    if dest.exists() and not args.overwrite:
        fail(f"{dest} exists (pass --overwrite)")
    if not args.no_backup:
        write_text(src.with_suffix(src.suffix + ".bak"), text)

    header = read_text(Path(args.header_file)) if args.header_file else ""
    write_text(dest, header + span)
    print(f"wrote {dest} ({len(header) + len(span)} chars)")

    if not args.keep:
        new_text = text[:remove_start] + pointer + text[remove_end:]
        write_text(src, new_text)
        print(f"source now {len(new_text)} chars")
    return 0


if __name__ == "__main__":
    sys.exit(main())
