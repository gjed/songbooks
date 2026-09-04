---
name: chordpro-songbook-management
description: Use when working on ChordPro songbook structure or rendering — creating a new songbook folder, numbering or renaming song files, building PDFs with make/chordpro, editing songbook.yaml (metadata, bilingual strings, cover/intro/back layout), managing Spotify playlist manifests, defining or suppressing ukulele chord diagrams in chordpro-ukulele.json, or debugging "unknown chord" warnings and page-overflow issues. Triggers - "new songbook", "build pdf", "make", "cover page", "back cover", "intro page", "songbook.yaml", "spotify", "playlist", "translation", "chord diagram", "define chord", "suppress", "rename songs".
---

# ChordPro Songbook Management

## When to use

Use this skill when: creating/organizing songbook folders, numbering files,
building PDFs, editing `songbook.yaml` (metadata, bilingual strings,
cover/intro/back layout), curating Spotify manifests, editing
`chordpro-ukulele.json` (chord definitions, diagram suppression, layout),
or adding cover/chart/back-cover pages.

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

## Songbook metadata (`songbook.yaml`)

Every songbook ships a human-authored `songbooks/<slug>/songbook.yaml` —
the single source for identity and prose (full schema in CONTRIBUTING.md):

```yaml
slug: bricioline          # matches the folder name
title: Bricioline         # display name (README table, Spotify playlists)
artist: Queen of Saba     # optional — single-artist songbooks only
language: it              # primary language — picks the printed locale
notation: common          # chord names in the .cho files: common | latin
blurb: …                  # one line, README table
description: { it: …, en: … }   # longer prose, markdown allowed
```

- `language:` decides which locale is printed (`it` or `en`). Current
  assignment: `hsb-eng`, `good-songs`, `wanderwaal` are `en`; everything
  else is `it`.
- `notation:` records what the `.cho` files store. New songbooks are
  always `common`; `latin` exists only for legacy songbooks
  (`canzoni-ribelli`, `hbs-ita`).
- `spotify.yaml` is a **separate, machine-written** file — never fold its
  content into `songbook.yaml`.
- After adding/editing a `songbook.yaml`, regenerate the README table:
  `python3 scripts/readme-table.py` (never edit it by hand).

### Bilingual strings (i18n)

Any string value in `songbook.yaml` may be a **locale map** instead of a
plain string:

```yaml
blurb:
  it: Queen of Saba — musica italiana per bambini
  en: Queen of Saba — Italian children's music
```

- Printed PDF (`make-cover.py`) uses the songbook's own `language:`; the
  root README table always uses `en`; the website uses the visitor's
  locale.
- A missing translation falls back to `en` — half-translated songbooks
  still build.
- Only mappings whose keys are *all* known locales (`it`, `en`) are
  treated as translatable; other nested objects (`rules:`, `links:`) pass
  through untouched. Shared implementation: `scripts/songbook_meta.py`.
- A print run is monolingual: the other locale exists for README/site
  only and never reaches the page.

## Build

- `make` builds every songbook; `make <slug>` builds one (target name =
  folder name). Output: `pdf/<slug>.pdf`.
- The Makefile gates cover pages on the `songbook.yaml` sections: a
  `cover:` section means `scripts/make-cover.py` renders the cover/back
  pages and ghostscript merges them, an `intro:` section adds the intro
  page. With neither, all `.cho` files go straight through `chordpro`.
- Chord names print as authored (common notation). Italian-notation output
  is a **build-time transcode**, not a file change:
  `make guitar-ita SB=<slug>` renders with `--transcode=latin`
  (`guitar-eng` keeps `common`). These are previews, not release artifacts.
- Optional per-songbook layout overlay `songbooks/<slug>/layout.json` is
  merged on top of the global config (later config wins) — used e.g. to
  reclaim space so every song fits one page.
- Manual render of a subset:
  `chordpro --config chordpro-ukulele.json songbooks/<slug>/*.cho -o out.pdf`

Constraint: **one song = one page** (2-column layout). After any build,
check the page count matches the song count; a song spilling to a second
page needs content fixes or user sign-off, not silent acceptance.

## Site variants and build enforcement

A song may have an optional `.site.cho` variant used only by the online (HTML) build. If the variant exists, the HTML build uses it; the PDF/print build always ignores `.site.cho` files and uses the original. This allows the online view to show chords on all verses and expanded choruses without breaking the print constraint of one song per page.

A guard script, `scripts/check-site-variants.py`, runs during `make site` and in CI. For each `.site.cho` it normalizes both files — expands chorus recalls into the full chorus block, strips all inline `[CHORD]` brackets, collapses whitespace — and requires the results to be identical. Any other difference (lyric text, section order, directives) hard-fails the build with a diff report.

Both "repeat the chorus" idioms count as a recall and expand to the same block: the bare `{chorus}` / `{chorus: x2}` directive, and an empty `{start_of_chorus}`…`{end_of_chorus}` block holding only directives such as `{comment: RIT}`. Recall arguments are dropped on expansion, so a variant for a `{chorus: x2}` song writes the chorus block out once.

**To fix a reported divergence**: re-sync the variant to the original by checking that:

