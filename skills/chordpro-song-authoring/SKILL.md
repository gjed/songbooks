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
- Capo position: use the `{capo: N}` meta directive, placed right after
  `{key: ...}`, never a `{comment: capotasto N}` (or "capo N") line.
  `{capo: N}` is metadata only here — it does not transpose chords or
  print anything inline (project config has `decapo: false`), so any
  other note about the song (e.g. original key/tuning) stays as its own
  separate `{comment: ...}` line, not merged with the capo note.

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

| Temptation                                                    | Correct behavior                                                                                                        |
| ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Source shows chords only on verse 1 → copy them onto verse 2+ | NO. Later verses/choruses get **no inline chords** unless the source explicitly shows them                              |
| Put intro chords in a `{comment:}`                            | Use `{start_of_verse label="Intro"}` with inline `[CHORD]`s                                                             |
| Write `{key: Do}` for Italian songs                           | Key header is English: `{key: C}`                                                                                       |
| OCR/HTML source looks plausible                               | Verify chord placement against the source alignment; mark uncertainty with a `# TODO` comment line rather than guessing |
| Second voice as separate verse/lines                          | Render harmony as `first voice (second voice)` on ONE line                                                              |
| Invent missing lyrics or chords                               | Never. Transcribe only what the source provides                                                                         |
| Source notes capo as text ("capotasto III")                   | Use `{capo: 3}`, not `{comment: capotasto III}`                                                                         |

## Steps

1. Read 1–2 sibling `.cho` files in the target songbook to confirm chord
   notation (Italian vs English) and local conventions.
1. Extract metadata (title, artist, album, key) and write the header block.
1. Convert body: chords-over-lyrics → inline `[CHORD]` at the exact
   syllable position given by column alignment in the source.
1. Wrap sections in paired verse/chorus markers; label intro/bridge/outro.
1. Verify:
   - every `start_of_*` has a matching `end_of_*` (grep both, counts equal);
   - no `{comment:}` line contains only chords;
   - no chords appear in verses the source left unchorded;
   - file renders: `chordpro --config chordpro-ukulele.json <file> -o /tmp/test.pdf`
     exits 0 with no "unknown chord" warnings (new chords may need defining —
     see chordpro-songbook-management).

## Site variants

A song may optionally have a "site variant" file used only by the online (HTML) build:

```text
NN-song-slug.cho           # original — the print source of truth
NN-song-slug.site.cho      # optional site variant (online view only)
```

If a variant exists, the online view uses it instead of the original. The PDF/print build always uses the original and never reads `.site.cho` files. Cover pseudo-songs (`00-cover.cho`, `01-chord-chart.cho`, `99-back-cover.cho`) never get site variants.

**Permitted differences** — the variant may differ ONLY by:

1. Additional inline `[CHORD]` brackets (chords on later verses).
1. Choruses written out in full where the original only refers to them.

Anything else — lyric text, verse/chorus structure, section order, metadata/directives — is a divergence and is a build failure. **The original ALWAYS has precedence on correctness**: when the two disagree, the original is right and the variant must be re-synced to it.

### Why choruses need writing out

Two idioms in the print sources stand for "repeat the chorus here", and ChordPro
renders **both** as a label in the PDF and as **nothing at all** in HTML:

```text
{chorus}                    # bare recall directive (also {chorus: x2})

{start_of_chorus}           # empty chorus block: directives but no lyrics
{comment: RIT}
{end_of_chorus}
```

That is fine in print, where the reader scrolls back up one page. Online each
song is its own page and the repeat simply vanishes, so a site variant writes
the chorus out in full at every recall.

### Placing chords on later verses

Copy a chord line verbatim only when the later verse's lyric line is
**character-identical** to an already-chorded line — then the chord positions
are known-correct by construction.

Otherwise the chords must be **placed by hand** against the source material.
Never stretch the first verse's progression over different words: syllable
counts shift between verses and the chords land on the wrong beats. If the
source never recorded chords for a verse, leave that verse unchorded — an
invented progression is worse than none.

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
