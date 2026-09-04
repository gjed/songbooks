---
name: add-song-from-link
description: Use when the user provides a URL and wants it turned into songbook content — adding a new song to an existing songbook from a link (Ultimate Guitar, chord/lyric sites, band pages), or bootstrapping a whole new songbook from a link (album page, artist page, tracklist). Triggers - "add this song", "add song from", "new songbook from", a bare URL plus a songbook name, "transcribe this link".
---

# Add Song or Songbook From a Link

## When to use

Use this skill when the input is a **link** and the goal is new songbook
content: one song into an existing songbook, or a brand-new songbook.

This skill is the intake workflow. The content rules live elsewhere and
are binding:

- `chordpro-song-authoring` — transcription rules (notation, sections,
  chord placement, no labels).
- `chordpro-songbook-management` — folder layout, `songbook.yaml`, covers,
  Spotify, builds.
- `atomic-conventional-commits` — one commit per song / logical change.

## Flow A: new song into an existing songbook

Input: a link to one song (chord sheet, lyrics+chords page, tab).

1. **Fetch the source.** Retrieve the page and extract title, artist,
   album, key/capo, and the chords-over-lyrics body. If the page is
   unreachable or chords are ambiguous, stop and report — never invent
   content the source doesn't provide.
1. **Pick the filename.** Check the songbook's numbering scheme
   (sequential `NN-` vs flat prefix — see `chordpro-songbook-management`);
   take the next free number, kebab-case slug from the title.
1. **Transcribe** per `chordpro-song-authoring`: required headers
   (`{key: ...}` and all chords in common notation), inline `[CHORD]`
   brackets at exact syllable positions, paired section markers, no
   `label=` attributes, `{capo: N}` directive when the source notes a
   capo, chords only where the source shows them.
1. **Verify locally**:
   - `chordpro --config chordpro-ukulele.json songbooks/<slug>/<file> -o /tmp/test.pdf`
     exits 0, no "unknown chord" warnings (define missing chords per
     `chordpro-songbook-management`);
   - the song fits **one page** (`pdfinfo /tmp/test.pdf`) — if it spills,
     flag to the user instead of shrinking silently;
   - `make <slug>` still exits 0 and total page count is right.
1. **Commit**: `feat(<slug>): add <song-title>` — the new `.cho` file (and
   any chord definition it required) only. Chord config changes that are
   independently meaningful get their own `feat(config):` commit.
1. **Optional follow-ups** (each its own step, only on request): Spotify
   pin via `make spotify-resolve SB=<slug>`; a `.site.cho` variant for the
   online view.

## Flow B: new songbook from a link

Input: a link to an album, artist page, or tracklist.

1. **Fetch the source** and extract: band name, album/collection title,
   tracklist with order, language of the material.
1. **Confirm scope with the user before transcribing**: which tracks are
   in, where each song's chords will come from (the album link rarely
   carries chord sheets — each song usually needs its own source), and the
   songbook slug. Do not transcribe N songs from guessed sources.
1. **Bootstrap the songbook** per `chordpro-songbook-management`:
   `songbooks/<slug>/` + `songbook.yaml` (slug, title, `artist:` if
   single-artist, `language:`, `notation: common`, `blurb`, bilingual
   `description:` as `it`/`en` map). Regenerate the README table:
   `python3 scripts/readme-table.py`.
1. **Commit the scaffold**: `feat(<slug>): add songbook metadata` (yaml +
   regenerated README).
1. **Add songs one at a time** via Flow A — one commit per song. Verify
   the build after each song, not just at the end.
1. **Optional, on request**: cover/intro/back sections in `songbook.yaml`
   plus image assets; Spotify curation (`make spotify-resolve SB=<slug>`).

## Source handling rules

- The linked source is **ground truth**: transcribe what it shows, flag
  what it lacks. No invented chords, no invented verses, no "probably the
  same progression".
- Chords from Italian sources (`DO`, `SOL-`) are converted to common
  notation at transcription time — the mapping is in
  `chordpro-song-authoring`.
- When several versions exist on the page (e.g. UG has multiple ratings),
  say which one was used.
- Record uncertainty inline with a `# TODO` comment line rather than
  guessing, and list open TODOs when reporting done.

## Edge cases

- **Link behind a paywall/JS wall**: report what could not be read; ask
  the user to paste the sheet rather than scraping around it.
- **Song already exists in another songbook**: songs are per-songbook
  files; copying is allowed but say so, and re-check notation and page
  fit under the target songbook's layout.
- **Tracklist link with per-song chord links**: treat each song link as a
  Flow A input; keep the one-commit-per-song rule.
