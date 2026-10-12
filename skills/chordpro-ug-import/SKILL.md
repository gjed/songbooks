---
name: chordpro-ug-import
description: Use when converting a chords page from tabs.ultimate-guitar.com (Ultimate Guitar, "UG") into a ChordPro `.cho` file for this repo — fetching the page, pulling the chord sheet out of the page data, and mapping chords-above-lyrics onto inline `[CHORD]` positions without shifting any chord. Triggers - "ultimate guitar", "tabs.ultimate-guitar.com", "import song from UG", "get the chords from this link", "convert tab to chordpro", "chords in the wrong place".
---

# Importing a song from Ultimate Guitar

## When to use

A user gives a `tabs.ultimate-guitar.com/tab/...-chords-<id>` URL and wants
the song as a `.cho` file. Authoring rules for the result (headers, sections,
notation, one page per song) stay in `chordpro-song-authoring`; this skill
covers only getting the sheet off the site and placing chords correctly.

Do NOT use for `-tabs-` (guitar tablature), `-bass-`, `-ukulele-` or `-pro-`
pages: tablature is not a chord sheet and `-pro-` data is not plain text.
`-ukulele-` pages are fine as a *chord* source; say so when you use one.

## 1. Fetch

Plain HTTP works with a desktop User-Agent; no login, no browser needed:

```bash
curl -sL -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36" \
  -o /tmp/ug.html "<url>"
```

If it returns a challenge page or a missing `js-store` (see below), fall back
to the browser tooling (`agent-browser`) and read the same JSON from the live
DOM. Never scrape the rendered text: it loses the column positions.

## 2. Extract

The page embeds its data as HTML-escaped JSON in one element:

```python
import re, json, html
s = open("/tmp/ug.html", encoding="utf-8", errors="replace").read()
store = json.loads(html.unescape(
    re.search(r'class="js-store"\s+data-content="([^"]+)"', s).group(1)))
data  = store["store"]["page"]["data"]
tab   = data["tab"]                       # song_name, artist_name, type, version, tonality_name
text  = data["tab_view"]["wiki_tab"]["content"]
```

Check `tab["type"] == "Chords"` first. Inspect `data["tab_view"]` keys for
tuning / capo / tonality hints instead of assuming them; capo is often only
written inside `text` ("Capo 2") or missing.

`text` is monospace layout with UG markup:

- `[ch]Am7[/ch]` wraps every chord; `[tab]...[/tab]` wraps lines that must be
  rendered monospace. Strip both tags — but **only after** you have measured
  columns (step 3), and measure on text with `[ch]`/`[/ch]` removed first.
- `[Verse 1]`, `[Chorus]`, `[Intro]`… on their own line are section headers.
- Line endings are `\r\n`; normalise to `\n`. Tabs (`\t`) should not appear;
  if they do, expand to 8 columns before measuring.
- Lines can mix a chord line and annotations (`x2`, `(riff)`, `N.C.`).
  Keep annotations out of the lyric; put `x2` into `{comment: ...}` only if
  the chorus is genuinely repeated there.

## 3. Place chords (the part that goes wrong)

A chord line sits directly above its lyric line and aligns by **character
column** in monospace. The only correct mapping is column → character index.
Do it mechanically, never by eye and never by "snapping" to word starts.

For each chord line `C` followed by a lyric line `L` (blank/section lines
break the pairing):

1. Strip `[ch]`/`[/ch]` from `C` so every remaining character is one column.
1. Find each chord token and its start column `c` (regex `\S+`).
1. Insert `[token]` into `L` at index `c`, processing right-to-left so earlier
   indices do not move.
1. If `c >= len(L)`, pad `L` with spaces to `c` first, then append — the chord
   belongs after the last word, not squeezed into it.
1. A chord that lands inside a word stays inside the word (ChordPro supports
   mid-word chords; sung syllables often change there). Do not move it.
1. Chord line with no lyric beneath (intro, solo, outro, bridge riff): emit one
   line of chords separated by single spaces, `[C] [G] [Am]`.
1. A lyric line with no chord line above it: copy it unchanged — it continues
   the previous chord. Never carry chords down from a previous line.

Reference implementation (no lyrics involved, safe to keep in a scratch file):

```python
import re

def merge(chord_line: str, lyric: str) -> str:
    tokens = [(m.start(), m.group()) for m in re.finditer(r"\S+", chord_line)]
    out = lyric
    for col, chord in reversed(tokens):
        if col >= len(out):
            out = out.ljust(col) + f"[{chord}]"
        else:
            out = out[:col] + f"[{chord}]" + out[col:]
    return out.rstrip()
```

### Verify placement (mandatory)

Round-trip every paired line: rebuild the original columns from your output
and compare to the source.

```python
def roundtrip_ok(chord_line, lyric, merged):
    cols, plain = [], ""
    for part in re.split(r"(\[[^\]]+\])", merged):
        if part.startswith("["):
            cols.append((len(plain), part[1:-1]))
        else:
            plain += part
    src = [(m.start(), m.group()) for m in re.finditer(r"\S+", chord_line)]
    return cols == src and plain.rstrip() == lyric.rstrip()
```

Every pair must pass. Then read three random lines aloud-style against the UG
page: the chord must precede the same syllable as in the source. Report any
line where the source itself looks misaligned (UG authors make mistakes);
fix only when the intended syllable is unambiguous, and say so.

## 4. Convert to this repo's conventions

- **Notation**: all `.cho` in this repo are common (`C Am G7`). UG pages for
  Italian songs are normally already common; if you see `DO`/`SOL`/`LA-`,
  map to common before writing (never mix notations).
- **Headers**: `{title}` and `{artist}` from `tab`. `{album}` and `{key}` are
  required but not on UG — look the album up (Spotify/MusicBrainz) and take
  the key from the first chord of the song or the UG tonality when present.
  If either is a guess, say it in the hand-off; never invent silently.
  Capo: `{capo: N}` right after `{key: ...}`, only if the page states it.
- **Sections**: `[Verse N]` → `{start_of_verse}`/`{end_of_verse}`, `[Chorus]`
  → `{start_of_chorus}` + `{comment: RIT}`… exactly as `chordpro-song-authoring`
  prescribes (no `label=`; intro/bridge/outro are plain verse blocks).
- **Repeats**: write what the page writes. Collapse to a `{chorus}` recall
  only if the later text is identical, and only if the page shows chords once
  (see the site-variant rule in `chordpro-song-authoring`).
- **One page**: after writing, render the file alone
  (`chordpro --config chordpro-ukulele.json <file> -o /tmp/x.pdf`) and check
  `pdfinfo | grep Pages` is `1`; a longer song needs a user decision.

## 5. Hand-off checklist

Report: source URL and UG version number, what was guessed (key, album,
capo), any line where the source alignment looked wrong, and the round-trip
result. Commit the song on its own (`feat(<songbook>): add <title>`).

## Gotchas

- Do not trust the page's visible text order for repeated sections; use
  `text` as returned.
- `[ch]` can sit inside a word's column span; a regex that matches chords
  *inside* the already-stripped text will offset every later chord by 9
  characters per chord. Strip tags first.
- Rating/"hits" and user comments live elsewhere in the JSON; ignore them.
- This is a private songbook workflow: do not paste the sheet into commit
  messages, issues, or chat logs, only into the `.cho` file.
