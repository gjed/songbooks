#!/usr/bin/env python3
"""Generate Hugo content and assets from songbooks.

Converts songbook folders into Hugo markdown files with YAML front matter,
extracts PDF thumbnails, and copies PDFs for download.

Usage:
  python3 scripts/site-data.py [--version TAG] [--pdf-dir pdf] [--site-dir site]

--version defaults to "dev".
"""

from __future__ import annotations

import argparse
import html as html_module
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - dependency guard
    sys.exit(
        "error: PyYAML is required.\n"
        "  fix: pip install PyYAML   (or: pip install -r requirements.txt)"
    )

REPO_ROOT = Path(__file__).resolve().parent.parent

# Import the shared metadata module
sys.path.insert(0, str(Path(__file__).parent))
from songbook_meta import LOCALES, load_metadata, localize, language_of

SONGBOOKS_DIR = REPO_ROOT / "songbooks"
HEADER_RE = re.compile(r"^\{(?P<key>[a-z_]+):\s*(?P<value>.*?)\s*\}\s*$")
PSEUDO_SONGS = {"00-cover.cho", "01-chord-chart.cho", "99-back-cover.cho"}

# ChordPro's HTML backend emits a standalone document per song; the site only
# wants the body, minus the <style> block (it carries @page print rules).
BODY_RE = re.compile(r"<body[^>]*>(?P<body>.*)</body>", re.DOTALL | re.IGNORECASE)
STYLE_RE = re.compile(r"<style[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)

# Leading track number on a .cho filename, dropped from the public URL.
TRACK_NUM_RE = re.compile(r"^\d+[-_]")

# ── songline wrap transform ──────────────────────────────────────────────
# ChordPro's HTML backend emits one <table class="songline"> per lyric line,
# with the chord in column N sitting above the lyric fragment in column N —
# alignment carried entirely by table columns. A <tr> has no wrapping model,
# so long lines cannot wrap in that markup no matter what CSS says. This
# section rewrites each table into a flat inline <div>: atomic
# chord+syllable groups (which never wrap internally) separated by plain
# breakable tail text (which wraps at every space). See
# site/assets/css/chordpro.css's "songline table" section for the CSS half
# of this contract (.songline/.cl/.clx).
SONGLINE_TABLE_RE = re.compile(r'<table class="songline">(.*?)</table>', re.DOTALL)
SONGLINE_ROW_RE = re.compile(r'<tr class="(chords|lyrics)">(.*?)</tr>', re.DOTALL)
SONGLINE_TD_RE = re.compile(r'<td( class="indent")?>(.*?)</td>', re.DOTALL)

NBSP = "\u00a0"
# Rough monospace glyph-advance ratio (advance ≈ 0.6 * font-size), used only
# to decide how many lyric words an anchor needs to visually cover its
# chord — not for pixel-perfect layout. See chordpro.css: chord row is
# 12px/700, lyric row is 15px/400.
_CHORD_GLYPH_PX = 12 * 0.6
_LYRIC_GLYPH_PX = 15 * 0.6


def _songline_encode_tail(text: str) -> str:
    """Encode a run of breakable lyric text: escape it, and turn space runs
    into (n-1) no-break spaces + one real breakable space, so exactly one
    wrap opportunity survives per run. A lone space stays a lone (breakable)
    space. Hugo's minifier is configured with keepWhitespace=true (see
    site/hugo.toml) so these interior spaces are not at risk of being
    trimmed the way protect_cell_whitespace once had to guard against."""
    if not text:
        return ""
    parts: list[str] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] == " ":
            j = i
            while j < n and text[j] == " ":
                j += 1
            run = j - i
            parts.append((NBSP * (run - 1) + " ") if run > 1 else " ")
            i = j
        else:
            j = i
            while j < n and text[j] != " ":
                j += 1
            parts.append(html_module.escape(text[i:j], quote=False))
            i = j
    return "".join(parts)


