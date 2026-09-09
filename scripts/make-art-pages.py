"""Generate the blank, index, and artwork pages of an art-edition songbook.

Usage:
  python3 make-art-pages.py <songbook-dir> <output-dir>

The art edition is a duplex booklet: every song sits on a recto with its
album artwork facing it on the opposing verso. This script draws the
pages ChordPro cannot -- the blank leaf, the index, and one full page per
artwork -- and leaves the song pages and the final merge to the Makefile.

Emitted files, all in <output-dir>:

  <slug>-blank.pdf            one empty A4 page
  <slug>-toc.pdf              the index
  <slug>-art-<stem>.pdf       one page per song, <stem> being the song's
                              filename without .cho
  <slug>-art-manifest.txt     the songs to bind, one stem per line, in
                              page order

The manifest exists so the Makefile need not re-derive the edition's
contents from the songbook directory. Track order, and which songs the
edition carries at all, are decided here from songbook.yaml; the
Makefile renders and merges whatever the manifest lists, and so cannot
disagree with the index printed on page three.

Layout comes from the `art` section of the songbook's songbook.yaml:

  art:
    width: 480                # artwork edge length in pt
    offset: 10                # optical lift above the frame's centre
    rules: []                 # defaults to the cover's rules
    exclude: []               # song stems the art edition leaves out
    toc:
      title: indice
      title_font: Courier-Bold
      title_size: 20
      title_color: "#000000"
      number_font: Courier-Bold
      number_color: "#000000"  # defaults to title_color
      entry_font: Courier
      entry_size: 12
      entry_color: "#000000"   # defaults to title_color
      entry_leading: 26
      rules: []                # defaults to the section's rules
    songs:
      01-come-una-foglia: images/Come una Foglia_Artwork_jpeg.jpg

`songs` is the whole mapping: a song without an entry gets no artwork
page, and the booklet's page pairing depends on every song having one,
so an unmapped song is a hard error rather than a silently dropped leaf.
Two songs may point at the same image -- an alternate take facing the
artwork of the song it belongs to keeps the spread pairing intact.

`exclude` is the other half of that bargain: a song the art edition
omits on purpose has to say so, and is then dropped whole -- no artwork
page, no song page, no index entry. That way a print edition carrying a
subset of the songbook stays one hard error away from a song dropped by
accident. Excluding a song affects only the art edition; `make <slug>`
still renders every song the songbook has.

Index entries are read straight from the songs' `{title: ...}` headers,
in track order, numbered from the `NN-` filename prefix, so the printed
index cannot drift from the songs actually bound into the book.

Artwork pages carry the same horizontal rule motif as the cover, intro
and back pages: the frame is what makes the booklet read as one object
rather than a PDF merge, and a square cover on A4 portrait leaves the
room for it without crowding the art.

Both the artwork and the index block are centred on that frame rather
than on the page. The rule bands are not placed symmetrically -- this
book's sit higher at the top than at the bottom -- so page-centred
content reads as crowding the top rules and floating away from the
bottom ones. `offset` then lifts the block off the frame's centre by the
small amount that stops a large square from looking like it is sinking.
"""

import importlib.util
import os
import re
import sys

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from songbook_meta import language_of, load_metadata, localize

# make-cover.py owns this project's drawing vocabulary -- page geometry,
# the rule motif, aspect-preserving image placement -- but its hyphenated
# filename is not an importable module name. Load it by path instead of
# duplicating the helpers here, so both page sets stay in visual sync.
_COVER_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "make-cover.py")
_SPEC = importlib.util.spec_from_file_location("make_cover", _COVER_PY)
make_cover = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(make_cover)

PAGE_W, PAGE_H = A4
MARGIN = make_cover.MARGIN

TRACK_RE = re.compile(r"^(\d+)-")
TITLE_RE = re.compile(r"^\{title:\s*(.+?)\s*\}\s*$")

DEFAULTS = {
    "width": 480,
    "offset": 10,
    "rules": None,          # None -> inherit the cover's rules
    "songs": {},
    "exclude": [],
}

TOC_DEFAULTS = {
    "title": "indice",
    "title_font": "Courier-Bold",
    "title_size": 20,
    "title_color": "#000000",
    "number_font": "Courier-Bold",
    "number_color": None,   # None -> title_color
    "entry_font": "Courier",
    "entry_size": 12,
    "entry_color": None,    # None -> title_color
    "entry_leading": 26,
    "rules": None,          # None -> the art section's rules
}


