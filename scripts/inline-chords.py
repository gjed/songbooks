#!/usr/bin/env python3
"""
Convert chord-above-lyric {comment: CHORDS} lines to inline [CHORD]lyric format.
"""

import re
import sys
import os

CHORD_RE = re.compile(
    r'^[A-G][#b]?(m|maj|min|dim|aug|sus|add)?(\d)?(\/[A-G][#b]?)?'
    r'(sus\d?|add\d?|maj\d?|m\d?)?$'
)

def is_chord(token):
    """Return True if token looks like a chord name."""
    # Strip trailing punctuation
    token = token.rstrip('.,;:')
    return bool(CHORD_RE.match(token))

def is_chord_line(text):
    """Return True if text is a pure chord line (all tokens are chords)."""
    text = text.strip()
    if not text:
        return False
    tokens = text.split()
    if not tokens:
        return False
    # Must have at least one chord and all tokens must be chords
    return len(tokens) >= 1 and all(is_chord(t) for t in tokens)

def extract_chords_from_comment(line):
    """Extract chord text from {comment: ...} line. Returns None if not a chord comment."""
    m = re.match(r'^\{comment:\s*(.*?)\s*\}$', line.strip())
    if not m:
        return None
    content = m.group(1)
    if is_chord_line(content):
        return content
    return None

def merge_chords_into_lyric(chord_line, lyric_line):
    """
    Given a chord line like 'Am         G    C' and a lyric line,
    insert [CHORD] markers at the appropriate positions.
    """
    # Find chord positions in the chord line
    chords = []
    for m in re.finditer(r'\S+', chord_line):
        token = m.group()
        if is_chord(token):
            chords.append((m.start(), token))

    if not chords:
        return lyric_line

    # Insert chords into lyric at corresponding positions
    # We'll build the result character by character
    result = list(lyric_line)
    # Insert from right to left to preserve positions
    offset = 0
    insertions = []
    for pos, chord in chords:
        # Map chord position to lyric position (clamp to lyric length)
        lyric_pos = min(pos, len(lyric_line))
        insertions.append((lyric_pos, f'[{chord}]'))

    # Sort by position, insert from left to right tracking offset
    insertions.sort(key=lambda x: x[0])
    result_str = lyric_line
    offset = 0
    for pos, tag in insertions:
        insert_at = pos + offset
        result_str = result_str[:insert_at] + tag + result_str[insert_at:]
        offset += len(tag)

    return result_str

def convert_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    out = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip('\n')

        # Check if this is a chord comment line
        chord_text = extract_chords_from_comment(line)
        if chord_text is not None:
            # Look ahead for the next non-empty, non-directive line
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1

            if j < len(lines):
                next_line = lines[j].rstrip('\n')
                # Only merge if next line is a lyric (not a directive or another chord comment)
                if (not next_line.strip().startswith('{') and
                    not extract_chords_from_comment(next_line) and
                    next_line.strip()):
                    # Merge chord into lyric
                    merged = merge_chords_into_lyric(chord_text, next_line)
                    out.append(merged + '\n')
                    i = j + 1
                    continue

            # No lyric follows — keep as comment but strip chord-only comments
            # (they're structural markers with no lyric to attach to)
            # Keep it as a comment for now
            out.append(line + '\n')
        else:
            out.append(line + '\n')
        i += 1

    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(out)

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <file.cho> [file2.cho ...]")
        sys.exit(1)

    for path in sys.argv[1:]:
        print(f"Converting: {path}")
        convert_file(path)

if __name__ == '__main__':
    main()
