# Contributing

Technical reference for working on the songbooks: file conventions, build
setup, and PR workflow.

## Repository layout

```text
songbooks/
  <songbook-slug>/      one folder per songbook, kebab-case
    NN-song-slug.cho    two-digit track prefix, kebab-case slug
    songbook.yaml       metadata + optional cover / intro / back layout
    layout.json         optional per-songbook layout overlay
    spotify.yaml        Spotify mapping (machine-written, see below)
pdf/                    compiled PDFs (build output)
scripts/                helper scripts (cover generation)
chordpro-ukulele.json   global ChordPro config
Makefile                build targets
```

Numbering conventions:

- Content songbooks use sequential prefixes: `01-`, `02-`, …
- Songbooks with special pages reserve `00-cover.cho`,
  `01-chord-chart.cho`, and `99-back-cover.cho`; songs start at `10-`.

## Songbook metadata (`songbook.yaml`)

Every songbook ships a human-authored `songbooks/<slug>/songbook.yaml`.
It is the single source for the songbook's identity and prose:

```yaml
slug: bricioline          # matches the folder name
title: Bricioline         # display name (README table, Spotify playlists)
artist: Queen of Saba     # optional — single-artist songbooks only
language: it              # primary language — picks the printed locale
notation: common          # chord names in the .cho files: common | latin

blurb: Queen of Saba — Italian children's music   # one line, README table

description:              # longer prose, markdown allowed
  it: >-
    Songbook di *Bricioline (Canzoni per chi cresce)* …
  en: >-
    Songbook for *Bricioline (Canzoni per chi cresce)* …
```

The songbook table in the root `README.md` is generated from these
files — after adding or editing one, run:

```bash
python3 scripts/readme-table.py
```

Never edit the table by hand.

The optional `cover:`, `intro:`, and `back:` sections of the same file
drive the printed cover pages (next section). `spotify.yaml` stays a
separate file because it is machine-written: `spotify_playlists.py resolve` rewrites it wholesale.

### Bilingual strings

Any string in `songbook.yaml` may be written as a **locale map** — a
mapping whose keys are locale codes (`it`, `en`) — instead of a plain
string:

```yaml
blurb:
  it: Queen of Saba — musica italiana per bambini
  en: Queen of Saba — Italian children's music
```

Which one is used depends on the consumer:

| Consumer                      | Locale                         |
| ----------------------------- | ------------------------------ |
| Printed PDF (`make-cover.py`) | the songbook's own `language:` |
| Root `README.md` table        | always `en`                    |

A print run is monolingual — the other locales exist for the README and
the website, and never reach the page. A missing translation falls back
to `en` rather than printing nothing, so a half-translated songbook
still builds.

Locale maps are recognised by their keys, so ordinary nested objects
(`rules:` entries, `links:` entries) are left alone. Only a mapping whose
keys are *all* known locales is treated as translatable — a typo like
`{en: …, de: …}` is passed through untouched instead of being silently
half-resolved. Both readers share one implementation in
`scripts/songbook_meta.py`.

## Covers

Covers are not rendered by ChordPro. `scripts/make-cover.py` draws them
with `reportlab`, and the Makefile merges them around the ChordPro-rendered
songs with Ghostscript.

A songbook gets cover pages when its `songbook.yaml` declares a `cover:`
section (and an intro page when it declares `intro:`). Every key is
optional; omitted keys fall back to the built-in defaults:

```yaml
cover:
  title: Songbook Title
  title_font: Courier-Bold
  title_size: 28
  title_color: "#000000"
  subtitle: ukulele
  logo: cover-logo.png
  logo_width: 470
  logo_offset: 10
  strip_top: strip-top.png
  strip_bottom: strip-bottom.png
  background: "#FFFFFF"
  rules:
    - { color: "#D7489A", y: 764, height: 9 }

back:
  image: back-logo.png
  image_width: 260
  caption: "Album  ·  Album  ·  Album"
  description:
    - First paragraph.
    - Second paragraph.
  description_font: Courier
  description_size: 9
  description_color: "#000000"
  description_leading: 13.5
  description_width: 360
  description_y: null
  spotify: true
  spotify_label: Listen on Spotify
  spotify_font: Courier-Bold
  spotify_url_font: Courier
  spotify_size: 9
  spotify_color: null
  spotify_qr_size: 72
  spotify_qr_color: null
  spotify_x: null
  spotify_y: null
  rules: []
```

Notes:

- `rules` draw full-width horizontal colour bars; `y` is measured in PDF
  points from the bottom of an A4 page (0–842).
