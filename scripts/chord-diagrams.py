#!/usr/bin/env python3
"""Generate chord diagram data for the songbook site.

Produces JSON files for ukulele and guitar chord diagrams with fingerings,
tuning, and alias mapping from corpus-observed chord tokens to standardized
ChordPro chord names.

Usage:
  python3 scripts/chord-diagrams.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SONGBOOKS_DIR = REPO_ROOT / "songbooks"
SITE_ASSETS_DIR = REPO_ROOT / "site" / "assets" / "chords"

# ChordPro builtin config paths
BUILTIN_UKULELE = Path("/usr/share/perl5/ChordPro/res/config/ukulele.json")
BUILTIN_GUITAR = Path("/usr/share/perl5/ChordPro/res/config/guitar.json")

# Project override for ukulele (no guitar override yet)
PROJECT_UKULELE_OVERRIDE = REPO_ROOT / "chordpro-ukulele.json"

# Regex to extract chord tokens from .cho files: [CHORD]
CHORD_TOKEN_RE = re.compile(r"\[([^\]\s]+)\]")

# Latin/solfège note mappings
LATIN_TO_COMMON = {
    "do": "C",
    "re": "D",
    "mi": "E",
    "fa": "F",
    "sol": "G",
    "la": "A",
    "si": "B",
}

# Enharmonic equivalents (sharp ↔ flat)
ENHARMONIC_MAP = {
    "C#": "Db",
    "Db": "C#",
    "D#": "Eb",
    "Eb": "D#",
    "F#": "Gb",
    "Gb": "F#",
    "G#": "Ab",
    "Ab": "G#",
    "A#": "Bb",
    "Bb": "A#",
}


def sanitize_json(text: str) -> str:
    """Remove // comments and trailing commas from relaxed JSON.
    
    Handles comments not inside strings and trailing commas before } or ].
    """
    lines = []
    for line in text.split("\n"):
        # Find // comment position (but not inside strings)
        in_string = False
        escape_next = False
        comment_pos = -1
        for i, char in enumerate(line):
            if escape_next:
                escape_next = False
                continue
            if char == "\\":
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string and char == "/" and i + 1 < len(line) and line[i + 1] == "/":
                comment_pos = i
                break
        if comment_pos >= 0:
            line = line[:comment_pos]
        
        # Strip trailing commas before } or ] (both inline and at end of line)
        # Handle: "key": value, (before }) or "key": value, (before ]) 
        line = re.sub(r",(\s*[}\]])", r"\1", line)
        
        lines.append(line)
    
    # Post-process: handle trailing commas that span lines
    # Join all lines and fix any remaining trailing comma issues
    joined = "\n".join(lines)
    # Final pass: fix trailing commas before } or ]
    joined = re.sub(r",(\s*[}\]])", r"\1", joined)
    
    return joined



def load_json_config(path: Path) -> dict[str, Any]:
    """Load a ChordPro JSON config file (handles relaxed JSON with comments)."""
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    text = path.read_text(encoding="utf-8")
    text = sanitize_json(text)
    return json.loads(text)


def extract_chord_tokens_from_corpus() -> set[str]:
    """Extract all chord tokens used in .cho files."""
    tokens = set()
    for cho_file in SONGBOOKS_DIR.rglob("*.cho"):
        if cho_file.name.endswith(".site.cho"):
            # Skip site variants; they're duplicates of the base files
            continue
        try:
            content = cho_file.read_text(encoding="utf-8")
            for match in CHORD_TOKEN_RE.finditer(content):
                token = match.group(1).strip()
                if token and token != "N.C.":  # Exclude N.C.
                    tokens.add(token)
        except Exception as e:
            print(f"warning: {cho_file}: failed to extract chords — {e}", file=sys.stderr)
    return tokens


def translate_latin_chord(token: str) -> str | None:
    """Translate a Latin/solfège chord token to common notation.
    
    Handles:
    - DO, RE, MI, FA, SOL, LA, SI (case-insensitive on note)
    - Suffix rules: - = minor, 7 = dom7, m = minor, b = flat
    
    Examples: LA- → Am, MI7 → E7, SIb → Bb, MI-7 → Em7
    
    Returns None if translation fails.
    """
    token_lower = token.lower()
    
    # Try to extract note name from start of token.
    # Match against known solfège names by longest-first (so "sol" wins over
    # "so"), NOT a greedy [a-z]+ regex — a greedy match swallows suffix
    # letters like the "b" in "sib"/"mib" into the note part, silently
    # breaking flat translation (SIb, MIb, LAb, etc. never resolved).
    note_part = None
    suffix = ""
    for candidate in sorted(LATIN_TO_COMMON, key=len, reverse=True):
        if token_lower.startswith(candidate):
            note_part = candidate
            suffix = token_lower[len(candidate):]
            break
    
    if note_part is None:
        return None
    
    note = LATIN_TO_COMMON[note_part]
    
    # Process suffix modifiers
    # Observed patterns:
    # - LA- = Am (minor)
    # - MI7 = E7 (dominant 7)
    # - MI-7 = Em7 (minor 7)
    # - SIb = Bb (flat)
    # - DO# = C# (sharp, but less common in the corpus)
    
    # Handle flat (b) — typically at end like "SIb" or in middle like "MI-7"
    if "b" in suffix:
        note = note + "b"
        suffix = suffix.replace("b", "")
    
    # Handle sharp (#)
    if "#" in suffix:
        note = note + "#"
        suffix = suffix.replace("#", "")
    
    # Handle minor: - or m
    if "-" in suffix or "m" in suffix:
        suffix = suffix.replace("-", "").replace("m", "")
        if not suffix.startswith("7") and not suffix.startswith("maj"):
            # Plain minor (LA- → Am, MI- → Em)
            note = note + "m"
        elif suffix.startswith("7"):
            # Minor 7 (MI-7 → Em7)
            note = note + "m7"
            suffix = suffix[1:]  # Remove leading "7"
        elif suffix.startswith("maj"):
            # Rare: LA-maj7 → Ammaj7 (or Amin(maj7)?)
            note = note + "m" + suffix
            suffix = ""
    
    # Handle plain 7 (dominant 7)
    if suffix.startswith("7"):
        note = note + "7"
        suffix = suffix[1:]
    
    # Handle maj7 (if not already processed as part of minor)
    if suffix.startswith("maj"):
        note = note + suffix
        suffix = ""
    
    # If there's still unhandled suffix, bail
    if suffix.strip():
        return None
    
    return note


def resolve_slash_chord(token: str, chords_map: dict[str, Any]) -> str | None:
    """Resolve a slash chord (base/bass) to its base chord.
    
    E.g. D/F# → D, Am/C → Am, A#/D → A#
    
    Returns the base chord name if found and exists in chords_map, else None.
    """
    if "/" not in token:
        return None
    
    base, bass = token.split("/", 1)
    base = base.strip()
    bass = bass.strip()
    
    # Check if bass part is a note name (A-G with optional #/b)
    # Exclude things like A7/5b, D6/9, etc. (non-note denominators)
    if not re.match(r"^[A-Ga-g][#b]?$", bass):
        return None
    
    # Try to find base chord in map
    if base in chords_map:
        return base
    
    # Try to translate base as latin chord
    translated = translate_latin_chord(base)
    if translated and translated in chords_map:
        return translated
    
    # Try enharmonic mapping on base
    enharmonic = ENHARMONIC_MAP.get(base)
    if enharmonic and enharmonic in chords_map:
        return enharmonic
    
    return None


def try_enharmonic_fallback(token: str, chords_map: dict[str, Any]) -> str | None:
    """Try to resolve a token via enharmonic mapping (C# → Db, etc.)."""
    enharmonic = ENHARMONIC_MAP.get(token)
    if enharmonic and enharmonic in chords_map:
        return enharmonic
    return None


def build_aliases(
    chords_map: dict[str, Any], corpus_tokens: set[str]
) -> tuple[dict[str, str], set[str]]:
    """Build alias table and return unresolved tokens.
    
    For each token in corpus_tokens not directly in chords_map, attempt
    translation via:
    1. Latin/solfège notation
    2. Slash chord (base/bass)
    3. Enharmonic fallback (C# → Db)
    
    Returns (aliases dict, unresolved set).
    """
    aliases = {}
    unresolved = set()
    
    for token in corpus_tokens:
        if token in chords_map:
            # Already in map, no alias needed
            continue
        
        resolved = None
        
        # Try latin translation
        translated = translate_latin_chord(token)
        if translated and translated in chords_map:
            resolved = translated
        
        # Try slash chord resolution
        if not resolved:
            resolved = resolve_slash_chord(token, chords_map)
        
        # Try enharmonic fallback
        if not resolved:
            resolved = try_enharmonic_fallback(token, chords_map)
        
        if resolved:
            aliases[token] = resolved
        else:
            unresolved.add(token)
    
    return aliases, unresolved


def merge_chord_configs(
    builtin: dict[str, Any], override: dict[str, Any] | None = None
) -> tuple[dict[str, Any], list[str]]:
    """Merge builtin and optional override configs (override wins).
    
    Normalizes chords to a dict keyed by name, filtering out N.C.
    
    Returns (normalized chords dict, tuning list).
    """
    if not isinstance(builtin, dict):
        raise ValueError(f"Invalid builtin config: expected dict, got {type(builtin)}")
    
    # Use tuning from override if present, else builtin
    tuning = override.get("tuning", builtin.get("tuning", [])) if override else builtin.get("tuning", [])
    
    # Merge chords: start with builtin, overlay with override
    chords_dict = {}
    
    # Process builtin chords
    for chord_entry in builtin.get("chords", []):
        if not isinstance(chord_entry, dict):
            continue
        name = chord_entry.get("name")
        if name and name != "N.C.":
            # Extract relevant fields: base, frets, fingers (if present)
            chord_data = {
                "base": chord_entry.get("base", 1),
                "frets": chord_entry.get("frets", []),
            }
            if "fingers" in chord_entry:
                chord_data["fingers"] = chord_entry["fingers"]
            chords_dict[name] = chord_data
    
    # Process override chords (if provided)
    if override and isinstance(override, dict):
        for chord_entry in override.get("chords", []):
            if not isinstance(chord_entry, dict):
                continue
            name = chord_entry.get("name")
            if name and name != "N.C.":
                chord_data = {
                    "base": chord_entry.get("base", 1),
                    "frets": chord_entry.get("frets", []),
                }
                if "fingers" in chord_entry:
                    chord_data["fingers"] = chord_entry["fingers"]
                chords_dict[name] = chord_data
    
    return chords_dict, tuning



def generate_output(
    instrument: str,
    strings: int,
    tuning: list[str],
    chords_dict: dict[str, Any],
    aliases: dict[str, str],
) -> dict[str, Any]:
    """Generate the output JSON structure."""
    return {
        "instrument": instrument,
        "strings": strings,
        "tuning": tuning,
        "chords": chords_dict,
        "aliases": aliases,
    }


def main() -> int:
    """Main entry point."""
    try:
        # Load builtin configs
        print("Loading ChordPro builtin configs...", file=sys.stderr)
        builtin_uke = load_json_config(BUILTIN_UKULELE)
        builtin_guitar = load_json_config(BUILTIN_GUITAR)
        
        # Load project overrides (if they exist)
        project_uke_override = None
        if PROJECT_UKULELE_OVERRIDE.exists():
            print("Loading ukulele project override...", file=sys.stderr)
            project_uke_override = load_json_config(PROJECT_UKULELE_OVERRIDE)
        
        # Extract corpus tokens
        print("Scanning corpus for chord tokens...", file=sys.stderr)
        corpus_tokens = extract_chord_tokens_from_corpus()
        print(f"Found {len(corpus_tokens)} unique chord tokens in corpus", file=sys.stderr)
        
        # Merge ukulele configs
        print("Merging ukulele configs...", file=sys.stderr)
        uke_chords, uke_tuning = merge_chord_configs(builtin_uke, project_uke_override)
        uke_aliases, uke_unresolved = build_aliases(uke_chords, corpus_tokens)
        
        # Merge guitar configs
        print("Merging guitar configs...", file=sys.stderr)
        guitar_chords, guitar_tuning = merge_chord_configs(builtin_guitar, None)
        guitar_aliases, guitar_unresolved = build_aliases(
            guitar_chords, corpus_tokens
        )
        
        # Generate outputs
        uke_output = generate_output(
            instrument="ukulele",
            strings=len(uke_tuning),
            tuning=uke_tuning,
            chords_dict=uke_chords,
            aliases=uke_aliases,
        )
        
        guitar_output = generate_output(
            instrument="guitar",
            strings=len(guitar_tuning),
            tuning=guitar_tuning,
            chords_dict=guitar_chords,
            aliases=guitar_aliases,
        )
        
        # Create output directory
        SITE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Write ukulele output
        uke_path = SITE_ASSETS_DIR / "ukulele.json"
        uke_path.write_text(json.dumps(uke_output, indent=2), encoding="utf-8")
        print(f"✓ {uke_path}", file=sys.stderr)
        
        # Write guitar output
        guitar_path = SITE_ASSETS_DIR / "guitar.json"
        guitar_path.write_text(
            json.dumps(guitar_output, indent=2), encoding="utf-8"
        )
        print(f"✓ {guitar_path}", file=sys.stderr)
        
        # Print summary
        print("", file=sys.stderr)
        print("SUMMARY", file=sys.stderr)
        print(f"  Ukulele: {len(uke_chords)} chords, {len(uke_aliases)} aliases",
              file=sys.stderr)
        print(f"  Guitar:  {len(guitar_chords)} chords, {len(guitar_aliases)} aliases",
              file=sys.stderr)
        print("", file=sys.stderr)
        
        if uke_unresolved:
            print("Unresolved tokens (Ukulele):", file=sys.stderr)
            for token in sorted(uke_unresolved):
                print(f"  {token}", file=sys.stderr)
            print("", file=sys.stderr)
        
        if guitar_unresolved:
            print("Unresolved tokens (Guitar):", file=sys.stderr)
            for token in sorted(guitar_unresolved):
                print(f"  {token}", file=sys.stderr)
            print("", file=sys.stderr)
        
        return 0
    
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
