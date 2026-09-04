#!/usr/bin/env python3
"""Guard for optional NN-slug.site.cho variants (see AGENTS.md and
skills/chordpro-song-authoring).

A site variant may differ from its original song source only by:
  1. Additional inline [CHORD] brackets — existing chords must stay exactly
     as they are; only new ones may be added.
  2. Choruses written out in full, repeated as many times as the original
     marks, where the original only refers to them.

Anything else is a divergence and fails the build: the original always has
precedence on correctness. This script normalizes both files — expanding
every chorus recall into its full chorus block (repeated by its marked
count), stripping all inline chords, and collapsing whitespace — and
requires the normalized forms to be identical. It also checks, line by
line, that every chord present in the original survives in the variant, in
the same order.

Three source idioms count as a recall, because ChordPro renders all of them
as a label (or nothing) in print and as nothing at all in HTML:
  1. The bare {chorus} directive, optionally with a repeat count
     ({chorus: x2} expands the block twice).
  2. An empty {start_of_chorus}/{end_of_chorus} block holding only
     directives such as {comment: RIT} (implicit count of 1).
  3. A standalone {comment: ...} line naming both "rit" and a repeat count
     (e.g. {comment: Ultimo rit. x 2}) — deliberately narrow so it can only
     ever match a genuine final-chorus marker, never an unrelated note like
     {comment: Stesso giro del rit.} or {comment: RIT} alone.

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
CHORD_TOKEN_RE = re.compile(r"\[([^\]]*)\]")
START_CHORUS_RE = re.compile(r"^\{start_of_chorus\b[^}]*\}$")
END_CHORUS_RE = re.compile(r"^\{end_of_chorus\b[^}]*\}$")
CHORUS_RECALL_RE = re.compile(r"^\{chorus\b([^}]*)\}$")
# Narrow on purpose: must name both "rit" and a repeat count, so it can only
# match a genuine final-chorus marker like "Ultimo rit. x 2" — never
# {comment: RIT} alone or an unrelated note like {comment: Stesso giro del
# rit.} (no count).
FINAL_CHORUS_COMMENT_RE = re.compile(
    r"^\{comment:\s*.*\brit\b.*\bx\s*(\d+)\s*\}$", re.IGNORECASE
)
REPEAT_COUNT_RE = re.compile(r"\bx\s*(\d+)\b", re.IGNORECASE)


def _repeat_count(recall_args: str) -> int:
    m = REPEAT_COUNT_RE.search(recall_args)
    return int(m.group(1)) if m else 1


def expand_chorus_recalls(text: str) -> str:
    """Expand every chorus recall into its full chorus block, repeated by its
    marked count, wrapped in {start_of_chorus}/{end_of_chorus} markers — the
    canonical written-out form a site variant is expected to use.

    Three source idioms count as a recall, because ChordPro renders all of
    them as a label (or nothing) in print and as *nothing* in HTML:

      1. A bare ``{chorus}`` / ``{chorus: x2}`` directive line — repeat
         count from the ``xN`` argument, default 1.
      2. An empty chorus block — ``{start_of_chorus}`` … ``{end_of_chorus}``
         holding only directives such as ``{comment: RIT}`` and no lyrics
         (implicit count of 1).
      3. A standalone ``{comment: ...}`` line naming both "rit" and an
         ``xN`` count, e.g. ``{comment: Ultimo rit. x 2}``.

    A recall with no preceding full chorus is left untouched (malformed
    source, not this script's concern)."""
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
        recall = CHORUS_RECALL_RE.match(stripped)
        if recall and last_chorus is not None:
            out.extend(last_chorus * _repeat_count(recall.group(1)))
            continue
        final = FINAL_CHORUS_COMMENT_RE.match(stripped)
        if final and last_chorus is not None:
            out.extend(last_chorus * _repeat_count(stripped))
            continue
        out.append(line)
    return "\n".join(out)


def normalize(text: str) -> list[str]:
    text = expand_chorus_recalls(text)
    text = CHORD_RE.sub("", text)
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _chord_lines(text: str) -> list[list[str]]:
    """Chord tokens per non-blank lyric line, in the same order and with the
    same filtering as normalize() — one entry per line normalize() keeps, so
    it aligns 1:1 with normalize()'s output once orig/var equality holds."""
    expanded = expand_chorus_recalls(text)
    result = []
    for line in expanded.splitlines():
        if not CHORD_RE.sub("", line).strip():
            continue
        result.append(CHORD_TOKEN_RE.findall(line))
    return result


def _is_subsequence(small: list[str], big: list[str]) -> bool:
    it = iter(big)
    return all(tok in it for tok in small)


def check_chord_preservation(original: Path, variant: Path) -> str | None:
    """A variant may only add chords, never delete or change one. Checked
    per corresponding lyric line: the original's chord tokens, in order,
    must appear as a subsequence of the variant's — anything else means an
    existing chord was dropped or mutated, which normalize() alone can't
    see because it strips all bracket contents before comparing."""
    orig_chords = _chord_lines(original.read_text(encoding="utf-8"))
    var_chords = _chord_lines(variant.read_text(encoding="utf-8"))
    if len(orig_chords) != len(var_chords):
        # normalize() already caught this as a text divergence; nothing new
        # to report here.
        return None
    for i, (orig_tokens, var_tokens) in enumerate(zip(orig_chords, var_chords)):
        if not _is_subsequence(orig_tokens, var_tokens):
            return (
                f"{variant}: line {i + 1} (by lyric position) dropped or changed an "
                f"existing chord — original {orig_tokens!r} is not preserved in "
                f"variant {var_tokens!r}"
            )
    return None


def check_pair(original: Path, variant: Path) -> str | None:
    if original.name in COVER_FILES:
        return f"{variant}: site variants are not allowed for cover pseudo-songs ({original.name})"
    if not original.exists():
        return f"{variant}: no matching original {original.name} — every .site.cho must pair with an existing song"

    orig_norm = normalize(original.read_text(encoding="utf-8"))
    var_norm = normalize(variant.read_text(encoding="utf-8"))
    if orig_norm == var_norm:
        return check_chord_preservation(original, variant)

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
