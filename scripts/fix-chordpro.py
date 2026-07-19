#!/usr/bin/env python3
"""Convert remaining {comment: CHORDS} lines to inline [CHORD] format and fix section markers."""
import re
import os
import glob

DIR = "/home/marco/repos/gjed/qos-songbook/songbooks/hsb-eng"
CHORD_RE = re.compile(r'^\{comment:\s*([A-G][#b]?(?:m|dim|aug|sus[24]|7|maj7|dim7|add9|6|9)?(?:\s*/\s*[A-G][#b]?)?(?:\s*[A-G][#b]?(?:m|dim|aug|sus[24]|7|maj7|dim7|add9|6|9)?)*)\s*\}$')
IS_CHORD = re.compile(r'^[A-G][#b]?(?:m|dim|aug|sus[24]|7|maj7|dim7|add9|6|9)?(?:\s*/\s*[A-G][#b]?(?:m|dim|aug|sus[24]|7|maj7|dim7|add9|6|9)?)?$')
# Also handle patterns like {comment: Am} - single chords
SINGLE_CHORD = re.compile(r'^\{comment:\s*([A-G][#b]?(?:m|dim|aug|sus[24]|7|maj7|dim7|add9|6|9)?)\s*\}$')

def is_chord_line(text):
    """Check if text is purely a sequence of chords."""
    text = text.strip().strip('{}')
    if text.startswith('comment:'):
        text = text[8:].strip()
    parts = text.split()
    if len(parts) == 0:
        return False
    # All parts must be valid chords
    return all(IS_CHORD.match(p) for p in parts)

def fix_file(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Check if this is a {comment: CHORDS} line
        m = CHORD_RE.match(stripped)
        if m:
            chord_str = m.group(1)
            chords = chord_str.split()
            if all(IS_CHORD.match(c) for c in chords):
                # Check next non-blank, non-directive line
                for j in range(i+1, len(lines)):
                    next_line = lines[j].strip()
                    if not next_line:
                        continue
                    # Don't merge into directives
                    if next_line.startswith('{') and not next_line.startswith('{comment'):
                        # Insert chord line as-is before directive
                        new_lines.append(line)
                        i += 1
                        break
                    if next_line.startswith('{comment'):
                        continue
                    # Found a lyric line — merge chords inline
                    lyric = lines[j]
                    # Place chords at the start of the lyric line
                    # (simple approach: put all chords at beginning)
                    chord_prefix = ''.join(f'[{c}]' for c in chords)
                    if lyric.strip():
                        new_lines.append(lyric.rstrip('\n') + ' ' + chord_prefix + '\n')
                    else:
                        new_lines.append(chord_prefix + '\n')
                    i = j + 1
                    break
                else:
                    new_lines.append(line)
                    i += 1
                continue

        # Check for bare chord lines (not in {comment})
        if stripped and not stripped.startswith('{'):
            parts = stripped.split()
            if len(parts) >= 2 and all(IS_CHORD.match(p) for p in parts):
                # Find the next lyric line to merge into
                for j in range(i+1, len(lines)):
                    next_line = lines[j].strip()
                    if not next_line:
                        # Bare chord line with nothing under — keep as comment
                        new_lines.append('{comment: ' + stripped + '}\n')
                        i += 1
                        break
                    if next_line.startswith('{'):
                        # Next is a directive — keep bare
                        new_lines.append(line)
                        i += 1
                        break
                    # Merge
                    chord_prefix = ''.join(f'[{c}]' for c in parts)
                    if next_line.strip():
                        new_lines.append(chord_prefix + next_line)
                    else:
                        new_lines.append(chord_prefix + '\n')
                    i = j + 1
                    break
                else:
                    new_lines.append(line)
                    i += 1
                continue

        new_lines.append(line)
        i += 1

    # Write back
    with open(filepath, 'w') as f:
        f.writelines(new_lines)

    return True

files = sorted(glob.glob(os.path.join(DIR, '10-*.cho')))
fixed = 0
for f in files:
    try:
        if fix_file(f):
            fixed += 1
    except Exception as e:
        print(f"ERROR {os.path.basename(f)}: {e}")

print(f"Fixed {fixed}/{len(files)} files")