def _songline_split_anchor(frag: str, chord_chars: int) -> tuple[str, str]:
    """Split a lyric fragment into (anchor, tail) at a word boundary.

    The anchor is the minimal run of whole words (each including its
    trailing space) whose rendered width covers the chord above it — so a
    short chord like "A" anchors to one syllable, not the whole fragment.
    If the fragment contains no space at all, the entire fragment becomes
    the anchor and the tail is empty — signalling to the caller that the
    next column's chord lands inside this same (still-open) word and must
    be merged into the same atomic group.
    """
    if not frag:
        return "", ""
    min_width = chord_chars * _CHORD_GLYPH_PX
    covered = 0.0
    i, n = 0, len(frag)
    last_space_end = 0
    while i < n:
        j = i
        while j < n and frag[j] != " ":
            j += 1
        word_end = j
        k = j
        while k < n and frag[k] == " ":
            k += 1
        covered += (word_end - i) * _LYRIC_GLYPH_PX
        if k > j:
            last_space_end = k
        if covered >= min_width or k >= n:
            if k >= n:
                if k > j:
                    return frag[:k], frag[k:]
                return frag, ""  # exhausted mid-word: whole frag is the anchor
            return frag[:k], frag[k:]
        i = k
    return frag[:last_space_end] or frag, frag[last_space_end:]


def _songline_emit_group(cols: list[tuple[str, str]]) -> str:
    """Render one atomic chord+syllable group. A single column becomes a
    `.cl` inline-block; two or more (a chord landing mid-word) become a
    `.clx` mini inline-table — ChordPro's own table alignment machinery,
    shrunk to one word, so it stays unbreakable by construction."""
    if len(cols) == 1:
        chord, lyric = cols[0]
        ch = (html_module.escape(chord, quote=False) + NBSP) if chord else ""
        ly = html_module.escape(lyric, quote=False)
        return f'<span class="cl"><span class="ch">{ch}</span><span class="ly">{ly}</span></span>'
    rows_ch = "".join(
        f'<span class="ch">{(html_module.escape(c, quote=False) + NBSP) if c else ""}</span>'
        for c, _ in cols
    )
    rows_ly = "".join(
        f'<span class="ly">{html_module.escape(l, quote=False)}</span>' for _, l in cols
    )
    return (
        '<span class="clx">'
        f'<span class="r">{rows_ch}</span>'
        f'<span class="r">{rows_ly}</span>'
        "</span>"
    )


def _transform_songline(table_body: str) -> str:
    """Rewrite one <table class="songline">...</table> body into a wrappable
    <div class="songline">. See the module-level comment above for why."""
    rows = dict(SONGLINE_ROW_RE.findall(table_body))
    has_chords = "chords" in rows

    if not has_chords:
        # Lyric-only line (not observed in the current corpus, but ChordPro
        # allows it — handle defensively rather than assume).
        cells = [
            html_module.unescape(text)
            for _, text in SONGLINE_TD_RE.findall(rows.get("lyrics", ""))
        ]
        return f'<div class="songline">{_songline_encode_tail("".join(cells))}</div>'

    chord_cells = [
        html_module.unescape(c).rstrip(" ")
        for _, c in SONGLINE_TD_RE.findall(rows["chords"])
    ]
    lyric_cells = [
        (html_module.unescape(text), bool(cls))
        for cls, text in SONGLINE_TD_RE.findall(rows.get("lyrics", ""))
    ]
    n = len(chord_cells)
    if len(lyric_cells) != n:
        # Chord-only line (chorded intro with no lyric row at all): pad so
        # every chord still gets an (empty) lyric anchor rather than being
        # dropped silently.
        lyric_cells = (lyric_cells + [("", False)] * n)[:n]

    parts: list[str] = []
    pending = ""  # breakable tail text collected since the last group
    first_group = True
    i = 0
    while i < n:
        frag, indent = lyric_cells[i]

        # A dangling non-space run at the end of `pending` (no boundary
        # since the previous fragment) belongs under THIS chord, not free
        # in the tail — otherwise it could wrap away from its chord.
        prefix = ""
        if pending and not pending.endswith(" ") and not indent:
            j = len(pending)
            while j > 0 and pending[j - 1] != " ":
                j -= 1
            prefix, pending = pending[j:], pending[:j]

        # ChordPro marks a fragment whose source began with real whitespace
        # as class="indent" (the space itself is stripped from the text).
        # Restore it as an actual breakable space — a no-break space only
        # at the very start of the line, where no break is wanted.
        if indent and not prefix:
            pending += NBSP if (first_group and not pending) else " "

        parts.append(_songline_encode_tail(pending))
        pending = ""

        cols = [("", prefix)] if prefix else []
        anchor, tail = _songline_split_anchor(frag, len(chord_cells[i]) or 1)
        cols.append((chord_cells[i], anchor))

        # The anchor consumed the whole fragment with no boundary after it:
        # the next chord lands inside this same still-open word (ChordPro's
        # mid-word split) — fuse it into the same atomic group.
        while tail == "" and anchor and not anchor.endswith(" ") and i + 1 < n:
            nxt_frag, nxt_indent = lyric_cells[i + 1]
            if nxt_indent:
                break  # false alarm: that IS a real word boundary
            i += 1
            anchor, tail = _songline_split_anchor(
                nxt_frag, len(chord_cells[i]) or 1
            )
            cols.append((chord_cells[i], anchor))

        parts.append(_songline_emit_group(cols))
        first_group = False
        pending = tail
        i += 1

    parts.append(_songline_encode_tail(pending))
    return f'<div class="songline">{"".join(parts)}</div>'


