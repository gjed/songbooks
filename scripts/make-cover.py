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
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


PAGE_W, PAGE_H = A4  # 595.27 x 841.89 pt
MARGIN = 10 * mm       # 28.35 pt


def make_cover(sb_dir, output):
    """Cover: title + strips + centered ukulele logo."""
    c = canvas.Canvas(output, pagesize=A4)
    strip_top = os.path.join(sb_dir, "strip-top.png")
    strip_bot = os.path.join(sb_dir, "strip-bottom.png")
    uke = os.path.join(sb_dir, "cover-uke.png")

    c.setFont("Courier-Bold", 28)
    c.drawCentredString(PAGE_W / 2, PAGE_H - MARGIN - 35, "HBS Songbook")

    # Top decorative strip
    if os.path.exists(strip_top):
        c.drawImage(strip_top, MARGIN, PAGE_H - MARGIN - 75,
                    width=PAGE_W - 2 * MARGIN, preserveAspectRatio=True)

    # Ukulele logo — centered vertically and horizontally
    if os.path.exists(uke):
        c.drawImage(uke, MARGIN, MARGIN,
                    width=PAGE_W - 2 * MARGIN, preserveAspectRatio=True)

    # Bottom decorative strip
    if os.path.exists(strip_bot):
        c.drawImage(strip_bot, MARGIN, MARGIN,
                    width=PAGE_W - 2 * MARGIN, preserveAspectRatio=True)

    c.showPage()
    c.save()


def make_chord_chart(sb_dir, output):
    """Full-page chord chart centered."""
    c = canvas.Canvas(output, pagesize=A4)
    img = os.path.join(sb_dir, "chords.png")
    if os.path.exists(img):
        c.drawImage(img, MARGIN, MARGIN,
                    width=PAGE_W - 2 * MARGIN, preserveAspectRatio=True)
    c.showPage()
    c.save()


def make_back_cover(sb_dir, output):
    """Back cover: Celtic knot centered."""
    c = canvas.Canvas(output, pagesize=A4)
    img = os.path.join(sb_dir, "cover-celtic.jpeg")
    if os.path.exists(img):
        c.drawImage(img, MARGIN, MARGIN,
                    width=PAGE_W - 2 * MARGIN, preserveAspectRatio=True)
    c.showPage()
    c.save()


def generate_cover_pdfs(sb_dir):
    """Generate all three PDFs in one call. Returns list of paths."""
    out_dir = os.path.join(sb_dir, "..", "..", "pdf")
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.basename(os.path.normpath(sb_dir))
    cover_pdf = os.path.join(out_dir, f"{base}-cover.pdf")
    chart_pdf = os.path.join(out_dir, f"{base}-chart.pdf")
    back_pdf = os.path.join(out_dir, f"{base}-back.pdf")
    make_cover(sb_dir, cover_pdf)
    make_chord_chart(sb_dir, chart_pdf)
    make_back_cover(sb_dir, back_pdf)
    return [cover_pdf, chart_pdf, back_pdf]


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: make-cover.py <songbook-dir> <output-dir>")
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
