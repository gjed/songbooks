---
name: chordpro-song-authoring
description: Use when creating, transcribing, converting, or fixing a ChordPro .cho song file — e.g. converting an Ultimate-Guitar / chords-over-lyrics sheet, adding a new song to a songbook, fixing section markers, chord placement, or {comment} chord lines, or handling intros, choruses, and second-voice harmony lines. Triggers - "add song", "transcribe", "convert to chordpro", ".cho", "fix chords", "inline chords".
---

# ChordPro Song Authoring

## When to use

Use this skill when: creating a new `.cho` file, converting a chord sheet
(chords-above-lyrics, UG-style, PDF, or plain text) to ChordPro, or fixing
chord/section formatting in an existing `.cho` file.

Do NOT use this skill for: songbook-level work (folder layout, numbering,
covers, PDF builds, config) — use `chordpro-songbook-management` instead.

## File skeleton

Every song file:

```text
{title: Song Title}
{artist: Band Name}
{album: Album Name}
{key: C}

{start_of_verse}
[DO]questa matt[LA-]ina,
[RE-]al primo inco[SOL7]ntro con lo specchio
{end_of_verse}

{start_of_chorus}
{comment: RIT}
e se mi dici balla io muovo la spalla
{end_of_chorus}
```

All four headers are required. `{key: ...}` always uses English note names
(`C`, `F`, `Am`) even when the song body uses Italian chords.

## Chord notation

- Chords are inline, in brackets, immediately **before** the syllable they
  fall on: `[DO]questa matt[LA-]ina` — never on their own `{comment:}` line.
- Match the notation of the target songbook: check sibling files first.
  Italian songbooks (e.g. `bricioline`) use `DO RE- MI7 FA SOL7 LA- SI`
  (minor = trailing `-`); English songbooks (e.g. `hsb-eng`) use `C Dm E7 G7 Am`.
- Italian ↔ English mapping: DO=C, RE=D, MI=E, FA=F, SOL=G, LA=A, SI=B;
  `LA-`=Am, `SOL7`=G7, `RE-7`=Dm7. Slash chords keep both parts: `DO/SOL`=C/G.
- Preserve slash chords intact (`[D/F#]`, `[FA/DO]`); never split them.
- Strip rhythm artifacts from sources: measure bars `|`, standalone beat
  slashes `/`, repeat counts inside chord lines. Keep `(x3)` repeat markers
  at end of lyric lines as plain text.

## Sections

- Verses: `{start_of_verse}` / `{end_of_verse}`. Choruses:
  `{start_of_chorus}` / `{end_of_chorus}` with `{comment: RIT}` as first
  line (Italian songbooks) — English songbooks omit the RIT comment.
- Every `start_of_*` MUST have its matching `end_of_*`. Never nest a verse
  inside a chorus or vice versa — fix nesting before touching chords.
- Intro/Bridge/Outro/Solo: use a labeled verse with inline chords, e.g.:

  ```text
  {start_of_verse label="Intro"}
  [FA][DO]
  [MIb][SIb][DO]
  {end_of_verse}
  ```

  NOT `{comment: Intro}` followed by a bare chord line.

## Critical rules (baseline failure modes)

| Temptation | Correct behavior |
|---|---|
| Source shows chords only on verse 1 → copy them onto verse 2+ | NO. Later verses/choruses get **no inline chords** unless the source explicitly shows them |
| Put intro chords in a `{comment:}` | Use `{start_of_verse label="Intro"}` with inline `[CHORD]`s |
| Write `{key: Do}` for Italian songs | Key header is English: `{key: C}` |
| OCR/HTML source looks plausible | Verify chord placement against the source alignment; mark uncertainty with a `# TODO` comment line rather than guessing |
| Second voice as separate verse/lines | Render harmony as `first voice (second voice)` on ONE line |
| Invent missing lyrics or chords | Never. Transcribe only what the source provides |

## Steps

1. Read 1–2 sibling `.cho` files in the target songbook to confirm chord
   notation (Italian vs English) and local conventions.
2. Extract metadata (title, artist, album, key) and write the header block.
3. Convert body: chords-over-lyrics → inline `[CHORD]` at the exact
   syllable position given by column alignment in the source.
4. Wrap sections in paired verse/chorus markers; label intro/bridge/outro.
5. Verify:
   - every `start_of_*` has a matching `end_of_*` (grep both, counts equal);
   - no `{comment:}` line contains only chords;
   - no chords appear in verses the source left unchorded;
   - file renders: `chordpro --config chordpro-ukulele.json <file> -o /tmp/test.pdf`
     exits 0 with no "unknown chord" warnings (new chords may need defining —
     see chordpro-songbook-management).

## Edge cases

- **Chord-only lines inside a section** (instrumental figures): allowed as
  consecutive `[CHORD]` brackets on one line inside a labeled verse.
- **Unknown/exotic chords** (`SOL7sus2`, `Cm6`): valid in the file, but the
  renderer needs a definition in `chordpro-ukulele.json` — hand off to
  `chordpro-songbook-management`.
- **Song longer than one page**: songbook layout is one song per page;
  flag it to the user instead of silently truncating or shrinking.

## Reference material

See [references/directives.md](references/directives.md) for the full
ChordPro directive list (sections, meta, formatting, output control).
