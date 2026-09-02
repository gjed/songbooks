#!/usr/bin/env python3
"""Guard for optional NN-slug.site.cho variants (see AGENTS.md and
skills/chordpro-song-authoring).

A site variant may differ from its original song source only by:
  1. Additional inline [CHORD] brackets.
  2. Choruses written out in full where the original only refers to them.

Anything else is a divergence and fails the build: the original always has
precedence on correctness. This script normalizes both files — expanding
every chorus recall into the most-recently-defined full chorus block,
stripping all inline chords, and collapsing whitespace — and requires the
normalized forms to be identical.

Two source idioms count as a recall, because ChordPro renders both as a
label in print and as nothing at all in HTML: the bare {chorus} directive
(including {chorus: x2}), and an empty {start_of_chorus}/{end_of_chorus}
block holding only directives such as {comment: RIT}.

Usage: scripts/check-site-variants.py
Exit 0: no variants, or every variant matches its original.
Exit 1: at least one variant diverges; a unified diff is printed per failure.
"""

from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SONGBOOKS_DIR = ROOT / "songbooks"

# Cover pseudo-songs never get site variants (drawn by reportlab for print,
# no HTML equivalent) — see Makefile COVER_FILES.
COVER_FILES = {"00-cover.cho", "01-chord-chart.cho", "99-back-cover.cho"}

CHORD_RE = re.compile(r"\[[^\]]*\]")
START_CHORUS_RE = re.compile(r"^\{start_of_chorus\b[^}]*\}$")
END_CHORUS_RE = re.compile(r"^\{end_of_chorus\b[^}]*\}$")
CHORUS_RECALL_RE = re.compile(r"^\{chorus\b[^}]*\}$")


def expand_chorus_recalls(text: str) -> str:
    """Expand every chorus recall into the most-recently defined full chorus,
    wrapped in its {start_of_chorus}/{end_of_chorus} markers — the canonical
    written-out form a site variant is expected to use.

    Two source idioms count as a recall, because ChordPro renders both as a
    label in print and as *nothing* in HTML:

      1. A bare ``{chorus}`` / ``{chorus: x2}`` directive line.
      2. An empty chorus block — ``{start_of_chorus}`` … ``{end_of_chorus}``
         holding only directives such as ``{comment: RIT}`` and no lyrics.

    A recall with no preceding full chorus is left untouched (malformed
    source, not this script's concern). Recall arguments are dropped, so
    ``{chorus: x2}`` normalizes to the same block as ``{chorus}`` and a
    variant for such a song writes the chorus block out once."""
    out: list[str] = []
    last_chorus: list[str] | None = None
    in_chorus = False
    chorus_buf: list[str] = []

    def has_lyrics(block: list[str]) -> bool:
        # Markers excluded by construction; a directive-only block (e.g. just
        # {comment: RIT}) carries no lyrics and is therefore a recall.
        return any(
            line.strip() and not line.strip().startswith("{") for line in block[1:-1]
        )

    for line in text.splitlines():
        stripped = line.strip()
        if START_CHORUS_RE.match(stripped):
            in_chorus = True
            chorus_buf = [line]
            continue
        if END_CHORUS_RE.match(stripped):
            in_chorus = False
            chorus_buf.append(line)
            if has_lyrics(chorus_buf):
                last_chorus = list(chorus_buf)
                out.extend(chorus_buf)
            elif last_chorus is not None:
                out.extend(last_chorus)
            else:
                out.extend(chorus_buf)
            continue
        if in_chorus:
            chorus_buf.append(line)
            continue
        if CHORUS_RECALL_RE.match(stripped) and last_chorus is not None:
            out.extend(last_chorus)
            continue
        out.append(line)
    return "\n".join(out)


def normalize(text: str) -> list[str]:
    text = expand_chorus_recalls(text)
    text = CHORD_RE.sub("", text)
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def check_pair(original: Path, variant: Path) -> str | None:
    if original.name in COVER_FILES:
        return f"{variant}: site variants are not allowed for cover pseudo-songs ({original.name})"
    if not original.exists():
        return f"{variant}: no matching original {original.name} — every .site.cho must pair with an existing song"

    orig_norm = normalize(original.read_text(encoding="utf-8"))
    var_norm = normalize(variant.read_text(encoding="utf-8"))
    if orig_norm == var_norm:
        return None

    diff = "\n".join(
        difflib.unified_diff(
            orig_norm,
            var_norm,
            fromfile=f"{original} (normalized)",
            tofile=f"{variant} (normalized)",
            lineterm="",
        )
    )
    return (
        f"{variant} diverges from {original} beyond permitted differences "
        f"(extra chords / full choruses only):\n{diff}"
    )


def main() -> int:
    if not SONGBOOKS_DIR.is_dir():
        print(f"error: {SONGBOOKS_DIR} not found", file=sys.stderr)
        return 1

    variants = sorted(SONGBOOKS_DIR.glob("*/*.site.cho"))
    if not variants:
        print("check-site-variants: no .site.cho files found — nothing to check")
        return 0

    errors: list[str] = []
    for variant in variants:
        name = variant.name
        original = variant.with_name(name[: -len(".site.cho")] + ".cho")
        error = check_pair(original, variant)
        if error:
            errors.append(error)

    if errors:
        print(
            f"check-site-variants: {len(errors)} of {len(variants)} variant(s) FAILED\n",
            file=sys.stderr,
        )
        for err in errors:
            print(err, file=sys.stderr)
            print(file=sys.stderr)
        return 1

    print(f"check-site-variants: {len(variants)} variant(s) OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
