#!/usr/bin/env python3
"""Import Ultimate Guitar chords to ChordPro format."""
import sys, json, re, html, urllib.request, urllib.error, argparse

ITALIAN = {'DO': 'C', 'RE': 'D', 'MI': 'E', 'FA': 'F', 'SOL': 'G', 'LA': 'A', 'SI': 'B'}

def merge(chord_line: str, lyric: str, conv=lambda t: t) -> str:
    # Columns come from the ORIGINAL chord line; conv only renames the token,
    # so converting SOL -> G never shifts a chord.
    tokens = [(m.start(), conv(m.group())) for m in re.finditer(r"\S+", chord_line)]
    out = lyric
    for col, chord in reversed(tokens):
        if col >= len(out):
            out = out.ljust(col) + f"[{chord}]"
        else:
            out = out[:col] + f"[{chord}]" + out[col:]
    return out.rstrip()

def roundtrip_ok(chord_line, lyric, merged, conv=lambda t: t) -> bool:
    cols, plain = [], ""
    for part in re.split(r"(\[[^\]]+\])", merged):
        if part.startswith("["):
            cols.append((len(plain), part[1:-1]))
        else:
            plain += part
    src = [(m.start(), conv(m.group())) for m in re.finditer(r"\S+", chord_line)]
    return cols == src and plain.rstrip() == lyric.rstrip()

def is_chord_line(line: str) -> bool:
    if not line.strip():
        return False
    tokens = re.findall(r"\S+", line)
    root = r"(?:[A-G]|DO|RE|MI|FA|SOL|LA|SI)[#b]?"
    pat = rf"^{root}(?:m|maj|min|dim|aug|sus\d?|add\d+|\d+|-|\+|\(\w+\))*(?:/{root})?$"
    return all(re.match(pat, t) for t in tokens)

def minor_to_m(tok: str) -> str:
    """`-` is minor (A- = Am, F#-7 = F#m7). The repo writes it `m`."""
    return re.sub(r'^([A-G][#b]?)-', r'\1m', tok)

def convert_token(tok: str) -> str:
    """Italian chord token -> common (SOL7 -> G7, LA- -> Am, DO/MI -> C/E)."""
    def one(part):
        m = re.match(r'^(DO|RE|MI|FA|SOL|LA|SI)(.*)$', part)
        return (ITALIAN[m.group(1)] + m.group(2)) if m else part
    return minor_to_m('/'.join(one(p) for p in tok.split('/')))

def extract_ug(html_content: str):
    match = re.search(r'class="js-store"\s+data-content="([^"]+)"', html_content)
    if not match:
        return None, None, None, None
    try:
        store = json.loads(html.unescape(match.group(1)))
        data = store["store"]["page"]["data"]
        tab = data["tab"]
        if tab.get("type") != "Chords":
            return None, None, None, None
        return tab.get("song_name", ""), tab.get("artist_name", ""), data["tab_view"]["wiki_tab"]["content"], tab.get("version", "Unknown")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None, None, None, None

