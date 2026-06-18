# AGENTS.md

Instructions for AI coding agents working in this repo.

## What this repo is

A multi-band songbook in [ChordPro](https://www.chordpro.org/) format.
Each `.cho` file is one song. One song = one page when rendered.

## Directory layout

```
songbooks/
  <songbook-slug>/      # one folder per songbook, kebab-case
    NN-song-slug.cho    # two-digit track number prefix, kebab-case slug
```

Band and album metadata live in each song's ChordPro headers, not in the folder structure.

## ChordPro conventions

- Default instrument: `{instrument: ukulele}`
- Chord notation: Italian (`DO`, `SOL7`, `LA-`, `RE-`, `FA`, `MI7`, etc.)
- Required headers in every `.cho` file:
  ```
  {title: Song Title}
  {artist: Band Name}
  {album: Album Name}
  {instrument: ukulele}
  {key: Do}
  ```
- Chords inline: `[DO]questa mattina, [LA-]al primo incontro`
- Section markers: `{start_of_verse}` / `{end_of_verse}`, `{start_of_chorus}` / `{end_of_chorus}`
- Chorus label: `{comment: RIT}`

## Adding a new song

1. Create `songbooks/<songbook>/NN-slug.cho`
2. Add required headers
3. Transcribe lyrics with inline chords
4. Commit: `feat(<songbook>): add <song title>`

## Adding a new songbook

1. Create `songbooks/<songbook-slug>/` directory
2. Add songs following the song convention above
3. Update `README.md` songbooks list

## Commit conventions

Follow Conventional Commits. Scope is the songbook slug.

Examples:
- `feat(bricioline): add come-una-foglia`
- `fix(bricioline): correct chords in dentini`
- `docs: update README with new songbook`