def make_songlines_wrappable(html: str) -> str:
    """Rewrite every <table class="songline"> in a rendered fragment into a
    wrappable <div class="songline">. See _transform_songline for why this
    exists and site/assets/css/chordpro.css's songline section for the CSS
    half of the contract."""
    return SONGLINE_TABLE_RE.sub(
        lambda m: _transform_songline(m.group(1)), html
    )


def parse_headers(path: Path) -> dict[str, str]:
    """Return the ChordPro directive headers of a .cho file."""
    headers: dict[str, str] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            match = HEADER_RE.match(line)
            if match:
                headers.setdefault(match["key"], match["value"])
            if len(headers) >= 8:
                break
    return headers


def extract_thumbnail(pdf_path: Path, thumb_path: Path) -> bool:
    """Extract first page of PDF as PNG thumbnail.
    
    Returns True if successful, False if extraction failed.
    """
    try:
        subprocess.run(
            [
                "gs",
                "-q",
                "-dBATCH",
                "-dNOPAUSE",
                "-r72",
                "-dFirstPage=1",
                "-dLastPage=1",
                "-sDEVICE=png16m",
                f"-sOutputFile={thumb_path}",
                str(pdf_path),
            ],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(
            f"warning: {pdf_path.name}: thumbnail extraction failed — {exc}",
            file=sys.stderr,
        )
        return False


def parse_tracklist(slug: str) -> tuple[list[dict[str, str]], int, bool]:
    """Parse tracklist from .cho files in a songbook.
    
    Returns (tracks, song_count, chart_only).
    - tracks: list of {title, artist, slug, source} dicts for non-special .cho
      files, in track order; `slug` is the song's URL segment and `source` its
      .cho stem, which is how the rendered HTML is looked up
    - song_count: number of real songs (non-special .cho files)
    - chart_only: True if all .cho files are special pages (00-, 01-, 99-)
    """
    songbook_dir = SONGBOOKS_DIR / slug
    tracks: list[dict[str, str]] = []
    
    for cho in sorted(songbook_dir.glob("*.cho")):
        if cho.name in PSEUDO_SONGS:
            continue
        
        headers = parse_headers(cho)
        title = headers.get("title", "").strip()
        artist = headers.get("artist", "").strip()
        
        if title and artist:
            tracks.append({
                "title": title,
                "artist": artist,
                "slug": song_url_slug(cho.name),
                "source": cho.stem,
            })
    
    # Check if all .cho files are special pages
    all_cho_files = list(songbook_dir.glob("*.cho"))
    chart_only = len(all_cho_files) > 0 and len(tracks) == 0
    
    return tracks, len(tracks), chart_only


def song_url_slug(cho_name: str) -> str:
    """Public URL slug for a song, from its .cho filename.

    Drops the leading track number so URLs read as titles rather than
    positions ("01-come-una-foglia.cho" -> "come-una-foglia"). Ordering is
    carried by front matter weight instead.
    """
    return TRACK_NUM_RE.sub("", Path(cho_name).stem)


def extract_song_fragment(html_path: Path) -> str | None:
    """Return one rendered song as an embeddable HTML fragment.

    Returns None when the render is missing or has no body, so a songbook with
    an incomplete render degrades to "no read view" instead of a broken page.
    """
    if not html_path.exists():
        return None

    try:
        content = html_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"warning: {html_path.name}: unreadable — {exc}", file=sys.stderr)
        return None

    match = BODY_RE.search(content)
    if not match:
        return None

    body = STYLE_RE.sub("", match["body"])
    body = make_songlines_wrappable(body)
    return body.strip() or None


