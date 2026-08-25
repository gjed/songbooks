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

# Cell text, captured so significant whitespace can be protected (see
# protect_cell_whitespace).
CELL_RE = re.compile(r"(<td[^>]*>)([^<]*)(</td>)", re.IGNORECASE)
# A space run Hugo's HTML minifier would destroy: leading, trailing, or 2+.
FRAGILE_SPACES_RE = re.compile(r"^ +| +$|  +")

# Leading track number on a .cho filename, dropped from the public URL.
TRACK_NUM_RE = re.compile(r"^\d+[-_]")


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


def protect_cell_whitespace(html: str) -> str:
    """Make whitespace inside <td> cells survive Hugo's HTML minifier.

    ChordPro splits a lyric line into adjacent <td> cells at each chord
    boundary, and the space that separates two words often lands at the END of
    a cell ("<td>la punta </td><td>del mio naso</td>"). Hugo's minifier trims
    leading and trailing whitespace inside inline elements, which silently
    glues the words together ("la puntadel"). Chord cells lose their trailing
    space the same way, shifting chords left of their syllable.

    CSS cannot compensate — `white-space: pre` styles whitespace that is still
    in the document, and by then the minifier has removed it. Nor can `&#32;`:
    the minifier decodes numeric entities for ordinary space and trims the
    result. Verified against Hugo 0.165 that only no-break space survives, so
    fragile runs (leading, trailing, or 2+ spaces) become `&#160;`. Single
    interior spaces are left alone — they are never trimmed, and keeping them
    readable matters more.

    No-break space is safe here specifically because the songline table sets
    `white-space: pre` and `width: max-content`, so nothing wraps anyway.
    """
    def fix(match: re.Match[str]) -> str:
        open_tag, text, close_tag = match.group(1), match.group(2), match.group(3)
        if not text or "&#160;" in text:
            return match.group(0)
        protected = FRAGILE_SPACES_RE.sub(
            lambda m: "&#160;" * len(m.group(0)), text
        )
        return f"{open_tag}{protected}{close_tag}"

    return CELL_RE.sub(fix, html)


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
    body = protect_cell_whitespace(body)
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
