#!/usr/bin/env python3
"""Fetch song lyrics (with section headers) from Genius.

usage:
  lyrics.py album Queen-of-saba Medusa                 # list the album's song slugs in order
  lyrics.py fetch -o WORK/lyrics Queen-of-saba principe-regina cagne-vere ...

fetch writes WORK/lyrics/<song-slug>.txt: Genius section headers ("[Strofa 1]",
"[Ritornello]") followed by the lyric lines.
"""
import argparse, html, os, re, sys, urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
# Genius salts lyrics with Cyrillic/Greek lookalike letters; map them back to Latin.
HOMO = str.maketrans("аеорсухіјѕԁһАВЕКМНОРСТХІЈЅοΟαΑ", "aeopcyxijsdhABEKMHOPCTXIJSoOaA")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=30).read().decode()


def album(artist, name):
    page = get(f"https://genius.com/albums/{artist}/{name}")
    urls = re.findall(rf"https://genius.com/{re.escape(artist)}-([a-z0-9-]+)-lyrics", page, flags=re.I)
    return list(dict.fromkeys(urls))


def lyrics(artist, slug):
    page = get(f"https://genius.com/{artist}-{slug}-lyrics")
    chunks = []
    for m in re.finditer(r'<div[^>]*data-lyrics-container="true"[^>]*>', page):
        i = j = m.end(); depth = 1
        while depth:                                  # walk to the matching </div>
            n = re.search(r"<(/?)div\b", page[j:]); j += n.end()
            depth += -1 if n.group(1) else 1
        chunks.append(page[i:j - len("</div")])
    if not chunks:
        sys.exit(f"lyrics: no lyrics container on {artist}-{slug}")
    t = "\n".join(chunks)
    t = re.sub(r'<div[^>]*data-exclude-from-selection="true".*?</div>', "", t, flags=re.S)
    t = re.sub(r"<br\s*/?>", "\n", t); t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t).translate(HOMO)
    t = re.sub(r"^.*?(?=\[)", "", t, count=1, flags=re.S)   # drop "N Contributors ... Lyrics" preamble
    return re.sub(r"\n{3,}", "\n\n", t).strip() + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("album"); s.add_argument("artist"); s.add_argument("name")
    f = sub.add_parser("fetch"); f.add_argument("-o", "--out", required=True)
    f.add_argument("artist"); f.add_argument("slugs", nargs="+")
    a = ap.parse_args()
    if a.cmd == "album":
        print("\n".join(album(a.artist, a.name)))
        return
    os.makedirs(a.out, exist_ok=True)
    for slug in a.slugs:
        t = lyrics(a.artist, slug)
        open(os.path.join(a.out, f"{slug}.txt"), "w").write(t)
        print(f"{slug:36} {len(t.splitlines()):3} lines")


if __name__ == "__main__":
    main()
