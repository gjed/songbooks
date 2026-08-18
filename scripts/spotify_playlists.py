"""Curate and sync one Spotify playlist per songbook.

Two phases, split by the committed manifest `spotify-playlists.yaml`:

  resolve   Local, interactive, human-curated. Searches Spotify, shows the
            candidates, and a human decides which recording is correct. The
            pick is pinned into the manifest.
  sync      CI, unattended. Reads the pinned track URIs and pushes them to
            Spotify. Performs no searching and no matching whatsoever.

The split is deliberate: fuzzy search must never run unattended, and CI must
never guess which recording is correct.

Each songbook is curated in one of two modes:

  mode: playlist (default)  One curated playlist per songbook, built song by
                            song. Used when a songbook mixes several artists
                            or several real albums (hsb-eng, good-songs,
                            diplomatico-e-collettivo, ...).
  mode: album               The songbook IS one official Spotify album (every
                            song shares one artist and one album). No
                            playlist is created — `resolve` just links the
                            album once, and `sync` has nothing to push for it.
                            Set by hand in the manifest (see its header).

  validate  Pure filesystem + YAML check. No network, no credentials. Runs on
            every pull request, so a contributor adding a song is told
            immediately that curation is pending.
  links     Pure manifest read. Prints a markdown list of every resolved
            Spotify link (playlist or album), for release notes.
  auth      One-time interactive login that prints the refresh token to paste
            into the CI secret.

Usage:
  python3 scripts/spotify_playlists.py validate
  python3 scripts/spotify_playlists.py resolve [--songbook SLUG]
                                               [--write-ids] [--recheck]
  python3 scripts/spotify_playlists.py sync [--songbook SLUG] [--apply]
  python3 scripts/spotify_playlists.py links [--songbook SLUG]
  python3 scripts/spotify_playlists.py auth

Credentials:
  resolve / auth  SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET,
                  SPOTIPY_REDIRECT_URI  (interactive browser login)
  sync            SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET,
                  SPOTIFY_REFRESH_TOKEN (headless, no browser, no cache)
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - dependency guard
    sys.exit(
        "error: PyYAML is required.\n"
        "  fix: pip install PyYAML   (or: pip install -r requirements.txt)"
    )


REPO_ROOT = Path(__file__).resolve().parent.parent
SONGBOOKS_DIR = REPO_ROOT / "songbooks"
MANIFEST_PATH = REPO_ROOT / "spotify-playlists.yaml"
TOKEN_CACHE = REPO_ROOT / ".spotify-token-cache.json"
README_PATH = REPO_ROOT / "README.md"

REPO_URL = "https://github.com/gjed/songbooks"
SCHEMA_VERSION = 1

# Cover / chord-chart / back-cover pages are ChordPro files but not songs.
PSEUDO_SONGS = {"00-cover.cho", "01-chord-chart.cho", "99-back-cover.cho"}

API_BASE = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPES = "playlist-modify-public playlist-modify-private"

SEARCH_LIMIT = 10  # Spotify caps /search at 10 results per request.
BATCH_SIZE = 100  # Spotify caps playlist item writes at 100 URIs.
HTTP_RETRIES = 5


# --------------------------------------------------------------------------
# Songbook scanning
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Song:
    """One real song, parsed from a ChordPro file."""

    stem: str  # filename without .cho, e.g. "01-portami-a-ballare"
    title: str
    artist: str
    album: str
    path: Path


@dataclass
class Songbook:
    """One songbook folder and the real songs inside it, in file order."""

    slug: str
    display_name: str
    songs: list[Song] = field(default_factory=list)


HEADER_RE = re.compile(r"^\{(?P<key>[a-z_]+):\s*(?P<value>.*?)\s*\}\s*$")
README_ROW_RE = re.compile(r"\[([^\]]+)\]\(songbooks/([^/)]+)/?\)")


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


def read_display_names() -> dict[str, str]:
    """Map songbook slug to display name using the README table."""
    names: dict[str, str] = {}
    if not README_PATH.exists():
        return names
    for label, slug in README_ROW_RE.findall(
        README_PATH.read_text(encoding="utf-8")
    ):
        names.setdefault(slug, label.strip())
    return names


def scan_songbooks(only: str | None = None) -> list[Songbook]:
    """Scan songbooks/ and return the real songs of each, in file order.

    Cover, chord-chart, and back-cover pseudo-songs are skipped: they match a
    reserved filename *and* carry an empty {artist:}. Any other file missing a
    title or artist cannot be matched against Spotify, so it is skipped with a
    warning rather than silently pinned as unresolvable.
    """
    display_names = read_display_names()
    books: list[Songbook] = []

    for folder in sorted(p for p in SONGBOOKS_DIR.iterdir() if p.is_dir()):
        slug = folder.name
        if only and slug != only:
            continue
        book = Songbook(slug=slug, display_name=display_names.get(slug, slug))
        for cho in sorted(folder.glob("*.cho")):
            headers = parse_headers(cho)
            title = headers.get("title", "").strip()
            artist = headers.get("artist", "").strip()
            if cho.name in PSEUDO_SONGS and not artist:
                continue
            if not title or not artist:
                print(
                    f"warning: {cho.relative_to(REPO_ROOT)} has no "
                    f"{'title' if not title else 'artist'} — skipping",
                    file=sys.stderr,
                )
                continue
            book.songs.append(
                Song(
                    stem=cho.stem,
                    title=title,
                    artist=artist,
                    album=headers.get("album", "").strip(),
                    path=cho,
                )
            )
        books.append(book)

    if only and not books:
        raise SystemExit(f"error: no such songbook: songbooks/{only}")
    return books


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------


class ManifestError(RuntimeError):
    """The manifest is missing or structurally wrong."""


def load_manifest() -> dict[str, Any]:
    """Load the manifest, or return an empty skeleton if absent."""
    if not MANIFEST_PATH.exists():
        return {"$schema_version": SCHEMA_VERSION, "songbooks": {}}
    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if data is None:
        return {"$schema_version": SCHEMA_VERSION, "songbooks": {}}
    if not isinstance(data, dict):
        raise ManifestError(
            f"{MANIFEST_PATH.name}: expected a mapping at the top level"
        )
    version = data.get("$schema_version")
    if version != SCHEMA_VERSION:
        raise ManifestError(
            f"{MANIFEST_PATH.name}: $schema_version is {version!r}, "
            f"this tool speaks {SCHEMA_VERSION}"
        )
    if not isinstance(data.get("songbooks"), dict):
        raise ManifestError(
            f"{MANIFEST_PATH.name}: 'songbooks' must be a mapping of "
            f"slug -> playlist entry"
        )
    return data


class _Dumper(yaml.SafeDumper):
    """SafeDumper that indents nested blocks so diffs stay readable."""

    def increase_indent(self, flow: bool = False, indentless: bool = False):
        return super().increase_indent(flow, False)


def save_manifest(data: dict[str, Any]) -> None:
    """Write the manifest atomically, preserving key order.

    Written via temp file + os.replace so a Ctrl-C mid-write can never leave a
    truncated manifest behind.
    """
    body = yaml.dump(
        data,
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        indent=2,
        width=100,
    )
    header = (
        "# Spotify playlist manifest — the contract between the two phases.\n"
        "#\n"
        "# `resolve` (local, interactive) pins a track/album URI for every\n"
        "# songbook. `sync` (CI, unattended) pushes those URIs and nothing else.\n"
        "#\n"
        "# Each songbook has a `mode`, set by hand:\n"
        "#   mode: playlist (default)  curate one track at a time -> a playlist\n"
        "#                             this repo owns and pushes to.\n"
        "#   mode: album               the songbook IS one official Spotify\n"
        "#                             album (one artist, one release). No\n"
        "#                             playlist is created; `resolve` just links\n"
        "#                             the album once. Flip a songbook to this\n"
        "#                             mode by hand when it stops being a\n"
        "#                             multi-artist compilation.\n"
        "#\n"
        "# String values (tracks, spotify_album, playlist_id) are one of three\n"
        "# states:\n"
        '#   ""                       not yet resolved — a search candidate\n'
        "#   spotify:track:<id> / spotify:album:<id>   pinned\n"
        "#   null                     deliberately not on Spotify — stop asking\n"
        "#\n"
        "# Track keys are .cho filename stems, in file order.\n"
        "# Regenerate entries with: make spotify-resolve\n"
    )
    fd, tmp_name = tempfile.mkstemp(
        dir=str(MANIFEST_PATH.parent), prefix=".spotify-playlists.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(header)
            handle.write(body)
        os.replace(tmp_name, MANIFEST_PATH)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def is_album_mode(entry: dict[str, Any]) -> bool:
    """True when a songbook is linked to one Spotify album instead of curated
    track by track. Set by hand in the manifest — see its header comment."""
    return str(entry.get("mode", "playlist")) == "album"


def entry_for(manifest: dict[str, Any], book: Songbook) -> dict[str, Any]:
    """Return (creating if needed) the manifest entry for a songbook.

    New entries default to `mode: playlist`. A human flips a songbook to
    `mode: album` by hand once it's confirmed to be one artist / one release
    (see the manifest header); this function then leaves that choice alone
    and only fills in the fields that mode actually uses.
    """
    books = manifest.setdefault("songbooks", {})
    entry: dict[str, Any] | None = books.get(book.slug)
    if entry is None:
        entry = {"mode": "playlist", "playlist_name": book.display_name}
        books[book.slug] = entry
    entry.setdefault("mode", "playlist")

    if is_album_mode(entry):
        entry.setdefault("spotify_album", "")
        # Flipping a book to album mode retires its per-track curation.
        entry.pop("tracks", None)
        entry.pop("playlist_id", None)
    else:
        entry.setdefault("playlist_name", book.display_name)
        entry.setdefault("playlist_id", None)
        if not isinstance(entry.get("tracks"), dict):
            entry["tracks"] = {}
    return entry


def reconcile(
    manifest: dict[str, Any], books: Sequence[Songbook]
) -> tuple[list[str], list[str]]:
    """Align manifest entries with the files on disk.

    For `mode: playlist` songbooks, adds missing songs as unresolved, prunes
    tracks whose .cho file is gone, and reorders keys to match file order.
    `mode: album` songbooks have no per-song tracks to reconcile — the album
    link is a single field, curated once. Returns (added, pruned) as
    "slug/stem" labels so the human sees exactly what moved.
    """
    added: list[str] = []
    pruned: list[str] = []

    for book in books:
        if not book.songs:
            # An empty songbook gets no playlist at all — drop any stale entry.
            if book.slug in manifest.get("songbooks", {}):
                pruned.append(f"{book.slug}/ (songbook has no songs)")
                del manifest["songbooks"][book.slug]
            continue

        entry = entry_for(manifest, book)
        if is_album_mode(entry):
            continue  # one album link, not per-song tracks

        tracks: dict[str, Any] = entry["tracks"]
        stems = [song.stem for song in book.songs]

        for stem in stems:
            if stem not in tracks:
                tracks[stem] = ""  # not yet resolved — distinct from null
                added.append(f"{book.slug}/{stem}")

        for stem in list(tracks):
            if stem not in stems:
                pruned.append(f"{book.slug}/{stem}")
                del tracks[stem]

        # Rewrite in file order so the manifest always mirrors the printed book.
        entry["tracks"] = {stem: tracks[stem] for stem in stems}

    return added, pruned


# --------------------------------------------------------------------------
# Normalisation and matching
# --------------------------------------------------------------------------


PARENTHETICAL_RE = re.compile(r"[(\[][^)\]]*[)\]]")
PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
SPACE_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Fold case, accents, punctuation, and parentheticals for comparison."""
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = folded.casefold()
    folded = PARENTHETICAL_RE.sub(" ", folded)
    folded = PUNCT_RE.sub(" ", folded)
    return SPACE_RE.sub(" ", folded).strip()


