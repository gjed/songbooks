# Songbook

A collection of songbooks in [ChordPro](https://www.chordpro.org/) format.

## Default instrument

Ukulele. Instrument is set via `chordpro-ukulele.json` (`"include": ["ukulele"]`), not in individual song files.

## Chord notation

Italian notation: `DO`, `RE`, `MI`, `FA`, `SOL`, `LA`, `SI`.
Minor chords use `-` suffix: `LA-`, `RE-`, `SOL-`.
Dominant sevenths: `SOL7`, `DO7`, etc.

## Structure

```text
songbooks/
  <songbook-slug>/
    NN-song-slug.cho
```

Songs are numbered with a two-digit prefix (`01`, `02`, …) to preserve track order.
Band and album metadata live in each song's ChordPro headers (`{artist:}`, `{album:}`).

## Songbooks

- [Bricioline](songbooks/bricioline/) — Queen of Saba, Italian children's music

## Rendering

Any ChordPro-compatible app can render `.cho` files.
Recommended: [ChordPro CLI](https://www.chordpro.org/chordpro/chordpro-installation/),
[Songbook Pro](https://www.songbookpro.app/), or [Chordsmith](https://chordsmith.app/).