def process_content(text: str):
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    has_italian = bool(re.search(r'\b(DO|RE|MI|FA|SOL|LA|SI)\b', text))
    text = re.sub(r'\[ch\]|\[/ch\]|\[tab\]|\[/tab\]', '', text)
    lines = text.split('\n')
    result, pair_count, i = [], 0, 0
    while i < len(lines):
        line = lines[i]
        if re.match(r'\[(Verse|Chorus|Intro|Bridge|Outro)(\s+\d+)?\]', line):
            result.append(('section', re.match(r'\[(\w+)', line).group(1)))
            i += 1
        elif not line.strip():
            i += 1
        elif is_chord_line(line):
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if next_line.strip() and not re.match(r'\[', next_line) and not is_chord_line(next_line):
                    conv = convert_token if has_italian else minor_to_m
                    merged = merge(line, next_line, conv)
                    if not roundtrip_ok(line, next_line, merged, conv):
                        return None, None, 7
                    result.append(('line', merged))
                    pair_count += 1
                    i += 2
                    continue
            conv = convert_token if has_italian else minor_to_m
            result.append(('line', ' '.join(f"[{conv(t)}]" for t in re.findall(r"\S+", line))))
            pair_count += 1
            i += 1
        else:
            result.append(('line', line.rstrip()))
            i += 1
    return result, pair_count, 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url_or_output', nargs='?')
    parser.add_argument('output', nargs='?')
    parser.add_argument('--file')
    parser.add_argument('--album')
    parser.add_argument('--key')
    parser.add_argument('--capo', type=int)
    args = parser.parse_args()

    if args.file:
        out_file = args.url_or_output
        if not out_file:
            parser.error('output file required')
        try:
            with open(args.file, 'r', encoding='utf-8', errors='replace') as f:
                html_content = f.read()
        except FileNotFoundError:
            print(f'Error: File not found: {args.file}', file=sys.stderr)
            sys.exit(2)
    else:
        url = args.url_or_output
        out_file = args.output
        if not url or not out_file:
            parser.error('URL and output required')
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'})
            with urllib.request.urlopen(req, timeout=10) as r:
                html_content = r.read().decode('utf-8', errors='replace')
        except urllib.error.URLError:
            print('Error: Network error fetching URL', file=sys.stderr)
            sys.exit(3)
        except Exception as e:
            print(f'Error: {e}', file=sys.stderr)
            sys.exit(2)

    title, artist, content, version = extract_ug(html_content)
    if not title:
        if 'class="js-store"' not in html_content:
            print('Error: Missing js-store (not a UG page or is a challenge page)', file=sys.stderr)
            sys.exit(4)
        print('Error: Tab type is not "Chords"', file=sys.stderr)
        sys.exit(5)

    result, pair_count, err = process_content(content)
    if err:
        print('Error: Round-trip verification failed', file=sys.stderr)
        sys.exit(7)
    if not result:
        print('Error: No chord/lyric pairs found', file=sys.stderr)
        sys.exit(6)

    title = title or 'TODO'
    artist = artist or 'TODO'
    album = args.album or 'TODO'
    key = args.key or 'TODO'

    cho = [f'{{title: {title}}}', f'{{artist: {artist}}}', f'{{album: {album}}}', f'{{key: {key}}}']
    if args.capo:
        cho.append(f'{{capo: {args.capo}}}')
    cho.append('')

    in_section = None
    for item_type, val in result:
        if item_type == 'section':
            if in_section:
                cho.append('{end_of_chorus}' if in_section == 'Chorus' else '{end_of_verse}')
            if val == 'Chorus':
                cho.append('{start_of_chorus}')
                cho.append('{comment: RIT}')
            else:
                cho.append('{start_of_verse}')
            in_section = val
        elif item_type == 'line':
            cho.append(val)

    if in_section:
        cho.append('{end_of_chorus}' if in_section == 'Chorus' else '{end_of_verse}')

    if not any(t == 'section' for t, _ in result):
        lines_only = [val for t, val in result if t == 'line']
        cho = cho[:-1] + ['{start_of_verse}'] + lines_only + ['{end_of_verse}']

    try:
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(cho) + '\n')
    except Exception as e:
        print(f'Error writing output: {e}', file=sys.stderr)
        sys.exit(8)

    todos = []
    if args.album is None:
        todos.append('album')
    if args.key is None:
        todos.append('key')

    src = args.file if args.file else args.url_or_output
    print(f'Source: {src}', file=sys.stderr)
    print(f'UG version: {version}', file=sys.stderr)
    print(f'Pairs: {pair_count}', file=sys.stderr)
    print(f'Round-trip: all {pair_count} pairs OK', file=sys.stderr)
    print(f'Output: {out_file}', file=sys.stderr)
    if todos:
        print(f'WARNING: Missing fields: {", ".join(todos)}', file=sys.stderr)

if __name__ == '__main__':
    main()
