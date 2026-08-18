"""Generate cover, intro, chord-chart, and back-cover PDFs for a songbook.

Usage:
  python3 make-cover.py <songbook-dir> <output-dir>

Layout is driven by an optional `cover.json` in the songbook directory.
When absent, the built-in defaults reproduce the original HBS layout:

  cover-uke.png        - logo (cover)
  strip-top.png        - top decorative strip
  strip-bottom.png     - bottom decorative strip
  cover-celtic.jpeg    - image (back cover)
  chords.png           - chord chart diagram

cover.json schema (all keys optional):

  {
    "cover": {
      "background": "#FFFFFF",
      "title": "HBS Songbook",
      "title_font": "Courier-Bold",
      "title_size": 28,
      "title_color": "#000000",
      "subtitle": "ukulele",
      "subtitle_font": "Courier",
      "subtitle_size": 13,
      "subtitle_color": "#000000",
      "strip_top": "strip-top.png",
      "strip_bottom": "strip-bottom.png",
      "logo": "cover-uke.png",
      "logo_width": 480,
      "logo_offset": -20,
      "rules": [ { "color": "#D7489A", "y": 700, "height": 6 } ]
    },
    "intro": {
      "background": "#FFFFFF",
      "title": "Album Name",
      "title_font": "Courier-Bold",
      "title_size": 20,
      "title_color": "#000000",
      "description": ["paragraph one", "paragraph two"],
      "description_font": "Courier",
      "description_size": 10,
      "description_color": "#000000",
      "description_leading": 15,
      "description_width": 380,
      "description_y": null,
      "spotify": true,
      "spotify_label": "Ascolta su Spotify",
      "spotify_font": "Courier-Bold",
      "spotify_url_font": "Courier",
      "spotify_size": 10,
      "spotify_color": "#000000",
      "spotify_qr_size": 96,
      "spotify_qr_color": "#000000",
      "spotify_y": null,
      "links": [
        { "label": "Bandcamp", "url": "https://example.bandcamp.com",
          "color": "#000000", "qr_color": "#000000" }
      ],
      "rules": []
    },
    "back": {
      "background": "#FFFFFF",
      "image": "cover-celtic.jpeg",
      "image_width": 240,
      "caption": "",
      "caption_font": "Courier",
      "caption_size": 11,
      "caption_color": "#000000",
      "description": ["paragraph one", "paragraph two"],
      "description_font": "Courier",
      "description_size": 9,
      "description_color": "#000000",
      "description_leading": 13.5,
      "description_width": 360,
      "description_y": 173,
      "spotify": true,
      "spotify_label": "Listen on Spotify",
      "spotify_font": "Courier-Bold",
      "spotify_url_font": "Courier",
      "spotify_size": 9,
      "spotify_color": "#000000",
      "spotify_qr_size": 72,
      "spotify_qr_color": "#000000",
      "spotify_x": 566.9,
      "spotify_y": 80.3,
      "links": [],
      "rules": []
    }
  }

`description` is a single string or a list of strings, one per
paragraph; each paragraph is wrapped to `description_width` and centred.
`description_y` is the first baseline and defaults to just below the back
image, so the block follows whatever `image_width` the songbook uses.

The Spotify block is automatic: the back page reads the songbook's own
`spotify.yaml` manifest and, when the songbook has a resolved album or
playlist link, draws a right-aligned label + URL (clickable) next to a
vector QR code of the same URL. Missing file, missing PyYAML, or an
unresolved link simply skips the block. `spotify_x` / `spotify_y` are the
right and bottom edges of that block.

The `intro` section is opt-in: no `intro` key means no intro page at all.
When present it renders one extra A4 page right after the cover with an
optional title, the description block, and a centred horizontal Spotify
row (QR code on the left, label stacked over the clickable URL on the
right). Set `spotify: false`, or leave the songbook unresolved in the
manifest, to get a description-only page. `spotify_y` is the bottom edge
of the QR code; it defaults to a spot in the lower third of the page.

`links` adds arbitrary hand-written link rows to the intro or back page:
a list of `{label, url}` objects, each optionally overriding `color` and
`qr_color`. These are pure cover.json data -- no manifest involved -- and
each row is drawn exactly like the Spotify one, stacked vertically and
centred as a single group. When both the automatic Spotify block and
custom `links` appear on a page they share that one stack: the `links`
entries first in array order, then the Spotify row last. Typography and
QR size come from the page's `spotify_*` keys so every row matches, and
several rows on one page scale their QR codes down together to fit. On
the back page, declaring `links` moves the whole group from its historic
bottom-right corner to the centred stack; with no `links` the corner
layout is untouched.
"""

