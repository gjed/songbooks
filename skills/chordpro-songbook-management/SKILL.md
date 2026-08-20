---
name: chordpro-songbook-management
description: Use when working on ChordPro songbook structure or rendering — creating a new songbook folder, numbering or renaming song files, building PDFs with make/chordpro, adding cover or chord-chart pages, defining or suppressing ukulele chord diagrams in chordpro-ukulele.json, or debugging "unknown chord" warnings and page-overflow issues. Triggers - "new songbook", "build pdf", "make", "cover page", "chord diagram", "define chord", "suppress", "rename songs".
---

# ChordPro Songbook Management

## When to use

Use this skill when: creating/organizing songbook folders, numbering files,
building PDFs, editing `chordpro-ukulele.json` (chord definitions, diagram
suppression, layout), or adding cover/chart/back-cover pages.

Do NOT use this skill for: writing or fixing the content of a single `.cho`
song — use `chordpro-song-authoring` instead.

## Layout and numbering

```text
songbooks/<songbook-slug>/        # kebab-case, one folder per songbook
  NN-song-slug.cho                # kebab-case slug, .cho extension
  00-cover.cho                    # optional special pages
  01-chord-chart.cho
  99-back-cover.cho
  cover-*.png, chords.png         # assets consumed by scripts/make-cover.py
```

Numbering schemes in use (check siblings before choosing):

- **Sequential**: `01-`, `02-`, … (e.g. `bricioline`) — file order = page order.
- **Flat prefix**: all songs share one prefix, e.g. `10-` (e.g. `hsb-eng`) —
  alphabetical order within the prefix; special pages use `00`/`01`/`99`.

Band/album metadata lives in each song's headers, never in folder names.

## Build

- `make` builds every songbook; `make <slug>` builds one (target name =
  folder name). Output: `pdf/<slug>.pdf`.
- The Makefile gates cover pages on the `songbook.yaml` sections: a
  `cover:` section means `scripts/make-cover.py` renders the cover/back
  pages and ghostscript merges them, an `intro:` section adds the intro
  page. With neither, all `.cho` files go straight through `chordpro`.
- Manual render of a subset:
  `chordpro --config chordpro-ukulele.json songbooks/<slug>/*.cho -o out.pdf`

Constraint: **one song = one page** (2-column layout). After any build,
check the page count matches the song count; a song spilling to a second
page needs content fixes or user sign-off, not silent acceptance.

## Chord configuration (`chordpro-ukulele.json`)

- Instrument comes from `"include": ["ukulele"]` — never set instrument
  inside `.cho` files.

- **Unknown chord warning** → add a definition to the `"chords"` array:

  ```json
  { "name": "SOL7sus2", "base": 1, "frets": [ 0, 2, 1, 0 ], "easy": true }
  ```

  `frets` are G-C-E-A strings, 0 = open. Italian chord names are aliases
  with the same fingering as their English equivalents — copy the English
  shape when adding an Italian alias.

- **Unwanted diagram** (slash chord, rare voicing that clutters the page)
  → add the exact chord name to `"diagrams".suppress`. Suppression hides
  the diagram but keeps the chord valid in lyrics.

- Layout knobs live under `"settings"` (columns) and `"pdf"` (fonts,
  spacing, margins). Change these repo-wide only with user approval —
  they affect every songbook.

## Steps: new songbook

1. `mkdir songbooks/<slug>` (kebab-case).
1. Add `songbooks/<slug>/songbook.yaml` (metadata: slug, title, language,
   notation, blurb, description — schema in CONTRIBUTING.md). Prose is
   written as `it`/`en` locale maps; `language:` selects which locale is
   printed, the README always uses `en`.
1. Add songs per `chordpro-song-authoring` conventions, numbered per the
   chosen scheme above.
1. Optionally declare `cover:` / `intro:` / `back:` sections in
   `songbook.yaml` plus image assets for `scripts/make-cover.py`.
1. Regenerate the root README songbook table:
   `python3 scripts/readme-table.py` (never edit it by hand).
1. Verify: `make <slug>` exits 0; inspect warnings; page count == song
   count (+ special pages).
1. Commit: `feat(<slug>): add <songbook or song title>` (Conventional
   Commits, scope = songbook slug).

## Edge cases

- **Renaming/renumbering songs**: use `git mv` so history survives; then
  rebuild to confirm ordering.
- **chordpro warnings about fonts**: the config points at
  `msttcorefonts` Courier paths; missing fonts are an environment problem,
  not a songbook problem — report, don't edit the config.
- **A chord needed in only one songbook**: definitions are global in
  `chordpro-ukulele.json`; that's fine, they're inert unless used.
- **Mixed-notation songbook** (Italian + English chords in one folder):
  stop and ask — each songbook should be internally consistent.

## Reference material

- `Makefile` — per-songbook rule generation, cover detection, gs merge.
- `chordpro-ukulele.json` — chord shapes, suppress list, PDF layout.
- `AGENTS.md` (repo root) — commit conventions and repo rules.
