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
      "rules": []
    }
  }
"""

import json
import os
import sys

from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


PAGE_W, PAGE_H = A4  # 595.27 x 841.89 pt
MARGIN = 10 * mm     # 28.35 pt

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
    """Back cover: centred image with optional caption and rules."""
    conf = cfg["back"]
    c = canvas.Canvas(output, pagesize=A4)
    _paint_background(c, conf.get("background"))
    _draw_rules(c, conf.get("rules"))

    img_path = _resolve(sb_dir, conf.get("image"))
    if img_path:
        _draw_centered_image(c, img_path, conf["image_width"], PAGE_H / 2)

    if conf.get("caption"):
        c.setFont(conf["caption_font"], conf["caption_size"])
        c.setFillColor(HexColor(conf["caption_color"]))
        c.drawCentredString(PAGE_W / 2, MARGIN + 40, conf["caption"])

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