def load_art_config(sb_dir):
    """Merge the songbook's `art` section on top of the built-in defaults.

    Rules fall back to the cover's, so an art edition inherits the book's
    frame without restating the palette. Locale maps are resolved here,
    against the songbook's own `language:`, exactly as make-cover.py does
    it, so the drawing helpers below only ever see plain strings.
    """
    meta = load_metadata(sb_dir)
    language = language_of(meta)
    section = meta.get("art")
    if not isinstance(section, dict):
        raise SystemExit(
            f"{sb_dir}/songbook.yaml declares no `art:` section -- the art "
            "edition needs one (see scripts/make-art-pages.py)")

    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in section.items() if k != "toc"})
    cover_rules = (meta.get("cover") or {}).get("rules") or []
    if cfg["rules"] is None:
        cfg["rules"] = cover_rules

    toc = dict(TOC_DEFAULTS)
    toc.update(section.get("toc") or {})
    if toc["rules"] is None:
        toc["rules"] = cfg["rules"]
    for key in ("number_color", "entry_color"):
        if toc[key] is None:
            toc[key] = toc["title_color"]
    cfg["toc"] = toc

    return localize(cfg, language)


def song_sources(sb_dir, exclude=()):
    """Return the song files the art edition binds, in track order.

    Mirrors the Makefile's own notion of a song -- .site.cho variants are
    HTML-only and the three cover pseudo-songs are drawn, not rendered --
    and then drops the stems named in `art.exclude`.
    """
    skip = {"00-cover.cho", "01-chord-chart.cho", "99-back-cover.cho"}
    dropped = list(exclude or ())
    # An exclusion that matches no song is a silent no-op today and binds
    # an unwanted song the moment a file is renamed, so refuse it here
    # rather than let the booklet quietly gain a leaf later.
    for stem in dropped:
        if not os.path.exists(os.path.join(sb_dir, f"{stem}.cho")):
            raise SystemExit(
                f"`art.exclude` lists {stem}, which is not a song of "
                f"{sb_dir} -- check it against the .cho filenames")
    names = [n for n in os.listdir(sb_dir)
             if n.endswith(".cho") and not n.endswith(".site.cho")
             and n not in skip and n[: -len(".cho")] not in set(dropped)]
    return [os.path.join(sb_dir, n) for n in sorted(names)]


def song_entry(path):
    """Return (track, title) for one song file.

    The track number comes from the `NN-` filename prefix and the title
    from the song's own `{title: ...}` header, so the index always agrees
    with what ChordPro will print on the facing page.
    """
    stem = os.path.basename(path)[: -len(".cho")]
    match = TRACK_RE.match(stem)
    track = match.group(1) if match else ""
    title = None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            found = TITLE_RE.match(line.strip())
            if found:
                title = found.group(1)
                break
    if not title:
        raise SystemExit(f"{path} has no {{title: ...}} header")
    return track, title


def make_blank(output):
    """One deliberately empty A4 page: the verso facing the index."""
    c = canvas.Canvas(output, pagesize=A4)
    c.showPage()
    c.save()


def make_toc(output, cfg, entries):
    """Draw the index: track number and title, one row per song.

    Title, an underscore echoing the frame, and the rows are measured as
    one block and centred together inside the rules, so the index holds
    the same optical position as the artwork on the pages that follow --
    however many songs the songbook happens to have.
    """
    conf = cfg["toc"]
    c = canvas.Canvas(output, pagesize=A4)
    make_cover._draw_rules(c, conf["rules"])

    size = conf["entry_size"]
    leading = conf["entry_leading"]
    title_size = conf["title_size"] if conf.get("title") else 0
    head_gap = title_size * 2.6

    # Measured block: title cap, the air under it, the rows, and the last
    # row's descender. Centred on the frame, then lifted by `offset`.
    block_h = title_size + head_gap + (len(entries) - 1) * leading + size * 0.3
    top, bottom = _band_edges(conf["rules"])
    block_top = (top + bottom) / 2 + cfg["offset"] + block_h / 2

    title_baseline = block_top - title_size
    if conf.get("title"):
        c.setFont(conf["title_font"], title_size)
        c.setFillColor(HexColor(conf["title_color"]))
        c.drawCentredString(PAGE_W / 2, title_baseline, conf["title"])
        # A short bar under the title, in the numbers' accent colour: the
        # book's rule motif restated at word scale, tying the lone heading
        # to the list instead of leaving it adrift above it.
        bar_w = c.stringWidth(conf["title"], conf["title_font"], title_size)
        c.setFillColor(HexColor(conf["number_color"]))
        c.rect((PAGE_W - bar_w) / 2, title_baseline - title_size * 0.55,
               bar_w, 2.5, stroke=0, fill=1)

    # One shared left edge for the numbers and one for the titles, so the
    # rows read as a column instead of a ragged centred list. The block as
    # a whole is centred on the widest entry.
    number_font, entry_font = conf["number_font"], conf["entry_font"]
    gap = size * 2.2
    number_w = max(c.stringWidth(track, number_font, size)
                   for track, _ in entries)
    title_w = max(c.stringWidth(title, entry_font, size)
                  for _, title in entries)
    left = (PAGE_W - (number_w + gap + title_w)) / 2

    y = title_baseline - head_gap
    for track, title in entries:
        c.setFont(number_font, size)
        c.setFillColor(HexColor(conf["number_color"]))
        c.drawString(left, y, track)
        c.setFont(entry_font, size)
        c.setFillColor(HexColor(conf["entry_color"]))
        c.drawString(left + number_w + gap, y, title)
        y -= leading

    c.showPage()
    c.save()


