#!/usr/bin/env python3
"""Print one section of a large project document.

The planning documents are long enough that reading them whole wastes agent
context. This tool prints one heading and its body; --list shows the headings.

Usage:
    python tools/doc.py --list
    python tools/doc.py --list sequence
    python tools/doc.py sequence O1
    python tools/doc.py plan 5.1
    python tools/doc.py changelog 2.1.3
    python tools/doc.py readme Collections
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DOCS = {
    "agents": "AGENTS.md",
    "plan": "IMPROVEMENT_PLAN.md",
    "sequence": "IMPLEMENTATION_SEQUENCE.md",
    "readme": "README.md",
    "changelog": "CHANGELOG.md",
    "baseline": "tests/BASELINE.md",
    "reports": "reports/README.md",
    "context": "docs/agent/context-map.md",
    "smoke": "docs/agent/smoke.md",
    "release": "docs/agent/release.md",
}

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
KEY_RE = re.compile(r"^\[?(\d+(?:\.\d+)*|[A-Za-z]\d+(?:\.\d+)?)\]?(?:[.):\s]|$)")


@dataclass(frozen=True)
class Heading:
    line: int
    level: int
    text: str
    key: str


def estimate_tokens(text: str) -> int:
    """Return a rough token count; four characters per token is close enough."""
    return max(1, (len(text) + 3) // 4)


def doc_path(name: str) -> Path:
    try:
        relative = DOCS[name]
    except KeyError:
        names = ", ".join(sorted(DOCS))
        raise LookupError("Unknown document %r. Use one of: %s" % (name, names))
    return ROOT / relative


def read_lines(name: str) -> list[str]:
    path = doc_path(name)
    if not path.exists():
        raise LookupError("Document not found: %s" % path)
    return path.read_text(encoding="utf-8").splitlines()


def parse_headings(lines: list[str]) -> list[Heading]:
    headings = []
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if not match:
            continue
        level = len(match.group(1))
        text = match.group(2).strip()
        key_match = KEY_RE.match(text)
        key = key_match.group(1).lower() if key_match else ""
        headings.append(Heading(index + 1, level, text, key))
    return headings


def _normalize_query(query: str) -> str:
    return query.strip().lstrip("#").rstrip(".").lower()


def _matches_prefix(text: str, query: str) -> bool:
    text = text.lower()
    return text == query or text.startswith(query + " ") or text.startswith(query + ".") \
        or text.startswith(query + ":") or text.startswith(query + " [")


def find_heading(headings: list[Heading], query: str) -> Heading:
    query = _normalize_query(query)
    if not query:
        raise LookupError("Empty section query.")

    exact = [heading for heading in headings if heading.key == query]
    if exact:
        return exact[0]

    prefix = [heading for heading in headings if _matches_prefix(heading.text, query)]
    if prefix:
        return min(prefix, key=lambda heading: len(heading.text))

    available = ", ".join(
        heading.key or heading.text for heading in headings if heading.level <= 3
    )
    raise LookupError(
        "No section %r in this document. Try --list. Known sections: %s"
        % (query, available)
    )


def find_section(name: str, query: str) -> str:
    lines = read_lines(name)
    headings = parse_headings(lines)
    target = find_heading(headings, query)
    start = target.line - 1
    end = len(lines)
    for heading in headings:
        if heading.line - 1 > start and heading.level <= target.level:
            end = heading.line - 1
            break
    return "\n".join(lines[start:end]).rstrip() + "\n"


def print_list(name: str | None) -> None:
    names = [name] if name else list(DOCS)
    for doc_name in names:
        path = doc_path(doc_name)
        if not path.exists():
            print("%-12s %s (missing)" % (doc_name, path), file=sys.stderr)
            continue
        text = path.read_text(encoding="utf-8")
        print("%s  (%s, ~%d tokens)" % (path.relative_to(ROOT), doc_name,
                                        estimate_tokens(text)))
        for heading in parse_headings(text.splitlines()):
            marker = heading.key or "-"
            print("  L%-5d %-12s %s" % (heading.line, marker, heading.text))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print one section of a project document.",
    )
    parser.add_argument("doc", nargs="?", help="document name, for example sequence")
    parser.add_argument("section", nargs="?", help="heading number, ID or name")
    parser.add_argument("--list", action="store_true", help="list headings instead")
    args = parser.parse_args(argv)

    try:
        if args.list:
            if args.section:
                parser.error("--list accepts at most one document name")
            print_list(args.doc)
            return 0
        if not args.doc or not args.section:
            parser.error("doc and section are required unless --list is used")
        sys.stdout.write(find_section(args.doc, args.section))
        return 0
    except LookupError as exc:
        print(exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