- `logo_offset` shifts the logo vertically from the page centre.
- Set a value to `null` to drop that element (for example `"title": null`
  when the logo already contains the band name).
- `description` is a string or a list of strings (one per paragraph),
  wrapped to `description_width` points and centred. `description_y` is
  the first baseline; by default the block sits just below the back image.
- Any string here may be a locale map (see "Bilingual strings" above);
  the printed page uses the songbook's `language:`. `spotify_label`
  defaults to a translated string, so an Italian songbook prints an
  Italian label without spelling one out.
- The Spotify block is automatic: when the songbook has a resolved
  playlist or album link in its `spotify.yaml`, the back page draws
  a label + clickable URL next to a vector QR code of the same link. An
  unresolved link (or a missing manifest) skips the block silently. Set
  `"spotify": false` to opt out. `spotify_color` and `spotify_qr_color`
  default to `caption_color`; `spotify_x` / `spotify_y` are the right and
  bottom edges of the block in PDF points.
- Images may carry alpha; transparency is preserved.
- The chord-chart page is emitted only when the songbook ships a
  `chords.png`.

## ChordPro conventions

- Default instrument: ukulele — set via `chordpro-ukulele.json`
  (`"include": ["ukulele"]`), not in individual `.cho` files.

- Chord notation: Italian (`DO`, `SOL7`, `LA-`, `RE-`, `FA`, `MI7`, …).
  Minor chords use the `-` suffix.

- Required headers in every `.cho` file:

  ```text
  {title: Song Title}
  {artist: Band Name}
  {album: Album Name}
  {key: Do}
  ```

- Chords inline with lyrics: `[DO]questa mattina, [LA-]al primo incontro`

- Section markers, always paired: `{start_of_verse}` / `{end_of_verse}`,
  `{start_of_chorus}` / `{end_of_chorus}`

- Chorus label: `{comment: RIT}`

- Capo position: `{capo: N}` directive right after `{key: ...}`, never a
  `{comment: capotasto N}` line. It's metadata only (no inline print, no
  transposition here); an unrelated note (e.g. original key) stays its
  own separate `{comment: ...}` line.

- Chord diagrams for slash/unusual chords are suppressed via
  `diagrams.suppress` in `chordpro-ukulele.json`.

## Adding a song

1. Create `songbooks/<songbook>/NN-slug.cho`
1. Add the required headers
1. Transcribe lyrics with inline chords
1. Build the songbook locally to verify (see below)
1. Commit: `feat(<songbook>): add <song title>`

## Adding a songbook

1. Create `songbooks/<songbook-slug>/`
1. Add `songbook.yaml` with at least `slug`, `title`, `language`,
   `notation`, `blurb`, and `description` (`description` as an `it`/`en`
   locale map — see "Bilingual strings" above)
1. Add songs following the conventions above
1. Regenerate the root README table: `python3 scripts/readme-table.py`

## Building PDFs locally

Requirements:

