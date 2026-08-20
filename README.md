# Songbooks

A collection of songbooks for singing and playing together — with lyrics and
ukulele chords. No technical knowledge needed to enjoy them.

## Just want the songbooks?

Ready-to-print PDFs are attached to every release:

**[Download the latest PDFs from the Releases page](../../releases/latest)**

Each songbook is a single PDF, one song per page. Download it, print it,
or open it on a tablet — that's it.

Browse all songbooks online: **[https://gjed.github.io/songbooks/](https://gjed.github.io/songbooks/)**

## The songbooks

<!-- songbooks:begin -->

| Songbook                                                                       | What's inside                                            |
| ------------------------------------------------------------------------------ | -------------------------------------------------------- |
| [Bricioline](songbooks/bricioline/)                                            | Queen of Saba — Italian children's music                 |
| [Canzoni Ribelli](songbooks/canzoni-ribelli/)                                  | Italian rebel and protest songs                          |
| [Diplomatico e il Collettivo Ninco Nanco](songbooks/diplomatico-e-collettivo/) | È tutto un falso, Ho visto il mondo, Troppe Parole       |
| [España Circo Este](songbooks/espana-circo-este/)                              | Italian reggae/indie band, Italian and Spanish lyrics    |
| [faccianuvola](songbooks/faccianuvola/)                                        | Italian indie-pop singer-songwriter faccianuvola         |
| [Good Songs](songbooks/good-songs/)                                            | A mixed bag of favourites (Ed Sheeran, Anna Kendrick, …) |
| [HBS Songbook — Italiano](songbooks/hbs-ita/)                                  | Italian songs, with cover and chord chart                |
| [HBS Songbook — English](songbooks/hsb-eng/)                                   | 100+ English songs, with cover and chord chart           |
| [Nené](songbooks/nene/)                                                        | Homemade Italian singles, phone-recorded                 |

<!-- songbooks:end -->

The table above is generated from each songbook's `songbook.yaml` —
edit that file and run `python3 scripts/readme-table.py`, don't edit
the table by hand.

## How this repo is organized

Every song lives in its own small text file. Files are grouped into folders,
one folder per songbook:

```text
songbooks/
  bricioline/                    ← one folder = one songbook
    01-come-una-foglia.cho       ← one file = one song
    02-cose-un-limone.cho
  hsb-eng/
    ...
pdf/                             ← compiled PDFs land here
```

The number at the start of each filename (`01`, `02`, …) sets the song order
in the printed book.

## What's inside a song file?

Song files use a simple text format called
[ChordPro](https://www.chordpro.org/). You can open any `.cho` file right
here on GitHub and read it — lyrics are plain text, and chords sit in square
brackets exactly where you play them:

```text
{title: Come una foglia}
{artist: Queen of Saba}

[DO]Questa mattina, [LA-]al primo incontro
```

Chords use Italian names: `DO`, `RE`, `MI`, `FA`, `SOL`, `LA`, `SI`
(instead of C, D, E, F, G, A, B). A minus sign means minor: `LA-` is
A minor.

## Other ways to use the songs

Besides the PDFs, any ChordPro-compatible app can open the `.cho` files
directly — handy for transposing to another key or changing instrument.
Popular choices: [Songbook Pro](https://www.songbookpro.app/) and
[Chordsmith](https://chordsmith.app/).

## Want to add or fix a song?

Spotted a wrong chord, or want to contribute a song? Wonderful!

- **Easiest**: [open an issue](../../issues/new) describing the song or the
  fix — no coding required.
- **Hands-on**: see [CONTRIBUTING.md](CONTRIBUTING.md) for the file
  conventions, how PDFs get built, and how to open a pull request.

## License

This repository does not claim any rights over the songs themselves. All
lyrics, music, and chords remain the property of their respective artists,
songwriters, and publishers. This project only repackages and organizes
publicly available songs and chords into printable songbooks for personal,
non-commercial use (rehearsals, sing-alongs, and the like).

If you are a rights holder and want a song removed, please
[open an issue](../../issues/new).
