#!/usr/bin/env python3
"""Print one version's section of CHANGELOG.md (used as GitHub release notes).

Usage: python scripts/changelog_section.py 0.2.0 [--changelog CHANGELOG.md]

The section runs from its "## [<version>]" heading up to the next "## " heading
and includes the version's compare link. Exits 1 if the version has no section
or the section has no entries.
"""

import argparse
import pathlib
import sys


def extract_section(text: str, version: str) -> str:
    lines = text.replace("\r\n", "\n").split("\n")
    heading = f"## [{version}]"
    start = next(
        (i for i, line in enumerate(lines)
         if line == heading or line.startswith(heading + " ")),
        None,
    )
    if start is None:
        raise LookupError(f"CHANGELOG has no section for version {version}")

    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    body = lines[start:end]
    if not any(line.startswith("- ") for line in body):
        raise LookupError(f"CHANGELOG section for version {version} has no entries")

    while body and not body[-1].strip():
        body.pop()
    return "\n".join(body) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="version without the 'v' prefix, e.g. 0.2.0")
    parser.add_argument("--changelog", default="CHANGELOG.md")
    args = parser.parse_args()

    text = pathlib.Path(args.changelog).read_text(encoding="utf-8")
    try:
        sys.stdout.write(extract_section(text, args.version))
    except LookupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