- [ChordPro](https://www.chordpro.org/chordpro/chordpro-installation/) ≥ 6
- GNU Make
- Ghostscript (`gs`) — only for songbooks with cover pages
- Python 3 with `Pillow`, `reportlab`, and `PyYAML` — only for cover
  generation

Build:

```bash
make all           # every songbook
make bricioline    # a single songbook (target = folder slug)
```

Output lands in `pdf/<slug>.pdf`, one song per page.

To preview a songbook for guitar instead of the tracked ukulele config, use:

```bash
make guitar-ita SB=diplomatico-e-collettivo   # Italian notation (Do, Re, Mi...)
make guitar-eng SB=diplomatico-e-collettivo   # English notation (C, D, E...)
```

Output lands in `pdf/<slug>-guitar-ita.pdf` / `pdf/<slug>-guitar-eng.pdf`.
This bypasses cover pages and any custom chord diagrams — it's a preview
render, not a release artifact.

## Commits and pull requests

Follow the `skills/atomic-conventional-commits` skill. Non-negotiable rules:

- **Atomic commits**: one logical change per commit. Stage files explicitly
  by path — never `git add -A` or `git add .`.
- **Conventional Commits**: `<type>(<scope>): <subject>`. Scope is the
  songbook slug (`config` / `ci` for config and workflow changes).

Open PRs against `main`. CI compiles every songbook touched by the PR
(`.github/workflows/pr-check.yml`), so a broken `.cho` file fails the check.

## Releases

Releases are cut automatically by
[semantic-release](https://semantic-release.gitbook.io/) on every push to
`main` (`.github/workflows/release.yml`):

- `feat:` → minor version
- `fix:` → patch version
- `BREAKING CHANGE` → major version
- everything else → no release

Each release compiles all songbooks and attaches the PDFs as release
assets. Commit types directly control published versions — pick them
accurately.

## Spotify playlists

Each non-empty songbook maps to a Spotify link: either a playlist this repo
owns and curates track by track, or — when the songbook *is* one official
release (like `bricioline`) — a direct link to that album. Each songbook
owns its mapping in `songbooks/<slug>/spotify.yaml`, driven by
`scripts/spotify_playlists.py`.

### Two-phase model

Track matching is human work; playlist pushing is machine work. They never
mix:

1. **resolve** (local, interactive): scans `.cho` files, searches Spotify,
   and a human picks the right recording for each song. Picks are written
   into the songbook's `spotify.yaml` and committed. Never runs in CI.
1. **sync** (CI, unattended): reads the committed manifests and pushes the
   pinned URIs to Spotify on every push to `main`
   (`.github/workflows/spotify-sync.yml`). Only songbooks changed by the
   push are synced (manual `workflow_dispatch` reruns sync everything).
   It performs no searching and no guessing.

Curation is **optional** — there is no guarantee a song exists on Spotify
at all, so nothing enforces full coverage. `sync` pushes a playlist only
for songbooks with at least one pinned track and silently skips the rest;
unpinned songs are simply absent from the playlist. A PR check
(`spotify-validate` in `pr-check.yml`) only fails on a *malformed* manifest
(bad YAML shape, invalid URIs); coverage gaps are reported as notes — no
network, no secrets, safe on fork PRs.

### Manifest modes

Each songbook entry has a `mode`, set by hand in the manifest:

- `mode: playlist` (default) — per-song curation into a repo-owned playlist.
- `mode: album` — the songbook is one artist's official release; `resolve`
  links the album once (`spotify_album`) and `sync` has nothing to push.

Track values are one of three states: `""` (not yet resolved), a
`spotify:track:<id>` URI (pinned), or `null` (deliberately not on Spotify —
resolve stops asking).

### One-time Spotify app setup

1. Create an app at <https://developer.spotify.com/dashboard> (Development
   Mode is enough; the owner account needs Premium).
1. Add a redirect URI, e.g. `http://127.0.0.1:8080/callback`.
1. Export `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`,
   `SPOTIPY_REDIRECT_URI` locally.
1. Install dependencies: `pip install -r requirements.txt`.

### Curating a new song

```bash
make spotify-resolve SB=<slug>   # or without SB= for all songbooks
```

For each unmatched song you get numbered candidates; press Enter to accept
the pre-selected exact match, type a number to pick another, `s` to skip
for now, `n` to pin "not on Spotify", `q` to quit. The manifest is saved
after every pick, so Ctrl-C is always safe. Commit the updated
`songbooks/<slug>/spotify.yaml`.

If a curated songbook has no `playlist_id` yet, `sync` creates the playlist
on the fly (matching by exact name first, so re-runs never duplicate).
Recording the id in the manifest is still the durable fix:

```bash
python3 scripts/spotify_playlists.py resolve --write-ids
```

### Fixing a bad pick

```bash
python3 scripts/spotify_playlists.py resolve --songbook <slug> --recheck
```

### Release notes

The release workflow appends a "Spotify" section with every resolved
playlist/album link to the release notes, via
`python3 scripts/spotify_playlists.py links` (pure manifest read).

### CI credentials and token rotation

CI reads `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and
`SPOTIFY_REFRESH_TOKEN` from GitHub Actions secrets. Generate the refresh
token once:

```bash
python3 scripts/spotify_playlists.py auth
```

It prints the refresh token exactly once — paste it into the
`SPOTIFY_REFRESH_TOKEN` repository secret and don't store it anywhere else.

**When the sync job fails on authentication** (Spotify invalidates refresh
tokens periodically — expect roughly every 6 months for Development Mode
apps): rerun `auth` locally and update the `SPOTIFY_REFRESH_TOKEN` secret.
That is the whole fix; nothing in the repo changes.

## Agent skills

Vendor-neutral skills (SKILL.md standard) live in `skills/`:

- `skills/chordpro-song-authoring` — writing or fixing `.cho` files
- `skills/chordpro-songbook-management` — songbook structure, builds, chord config
- `skills/atomic-conventional-commits` — committing and PR hygiene