def is_exact(song: Song, track: dict[str, Any]) -> bool:
    """True when title and any artist match after normalisation."""
    if normalize(track.get("name", "")) != normalize(song.title):
        return False
    wanted = normalize(song.artist)
    return any(
        normalize(artist.get("name", "")) == wanted
        for artist in track.get("artists", [])
    )


def track_label(track: dict[str, Any]) -> str:
    """One-line human description of a search hit."""
    artists = ", ".join(a.get("name", "?") for a in track.get("artists", []))
    album = track.get("album", {}) or {}
    year = str(album.get("release_date", ""))[:4]
    name = album.get("name", "")
    where = f"{name} · {year}" if year else name
    return f"{track.get('name', '?')} — {artists}  [{where}]"


def album_label(album: dict[str, Any]) -> str:
    """One-line human description of an album search hit."""
    artists = ", ".join(a.get("name", "?") for a in album.get("artists", []))
    year = str(album.get("release_date", ""))[:4]
    count = album.get("total_tracks")
    detail = " · ".join(
        part
        for part in (year, f"{count} tracks" if count else "")
        if part
    )
    return f"{album.get('name', '?')} — {artists}" + (f"  [{detail}]" if detail else "")


# --------------------------------------------------------------------------
# Spotify HTTP client
# --------------------------------------------------------------------------


