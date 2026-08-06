# ChordPro directive reference

Condensed from <https://www.chordpro.org/chordpro/chordpro-directives/>.
Directives use `{name: value}` or `{name}` syntax, one per line. Lines
starting with `#` are source comments (never rendered).

## Meta-data

| Directive | Short | Meaning |
|---|---|---|
| `title` | `t` | Song title |
| `subtitle` | `st` | Subtitle / alternate title |
| `artist` | — | Performing artist or band |
| `composer` / `lyricist` | — | Music / lyric writers |
| `album` | — | Album name |
| `year` | — | Release year |
| `key` | — | Musical key (English names) |
| `time` | — | Time signature |
| `tempo` | — | BPM |
| `capo` | — | Capo position |
| `meta` | — | Custom key-value metadata |
| `sorttitle` / `sortartist` | — | Sort overrides for collections |

## Sections (environments)

| Directive | Short | Meaning |
|---|---|---|
| `start_of_verse` / `end_of_verse` | `sov` / `eov` | Verse |
| `start_of_chorus` / `end_of_chorus` | `soc` / `eoc` | Chorus |
| `start_of_bridge` / `end_of_bridge` | `sob` / `eob` | Bridge |
| `start_of_tab` / `end_of_tab` | `sot` / `eot` | Tablature (monospace) |
| `start_of_grid` / `end_of_grid` | `sog` / `eog` | Chord grid |
| `chorus` | — | Recall the last chorus ("repeat chorus") |

All `start_of_*` directives accept `label="Text"` to print a section
label (Intro, Bridge, Outro, Solo…).

## Formatting

| Directive | Short | Meaning |
|---|---|---|
| `comment` | `c` | Rendered annotation line |
| `comment_italic` | `ci` | Italic annotation |
| `comment_box` | `cb` | Boxed annotation |
| `highlight` | — | Highlighted annotation |
| `image` | — | Embed image (`src=`, `scale=`) |

## Chords

| Directive | Meaning |
|---|---|
| `define` | Define a chord diagram: `{define: NAME base-fret N frets f f f f}` |
| `chord` | Show a diagram / configure a chord inline |
| `transpose` | Transpose following chords by N semitones |

Inline markup: `[CHORD]` before the target syllable; `[*text]` for
annotations rendered in the chord row.

## Output / layout

| Directive | Short | Meaning |
|---|---|---|
| `new_page` | `np` | Page break |
| `new_physical_page` | `npp` | Physical page break |
| `column_break` | `colb` | Column break |
| `columns` | `col` | Number of columns |
| `new_song` | `ns` | Next song in a multi-song file |
| `diagrams` | — | Control chord diagram display |

## Conditional selectors

Any directive may carry a selector suffix: `{directive-ukulele: ...}`
applies only when the ukulele config is active. Custom app-specific
directives are prefixed `x_`.
