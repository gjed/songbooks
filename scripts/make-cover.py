"""Generate cover, chord-chart, and back-cover PDFs for a songbook.

Usage:
  python3 make-cover.py <songbook-dir> <output-dir>

Requires images in the songbook directory:
  cover-uke.png        — ukulele logo (cover)
  strip-top.png        — top decorative strip
  strip-bottom.png     — bottom decorative strip
  cover-celtic.jpeg    — Celtic knot (back cover)
  chords.png           — chord chart diagram
"""

import os
import sys
import tempfile
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


PAGE_W, PAGE_H = A4  # 595.27 x 841.89 pt
MARGIN = 10 * mm       # 28.35 pt


def _open_img(img_path):
    """Open an image and return reportlab ImageReader (handles alpha)."""
    im = Image.open(img_path)
    if im.mode in ("LA", "P"):
        im = im.convert("RGBA")
    return ImageReader(im)


def make_cover(sb_dir, output):
    """Cover: title + strips + centered ukulele logo."""
    c = canvas.Canvas(output, pagesize=A4)
    strip_top = os.path.join(sb_dir, "strip-top.png")
    strip_bot = os.path.join(sb_dir, "strip-bottom.png")
    uke = os.path.join(sb_dir, "cover-uke.png")

    c.setFont("Courier-Bold", 28)
    c.drawCentredString(PAGE_W / 2, PAGE_H - MARGIN - 35, "HBS Songbook")

    # Top strip
    if os.path.exists(strip_top):
        img = _open_img(strip_top)
        c.drawImage(img, MARGIN, PAGE_H - MARGIN - 75,
                    width=PAGE_W - 2 * MARGIN, preserveAspectRatio=True, anchor='n')

    # Ukulele logo — centered horizontally, positioned slightly below true center
    if os.path.exists(uke):
        uke_img = _open_img(uke)
        avail_w = PAGE_W - 2 * MARGIN
        w, h = uke_img.getSize()
        aspect = h / w
        disp_w = min(avail_w, 480)
        disp_h = disp_w * aspect
        x = (PAGE_W - disp_w) / 2
        y = (PAGE_H - disp_h) / 2 - 20  # slightly below true center to balance title
        c.drawImage(uke_img, x, y, width=disp_w, height=disp_h, preserveAspectRatio=True)

    # Bottom strip
    if os.path.exists(strip_bot):
        bot_img = _open_img(strip_bot)
        c.drawImage(bot_img, MARGIN, MARGIN + 10,
                    width=PAGE_W - 2 * MARGIN, preserveAspectRatio=True, anchor='s')

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
        c.drawImage(img, x, y, width=disp_w, height=disp_h, preserveAspectRatio=True)
    c.showPage()
    c.save()


def make_back_cover(sb_dir, output):
    """Back cover: Celtic knot centered at ~240pt wide."""
    c = canvas.Canvas(output, pagesize=A4)
    img_path = os.path.join(sb_dir, "cover-celtic.jpeg")
    if os.path.exists(img_path):
        img = _open_img(img_path)
        w, h = img.getSize()
        aspect = h / w
        disp_w = 240  # matching previous ChordPro scale=0.9 column-width size
        disp_h = disp_w * aspect
        x = (PAGE_W - disp_w) / 2
        y = (PAGE_H - disp_h) / 2
        c.drawImage(img, x, y, width=disp_w, height=disp_h, preserveAspectRatio=True)
    c.showPage()
    c.save()


def generate_cover_pdfs(sb_dir):
    """Generate all three PDFs. Returns (cover, chart, back) paths."""
    out_dir = os.path.join(sb_dir, "..", "..", "pdf")
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.basename(os.path.normpath(sb_dir))
    cover_pdf = os.path.join(out_dir, f"{base}-cover.pdf")
    chart_pdf = os.path.join(out_dir, f"{base}-chart.pdf")
    back_pdf = os.path.join(out_dir, f"{base}-back.pdf")
    make_cover(sb_dir, cover_pdf)
    make_chord_chart(sb_dir, chart_pdf)
    make_back_cover(sb_dir, back_pdf)
    return cover_pdf, chart_pdf, back_pdf


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: make-cover.py <songbook-dir> <output-dir>", file=sys.stderr)
        sys.exit(1)
    sb_dir = sys.argv[1]
    out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.basename(os.path.normpath(sb_dir))
    cover_pdf = os.path.join(out_dir, f"{base}-cover.pdf")
    chart_pdf = os.path.join(out_dir, f"{base}-chart.pdf")
    back_pdf = os.path.join(out_dir, f"{base}-back.pdf")
    make_cover(sb_dir, cover_pdf)
    make_chord_chart(sb_dir, chart_pdf)
    make_back_cover(sb_dir, back_pdf)
    print(f"Cover → {cover_pdf}")
    print(f"Chart → {chart_pdf}")
    print(f"Back  → {back_pdf}")