def load_spotify_manifest(slug: str) -> dict[str, Any]:
    """Load spotify.yaml for a songbook."""
    path = SONGBOOKS_DIR / slug / "spotify.yaml"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else {}


def is_album_mode(entry: dict[str, Any]) -> bool:
    """True when a songbook is linked to one Spotify album instead of curated
    track by track. Default mode is playlist."""
    return str(entry.get("mode", "playlist")) == "album"


def build_spotify_url(spotify_manifest: dict[str, Any]) -> str | None:
    """Build Spotify URL from manifest.
    
    - Album mode: use spotify_album field (spotify:album:<id> URI)
    - Playlist mode: use playlist_id field (bare id string)
    Returns None if no valid link found.
    """
    if not spotify_manifest:
        return None
    
    if is_album_mode(spotify_manifest):
        # Album mode: spotify_album is a URI like "spotify:album:6V2grIdTNAYNMe8UnG3lmp"
        spotify_uri = spotify_manifest.get("spotify_album")
        if spotify_uri and isinstance(spotify_uri, str) and spotify_uri.startswith("spotify:album:"):
            album_id = spotify_uri.replace("spotify:album:", "")
            return f"https://open.spotify.com/album/{album_id}"
        return None
    else:
        # Playlist mode: playlist_id is a bare id string
        playlist_id = spotify_manifest.get("playlist_id")
        if playlist_id and isinstance(playlist_id, str):
            return f"https://open.spotify.com/playlist/{playlist_id}"
        return None


def has_spotify_link(spotify_manifest: dict[str, Any]) -> bool:
    """Check if manifest has a valid Spotify link."""
    return build_spotify_url(spotify_manifest) is not None


