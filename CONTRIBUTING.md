# Contributing

Technical reference for working on the songbooks: file conventions, build
setup, and PR workflow.

## Repository layout

```text
songbooks/
  <songbook-slug>/      one folder per songbook, kebab-case
    NN-song-slug.cho    two-digit track prefix, kebab-case slug
    layout.json         optional per-songbook layout overlay
pdf/                    compiled PDFs (build output)
scripts/                helper scripts (cover generation)
chordpro-ukulele.json   global ChordPro config
Makefile                build targets
```

Numbering conventions:

- Content songbooks use sequential prefixes: `01-`, `02-`, …
- Songbooks with special pages reserve `00-cover.cho`,
  `01-chord-chart.cho`, and `99-back-cover.cho`; songs start at `10-`.

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
1. Add songs following the conventions above
1. Update the songbook table in `README.md`

## Building PDFs locally

Requirements:

- [ChordPro](https://www.chordpro.org/chordpro/chordpro-installation/) ≥ 6
- GNU Make
- Ghostscript (`gs`) — only for songbooks with cover pages
- Python 3 with `Pillow` and `reportlab` — only for cover generation

Build:

```bash
make all           # every songbook
make bricioline    # a single songbook (target = folder slug)
```

Output lands in `pdf/<slug>.pdf`, one song per page.

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

## Agent skills

Vendor-neutral skills (SKILL.md standard) live in `skills/`:

- `skills/chordpro-song-authoring` — writing or fixing `.cho` files
- `skills/chordpro-songbook-management` — songbook structure, builds, chord config
- `skills/atomic-conventional-commits` — committing and PR hygiene
