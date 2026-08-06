---
name: atomic-conventional-commits
description: Use whenever committing changes in this repository — staging files, writing commit messages, splitting work into commits, or preparing a PR. Enforces atomic commits (one logical change per commit) and Conventional Commits format, which drives semantic-release versioning. Triggers - "commit", "git add", "stage", "open pr", "push changes".
---

# Atomic & Conventional Commits

## When to use

Every time you create a commit in this repository. No exceptions — releases
are cut automatically by semantic-release from commit messages, so a
malformed or bloated commit directly corrupts versioning and release notes.

## Atomic commits

One commit = one logical change. Never batch independent changes.

- Each user-requested file modification is committed separately.
- Adding a song, fixing chords in another song, and touching config are
  **three commits**, even if edited in the same session.
- A commit must leave the repo in a working state: `make <slug>` (or
  `make all` for config changes) exits 0 at every commit.
- Stage explicitly by path (`git add <file>...`). Never `git add -A` or
  `git add .` — untracked or unrelated files must not ride along.
- If a change cannot be described without "and", split it.

## Conventional Commits

Format: `<type>(<scope>): <subject>`

- **type** determines the semantic-release version bump:
  - `feat` → minor bump (new song, new songbook, new capability)
  - `fix` → patch bump (wrong chord, typo, layout fix, broken build)
  - `docs`, `chore`, `ci`, `refactor`, `style`, `test` → **no release**
  - `BREAKING CHANGE:` footer or `!` after type → major bump
- **scope** = songbook slug for song/songbook changes (`bricioline`,
  `hsb-eng`, `diplomatico-e-collettivo`, …); `config` for
  `chordpro-ukulele.json`; `ci` for workflows; omit only for repo-wide
  changes with no natural scope.
- **subject**: imperative, lowercase, no trailing period, ≤ 72 chars.

Examples:

```text
feat(bricioline): add come-una-foglia
fix(bricioline): correct chords in dentini
feat(config): add diagram for F#7
fix(config): Ab diagram base fret 3, was overflowing 4-fret window
ci: pin chordpro appimage version
docs: update README with new songbook
```

## Checklist before every commit

1. `git status --short` — confirm only the intended files are staged.
2. Change builds: `make <affected-slug>` exits 0.
3. Message type matches the actual change (would a reader agree this is a
   `fix` vs `feat`?), scope is the songbook slug, subject is imperative.
4. The commit is self-contained: revertable without breaking anything else.

## Edge cases

- **Mixed staged changes discovered**: unstage (`git restore --staged`),
  then commit in separate slices.
- **Follow-up to a just-made commit not yet pushed**: prefer a new commit;
  amend only for message typos, never after push.
- **Merge/rebase conflicts**: resolve, then keep the original message —
  do not invent a new type.
- **Uncertain between `feat` and `fix`**: new content = `feat`; correcting
  existing content = `fix`. Version bump follows.