class SpotifyError(RuntimeError):
    """An API call failed in a way the caller cannot paper over."""


class AuthError(SpotifyError):
    """Credentials are missing, malformed, or no longer accepted."""


class Spotify:
    """Minimal Spotify Web API client over the stdlib.

    Deliberately not spotipy: this pins the endpoint paths (playlist items live
    at /items), the /search limit cap, and Retry-After handling in this repo
    rather than in a dependency. spotipy is used only for the interactive
    browser login, where it earns its keep.
    """

    def __init__(self, access_token: str) -> None:
        self._token = access_token

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = path if path.startswith("http") else f"{API_BASE}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        payload = json.dumps(body).encode("utf-8") if body is not None else None

        for attempt in range(HTTP_RETRIES):
            request = urllib.request.Request(url, data=payload, method=method)
            request.add_header("Authorization", f"Bearer {self._token}")
            request.add_header("Accept", "application/json")
            if payload is not None:
                request.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    raw = response.read()
                return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as exc:
                detail = _http_detail(exc)
                if exc.code == 429:
                    delay = _retry_after(exc, attempt)
                    print(
                        f"  rate limited, waiting {delay:.0f}s "
                        f"(attempt {attempt + 1}/{HTTP_RETRIES})",
                        file=sys.stderr,
                    )
                    time.sleep(delay)
                    continue
                if exc.code == 401:
                    raise AuthError(
                        "Spotify rejected the access token (401).\n"
                        "  If this is CI: the SPOTIFY_REFRESH_TOKEN secret is "
                        "no longer valid.\n"
                        "  fix: run `python3 scripts/spotify_playlists.py auth` "
                        "locally and update the secret."
                    ) from exc
                if exc.code >= 500 and attempt < HTTP_RETRIES - 1:
                    time.sleep(2**attempt)
                    continue
                raise SpotifyError(
                    f"{method} {url} failed: HTTP {exc.code} {detail}"
                ) from exc
            except urllib.error.URLError as exc:
                if attempt < HTTP_RETRIES - 1:
                    time.sleep(2**attempt)
                    continue
                raise SpotifyError(f"{method} {url} failed: {exc.reason}") from exc

        raise SpotifyError(f"{method} {url} failed after {HTTP_RETRIES} attempts")

    # -- convenience wrappers ---------------------------------------------

    def me(self) -> dict[str, Any]:
        return self.request("GET", "/me")

    def search_track(self, song: Song) -> list[dict[str, Any]]:
        query = f'track:"{song.title}" artist:"{song.artist}"'
        found = self.request(
            "GET",
            "/search",
            params={"q": query, "type": "track", "limit": SEARCH_LIMIT},
        )
        items = (found.get("tracks") or {}).get("items") or []
        if items:
            return items
        # Filtered search is strict; fall back to a plain phrase search before
        # telling a human there is nothing to pick from.
        found = self.request(
            "GET",
            "/search",
            params={
                "q": f"{song.title} {song.artist}",
                "type": "track",
                "limit": SEARCH_LIMIT,
            },
        )
        return (found.get("tracks") or {}).get("items") or []

    def search_album(self, artist: str, album: str) -> list[dict[str, Any]]:
        query = f'album:"{album}" artist:"{artist}"'
        found = self.request(
            "GET",
            "/search",
            params={"q": query, "type": "album", "limit": SEARCH_LIMIT},
        )
        items = (found.get("albums") or {}).get("items") or []
        if items:
            return items
        found = self.request(
            "GET",
            "/search",
            params={"q": f"{album} {artist}", "type": "album", "limit": SEARCH_LIMIT},
        )
        return (found.get("albums") or {}).get("items") or []

    def my_playlists(self) -> Iterable[dict[str, Any]]:
        path: str | None = "/me/playlists"
        params: dict[str, Any] | None = {"limit": 50}
        while path:
            page = self.request("GET", path, params=params)
            for item in page.get("items") or []:
                if item:
                    yield item
            path = page.get("next")
            params = None

    def create_playlist(self, user_id: str, name: str, description: str) -> str:
        created = self.request(
            "POST",
            f"/users/{urllib.parse.quote(user_id)}/playlists",
            body={"name": name, "public": True, "description": description},
        )
        playlist_id = created.get("id")
        if not playlist_id:
            raise SpotifyError(f"Spotify did not return an id for playlist {name!r}")
        return str(playlist_id)

    def playlist(self, playlist_id: str) -> dict[str, Any]:
        return self.request(
            "GET",
            f"/playlists/{playlist_id}",
            params={"fields": "name,description"},
        )

    def playlist_uris(self, playlist_id: str) -> list[str]:
        """Current track URIs of a playlist, in order."""
        uris: list[str] = []
        path: str | None = f"/playlists/{playlist_id}/items"
        params: dict[str, Any] | None = {
            "limit": 100,
            "fields": "next,items(track(uri))",
        }
        while path:
            page = self.request("GET", path, params=params)
            for item in page.get("items") or []:
                track = (item or {}).get("track") or {}
                if track.get("uri"):
                    uris.append(str(track["uri"]))
            path = page.get("next")
            params = None
        return uris

    def replace_items(self, playlist_id: str, uris: Sequence[str]) -> None:
        """Replace the whole playlist with `uris`, in order.

        A full replace makes removals and reordering free. Spotify accepts at
        most 100 URIs per call, so the first 100 replace and the rest append.
        """
        head, tail = list(uris[:BATCH_SIZE]), list(uris[BATCH_SIZE:])
        self.request(
            "PUT", f"/playlists/{playlist_id}/items", body={"uris": head}
        )
        for start in range(0, len(tail), BATCH_SIZE):
            self.request(
                "POST",
                f"/playlists/{playlist_id}/items",
                body={"uris": tail[start : start + BATCH_SIZE]},
            )

    def set_details(self, playlist_id: str, name: str, description: str) -> None:
        self.request(
            "PUT",
            f"/playlists/{playlist_id}",
            body={"name": name, "description": description},
        )