import json
import os
import sys

from PIL import Image
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


PAGE_W, PAGE_H = A4  # 595.27 x 841.89 pt
MARGIN = 10 * mm     # 28.35 pt

MANIFEST = "spotify.yaml"  # lives inside each songbook folder
SPOTIFY_URL = "https://open.spotify.com/{kind}/{ident}"

LINK_ROW_GAP = 18  # vertical breathing room between stacked link rows
MIN_QR_SIZE = 56   # floor when several rows are scaled down to fit
MIN_IMAGE_HEIGHT = 180  # back-cover art never shrinks below this for links

DEFAULTS = {
    "cover": {
        "background": None,
        "title": "HBS Songbook",
        "title_font": "Courier-Bold",
        "title_size": 28,
        "title_color": "#000000",
        "subtitle": None,
        "subtitle_font": "Courier",
        "subtitle_size": 13,
        "subtitle_color": "#000000",
        "strip_top": "strip-top.png",
        "strip_bottom": "strip-bottom.png",
        "logo": "cover-uke.png",
        "logo_width": 480,
        "logo_offset": -20,
        "rules": [],
    },
    "intro": {
        "background": None,
        "title": None,
        "title_font": "Courier-Bold",
        "title_size": 20,
        "title_color": "#000000",
        "description": None,
        "description_font": "Courier",
        "description_size": 10,
        "description_color": None,
        "description_leading": None,
        "description_width": 380,
        "description_y": None,
        "spotify": True,
        "spotify_label": "Open with Spotify",
        "spotify_font": "Courier-Bold",
        "spotify_url_font": "Courier",
        "spotify_size": 10,
        "spotify_color": None,
        "spotify_qr_size": 96,
        "spotify_qr_color": None,
        "spotify_y": None,
        "links": [],
        "rules": [],
    },
    "back": {
        "background": None,
        "image": "cover-celtic.jpeg",
        "image_width": 240,
        "caption": None,
        "caption_font": "Courier",
        "caption_size": 11,
        "caption_color": "#000000",
        "description": None,
        "description_font": "Courier",
        "description_size": 9,
        "description_color": None,
        "description_leading": None,
        "description_width": 360,
        "description_y": None,
        "spotify": True,
        "spotify_label": "Listen on Spotify",
        "spotify_font": "Courier-Bold",
        "spotify_url_font": "Courier",
        "spotify_size": 9,
        "spotify_color": None,
        "spotify_qr_size": 72,
        "spotify_qr_color": None,
        "spotify_x": None,
        "spotify_y": None,
        "links": [],
        "rules": [],
    },
}


