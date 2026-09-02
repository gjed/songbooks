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
    NN-song-slug.site.cho  # optional site variant (online view only)
```

Band and album metadata live in each song's ChordPro headers, not in the folder structure.

**Site variants**: a song may have an optional `.site.cho` file used by the HTML build but not PDF. If it exists, the online view uses it; if not, the original is used. Adoption is per-song, fully opt-in. See `skills/chordpro-song-authoring` for permitted differences and `skills/chordpro-songbook-management` for build enforcement.

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

- Capo position: `{capo: N}` directive right after `{key: ...}`, never a
  `{comment: capotasto N}` line

## Adding a new song

1. Create `songbooks/<songbook>/NN-slug.cho`
1. Add required headers
1. Transcribe lyrics with inline chords
1. Commit: `feat(<songbook>): add <song title>`

## Adding a new songbook

1. Create `songbooks/<songbook-slug>/` directory
1. Add `songbooks/<slug>/songbook.yaml` (metadata: slug, title, language,
   notation, blurb, description — see CONTRIBUTING.md). Prose fields are
   `it`/`en` locale maps; `language:` picks the locale that gets printed
1. Add songs following the song convention above
1. Regenerate the root `README.md` songbook table:
   `python3 scripts/readme-table.py` (never edit the table by hand)

## Commit conventions

Follow the `skills/atomic-conventional-commits` skill for every commit.
Non-negotiable rules:

- **Atomic commits**: one logical change per commit. Independent changes
  (new song, chord fix, config tweak) are separate commits. Stage files
  explicitly by path — never `git add -A` or `git add .`.
- **Conventional Commits**: `<type>(<scope>): <subject>`. Scope is the
  songbook slug (`config` / `ci` for config and workflow changes).
- Releases are cut automatically by **semantic-release** on push to
  `main`: `feat` → minor, `fix` → patch, `BREAKING CHANGE` → major,
  everything else → no release. Commit types directly control published
  versions — pick them accurately.

Examples:

- `feat(bricioline): add come-una-foglia`
- `fix(bricioline): correct chords in dentini`
- `docs: update README with new songbook`

## Agent skills

Vendor-neutral skills (Agent Skills / SKILL.md standard) live in
`skills/`. Consult them before working:

- `skills/chordpro-song-authoring` — writing or fixing `.cho` files
- `skills/chordpro-songbook-management` — songbook structure, builds, chord config
- `skills/atomic-conventional-commits` — committing and PR hygiene
