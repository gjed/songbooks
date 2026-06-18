# AGENTS.md

Instructions for AI coding agents working in this repo.

## What this repo is

A multi-band songbook in [ChordPro](https://www.chordpro.org/) format.
Each `.cho` file is one song. One song = one page when rendered.

## Directory layout

```
songbooks/
  <band-slug>/          # one folder per band, kebab-case
    <album-slug>/       # one folder per album, kebab-case
      NN-song-slug.cho  # two-digit track number prefix, kebab-case slug
```

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

1. Create `songbooks/<band>/<album>/NN-slug.cho`
2. Add required headers
3. Transcribe lyrics with inline chords
4. Commit: `feat(<band>/<album>): add <song title>`

## Adding a new album

1. Create `songbooks/<band>/<album-slug>/` directory
2. Add songs following the song convention above
3. Update `README.md` band entry if it's a new band

## Commit conventions

Follow Conventional Commits. Scope is `<band>/<album>` or `<band>` for band-level changes.

Examples:
- `feat(queen-of-saba/bricioline): add come-una-foglia`
- `fix(queen-of-saba/bricioline): correct chords in dentini`
- `docs: update README with new band`
