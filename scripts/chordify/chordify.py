#!/usr/bin/env python3
"""Search Chordify and pull chord timelines through a headed agent-browser session.

Chordify sits behind a Cloudflare challenge: curl and headless Chrome are
blocked, a headed browser passes. The page's own JSON API is then called with
fetch() from inside the page.

usage:
  chordify.py search "Artist" "Title" ["Title" ...]       # candidates per title
  chordify.py pull -o WORK/chordify slug=youtube:ID[,youtube:ID] ...

pull writes WORK/chordify/<slug>.json: a list of
  {id, title, slug, chordInfo{derivedKey, derivedBpm, ...}, chords}
where `chords` is Chordify's raw timeline, one beat per line:
  "<bar.beat>;<label>;<start s>;<end s>"  (labels like C:maj, A:min, Bb:7, N)
"""
import argparse, json, os, subprocess, sys, time

BASE = "https://chordify.net/"


def browser(*args, timeout=180):
    r = subprocess.run(["agent-browser", *args], capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""


def open_session():
    browser("close")
    browser("--headed", "open", BASE)
    for _ in range(30):                       # wait for the Cloudflare challenge to clear
        if "Just a moment" not in browser("get", "title"):
            return
        time.sleep(2)
    sys.exit("chordify: Cloudflare challenge did not clear in the headed browser")


def evaluate(js):
    raw = browser("eval", js, timeout=300)
    try:
        return json.loads(json.loads(raw))
    except (json.JSONDecodeError, TypeError):
        sys.exit(f"chordify: eval failed: {raw[:300]}")


SEARCH_JS = r"""(async()=>{
const artist=%s, titles=%s;
const norm=s=>s.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"");
const art=norm(artist).replace(/\s+/g,"."), out={};
await Promise.all(titles.map(async t=>{
 const seen={};
 const qs=[artist+" "+t, t+" "+artist, t];
 const js=await Promise.all(qs.map(q=>fetch('/api/v2/search?q='+encodeURIComponent(q)).then(r=>r.json())));
 for(const j of js) for(const s of (j.songs||[])){
  const c=s.chordified||s.unchordified; if(!c) continue;
  const title=c.songInfo.title, hay=(c.slug||'')+' '+norm(title);
  if(!norm(title).includes(norm(t)) || !new RegExp(art).test(hay)) continue;
  seen[c.pseudoId]={chordified:!!s.chordified,title,jams:c.songInfo.jamSessions,
                    summary:(c.chordSummary||[]).join(" "),slug:c.slug||""};
 }
 out[t]=seen;
}));
return JSON.stringify(out);})()"""

PULL_JS = r"""(async()=>{
const M=%s, out={};
await Promise.all(Object.entries(M).flatMap(([k,ids])=>ids.map(async p=>{
 const [meta,ch]=await Promise.all([fetch('/api/v2/songs/'+p).then(r=>r.json()),
                                    fetch('/api/v2/songs/'+p+'/chords').then(r=>r.json())]);
 (out[k]=out[k]||[]).push({id:p,title:meta.songInfo&&meta.songInfo.title,slug:meta.slug,
                          chordInfo:ch.chordInfo,chords:ch.chords});
})));
return JSON.stringify(out);})()"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("artist"); s.add_argument("titles", nargs="+")
    p = sub.add_parser("pull"); p.add_argument("-o", "--out", required=True); p.add_argument("pairs", nargs="+")
    a = ap.parse_args()

    open_session()
    try:
        if a.cmd == "search":
            res = evaluate(SEARCH_JS % (json.dumps(a.artist), json.dumps(a.titles)))
            for t in a.titles:
                print(f"## {t}")
                hits = res.get(t, {})
                if not hits:
                    print("   (no match)")
                for pid, h in hits.items():
                    flag = "C" if h["chordified"] else "U"   # U = never analysed, no chords
                    print(f"   {flag} {pid} | {h['title']} | jams={h['jams']} | {h['summary']}")
        else:
            want = {}
            for pair in a.pairs:
                slug, _, ids = pair.partition("=")
                want[slug] = [i if i.startswith("youtube:") else "youtube:" + i for i in ids.split(",")]
            res = evaluate(PULL_JS % json.dumps(want))
            os.makedirs(a.out, exist_ok=True)
            for slug, entries in res.items():
                with open(os.path.join(a.out, f"{slug}.json"), "w") as f:
                    json.dump(entries, f, ensure_ascii=False, indent=1)
                for e in entries:
                    rows = (e["chords"] or "").strip().splitlines()
                    end = float(rows[-1].split(";")[3]) if rows else 0
                    ci = e["chordInfo"] or {}
                    print(f"{slug:32} {e['id']:22} beats={len(rows):4} dur={end:6.1f}s "
                          f"bpm={ci.get('derivedBpm')} key={ci.get('derivedKey')} | {e['title']}")
    finally:
        browser("close")


if __name__ == "__main__":
    main()
