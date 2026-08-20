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
    - tracks: list of {title, artist} dicts for non-special .cho files
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
            tracks.append({"title": title, "artist": artist})
    
    # Check if all .cho files are special pages
    all_cho_files = list(songbook_dir.glob("*.cho"))
    chart_only = len(all_cho_files) > 0 and len(tracks) == 0
    
    return tracks, len(tracks), chart_only


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
) -> str:
    """Generate Hugo markdown content for one songbook in one language."""
    localized = localize(meta, lang)
    
    # Build front matter
    front_matter: dict[str, Any] = {
        "title": localized.get("title") or slug.replace("-", " ").title(),
        "slug": slug,
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
    args = parser.parse_args()
    
    pdf_dir = REPO_ROOT / args.pdf_dir
    site_dir = REPO_ROOT / args.site_dir
    
    # Recreate generated directories
    content_dir = site_dir / "content" / "songbooks"
    static_pdf_dir = site_dir / "static" / "pdf"
    static_thumbs_dir = site_dir / "static" / "thumbs"
    
    for d in [content_dir, static_pdf_dir, static_thumbs_dir]:
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)
    
    # Create _index files for the section
    for lang in LOCALES:
        index_path = site_dir / "content" / "songbooks" / f"_index.{lang}.md"
        index_path.write_text(f"---\ntitle: Songbooks\n---\n", encoding="utf-8")
    
    # Scan songbooks
    errors = False
    
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
            )
            
            output_path = content_dir / f"{slug}.{lang}.md"
            output_path.write_text(content, encoding="utf-8")
        
        # Status line
        thumb_status = "thumb ok" if thumb_ok else "thumb skip"
        spotify_manifest = load_spotify_manifest(slug)
        spotify_status = "spotify yes" if has_spotify_link(spotify_manifest) else "spotify no"
        print(f"{slug}: {song_count} songs, {thumb_status}, {spotify_status}")
    
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