def _http_detail(exc: urllib.error.HTTPError) -> str:
    try:
        payload = json.loads(exc.read() or b"{}")
    except (ValueError, OSError):
        return exc.reason or ""
    error = payload.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or exc.reason or "")
    return str(error or exc.reason or "")


def _retry_after(exc: urllib.error.HTTPError, attempt: int) -> float:
    """Honour Retry-After, falling back to exponential backoff."""
    raw = exc.headers.get("Retry-After") if exc.headers else None
    try:
        return float(raw) + 1.0 if raw is not None else float(2**attempt)
    except (TypeError, ValueError):
        return float(2**attempt)


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------


def _require_env(*names: str) -> list[str]:
    missing = [name for name in names if not os.environ.get(name)]
    return missing


def interactive_token() -> str:
    """Access token via the interactive Authorization Code flow (spotipy)."""
    try:
        from spotipy.oauth2 import SpotifyOAuth  # noqa: PLC0415 - optional dep
    except ModuleNotFoundError as exc:
        raise AuthError(
            "spotipy is required for interactive login.\n"
            "  fix: pip install spotipy   (or: pip install -r requirements.txt)"
        ) from exc

    missing = _require_env("SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET")
    if missing:
        raise AuthError(
            "missing Spotify credentials: " + ", ".join(missing) + "\n"
            "  Create an app at https://developer.spotify.com/dashboard, then:\n"
            "    export SPOTIPY_CLIENT_ID=...\n"
            "    export SPOTIPY_CLIENT_SECRET=...\n"
            "    export SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback\n"
            "  (the redirect URI must match the one registered in the app)"
        )
    os.environ.setdefault(
        "SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback"
    )
    auth = SpotifyOAuth(
        scope=SCOPES,
        cache_path=str(TOKEN_CACHE),
        open_browser=True,
    )
    token = auth.get_access_token(as_dict=True)
    if not token or not token.get("access_token"):
        raise AuthError("interactive login did not return an access token")
    return str(token["access_token"])


def refresh_token_grant(
    client_id: str, client_secret: str, refresh_token: str
) -> dict[str, Any]:
    """Exchange a refresh token for an access token. No cache, no browser."""
    basic = base64.b64encode(
        f"{client_id}:{client_secret}".encode("utf-8")
    ).decode("ascii")
    data = urllib.parse.urlencode(
        {"grant_type": "refresh_token", "refresh_token": refresh_token}
    ).encode("utf-8")
    request = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    request.add_header("Authorization", f"Basic {basic}")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raise AuthError(
            "Spotify refused the refresh token "
            f"(HTTP {exc.code} {_http_detail(exc)}).\n"
            "  The token has been revoked or the client credentials changed.\n"
            "  fix: run `python3 scripts/spotify_playlists.py auth` locally, "
            "then update the SPOTIFY_REFRESH_TOKEN secret."
        ) from exc
    except urllib.error.URLError as exc:
        raise AuthError(f"could not reach {TOKEN_URL}: {exc.reason}") from exc


def headless_token() -> str:
    """Access token for unattended runs (CI)."""
    missing = _require_env(
        "SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REFRESH_TOKEN"
    )
    if missing:
        raise AuthError(
            "missing Spotify credentials for unattended sync: "
            + ", ".join(missing)
            + "\n"
            "  In CI these come from repository secrets.\n"
            "  Locally, either export them or run "
            "`python3 scripts/spotify_playlists.py auth` first "
            "(that caches an interactive login this command can reuse)."
        )
    payload = refresh_token_grant(
        os.environ["SPOTIFY_CLIENT_ID"],
        os.environ["SPOTIFY_CLIENT_SECRET"],
        os.environ["SPOTIFY_REFRESH_TOKEN"],
    )
    access = payload.get("access_token")
    if not access:
        raise AuthError("refresh grant returned no access_token")
    if payload.get("refresh_token"):
        # Spotify normally keeps the same refresh token; when it does rotate,
        # the old one stops working and the secret must be updated.
        print(
            "::warning::Spotify returned a rotated refresh token. Update the "
            "SPOTIFY_REFRESH_TOKEN secret or the next sync will fail auth.",
            file=sys.stderr,
        )
    return str(access)