def generate_songbook_content(
    slug: str,
    meta: dict[str, Any],
    tracks: list[dict[str, str]],
    song_count: int,
    chart_only: bool,
    thumb_exists: bool,
    pdf_exists: bool,
    version: str,
    lang: str,
    read_url: str | None = None,
) -> str:
    """Generate Hugo markdown content for one songbook in one language."""
    localized = localize(meta, lang)
    
    # Build front matter
    front_matter: dict[str, Any] = {
        "title": localized.get("title") or slug.replace("-", " ").title(),
        "slug": slug,
        "language": language_of(meta),
    }
    
    # Optional fields
    if localized.get("artist"):
        front_matter["artist"] = localized["artist"]
    
    if localized.get("blurb"):
        front_matter["blurb"] = localized["blurb"]
    
    # Accent color from cover.subtitle_color
    if meta.get("cover", {}).get("subtitle_color"):
        front_matter["accent"] = meta["cover"]["subtitle_color"]
    
    # Thumbnail
    if thumb_exists:
        front_matter["thumb"] = f"thumbs/{slug}.png"
    
    # PDF
    if pdf_exists:
        front_matter["pdf"] = f"pdf/{slug}.pdf"
    
    # Online read view — points at the first song, and gates the View button
    if read_url:
        front_matter["read"] = read_url
    
    # Song count and chart-only flag
    front_matter["songCount"] = song_count
    if chart_only:
        front_matter["chartOnly"] = True
    
    # Spotify link
    spotify_manifest = load_spotify_manifest(slug)
    spotify_url = build_spotify_url(spotify_manifest)
    if spotify_url:
        front_matter["spotify"] = spotify_url
    
    # Links from intro.links
    if localized.get("intro", {}).get("links"):
        links = []
        for link in localized["intro"]["links"]:
            if link.get("label") and link.get("url"):
                links.append({"label": link["label"], "url": link["url"]})
        if links:
            front_matter["links"] = links
    
    # Tracks
    if not chart_only:
        front_matter["tracks"] = tracks
    
    # Version
    front_matter["version"] = version
    
    # Dump front matter
    fm_yaml = yaml.safe_dump(
        front_matter,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    
    # Body: description
    body = ""
    if localized.get("description"):
        desc = localized["description"]
        if isinstance(desc, str):
            body = desc
        elif isinstance(desc, list):
            body = "\n\n".join(str(d) for d in desc if d)
    
    return f"---\n{fm_yaml}---\n{body}\n"


def generate_song_content(
    slug: str,
    book_title: str,
    accent: str | None,
    track: dict[str, str],
    index: int,
    tracks: list[dict[str, str]],
    lang: str,
) -> str:
    """Generate the Hugo page for a single song's chords-and-lyrics view.

    Song pages live in their own `songpages` section so the songbook keeps its
    regular-page kind (the home, section and song-index layouts all select on
    `where .Site.RegularPages "Section" "songbooks"`). An explicit `url` then
    places them under the songbook path, which Hugo could not do structurally
    without turning each songbook into a section.

    Prev/next and the full sibling list are resolved here rather than in the
    template, because Hugo cannot order these pages by track number once the
    numeric filename prefix has been dropped from the URL.
    """
    siblings = [
        {"title": t["title"], "url": f"songbooks/{slug}/{t['slug']}/"}
        for t in tracks
    ]

    front_matter: dict[str, Any] = {
        "title": track["title"],
        "url": f"songbooks/{slug}/{track['slug']}/",
        "layout": "song",
        "songbook": slug,
        "songbookTitle": book_title,
        "songbookUrl": f"songbooks/{slug}/",
        "songSlug": track["slug"],
        "sourcePath": f"songbooks/{slug}/{track['source']}.cho",
        "weight": index + 1,
        "trackNumber": index + 1,
        "trackTotal": len(tracks),
        "songs": siblings,
        # Kept out of every listing: these pages are reached from the songbook
        # or by prev/next, never from a collection.
        "build": {"list": "never"},
    }

    if track.get("artist"):
        front_matter["artist"] = track["artist"]
    if accent:
        front_matter["accent"] = accent
    if index > 0:
        front_matter["prev"] = siblings[index - 1]
    if index + 1 < len(tracks):
        front_matter["next"] = siblings[index + 1]

    fm_yaml = yaml.safe_dump(
        front_matter,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )

    return f"---\n{fm_yaml}---\n"


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate Hugo content and assets from songbooks"
    )
    parser.add_argument(
        "--version",
        default="dev",
        help="Version tag (default: dev)",
    )
    parser.add_argument(
        "--pdf-dir",
        default="pdf",
        help="PDF directory (default: pdf)",
    )
    parser.add_argument(
        "--site-dir",
        default="site",
        help="Site directory (default: site)",
    )
    parser.add_argument(
        "--html-dir",
        default="html",
        help="ChordPro HTML render directory (default: html)",
    )
    args = parser.parse_args()
    
    pdf_dir = REPO_ROOT / args.pdf_dir
    site_dir = REPO_ROOT / args.site_dir
    html_dir = REPO_ROOT / args.html_dir
    
    # Recreate generated directories
    content_dir = site_dir / "content" / "songbooks"
    songpages_dir = site_dir / "content" / "songpages"
    static_pdf_dir = site_dir / "static" / "pdf"
    static_thumbs_dir = site_dir / "static" / "thumbs"
    assets_songs_dir = site_dir / "assets" / "songs"
    
    for d in [content_dir, songpages_dir, static_pdf_dir, static_thumbs_dir,
              assets_songs_dir]:
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)
    
    # Clean up old song index files
    site_content_dir = site_dir / "content"
    for lang in LOCALES:
        old_index = site_content_dir / f"songs.{lang}.md"
        if old_index.exists():
            old_index.unlink()
    
    # Create _index files for the section
    for lang in LOCALES:
        index_path = site_dir / "content" / "songbooks" / f"_index.{lang}.md"
        index_path.write_text(f"---\ntitle: Songbooks\n---\n", encoding="utf-8")
    
    # Scan songbooks
    errors = False
    total_songs = 0
    total_songbooks = 0
    
    for songbook_dir in sorted(SONGBOOKS_DIR.iterdir()):
        if not songbook_dir.is_dir():
            continue
        
        slug = songbook_dir.name
        
        # Load metadata
        meta = load_metadata(songbook_dir)
        if not meta:
            # No songbook.yaml — skip
            continue
        
        # Check for .cho files
        cho_files = list(songbook_dir.glob("*.cho"))
        if not cho_files:
            print(f"warning: {slug}: no .cho files — skipping", file=sys.stderr)
            continue
        
        # Check for PDF
        pdf_path = pdf_dir / f"{slug}.pdf"
        if not pdf_path.exists():
            print(
                f"warning: {slug}: pdf/{slug}.pdf not found — skipping",
                file=sys.stderr,
            )
            continue
        
        # Extract thumbnail
        thumb_path = static_thumbs_dir / f"{slug}.png"
        thumb_ok = extract_thumbnail(pdf_path, thumb_path)
        
        # Copy PDF
        shutil.copy2(pdf_path, static_pdf_dir / f"{slug}.pdf")
        
        # Parse tracklist
        tracks, song_count, chart_only = parse_tracklist(slug)
        
        # Lift each rendered song into an embeddable fragment. A song without
        # a render is dropped from the read view rather than published broken.
        readable: list[dict[str, str]] = []
        for track in tracks:
            fragment = extract_song_fragment(
                html_dir / slug / f"{track['source']}.html"
            )
            if not fragment:
                print(
                    f"warning: {slug}/{track['source']}: no HTML render — "
                    "excluded from the read view",
                    file=sys.stderr,
                )
                continue
            (assets_songs_dir / f"{slug}--{track['slug']}.html").write_text(
                fragment, encoding="utf-8"
            )
            readable.append(track)
        
        book_title = localize(meta, LOCALES[0]).get("title") or slug
        accent = meta.get("cover", {}).get("subtitle_color")
        read_url = (
            f"songbooks/{slug}/{readable[0]['slug']}/" if readable else None
        )
        
        # Generate content for each language
        for lang in LOCALES:
            content = generate_songbook_content(
                slug=slug,
                meta=meta,
                tracks=tracks,
                song_count=song_count,
                chart_only=chart_only,
                thumb_exists=thumb_ok,
                pdf_exists=True,
                version=args.version,
                lang=lang,
                read_url=read_url,
            )
            
            output_path = content_dir / f"{slug}.{lang}.md"
            output_path.write_text(content, encoding="utf-8")
            
            localized_title = localize(meta, lang).get("title") or book_title
            for index, track in enumerate(readable):
                song_page = generate_song_content(
                    slug=slug,
                    book_title=localized_title,
                    accent=accent,
                    track=track,
                    index=index,
                    tracks=readable,
                    lang=lang,
                )
                song_dir = songpages_dir / slug
                song_dir.mkdir(parents=True, exist_ok=True)
                (song_dir / f"{track['slug']}.{lang}.md").write_text(
                    song_page, encoding="utf-8"
                )
        
        # Track counts
        total_songs += song_count
        total_songbooks += 1
        
        # Status line
        thumb_status = "thumb ok" if thumb_ok else "thumb skip"
        read_status = f"read {len(readable)}" if readable else "read none"
        spotify_manifest = load_spotify_manifest(slug)
        spotify_status = "spotify yes" if has_spotify_link(spotify_manifest) else "spotify no"
        print(
            f"{slug}: {song_count} songs, {thumb_status}, {read_status}, "
            f"{spotify_status}"
        )
    
    # Generate song index pages for each locale
    for lang in LOCALES:
        song_index_front_matter: dict[str, Any] = {
            "title": "",
            "layout": "songs",
            "version": args.version,
        }
        
        fm_yaml = yaml.safe_dump(
            song_index_front_matter,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )
        
        song_index_content = f"---\n{fm_yaml}---\n"
        
        song_index_path = site_content_dir / f"songs.{lang}.md"
        song_index_path.write_text(song_index_content, encoding="utf-8")
    
    # Status line for song index
    locales_str = ", ".join(LOCALES)
    print(f"song index: {total_songs} songs across {total_songbooks} songbooks ({locales_str})")
    
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
