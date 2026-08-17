"""Generate cover, chord-chart, and back-cover PDFs for a songbook.

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
      "rules": []
    }
  }

`description` is a single string or a list of strings, one per
paragraph; each paragraph is wrapped to `description_width` and centred.
`description_y` is the first baseline and defaults to just below the back
image, so the block follows whatever `image_width` the songbook uses.

The Spotify block is automatic: the back page reads the repo-root
`spotify-playlists.yaml` and, when the songbook has a resolved album or
playlist link, draws a right-aligned label + URL (clickable) next to a
vector QR code of the same URL. Missing file, missing PyYAML, or an
unresolved link simply skips the block. `spotify_x` / `spotify_y` are the
right and bottom edges of that block.
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

MANIFEST = "spotify-playlists.yaml"
SPOTIFY_URL = "https://open.spotify.com/{kind}/{ident}"

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
        "rules": [],
    },
}


def load_config(sb_dir):
    """Merge cover.json (if present) on top of the built-in defaults."""
    cfg = {section: dict(values) for section, values in DEFAULTS.items()}
    path = os.path.join(sb_dir, "cover.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            user = json.load(fh)
        for section in cfg:
            cfg[section].update(user.get(section, {}))
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


def _draw_centered_image(c, img_path, width, center_y):
    """Draw an image centred horizontally at the given width."""
    img = _open_img(img_path)
    w, h = img.getSize()
    disp_w = min(width, PAGE_W - 2 * MARGIN)
    disp_h = disp_w * (h / w)
    x = (PAGE_W - disp_w) / 2
    y = center_y - disp_h / 2
    c.drawImage(img, x, y, width=disp_w, height=disp_h,
                preserveAspectRatio=True, mask="auto")
    return disp_h


def _find_manifest(sb_dir):
    """Walk up from sb_dir looking for the Spotify manifest, else None."""
    path = os.path.abspath(sb_dir)
    while True:
        candidate = os.path.join(path, MANIFEST)
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def spotify_url(sb_dir):
    """Return the public Spotify URL for this songbook, or None.

    Reads the repo-root manifest. Anything missing or unresolved -- no
    manifest, no PyYAML, unknown songbook, empty album URI, null playlist
    id -- yields None so the back page simply omits the block.
    """
    path = _find_manifest(sb_dir)
    if not path:
        return None
    try:
        import yaml
    except ImportError:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    books = data.get("songbooks")
    if not isinstance(books, dict):
        return None
    entry = books.get(os.path.basename(os.path.normpath(sb_dir)))
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
    color = conf.get("description_color") or conf["caption_color"]

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

    The description block starts just under the image and reads down; the
    Spotify block sits in the bottom-right corner, clear of both.
    """
    conf = cfg["back"]
    c = canvas.Canvas(output, pagesize=A4)
    _paint_background(c, conf.get("background"))
    _draw_rules(c, conf.get("rules"))

    img_bottom = PAGE_H / 2
    img_path = _resolve(sb_dir, conf.get("image"))
    if img_path:
        img_h = _draw_centered_image(c, img_path, conf["image_width"],
                                     PAGE_H / 2)
        img_bottom = PAGE_H / 2 - img_h / 2

    if conf.get("caption"):
        c.setFont(conf["caption_font"], conf["caption_size"])
        c.setFillColor(HexColor(conf["caption_color"]))
        c.drawCentredString(PAGE_W / 2, MARGIN + 40, conf["caption"])

    _draw_description(c, conf, img_bottom - 22 - conf["description_size"])

    if conf.get("spotify"):
        url = spotify_url(sb_dir)
        if url:
            _draw_spotify(c, conf, url)

    c.showPage()
    c.save()


def generate_cover_pdfs(sb_dir, out_dir=None):
    """Generate the cover, optional chart, and back PDFs.

    The chord-chart page is produced only when the songbook ships a
    chords.png; otherwise the returned chart path is None.
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

    chart_pdf = None
    if _resolve(sb_dir, "chords.png"):
        chart_pdf = os.path.join(out_dir, f"{base}-chart.pdf")
        make_chord_chart(sb_dir, chart_pdf)
    return cover_pdf, chart_pdf, back_pdf


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: make-cover.py <songbook-dir> <output-dir>",
              file=sys.stderr)
        sys.exit(1)
    cover, chart, back = generate_cover_pdfs(sys.argv[1], sys.argv[2])
    print(f"Cover → {cover}")
    print(f"Chart → {chart or '(skipped, no chords.png)'}")
    print(f"Back  → {back}")
