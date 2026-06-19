# AGENTS.md

Instructions for AI coding agents working in this repo.

## What this repo is

A multi-band songbook in [ChordPro](https://www.chordpro.org/) format.
Each `.cho` file is one song. One song = one page when rendered.

## Directory layout

```text
songbooks/
  <songbook-slug>/      # one folder per songbook, kebab-case
    NN-song-slug.cho    # two-digit track number prefix, kebab-case slug
```

Band and album metadata live in each song's ChordPro headers, not in the folder structure.

## ChordPro conventions

- Default instrument: ukulele — set via `chordpro-ukulele.json` (`"include": ["ukulele"]`), not in `.cho` files

- Chord notation: Italian (`DO`, `SOL7`, `LA-`, `RE-`, `FA`, `MI7`, etc.)

- Required headers in every `.cho` file:

  ```text
  {title: Song Title}
  {artist: Band Name}
  {album: Album Name}
  {key: Do}
  ```

- Chords inline: `[DO]questa mattina, [LA-]al primo incontro`

- Section markers: `{start_of_verse}` / `{end_of_verse}`, `{start_of_chorus}` / `{end_of_chorus}`

- Chorus label: `{comment: RIT}`

## Adding a new song

1. Create `songbooks/<songbook>/NN-slug.cho`
1. Add required headers
1. Transcribe lyrics with inline chords
1. Commit: `feat(<songbook>): add <song title>`

## Adding a new songbook

1. Create `songbooks/<songbook-slug>/` directory
1. Add songs following the song convention above
1. Update `README.md` songbooks list

## Commit conventions

Follow Conventional Commits. Scope is the songbook slug.

Examples:

- `feat(bricioline): add come-una-foglia`
- `fix(bricioline): correct chords in dentini`
- `docs: update README with new songbook`