def load_config(sb_dir):
    """Merge cover.json (if present) on top of the built-in defaults.

    Each merged section carries a `_declared` flag telling whether the
    songbook actually spelled that section out, so opt-in pages (the
    intro) can distinguish "absent" from "present but all defaults".
    """
    cfg = {section: dict(values) for section, values in DEFAULTS.items()}
    user = {}
    path = os.path.join(sb_dir, "cover.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            user = json.load(fh)
    for section, conf in cfg.items():
        section_cfg = user.get(section)
        if isinstance(section_cfg, dict):
            conf["_declared"] = True
            conf.update(section_cfg)
        else:
            conf["_declared"] = False
    return cfg


def _open_img(img_path):
    """Open an image and return reportlab ImageReader (handles alpha)."""
    im = Image.open(img_path)
    if im.mode in ("LA", "P"):
        im = im.convert("RGBA")
    return ImageReader(im)


def _resolve(sb_dir, name):
    """Return an existing path for `name` inside sb_dir, else None."""
    if not name:
        return None
    path = os.path.join(sb_dir, name)
    return path if os.path.exists(path) else None


def _paint_background(c, color):
    if not color:
        return
    c.saveState()
    c.setFillColor(HexColor(color))
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    c.restoreState()


def _draw_rules(c, rules):
    """Draw full-width horizontal colour bars: [{color, y, height}]."""
    for rule in rules or []:
        c.saveState()
        c.setFillColor(HexColor(rule.get("color", "#000000")))
        inset = rule.get("inset", MARGIN)
        c.rect(inset, rule.get("y", 0), PAGE_W - 2 * inset,
               rule.get("height", 4), stroke=0, fill=1)
        c.restoreState()


def _draw_centered_image(c, img_path, width, center_y, max_height=None):
    """Draw an image centred horizontally at the given width.

    `max_height` scales the image down further when the caller has less
    vertical room than the requested width implies; without it the image
    keeps whatever height its aspect ratio dictates.
    """
    img = _open_img(img_path)
    w, h = img.getSize()
    disp_w = min(width, PAGE_W - 2 * MARGIN)
    disp_h = disp_w * (h / w)
    if max_height is not None and disp_h > max_height:
        disp_h = max_height
        disp_w = disp_h * (w / h)
    x = (PAGE_W - disp_w) / 2
    y = center_y - disp_h / 2
    c.drawImage(img, x, y, width=disp_w, height=disp_h,
                preserveAspectRatio=True, mask="auto")
    return disp_h


def spotify_url(sb_dir):
    """Return the public Spotify URL for this songbook, or None.

    Reads the songbook's own spotify.yaml manifest. Anything missing or
    unresolved -- no manifest, no PyYAML, empty album URI, null playlist
    id -- yields None so the back page simply omits the block.
    """
    path = os.path.join(sb_dir, MANIFEST)
    if not os.path.exists(path):
        return None
    try:
        import yaml
    except ImportError:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            entry = yaml.safe_load(fh) or {}
    except (OSError, ValueError):
        return None
    if not isinstance(entry, dict):
        return None
    if entry.get("mode") == "album":
        kind, ident = "album", entry.get("spotify_album")
    else:
        kind, ident = "playlist", entry.get("playlist_id")
    if not isinstance(ident, str) or not ident.strip():
        return None
    ident = ident.strip().rsplit(":", 1)[-1].rsplit("/", 1)[-1]
    return SPOTIFY_URL.format(kind=kind, ident=ident) if ident else None


def _wrap(c, text, font, size, max_width):
    """Greedy word wrap of one paragraph into a list of lines."""
    lines, line = [], ""
    for word in str(text).split():
        probe = f"{line} {word}".strip()
        if line and c.stringWidth(probe, font, size) > max_width:
            lines.append(line)
            line = word
        else:
            line = probe
    if line:
        lines.append(line)
    return lines


def _draw_description(c, conf, top_y):
    """Draw the centred description block; return the last baseline used."""
    text = conf.get("description")
    if not text:
        return top_y
    paragraphs = [text] if isinstance(text, str) else list(text)
    font = conf["description_font"]
    size = conf["description_size"]
    leading = conf.get("description_leading") or size * 1.5
    max_width = min(conf["description_width"], PAGE_W - 2 * MARGIN)
    color = (conf.get("description_color") or conf.get("caption_color")
             or "#000000")

    c.saveState()
    c.setFont(font, size)
    c.setFillColor(HexColor(color))
    y = conf.get("description_y")
    if y is None:
        y = top_y
    for index, paragraph in enumerate(paragraphs):
        if index:
            y -= leading * 0.6
        for line in _wrap(c, paragraph, font, size, max_width):
            c.drawCentredString(PAGE_W / 2, y, line)
            y -= leading
    c.restoreState()
    return y + leading


def _description_height(c, conf):
    """Vertical space the description block will occupy, 0 when empty."""
    text = conf.get("description")
    if not text:
        return 0
    paragraphs = [text] if isinstance(text, str) else list(text)
    font = conf["description_font"]
    size = conf["description_size"]
    leading = conf.get("description_leading") or size * 1.5
    max_width = min(conf["description_width"], PAGE_W - 2 * MARGIN)
    lines = sum(len(_wrap(c, p, font, size, max_width)) for p in paragraphs)
    gaps = leading * 0.6 * max(len(paragraphs) - 1, 0)
    return lines * leading + gaps


def _draw_qr(c, url, x, y, size, color):
    """Draw a vector QR code with its quiet zone inside the given box."""
    qr = QrCodeWidget(url, barLevel="M", barBorder=4)
    qr.barFillColor = HexColor(color)
    bounds = qr.getBounds()
    src_w = bounds[2] - bounds[0]
    src_h = bounds[3] - bounds[1]
    drawing = Drawing(size, size,
                      transform=[size / src_w, 0, 0, size / src_h, 0, 0])
    drawing.add(qr)
    renderPDF.draw(drawing, c, x, y)


def _draw_spotify(c, conf, url):
    """Draw the bottom-right QR code plus clickable label and URL."""
    right = conf.get("spotify_x")
    if right is None:
        right = PAGE_W - MARGIN
    bottom = conf.get("spotify_y")
    if bottom is None:
        bottom = MARGIN + 60
    size = conf["spotify_size"]
    color = conf.get("spotify_color") or conf["caption_color"]
    qr_size = conf["spotify_qr_size"]
    qr_color = conf.get("spotify_qr_color") or color
    label = conf.get("spotify_label")

    url_baseline = bottom
    label_baseline = url_baseline + size * 1.4
    qr_bottom = label_baseline + size * 0.9

    c.saveState()
    # Light plate so the code stays scannable over tinted backgrounds.
    c.setFillColorRGB(1, 1, 1)
    c.rect(right - qr_size, qr_bottom, qr_size, qr_size, stroke=0, fill=1)
    _draw_qr(c, url, right - qr_size, qr_bottom, qr_size, qr_color)

    c.setFillColor(HexColor(color))
    if label:
        c.setFont(conf["spotify_font"], size)
        c.drawRightString(right, label_baseline, label)
    c.setFont(conf["spotify_url_font"], size)
    c.drawRightString(right, url_baseline, url)
    c.restoreState()

    url_width = c.stringWidth(url, conf["spotify_url_font"], size)
    c.linkURL(url, (right - url_width, url_baseline - size * 0.3,
                    right, url_baseline + size), relative=0, thickness=0)
    c.linkURL(url, (right - qr_size, qr_bottom,
                    right, qr_bottom + qr_size), relative=0, thickness=0)


def _draw_link_row(c, x_center, y_bottom, label, url, color, qr_color,
                   qr_size, size, label_font, url_font):
    """Draw one QR + label/URL row centred on `x_center`.

    The QR sits on the left with a white plate under it, the label
    stacked over the clickable URL on its right, both left-aligned and
    vertically centred on the code. `y_bottom` is the QR's bottom edge.
    Both the QR square and the URL text get their own link region.
    """
    gap = size * 1.6
    label_w = c.stringWidth(label, label_font, size) if label else 0
    url_w = c.stringWidth(url, url_font, size)
    text_w = max(label_w, url_w)
    row_w = qr_size + gap + text_w
    qr_x = x_center - row_w / 2
    text_x = qr_x + qr_size + gap

    center_y = y_bottom + qr_size / 2
    if label:
        label_baseline = center_y + size * 0.35
        url_baseline = label_baseline - size * 1.7
    else:
        label_baseline = None
        url_baseline = center_y - size * 0.35

    c.saveState()
    # Light plate so the code stays scannable over tinted backgrounds.
    c.setFillColorRGB(1, 1, 1)
    c.rect(qr_x, y_bottom, qr_size, qr_size, stroke=0, fill=1)
    _draw_qr(c, url, qr_x, y_bottom, qr_size, qr_color)

    c.setFillColor(HexColor(color))
    if label:
        c.setFont(label_font, size)
        c.drawString(text_x, label_baseline, label)
    c.setFont(url_font, size)
    c.drawString(text_x, url_baseline, url)
    c.restoreState()

    c.linkURL(url, (text_x, url_baseline - size * 0.3,
                    text_x + url_w, url_baseline + size),
              relative=0, thickness=0)
    c.linkURL(url, (qr_x, y_bottom, qr_x + qr_size, y_bottom + qr_size),
              relative=0, thickness=0)
    return y_bottom


def _link_rows(conf, auto_url=None):
    """Build the ordered link-row descriptors for a page.

    The user-authored `links` entries come first in array order, then the
    manifest-driven Spotify row (when enabled and resolved) closes the
    stack. Entries inherit the page's spotify_* typography and QR size;
    each may override `color` and `qr_color`. Malformed or url-less
    entries are skipped rather than raising.
    """
    size = conf["spotify_size"]
    qr_size = conf["spotify_qr_size"]
    default_color = (conf.get("spotify_color") or conf.get("caption_color")
                     or "#000000")
    style = {
        "qr_size": qr_size,
        "size": size,
        "label_font": conf["spotify_font"],
        "url_font": conf["spotify_url_font"],
    }

    rows = []
    for entry in conf.get("links") or []:
        if not isinstance(entry, dict):
            continue
        url = entry.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        color = entry.get("color") or default_color
        rows.append(dict(style, label=entry.get("label"), url=url.strip(),
                         color=color,
                         qr_color=entry.get("qr_color") or color))
    if auto_url:
        color = default_color
        rows.append(dict(style, label=conf.get("spotify_label"),
                         url=auto_url, color=color,
                         qr_color=conf.get("spotify_qr_color") or color))
    return rows


def _link_stack_height(rows):
    """Total height of the stacked link rows, gaps included."""
    if not rows:
        return 0
    return (sum(row["qr_size"] for row in rows)
            + LINK_ROW_GAP * (len(rows) - 1))


def _row_width(c, row):
    """Full width of one link row: QR + gap + widest of label/URL."""
    size = row["size"]
    label = row["label"]
    label_w = c.stringWidth(label, row["label_font"], size) if label else 0
    url_w = c.stringWidth(row["url"], row["url_font"], size)
    return row["qr_size"] + size * 1.6 + max(label_w, url_w)


def _draw_link_stack(c, rows, y_top, x_center=None):
    """Draw link rows top-down from `y_top`; return the stack's bottom.

    The group is centred as a whole and every QR shares one left edge, so
    rows with different label/URL lengths line up instead of drifting
    left and right of each other.
    """
    if x_center is None:
        x_center = PAGE_W / 2
    rows = _fit_row_widths(c, rows)
    group_w = max(_row_width(c, row) for row in rows)
    qr_left = x_center - group_w / 2

    y = y_top
    for index, row in enumerate(rows):
        if index:
            y -= LINK_ROW_GAP
        y -= row["qr_size"]
        # Feed each row the centre that puts its QR on the shared edge.
        row_center = qr_left + _row_width(c, row) / 2
        _draw_link_row(c, row_center, y, row["label"], row["url"],
                       row["color"], row["qr_color"], row["qr_size"],
                       row["size"], row["label_font"], row["url_font"])
    return y


def _fit_rows(rows, available):
    """Shrink QR codes proportionally until the stack fits `available`.

    A single row keeps its configured size. Several rows on one page will
    happily overflow at the default 96pt, so they scale down together --
    never below MIN_QR_SIZE, which is still comfortably scannable.
    """
    stack_h = _link_stack_height(rows)
    if stack_h <= available or len(rows) < 2:
        return rows
    gaps = LINK_ROW_GAP * (len(rows) - 1)
    qr_total = sum(row["qr_size"] for row in rows)
    scale = max((available - gaps) / qr_total, 0)
    return [dict(row, qr_size=max(row["qr_size"] * scale, MIN_QR_SIZE))
            for row in rows]


def _fit_row_widths(c, rows):
    """Shrink QR codes so the widest row fits between the margins.

    Long URLs cannot wrap, so a row can be wider than the printable area.
    The QR is the only elastic part, and trimming it pulls the whole
    group back inside the margins. Bounded by MIN_QR_SIZE; a URL long
    enough to overflow even then is a cover.json problem, not a layout
    one.
    """
    if not rows:
        return rows
    available = PAGE_W - 2 * MARGIN
    overflow = max(_row_width(c, row) for row in rows) - available
    if overflow <= 0:
        return rows
    return [dict(row, qr_size=max(row["qr_size"] - overflow, MIN_QR_SIZE))
            for row in rows]


def _place_link_stack(rows, text_bottom, clearance, floor_pad):
    """Return (rows, y_top): rows fitted to free space, group centred.

    The band runs from `clearance` below the last text baseline down to
    `floor_pad` above the page margin. Rows are shrunk to fit that band,
    then the group is centred in it. If even MIN_QR_SIZE overflows -- a
    page asking for more link rows than its image and text leave room for
    -- the stack anchors on the floor and grows upward, so it always
    stays on the page instead of sliding under the bottom margin.
    """
    band_top = text_bottom - clearance
    band_bottom = MARGIN + floor_pad
    rows = _fit_rows(rows, band_top - band_bottom)
    stack_h = _link_stack_height(rows)
    if band_top - band_bottom >= stack_h:
        return rows, (band_top + band_bottom + stack_h) / 2
    return rows, band_bottom + stack_h


def make_intro(sb_dir, output, cfg):
    """Intro page: optional title, description, centred link rows.

    Opt-in via an `intro` section in cover.json. The text block sits in
    the upper-middle of the page; the link stack (any custom `links`,
    then the manifest Spotify row) is centred as one group in whatever
    space is left below it, so short and long descriptions both breathe.
    """
    conf = cfg["intro"]
    c = canvas.Canvas(output, pagesize=A4)
    _paint_background(c, conf.get("background"))
    _draw_rules(c, conf.get("rules"))

    text_top = PAGE_H - 225
    title = conf.get("title")
    if title:
        title_size = conf["title_size"]
        title_baseline = PAGE_H - 200
        c.setFont(conf["title_font"], title_size)
        c.setFillColor(HexColor(conf["title_color"]))
        c.drawCentredString(PAGE_W / 2, title_baseline, title)
        text_top = title_baseline - title_size * 2.3

    text_bottom = _draw_description(c, conf, text_top)

    auto_url = spotify_url(sb_dir) if conf.get("spotify") else None
    rows = _link_rows(conf, auto_url)
    if rows:
        override = conf.get("spotify_y")
        if override is None:
            rows, y_top = _place_link_stack(rows, text_bottom, 56, 96)
        else:
            y_top = override + _link_stack_height(rows)
        _draw_link_stack(c, rows, y_top)

    c.showPage()
    c.save()


def make_cover(sb_dir, output, cfg):
    """Cover: optional title/subtitle, decorative strips or rules, logo."""
    conf = cfg["cover"]
    c = canvas.Canvas(output, pagesize=A4)
    _paint_background(c, conf.get("background"))
    _draw_rules(c, conf.get("rules"))

    if conf.get("title"):
        c.setFont(conf["title_font"], conf["title_size"])
        c.setFillColor(HexColor(conf["title_color"]))
        c.drawCentredString(PAGE_W / 2, PAGE_H - MARGIN - 35, conf["title"])

    strip_top = _resolve(sb_dir, conf.get("strip_top"))
    if strip_top:
        c.drawImage(_open_img(strip_top), MARGIN, PAGE_H - MARGIN - 75,
                    width=PAGE_W - 2 * MARGIN, preserveAspectRatio=True,
                    anchor="n", mask="auto")

    logo = _resolve(sb_dir, conf.get("logo"))
    if logo:
        _draw_centered_image(c, logo, conf["logo_width"],
                             PAGE_H / 2 + conf["logo_offset"])

    if conf.get("subtitle"):
        c.setFont(conf["subtitle_font"], conf["subtitle_size"])
        c.setFillColor(HexColor(conf["subtitle_color"]))
        c.drawCentredString(PAGE_W / 2, MARGIN + 55, conf["subtitle"])

    strip_bot = _resolve(sb_dir, conf.get("strip_bottom"))
    if strip_bot:
        c.drawImage(_open_img(strip_bot), MARGIN, MARGIN + 10,
                    width=PAGE_W - 2 * MARGIN, preserveAspectRatio=True,
                    anchor="s", mask="auto")

    c.showPage()
    c.save()


def make_chord_chart(sb_dir, output):
    """Full-page chord chart centered."""
    c = canvas.Canvas(output, pagesize=A4)
    img_path = os.path.join(sb_dir, "chords.png")
    if os.path.exists(img_path):
        img = _open_img(img_path)
        avail_w = PAGE_W - 2 * MARGIN
        rw, rh = img.getSize()
        aspect = rh / rw
        disp_w = avail_w
        disp_h = disp_w * aspect
        if disp_h > PAGE_H - 2 * MARGIN:
            disp_h = PAGE_H - 2 * MARGIN
            disp_w = disp_h / aspect
        x = (PAGE_W - disp_w) / 2
        y = (PAGE_H - disp_h) / 2
        c.drawImage(img, x, y, width=disp_w, height=disp_h,
                    preserveAspectRatio=True)
    c.showPage()
    c.save()


def make_back_cover(sb_dir, output, cfg):
    """Back cover: centred image, optional caption, description, rules.

    The description block starts just under the image and reads down.
    With no custom `links`, the manifest Spotify block keeps its historic
    bottom-right corner placement. As soon as `links` are declared the
    page switches to the centred stack shared with the intro page, so
    every link gets the same treatment instead of one corner element
    fighting a second group for space.
    """
    conf = cfg["back"]
    c = canvas.Canvas(output, pagesize=A4)
    _paint_background(c, conf.get("background"))
    _draw_rules(c, conf.get("rules"))

    auto_url = spotify_url(sb_dir) if conf.get("spotify") else None
    rows = _link_rows(conf, auto_url) if conf.get("links") else []

    # A stacked link group needs its space reserved up front, otherwise a
    # large poster leaves the rows nowhere to go. Cap the image height to
    # whatever is left once the stack, description and caption are booked.
    img_max_h = None
    if rows:
        floor_pad = 70 if conf.get("caption") else 40
        reserved = (_link_stack_height(rows) + MARGIN + floor_pad + 40
                    + _description_height(c, conf) + 22
                    + conf["description_size"])
        # Never shrink the artwork away entirely: past MIN_IMAGE_HEIGHT the
        # QR rows scale down instead (see _fit_rows).
        img_max_h = max(2 * (PAGE_H / 2 - reserved), MIN_IMAGE_HEIGHT)

    img_bottom = PAGE_H / 2
    img_path = _resolve(sb_dir, conf.get("image"))
    if img_path:
        img_h = _draw_centered_image(c, img_path, conf["image_width"],
                                     PAGE_H / 2, img_max_h)
        img_bottom = PAGE_H / 2 - img_h / 2

    if conf.get("caption"):
        c.setFont(conf["caption_font"], conf["caption_size"])
        c.setFillColor(HexColor(conf["caption_color"]))
        c.drawCentredString(PAGE_W / 2, MARGIN + 40, conf["caption"])

    text_bottom = _draw_description(
        c, conf, img_bottom - 22 - conf["description_size"])

    if rows:
        override = conf.get("spotify_y")
        if override is None:
            floor_pad = 70 if conf.get("caption") else 40
            rows, y_top = _place_link_stack(rows, text_bottom, 40, floor_pad)
        else:
            y_top = override + _link_stack_height(rows)
        _draw_link_stack(c, rows, y_top)
    elif auto_url:
        _draw_spotify(c, conf, auto_url)

    c.showPage()
    c.save()


def generate_cover_pdfs(sb_dir, out_dir=None):
    """Generate the cover, optional intro/chart, and back PDFs.

    The intro page is produced only when cover.json declares an `intro`
    section, and the chord-chart page only when the songbook ships a
    chords.png; otherwise the matching returned path is None.
    """
    if out_dir is None:
        out_dir = os.path.join(sb_dir, "..", "..", "pdf")
    os.makedirs(out_dir, exist_ok=True)
    cfg = load_config(sb_dir)
    base = os.path.basename(os.path.normpath(sb_dir))
    cover_pdf = os.path.join(out_dir, f"{base}-cover.pdf")
    back_pdf = os.path.join(out_dir, f"{base}-back.pdf")
    make_cover(sb_dir, cover_pdf, cfg)
    make_back_cover(sb_dir, back_pdf, cfg)

    intro_pdf = None
    if cfg["intro"].get("_declared"):
        intro_pdf = os.path.join(out_dir, f"{base}-intro.pdf")
        make_intro(sb_dir, intro_pdf, cfg)

    chart_pdf = None
    if _resolve(sb_dir, "chords.png"):
        chart_pdf = os.path.join(out_dir, f"{base}-chart.pdf")
        make_chord_chart(sb_dir, chart_pdf)
    return cover_pdf, intro_pdf, chart_pdf, back_pdf


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: make-cover.py <songbook-dir> <output-dir>",
              file=sys.stderr)
        sys.exit(1)
    cover, intro, chart, back = generate_cover_pdfs(sys.argv[1], sys.argv[2])
    print(f"Cover → {cover}")
    if intro:
        print(f"Intro → {intro}")
    print(f"Chart → {chart or '(skipped, no chords.png)'}")
    print(f"Back  → {back}")
