#!/usr/bin/env python3
"""Fix remaining formatting issues in hsb-eng songs."""
import re
import os
import glob

DIR = "/home/marco/repos/gjed/qos-songbook/songbooks/hsb-eng"

def fix_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
        lines = content.split('\n')

    new_lines = []
    in_chorus = False
    in_verse = False
    blank_count = 0

    for line in lines:
        stripped = line.strip()

        # Track section context
        if stripped == '{start_of_chorus}':
            in_chorus = True
        elif stripped == '{end_of_chorus}':
            in_chorus = False
        elif stripped == '{start_of_verse}':
            in_verse = True
        elif stripped == '{end_of_verse}':
            in_verse = False

        # Remove redundant {comment: Chorus} inside chorus sections
        if in_chorus and stripped in ('{comment: Chorus}', '{comment: Chorus.}', '{comment: Chorus}'):
            # Also check for {comment: Chorus}  (with spaces)
            continue
        if re.match(r'^\{comment:\s*Chorus\.?\s*\}$', stripped) and in_chorus:
            continue

        # Convert bare structural text to {comment}
        if re.match(r'^Chorus\.?\s*\(.*\)$', stripped) or \
           re.match(r'^Chorus\.?\s*\+(.*)$', stripped) or \
           re.match(r'^Chorus\.\s*x\d', stripped) or \
           re.match(r'^Bridge\d?\s*:', stripped) or \
           re.match(r'^Intro\d?\s*:', stripped):
            # Only convert if not already inside a section
            if not in_chorus and not in_verse:
                new_lines.append('{comment: ' + stripped + '}')
                continue

        # Reduce excessive blank lines (more than 2 consecutive)
        if stripped == '':
            blank_count += 1
            if blank_count > 2:
                continue
        else:
            blank_count = 0

        new_lines.append(line)

    # Fix missing end tags
    result = '\n'.join(new_lines)

    with open(filepath, 'w') as f:
        f.write(result + '\n')

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