def cached_token() -> str | None:
    """Reuse a local interactive login, if one is cached and refreshable."""
    if not TOKEN_CACHE.exists():
        return None
    try:
        cached = json.loads(TOKEN_CACHE.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    client_id = os.environ.get("SPOTIPY_CLIENT_ID") or os.environ.get(
        "SPOTIFY_CLIENT_ID"
    )
    client_secret = os.environ.get("SPOTIPY_CLIENT_SECRET") or os.environ.get(
        "SPOTIFY_CLIENT_SECRET"
    )
    token = cached.get("refresh_token")
    if not (client_id and client_secret and token):
        return None
    payload = refresh_token_grant(client_id, client_secret, token)
    access = payload.get("access_token")
    return str(access) if access else None


# --------------------------------------------------------------------------
# validate
# --------------------------------------------------------------------------


def cmd_validate(args: argparse.Namespace) -> int:
    """Structural manifest check. No network, no credentials.

    Curation coverage is NOT enforced: songs may stay unresolved forever
    (there is no guarantee a song exists on Spotify at all), songbooks may
    lack a playlist, and none of that fails validation. Only a *malformed*
    manifest — unparseable YAML, wrong shapes, bad URIs — is an error.
    Coverage gaps are reported as information so curation stays visible.
    """
    books = scan_songbooks(args.songbook)
    if not MANIFEST_PATH.exists():
        # No manifest simply means nothing has been curated yet.
        print(f"{MANIFEST_PATH.name} not found — nothing curated yet, OK.")
        return 0

    manifest = load_manifest()
    entries = manifest.get("songbooks", {})

    unresolved: list[str] = []
    missing_entries: list[str] = []
    orphans: list[str] = []
    no_playlist: list[str] = []
    bad_uris: list[str] = []
    malformed: list[str] = []
    expected_slugs: set[str] = set()

    for book in books:
        if not book.songs:
            if book.slug in entries:
                orphans.append(
                    f"{book.slug}: songbook has no songs but has a manifest entry"
                )
            continue
        expected_slugs.add(book.slug)
        entry = entries.get(book.slug)
        if entry is not None and not isinstance(entry, dict):
            malformed.append(f"{book.slug}: manifest entry is not a mapping")
            continue
        if entry is None:
            missing_entries.append(
                f"{book.slug}: no manifest entry ({len(book.songs)} songs)"
            )
            continue

        if is_album_mode(entry):
            # One album link stands in for every song — no per-track curation.
            album_uri = entry.get("spotify_album")
            if album_uri is None:
                # A human can still decide "not on Spotify" for a whole album.
                continue
            if album_uri == "":
                unresolved.append(f"{book.slug} (album)")
                continue
            if not isinstance(album_uri, str) or not album_uri.startswith(
                "spotify:album:"
            ):
                bad_uris.append(f"{book.slug}: {album_uri!r}")
            continue

        tracks = entry.get("tracks")
        if tracks is None:
            tracks = {}
        if not isinstance(tracks, dict):
            malformed.append(f"{book.slug}: 'tracks' is not a mapping")
            continue

        for song in book.songs:
            if song.stem not in tracks:
                missing_entries.append(f"{book.slug}/{song.stem}")
                continue
            uri = tracks[song.stem]
            if uri is None:
                continue  # explicit "not on Spotify" — a resolved state
            if uri == "":
                unresolved.append(f"{book.slug}/{song.stem}")
                continue
            if not isinstance(uri, str) or not uri.startswith("spotify:track:"):
                bad_uris.append(f"{book.slug}/{song.stem}: {uri!r}")

        stems = {song.stem for song in book.songs}
        for stem in tracks:
            if stem not in stems:
                orphans.append(f"{book.slug}/{stem}")

        if not entry.get("playlist_id"):
            no_playlist.append(book.slug)

    for slug, entry in entries.items():
        if args.songbook and slug != args.songbook:
            continue
        if not isinstance(entry, dict):
            malformed.append(f"{slug}: manifest entry is not a mapping")
            continue
        if slug not in expected_slugs and slug not in {b.slug for b in books}:
            orphans.append(f"{slug}: no such songbook on disk")

    # --- fatal: the manifest itself is broken -----------------------------
    broken = False

    if malformed:
        broken = True
        print(
            f"error: {len(malformed)} malformed manifest entr(ies):",
            file=sys.stderr,
        )
        for item in malformed:
            print(f"  - {item}", file=sys.stderr)

    if bad_uris:
        broken = True
        print(
            f"error: {len(bad_uris)} malformed URI(s) "
            f"(expected spotify:track:<id> / spotify:album:<id> or null):",
            file=sys.stderr,
        )
        for item in bad_uris:
            print(f"  - {item}", file=sys.stderr)

    if broken:
        print(
            f"\n  {MANIFEST_PATH.name} is malformed — fix the entries above "
            f"by hand or re-run:  make spotify-resolve",
            file=sys.stderr,
        )
        return 1

    # --- informational: curation coverage is optional, never an error -----
    # A song with no Spotify counterpart may stay unresolved forever, and a
    # songbook without a playlist simply isn't synced.
    if missing_entries:
        print(f"note: {len(missing_entries)} song(s) have no manifest entry yet:")
        for item in missing_entries:
            print(f"  - {item}")

    if orphans:
        print(
            f"note: {len(orphans)} stale manifest entr(ies) point at songs "
            f"that no longer exist (resolve will prune them):"
        )
        for item in orphans:
            print(f"  - {item}")

    if unresolved:
        print(f"note: {len(unresolved)} song(s) not curated yet:")
        for item in unresolved:
            print(f"  - {item}")

    if no_playlist:
        print(
            f"note: {len(no_playlist)} songbook(s) have no playlist_id "
            f"(they are skipped by sync until one is written):"
        )
        for item in no_playlist:
            print(f"  - {item}")

    if missing_entries or orphans or unresolved or no_playlist:
        print(
            "\n  curation is optional — to curate, run:  make spotify-resolve"
            + (f" SB={args.songbook}" if args.songbook else "")
            + f"\n  then commit the updated {MANIFEST_PATH.name}"
        )

    total = sum(len(book.songs) for book in books)
    scoped = {
        slug: entry
        for slug, entry in entries.items()
        if slug in expected_slugs and isinstance(entry, dict)
    }
    pinned = sum(
        1
        for entry in scoped.values()
        if not is_album_mode(entry)
        for uri in (entry.get("tracks") or {}).values()
        if uri
    )
    album_slugs = sum(1 for entry in scoped.values() if is_album_mode(entry))
    playlist_slugs = len(expected_slugs) - album_slugs
    print(
        f"{MANIFEST_PATH.name} is well-formed: {total} songs across "
        f"{playlist_slugs} playlist songbook(s) and {album_slugs} linked "
        f"album(s) — {pinned} tracks pinned."
    )
    return 0


# --------------------------------------------------------------------------
# resolve
# --------------------------------------------------------------------------


PROMPT_HELP = (
    "  [enter] accept default   [1-9] pick   s skip   n not on Spotify   "
    "q save & quit"
)


def prompt_pick(
    song: Song, candidates: Sequence[dict[str, Any]], default: int | None
) -> str | None | object:
    """Ask the human which candidate is right.

    Returns a track URI, None to pin "not on Spotify", SKIP to leave the song
    unresolved, or QUIT to stop the session.
    """
    print(f"\n{song.stem}")
    print(f"  want: {song.title} — {song.artist}" + (f" · {song.album}" if song.album else ""))
    if not candidates:
        print("  no search results")
    for index, track in enumerate(candidates, start=1):
        marker = "*" if default == index else " "
        print(f"  {marker}{index}. {track_label(track)}")
        print(f"      {track.get('uri', '')}")
    print(PROMPT_HELP)

    while True:
        suffix = f" [{default}]" if default else ""
        try:
            answer = input(f"  pick{suffix}> ").strip().lower()
        except EOFError:
            return QUIT
        if not answer:
            if default:
                return str(candidates[default - 1].get("uri"))
            print("  no default — pick a number, or s / n / q")
            continue
        if answer == "q":
            return QUIT
        if answer == "s":
            return SKIP
        if answer == "n":
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(candidates):
            return str(candidates[int(answer) - 1].get("uri"))
        print("  not a valid choice")


SKIP = object()
QUIT = object()


def cmd_resolve(args: argparse.Namespace) -> int:
    """Interactive curation: pin a track URI for every unresolved song."""
    books = scan_songbooks(args.songbook)
    manifest = load_manifest()
    added, pruned = reconcile(manifest, books)

    if added:
        print(f"{len(added)} new song(s) added as unresolved:")
        for item in added:
            print(f"  + {item}")
    if pruned:
        print(f"{len(pruned)} stale manifest entr(ies) pruned:")
        for item in pruned:
            print(f"  - {item}")
    if added or pruned:
        save_manifest(manifest)

    def is_unresolved(book: Songbook, song: Song) -> bool:
        # "" means never asked; null means the human already said "not on
        # Spotify" and must not be re-prompted unless --recheck is passed.
        return manifest["songbooks"][book.slug]["tracks"].get(song.stem) == ""

    album_books = [
        book
        for book in books
        if book.songs and is_album_mode(manifest["songbooks"][book.slug])
    ]
    album_todo = [
        book
        for book in album_books
        if args.recheck or manifest["songbooks"][book.slug].get("spotify_album") == ""
    ]

    todo = [
        (book, song)
        for book in books
        if book.songs and book not in album_books
        for song in book.songs
        if args.recheck or is_unresolved(book, song)
    ]

    if not todo and not album_todo and not args.write_ids:
        print("nothing to resolve — every songbook is already pinned.")
        return 0

    token = interactive_token()
    client = Spotify(token)

    quit_early = False

    if album_todo:
        print(f"\n{len(album_todo)} album-linked songbook(s) to curate.")
    for book in album_todo:
        song = book.songs[0]
        try:
            candidates = client.search_album(song.artist, song.album or book.display_name)
        except SpotifyError as exc:
            print(f"  search failed for {book.slug}: {exc}", file=sys.stderr)
            continue
        choice = prompt_pick_album(book, candidates)
        if choice is QUIT:
            print("stopping here — manifest is saved up to this point.")
            quit_early = True
            break
        if choice is SKIP:
            continue
        manifest["songbooks"][book.slug]["spotify_album"] = choice
        save_manifest(manifest)

    if todo:
        print(f"\n{len(todo)} song(s) to curate. Ctrl-C is safe: every pick is "
              f"saved immediately.")
    for book, song in [] if quit_early else todo:
        try:
            candidates = client.search_track(song)
        except SpotifyError as exc:
            print(f"  search failed for {song.stem}: {exc}", file=sys.stderr)
            continue
        default = next(
            (i for i, track in enumerate(candidates, 1) if is_exact(song, track)),
            None,
        )
        try:
            choice = prompt_pick(song, candidates, default)
        except KeyboardInterrupt:
            print("\ninterrupted — manifest is intact.")
            quit_early = True
            break
        if choice is QUIT:
            print("stopping here — manifest is saved up to this point.")
            quit_early = True
            break
        if choice is SKIP:
            continue
        manifest["songbooks"][book.slug]["tracks"][song.stem] = choice
        save_manifest(manifest)  # atomic, after every pick

    if args.write_ids and not quit_early:
        write_playlist_ids(client, manifest, books)

    remaining = sum(
        1
        for book in books
        if book.songs and not is_album_mode(manifest["songbooks"][book.slug])
        for song in book.songs
        if manifest["songbooks"][book.slug]["tracks"].get(song.stem) == ""
    ) + sum(
        1
        for book in album_books
        if manifest["songbooks"][book.slug].get("spotify_album") == ""
    )
    print(
        f"\ndone. {remaining} songbook/song(s) still unresolved."
        if remaining
        else "\ndone. every songbook is pinned."
    )
    print(f"review the diff: git diff {MANIFEST_PATH.name}")
    return 0


def prompt_pick_album(
    book: Songbook, candidates: Sequence[dict[str, Any]]
) -> str | None | object:
    """Ask the human which album is right for an album-linked songbook."""
    print(f"\n{book.slug}  ({len(book.songs)} songs, mode: album)")
    if not candidates:
        print("  no search results")
    for index, album in enumerate(candidates, start=1):
        print(f"  {index}. {album_label(album)}")
        print(f"      {album.get('uri', '')}")
    print(PROMPT_HELP)

    while True:
        try:
            answer = input("  pick> ").strip().lower()
        except EOFError:
            return QUIT
        if not answer:
            print("  pick a number, or s / n / q")
            continue
        if answer == "q":
            return QUIT
        if answer == "s":
            return SKIP
        if answer == "n":
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(candidates):
            return str(candidates[int(answer) - 1].get("uri"))
        print("  not a valid choice")


def write_playlist_ids(
    client: Spotify, manifest: dict[str, Any], books: Sequence[Songbook]
) -> None:
    """Fill in missing playlist_id values, adopting an existing playlist first.

    Matching an existing playlist by exact name before creating one keeps this
    idempotent: re-running never leaves duplicate playlists behind.
    """
    pending = [
        book
        for book in books
        if book.songs
        and not is_album_mode(manifest["songbooks"][book.slug])
        and not manifest["songbooks"][book.slug].get("playlist_id")
    ]
    if not pending:
        return

    user_id = str(client.me().get("id", ""))
    existing = {
        str(playlist.get("name", "")): str(playlist.get("id"))
        for playlist in client.my_playlists()
    }

    for book in pending:
        entry = manifest["songbooks"][book.slug]
        name = str(entry.get("playlist_name") or book.display_name)
        playlist_id = existing.get(name)
        if playlist_id:
            print(f"  adopted existing playlist {name!r} ({playlist_id})")
        else:
            playlist_id = client.create_playlist(
                user_id, name, description_for(len(book.songs))
            )
            print(f"  created playlist {name!r} ({playlist_id})")
        entry["playlist_id"] = playlist_id
        save_manifest(manifest)


# --------------------------------------------------------------------------
# sync
# --------------------------------------------------------------------------


def description_for(count: int) -> str:
    return f"Auto-synced from {REPO_URL} — {count} songs"


def cmd_sync(args: argparse.Namespace) -> int:
    """Push the pinned URIs to Spotify. No searching, no matching.

    Sync is optional and coverage is never enforced: a songbook is synced
    only when it has at least one pinned track. Songbooks with nothing
    curated (or in album mode, where the album already exists on Spotify)
    are skipped without error. A curated songbook missing its playlist_id
    gets the playlist created on the fly (found by exact name first, so
    re-runs don't create duplicates) — committing the id via
    `resolve --write-ids` is still the durable fix.
    """
    books = scan_songbooks(args.songbook)
    manifest = load_manifest()
    entries = manifest.get("songbooks", {})

    # A structurally broken manifest is still a hard stop — pushing from
    # garbage would publish garbage. Coverage gaps are fine.
    structural = argparse.Namespace(songbook=args.songbook)
    if cmd_validate(structural) != 0:
        print(
            f"\nerror: refusing to sync — {MANIFEST_PATH.name} is malformed "
            f"(see above).",
            file=sys.stderr,
        )
        return 1

    plan: list[tuple[str, dict[str, Any], list[str], int]] = []
    for book in books:
        if not book.songs:
            continue
        entry = entries.get(book.slug)
        if not isinstance(entry, dict):
            print(f"{book.slug}: not curated yet — skipping")
            continue
        if is_album_mode(entry):
            # Nothing to push: the album already exists on Spotify as-is.
            print(f"{book.slug}: linked to an existing album — nothing to sync")
            continue
        tracks = entry.get("tracks") or {}
        uris = [tracks[song.stem] for song in book.songs if tracks.get(song.stem)]
        if not uris:
            print(f"{book.slug}: no tracks pinned yet — skipping")
            continue
        plan.append((book.slug, entry, uris, len(book.songs) - len(uris)))

    if not plan:
        print("\nnothing to sync — no songbook has pinned tracks.")
        return 0

    if not args.apply:
        for slug, entry, uris, absent in plan:
            target = (
                f"{entry['playlist_name']!r} ({entry['playlist_id']})"
                if entry.get("playlist_id")
                else f"{entry['playlist_name']!r} (playlist will be created)"
            )
            print(
                f"{slug}: would push {len(uris)} track(s) to {target}"
                + (f", {absent} song(s) unpinned" if absent else "")
            )
        print("\ndry run — nothing was written. Re-run with --apply to push.")
        return 0

    token = os.environ.get("SPOTIFY_REFRESH_TOKEN") and headless_token()
    if not token:
        token = cached_token()
    if not token:
        token = headless_token()  # raises AuthError with the full fix-it text
    client = Spotify(token)

    changed = 0
    by_name: dict[str, str] | None = None  # lazy: only fetched when needed
    for slug, entry, uris, absent in plan:
        name = str(entry["playlist_name"])
        description = description_for(len(uris))

        playlist_id = entry.get("playlist_id")
        if not playlist_id:
            # No committed id. Find the playlist by exact name first so
            # repeated CI runs never create duplicates; create otherwise.
            if by_name is None:
                by_name = {
                    str(p.get("name") or ""): str(p.get("id") or "")
                    for p in client.my_playlists()
                }
            playlist_id = by_name.get(name)
            if playlist_id:
                print(f"{slug}: found existing playlist {name!r} ({playlist_id})")
            else:
                user_id = str(client.me().get("id"))
                playlist_id = client.create_playlist(user_id, name, description)
                by_name[name] = playlist_id
                print(f"{slug}: created playlist {name!r} ({playlist_id})")
            print(
                f"{slug}: note — playlist_id is not in the manifest; run "
                f"'python3 scripts/spotify_playlists.py resolve --write-ids' "
                f"locally and commit it to make this durable."
            )
        playlist_id = str(playlist_id)

        current = client.playlist_uris(playlist_id)
        details = client.playlist(playlist_id)
        same_tracks = current == uris
        same_details = (
            html.unescape(str(details.get("description") or "")) == description
            and str(details.get("name") or "") == name
        )
        if same_tracks and same_details:
            print(f"{slug}: no changes ({len(uris)} tracks)")
            continue

        if not same_tracks:
            client.replace_items(playlist_id, uris)
            print(
                f"{slug}: pushed {len(uris)} track(s) to {name!r}"
                + (f", {absent} not on Spotify" if absent else "")
            )
        if not same_details:
            client.set_details(playlist_id, name, description)
            print(f"{slug}: updated playlist details")
        changed += 1

    print(
        f"\nsynced {changed} playlist(s)."
        if changed
        else "\nno changes — every playlist already matches the manifest."
    )
    return 0


# --------------------------------------------------------------------------
# auth
# --------------------------------------------------------------------------


def cmd_auth(args: argparse.Namespace) -> int:
    """One-time interactive login that prints the CI refresh token."""
    try:
        from spotipy.oauth2 import SpotifyOAuth  # noqa: PLC0415 - optional dep
    except ModuleNotFoundError as exc:
        raise AuthError(
            "spotipy is required for interactive login.\n"
            "  fix: pip install spotipy   (or: pip install -r requirements.txt)"
        ) from exc

    missing = _require_env("SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET")
    if missing:
        raise AuthError("missing Spotify credentials: " + ", ".join(missing))
    os.environ.setdefault(
        "SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback"
    )

    auth = SpotifyOAuth(
        scope=SCOPES, cache_path=str(TOKEN_CACHE), open_browser=True
    )
    token = auth.get_access_token(as_dict=True)
    refresh = (token or {}).get("refresh_token")
    if not refresh:
        raise AuthError("login returned no refresh token")

    print("\n" + "=" * 68)
    print("SPOTIFY_REFRESH_TOKEN (secret — do not paste into a PR or a log):")
    print()
    print(refresh)
    print()
    print("Store it as the SPOTIFY_REFRESH_TOKEN repository secret, together")
    print("with SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:")
    print("  Settings -> Secrets and variables -> Actions -> New secret")
    print()
    print("If the CI sync job ever fails on authentication, the token has been")
    print("revoked: re-run this command and update the secret.")
    print("=" * 68)
    return 0


# --------------------------------------------------------------------------
# links
# --------------------------------------------------------------------------


def _uri_to_url(uri: str) -> str:
    """spotify:playlist:ID / spotify:album:ID -> open.spotify.com URL."""
    parts = uri.split(":")
    if len(parts) == 3 and parts[0] == "spotify":
        return f"https://open.spotify.com/{parts[1]}/{parts[2]}"
    return uri


def render_links(manifest: dict[str, Any], only: str | None = None) -> list[str]:
    """Markdown bullet per songbook that has a resolved Spotify link.

    Playlist-mode books contribute their playlist_id; album-mode books their
    spotify_album. Unresolved ("" / null / absent) books are skipped silently —
    this is a display, not a gate (validate is the gate).
    """
    lines: list[str] = []
    for slug, entry in manifest.get("songbooks", {}).items():
        if only and slug != only:
            continue
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("playlist_name") or slug)
        if is_album_mode(entry):
            uri = entry.get("spotify_album")
            if not uri:
                continue
            lines.append(f"- [{name}]({_uri_to_url(str(uri))}) (album)")
        else:
            playlist_id = entry.get("playlist_id")
            if not playlist_id:
                continue
            url = _uri_to_url(f"spotify:playlist:{playlist_id}")
            lines.append(f"- [{name}]({url})")
    return lines