def make_art_page(output, cfg, image_path):
    """One artwork page: the rule frame plus the cover art, centred."""
    c = canvas.Canvas(output, pagesize=A4)
    make_cover._draw_rules(c, cfg["rules"])
    # Keep the art clear of the frame: the rules occupy the page's top and
    # bottom bands, so the artwork may only claim what is left between them.
    top, bottom = _band_edges(cfg["rules"])
    band = max(top - bottom - 2 * MARGIN, 0)
    make_cover._draw_centered_image(c, image_path, cfg["width"],
                                    (top + bottom) / 2 + cfg["offset"], band)
    c.showPage()
    c.save()


def _band_edges(rules):
    """The (top, bottom) y of the clear space between the rule bands.

    Falls back to the plain printable box when a songbook declares no
    rules, so an unframed art edition still gets sane margins. Callers
    centre on the midpoint of this band, not on the page: nothing
    guarantees the top and bottom bands sit at mirrored heights.
    """
    top, bottom = PAGE_H - MARGIN, MARGIN
    for rule in rules or []:
        y, height = rule.get("y", 0), rule.get("height", 4)
        if y > PAGE_H / 2:
            top = min(top, y)
        else:
            bottom = max(bottom, y + height)
    return top, bottom


def generate_art_pages(sb_dir, out_dir):
    """Write the blank, index, and per-song artwork PDFs.

    Returns the artwork page paths keyed by song stem; the Makefile pairs
    each with the song ChordPro renders for it.
    """
    os.makedirs(out_dir, exist_ok=True)
    cfg = load_art_config(sb_dir)
    slug = os.path.basename(os.path.normpath(sb_dir))
    sources = song_sources(sb_dir, cfg["exclude"])
    if not sources:
        raise SystemExit(f"{sb_dir} has no song files")

    entries = [song_entry(path) for path in sources]
    make_blank(os.path.join(out_dir, f"{slug}-blank.pdf"))
    make_toc(os.path.join(out_dir, f"{slug}-toc.pdf"), cfg, entries)

    mapping = cfg["songs"] or {}
    pages = {}
    for path in sources:
        stem = os.path.basename(path)[: -len(".cho")]
        name = mapping.get(stem)
        if not name:
            raise SystemExit(
                f"no artwork mapped for {stem} -- add it under `art.songs` "
                f"in {sb_dir}/songbook.yaml (every song needs one, or the "
                "booklet's art/song page pairing breaks)")
        image = os.path.join(sb_dir, name)
        if not os.path.exists(image):
            raise SystemExit(f"artwork not found for {stem}: {image}")
        output = os.path.join(out_dir, f"{slug}-art-{stem}.pdf")
        make_art_page(output, cfg, image)
        pages[stem] = output

    with open(os.path.join(out_dir, f"{slug}-art-manifest.txt"),
              "w", encoding="utf-8") as fh:
        fh.write("".join(f"{stem}\n" for stem in pages))
    return pages


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: make-art-pages.py <songbook-dir> <output-dir>",
              file=sys.stderr)
        sys.exit(1)
    written = generate_art_pages(sys.argv[1], sys.argv[2])
    for stem, path in written.items():
        print(f"Art   → {path}")
    print(f"{len(written)} artwork page(s), plus blank and index")
    print(f"Booklet: {2 * len(written) + 4} pages")
