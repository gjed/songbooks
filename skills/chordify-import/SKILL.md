---
name: chordify-import
description: Use when a song has no usable chord sheet (nothing on Ultimate Guitar or chord sites) and the chords must come from audio — pulling Chordify's chord timeline, verifying or filling it with a local audio pipeline (madmom chords, Demucs vocals, Whisper lyric alignment), and producing a ChordPro draft with chords placed on the sung words. Triggers - "chordify", "no chords online", "get chords from the audio", "chords from youtube/bandcamp", "verify chordify", "whole album without chord sheets".
---

# Chords from audio: Chordify + local verification

## Source status

Chordify and the local pipeline both **estimate** chords from audio. Neither
is a transcription. Output is a draft for human cleanup, never a finished
song. Chordify's terms forbid scraping: pull only what a songbook needs, by
hand, one-off — no scheduled or bulk crawling.

## When to use

- Use when no chord sheet exists for the song; if one exists, use
  `chordpro-ug-import` or `add-song-from-link` instead.
- Chordify is the primary source when it has the song. The local pipeline
  aligns, verifies and fills it, and replaces it when Chordify has nothing or
  analysed a different version.
- Song conventions still come from `chordpro-song-authoring`; songbook
  layout and builds from `chordpro-songbook-management`.

## Setup (once per machine)

Requirements: `agent-browser` (headed Chrome), `ffmpeg`, `uv`, and Python 3.11
for the analysis venv; the distro Python is too new for madmom.

```bash
W=/tmp/opencode/<work>            # scratch dir, never inside the repo
uv venv --python 3.11 $W/.venv && . $W/.venv/bin/activate
uv pip install --index-url https://download.pytorch.org/whl/cpu torch torchaudio
uv pip install -r scripts/chordify/requirements.txt
uv pip install --no-build-isolation "git+https://github.com/CPJKU/madmom"
```

## Workflow

Scripts live in `scripts/chordify/`; all write into the work dir `$W`.

1. **Tracklist + lyrics** (Genius, with section headers):
   `python3 scripts/chordify/lyrics.py album Queen-of-saba Medusa`, then
   `python3 scripts/chordify/lyrics.py fetch -o $W/lyrics Queen-of-saba <slug> ...`.
   Lyrics files are named by song slug.
1. **Audio**: the official album release, the same audio the songbook
   describes. Bandcamp works:
   `uvx yt-dlp -x --audio-format wav -o "$W/audio/%(playlist_index)02d.%(ext)s" <album-url>`.
1. **Chordify candidates**:
   `python3 scripts/chordify/chordify.py search "Artist" "Title" ...`.
   `C` = analysed (has chords), `U` = never analysed (no chords). Prefer the
   official "Topic" or album upload, then official video, then lyric video.
   Live versions are a last resort. Pull every plausible studio upload — merge
   picks the best fit:
   `python3 scripts/chordify/chordify.py pull -o $W/chordify slug=ID1,ID2 ...`.
1. **Local analysis** per song, in the venv (~2 min chords, ~5 min
   vocals + alignment per song on CPU; run chords in parallel, alignment
   sequentially):
   `python scripts/chordify/analyze.py --work $W $W/audio/NN.wav <slug>`.
1. **Merge** into a draft:
   `python scripts/chordify/merge.py --work $W --artist "Artist" <slug> "Title" "Album"`.
   It prints a report; the draft is `$W/out/<slug>.cho`.
1. Copy drafts to `songbooks/<slug>/NN-<song>.cho`. Render each one and check
   it fits one page; then `make <slug>`.

## Reading the merge report

| Field                   | Meaning                                                    | Action                             |
| ----------------------- | ---------------------------------------------------------- | ---------------------------------- |
| `source: chordify …`    | Chordify timeline used, aligned by `offset` seconds        | normal case                        |
| `agreement` ≥ 0.7       | Chordify and local mostly agree                            | light review                       |
| `agreement` 0.4–0.7     | frequent disagreement (often maj/min or 7th)               | review every `# check local:` line |
| `rejected: [id, score]` | agreement < 0.4: Chordify analysed another version or edit | draft is local-only; say so        |
| `source: local`         | no Chordify data                                           | the whole song needs ear review    |
| `check_lines`           | lines carrying a `# check local: <chords>` comment         | the cleanup list                   |
| `low_conf_words`        | words Whisper aligned with p < 0.3                         | many → chord placement is loose    |

`# check local:` lines are ChordPro comments. They never print and stay in
the file until the human cleanup resolves them.

## Failure modes already handled (don't re-debug)

- **Cloudflare**: curl and headless Chrome get "Just a moment…"; `chordify.py`
  opens a headed session and waits for the title to change.
- **Loop-based songs**: repeating progressions correlate at many lags, so the
  offset search is limited to the duration difference between the two
  audios (+5 s).
- **Video edits**: official videos may add intros or cuts (positive offset,
  e.g. 9 s). A different arrangement drops agreement below 0.4 and is rejected.
- **Genius artifacts**: Cyrillic lookalike letters, odd Unicode spaces,
  "N Contributors… Lyrics" preamble, `[?]` placeholders (rendered `(?)`).
- **Repeated sections**: an identical chorus becomes `{chorus}`; a chorus
  that repeats an earlier one plus extra lines becomes `{chorus}` plus a verse
  block holding the extra lines.
- **Accidentals**: spelled from the key (sharps in sharp keys, flats otherwise).

## Rules

- Never discard a Chordify result for looking too simple (a two-chord drone is
  a real song). Pull it, verify it locally, and report the numbers.
- Never invent lyrics: Genius is the lyric source. Tracks or sections Genius
  lacks stay as instrumental chord lines.
- Report per song: source, agreement, check-line count, and anything rejected.