def cmd_links(args: argparse.Namespace) -> int:
    """Print a markdown list of every resolved playlist / album link.

    Pure manifest read — no network, no secrets. Used by the release workflow
    to append Spotify links to the release notes.
    """
    manifest = load_manifest()
    lines = render_links(manifest, args.songbook)
    if not lines:
        return 0
    print("## Spotify")
    print()
    for line in lines:
        print(line)
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spotify_playlists.py",
        description="Curate and sync one Spotify playlist per songbook.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate",
        help="check the manifest against the songbooks (no network, no secrets)",
    )
    validate.add_argument("--songbook", metavar="SLUG")
    validate.set_defaults(func=cmd_validate)

    resolve = subparsers.add_parser(
        "resolve", help="interactively pin a Spotify track for each song"
    )
    resolve.add_argument("--songbook", metavar="SLUG")
    resolve.add_argument(
        "--recheck",
        action="store_true",
        help="re-prompt songs that are already pinned (to fix a bad pick)",
    )
    resolve.add_argument(
        "--write-ids",
        action="store_true",
        help="create or adopt playlists and record their ids",
    )
    resolve.set_defaults(func=cmd_resolve)

    sync = subparsers.add_parser(
        "sync", help="push the pinned track URIs to Spotify"
    )
    sync.add_argument("--songbook", metavar="SLUG")
    sync.add_argument(
        "--apply", action="store_true", help="actually write (default: dry run)"
    )
    sync.set_defaults(func=cmd_sync)

    auth = subparsers.add_parser(
        "auth", help="one-time interactive login; prints the CI refresh token"
    )
    auth.set_defaults(func=cmd_auth)

    links = subparsers.add_parser(
        "links",
        help="print a markdown list of resolved playlist/album links "
        "(no network, no secrets)",
    )
    links.add_argument("--songbook", metavar="SLUG")
    links.set_defaults(func=cmd_links)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except (AuthError, SpotifyError, ManifestError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
