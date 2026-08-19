"""Regenerate the songbook table in the root README.md.

Usage:
  python3 scripts/readme-table.py [--check]

Reads every songbooks/<slug>/songbook.yaml and rewrites the markdown
table between the `<!-- songbooks:begin -->` / `<!-- songbooks:end -->`
markers in README.md. Rows are ordered by slug. Each row uses the
songbook's `title` and one-line `blurb`.

--check exits 1 (without writing) when the README is out of date —
useful as a CI guard.
"""

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
SONGBOOKS = REPO_ROOT / "songbooks"
BEGIN = "<!-- songbooks:begin -->"
END = "<!-- songbooks:end -->"


def rows():
    for folder in sorted(p for p in SONGBOOKS.iterdir() if p.is_dir()):
        path = folder / "songbook.yaml"
        if not path.exists():
            continue
        meta = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        title = str(meta.get("title") or folder.name).strip()
        blurb = str(meta.get("blurb") or "").strip()
        yield f"[{title}](songbooks/{folder.name}/)", blurb


def render():
    cells = list(rows())
    header_right = "What's inside"
    left_w = max(len(left) for left, _ in cells)
    right_w = max(max(len(right) for _, right in cells), len(header_right))
    lines = [
        f"| {'Songbook'.ljust(left_w)} | {header_right.ljust(right_w)} |",
        f"| {'-' * left_w} | {'-' * right_w} |",
    ]
    lines += [f"| {left.ljust(left_w)} | {right.ljust(right_w)} |"
              for left, right in cells]
    return "\n".join(lines)


def main():
    text = README.read_text(encoding="utf-8")
    try:
        head, rest = text.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
    except ValueError:
        sys.exit(f"error: {BEGIN} / {END} markers not found in README.md")
    updated = f"{head}{BEGIN}\n\n{render()}\n\n{END}{tail}"
    if "--check" in sys.argv[1:]:
        if updated != text:
            sys.exit("README.md songbook table is out of date — "
                     "run: python3 scripts/readme-table.py")
        return
    if updated != text:
        README.write_text(updated, encoding="utf-8")
        print("README.md songbook table updated")
    else:
        print("README.md songbook table already up to date")


if __name__ == "__main__":
    main()