1. All lyric text and section structure match the original.
1. The only changes are additional `[CHORD]` brackets on later verses and/or choruses written out in full.
1. All other directives, metadata, and ordering match exactly.

Re-run `make site` to verify the guard passes. See `skills/chordpro-song-authoring` for permitted differences and the hand-placement rule.

## Cover, intro, and back pages

Covers are NOT rendered by ChordPro. `scripts/make-cover.py` draws them
with `reportlab`; the Makefile merges them around the ChordPro-rendered
songs with Ghostscript.

- Declared in `songbook.yaml`: a `cover:` section produces cover + back
  pages, an `intro:` section adds the intro page (album description +
  Spotify link). Every key is optional with built-in defaults; full key
  reference in CONTRIBUTING.md ("Covers").
- `cover:` keys: `title`, `subtitle` (default: none), `logo` +
  `logo_width`/`logo_offset`, `strip_top`/`strip_bottom`, `background`,
  `rules` (full-width color bars, `y` in PDF points from page bottom,
  0–842 on A4). Set a key to `null` to drop the element.
- `back:` keys: `image` + `image_width`, `caption`, `description`
  (string or list of paragraphs, wrapped and centred), font/size/color
  knobs, and the Spotify block.
- **Spotify block is automatic**: when the songbook's `spotify.yaml` has a
  resolved playlist/album link, the back page draws a label + clickable
  URL + vector QR of the same link. Unresolved/missing manifest skips it
  silently; `spotify: false` opts out. `spotify_label` defaults to a
  translated string (it: "Ascolta su Spotify" / en: "Listen on Spotify").
- Any string here may be a locale map (see Bilingual strings); the printed
  page uses the songbook's `language:`.
- Assets live in the songbook folder: `cover-*.png`, `strip-*.png`,
  `back-*.png`. The chord-chart page is emitted only when the songbook
  ships a `chords.png`. Image alpha is preserved.
- Special pages use reserved numbers: `00-cover.cho`, `01-chord-chart.cho`,
  `99-back-cover.cho` — placeholders consumed by the cover pipeline, never
  given site variants.

## Spotify playlists (`spotify.yaml`)

Each non-empty songbook maps to a Spotify link: a repo-owned curated
playlist, or a direct album link when the songbook *is* one official
release. Mapping lives in `songbooks/<slug>/spotify.yaml`, driven by
`scripts/spotify_playlists.py`. The manifest is **machine-written** —
never hand-edit URIs; run resolve instead.

Two-phase model — matching is human work, pushing is machine work:

1. **resolve** (local, interactive, never in CI):
   `make spotify-resolve SB=<slug>` scans `.cho` files, searches Spotify,
   a human pins each track. Picks are written to `spotify.yaml` and
   committed. Fix a bad pick with
   `python3 scripts/spotify_playlists.py resolve --songbook <slug> --recheck`.
1. **sync** (CI, unattended, on push to `main`): pushes pinned URIs only,
   no searching. Creates the playlist on the fly if `playlist_id` is
   missing (name-matched, so re-runs never duplicate).

Manifest facts:

- `mode: playlist` (default, per-song curation) or `mode: album` (one
  official release — resolve links the album once, sync pushes nothing).
- Track values: `""` = unresolved, `spotify:track:<id>` = pinned,
  `null` = deliberately not on Spotify (resolve stops asking).
- Coverage is optional: `spotify-validate` (PR check) hard-fails only on a
  malformed manifest; gaps are informational.
- The back-cover Spotify block and release notes
  (`spotify_playlists.py links`) both read this manifest — resolving a
  songbook is what makes its printed QR link appear.

## Chord configuration (`chordpro-ukulele.json`)

- Instrument comes from `"include": ["ukulele"]` — never set instrument
  inside `.cho` files. Note parsing is `"notes".system: common` — chord
  names in `.cho` files are always common notation (see
  `chordpro-song-authoring`); Italian names appear only via build-time
  transcode.

- **Unknown chord warning** → add a definition to the `"chords"` array:

  ```json
  { "name": "G7sus2", "base": 1, "frets": [ 0, 2, 1, 0 ], "easy": true }
  ```

  `frets` are G-C-E-A strings, 0 = open.

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
1. Optionally curate Spotify: `make spotify-resolve SB=<slug>`, commit the
   resulting `spotify.yaml`.
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
  stop and ask — each songbook must be internally consistent, and new
  content is always common notation.
- **Spotify sync auth failure in CI**: refresh token expired (~6 months on
  Development Mode apps). Rerun `python3 scripts/spotify_playlists.py auth`
  locally and update the `SPOTIFY_REFRESH_TOKEN` repo secret — nothing in
  the repo changes.

## Reference material

- `Makefile` — per-songbook rule generation, cover detection, gs merge,
  transcode previews, spotify targets, site targets.
- `chordpro-ukulele.json` — note system, chord shapes, suppress list, PDF
  layout.
- `CONTRIBUTING.md` — full `songbook.yaml` schema, cover key reference,
  Spotify setup/rotation.
- `scripts/make-cover.py`, `scripts/songbook_meta.py` — cover rendering
  and locale-map resolution.
- `scripts/spotify_playlists.py` — auth/resolve/sync/validate/links.
- `AGENTS.md` (repo root) — commit conventions and repo rules.
