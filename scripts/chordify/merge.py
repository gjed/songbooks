#!/usr/bin/env python3
"""Merge a chord timeline with word-aligned lyrics into a ChordPro draft.

Chordify is the primary chord source when WORK/chordify/<slug>.json exists; the
local madmom timeline aligns it to the audio (best time offset) and verifies it.
Lines where the two disagree for most of their duration get a
`# check local: <chords>` comment. When agreement is below MIN_AGREE (Chordify
analysed a different version/edit), Chordify is rejected and local is used.

usage: merge.py --work WORK --artist ARTIST SLUG TITLE ALBUM [--chordify-id youtube:ID] [--key KEY]
reads   WORK/local/SLUG.madmom.json, WORK/local/SLUG.align.json, WORK/chordify/SLUG.json (optional)
writes  WORK/out/SLUG.cho, WORK/out/SLUG.report.json (also printed)
"""
import json, re, sys, os, argparse
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("slug"); ap.add_argument("title"); ap.add_argument("album")
ap.add_argument("--chordify-id"); ap.add_argument("--artist", required=True)
ap.add_argument("--key"); ap.add_argument("--work", required=True)
a = ap.parse_args()
os.chdir(a.work)

MIN_BEATS = 2          # chord segments shorter than this many beats are merged away
ATTACH = 1.5           # max seconds a chord may precede the word it is attached to
GAP = 4.0              # vocal gap (s) that becomes an instrumental chord line
GRID = 0.05
MIN_AGREE = 0.40       # below this chordify/local agreement the chordify timeline is rejected
rejected = None
cfe = None

def sym(lab):
    """Chordify/madmom label -> common notation."""
    if lab in ("N", "X", ""): return None
    root, _, q = lab.partition(":")
    root = {"A#": "Bb", "D#": "Eb", "G#": "Ab"}.get(root, root)
    q = {"maj": "", "min": "m", "7": "7", "min7": "m7", "maj7": "maj7", "": "",
         "dim": "dim", "aug": "aug", "sus4": "sus4", "sus2": "sus2", "maj6": "6", "min6": "m6"}.get(q, q)
    return root + q

def triad(lab):
    """Reduce to root+maj/min for comparison, enharmonics unified."""
    if lab in ("N", "X", "", None): return "N"
    root, _, q = lab.partition(":")
    enh = {"Db": "C#", "D#": "Eb", "Gb": "F#", "G#": "Ab", "A#": "Bb", "Cb": "B", "Fb": "E", "E#": "F", "B#": "C"}
    root = enh.get(root, root)
    return root + ("m" if q.startswith("min") or q in ("dim",) else "")

mad = json.load(open(f"local/{a.slug}.madmom.json"))
ali = json.load(open(f"local/{a.slug}.align.json"))
beats = np.array(mad["beats"])
beat_len = float(np.median(np.diff(beats))) if len(beats) > 2 else 0.5
dur = max(mad["chords"][-1][1], ali["words"][-1]["e"] if ali["words"] else 0)

def grid_labels(segs, offset=0.0, n=None):
    n = n or int(dur / GRID) + 1
    out = np.array(["N"] * n, dtype=object)
    for s, e, lab in segs:
        i, j = int(round((s - offset) / GRID)), int(round((e - offset) / GRID))
        i, j = max(i, 0), min(j, n)
        if j > i: out[i:j] = triad(lab)
    return out

mad_segs = [(s, e, l) for s, e, l in mad["chords"]]
mad_grid = grid_labels(mad_segs)

source, offset, agree = "local", 0.0, None
segs = mad_segs
if a.chordify_id or os.path.exists(f"chordify/{a.slug}.json"):
    entries = json.load(open(f"chordify/{a.slug}.json"))
    if a.chordify_id: entries = [x for x in entries if x["id"] == a.chordify_id]
    def fit(cfe):
        """Best time offset (chordify_time = audio_time + offset) and agreement vs local."""
        rows = [l.split(";") for l in cfe["chords"].strip().splitlines()]
        cf = [(float(r[2]), float(r[3]), r[1]) for r in rows]
        cf_n = int(max(r[1] for r in cf) / GRID) + 1
        cf_grid = grid_labels(cf, 0.0, cf_n)
        best = (-1, 0)
        # loop-based songs correlate at many lags: only search lags the duration difference allows
        win = min(60.0, abs(max(r[1] for r in cf) - dur) + 5.0)
        for sh in range(int(-win / GRID), int(win / GRID) + 1):
            lo, hi = max(0, -sh), min(len(mad_grid), cf_n - sh)
            if hi - lo < len(mad_grid) * 0.5: continue
            m, c = mad_grid[lo:hi], cf_grid[lo + sh:hi + sh]
            mask = (m != "N") & (c != "N")
            if mask.sum() == 0: continue
            score = (m[mask] == c[mask]).mean()
            if score > best[0]: best = (score, sh)
        return float(best[0]), best[1] * GRID, cf
    fits = sorted(((fit(x), x) for x in entries), key=lambda t: -t[0][0])
    (agree, offset, cf), cfe = fits[0]
    alternatives = {x["id"]: round(f[0], 3) for f, x in fits}
    if agree < MIN_AGREE:   # chordify upload is a different version/edit: it cannot be mapped onto this audio
        rejected = (cfe["id"], round(agree, 3)); agree = None; offset = 0.0
        cfe = None
    if cfe:
        segs = [(s - offset, en - offset, l) for s, en, l in cf]
        source = f"chordify {cfe['id']}"

def smooth(segs):
    out = []
    for s, e, l in segs:
        if out and out[-1][2] == l: out[-1][1] = e; continue
        out.append([s, e, l])
    changed = True
    while changed:
        changed = False
        for i, (s, e, l) in enumerate(out):
            if l != "N" and (e - s) < MIN_BEATS * beat_len * 0.9 and len(out) > 1:
                if i > 0: out[i - 1][1] = e
                else: out[1][0] = s
                del out[i]; changed = True
                break
        merged = []
        for x in out:
            if merged and merged[-1][2] == x[2]: merged[-1][1] = x[1]
            else: merged.append(x)
        out = merged
    return out

timeline = [x for x in smooth(segs) if sym(x[2])]
mad_tl = [x for x in smooth(mad_segs) if sym(x[2])]

# ---- map words back to lines -------------------------------------------------
secs = ali["sections"]
words = ali["words"]
lines, wi = [], 0
seg_iter = iter(ali["segments"])
for si, sec in enumerate(secs):
    for text in sec["lines"]:
        seg = next(seg_iter)
        ws = []
        while wi < len(words) and words[wi]["s"] < seg["e"] + 1e-3 and len(ws) < 400:
            ws.append(words[wi]); wi += 1
            if "".join(w["w"] for w in ws).strip() == seg["text"].strip(): break
        lines.append({"sec": si, "text": text, "words": ws, "s": seg["s"], "e": seg["e"]})

# ---- attach chords to words --------------------------------------------------
flat = [(li, k, w) for li, L in enumerate(lines) for k, w in enumerate(L["words"])]
starts = np.array([w["s"] for _, _, w in flat])
attach = {}          # (line, word) -> chord
instr = {}           # line index -> list of chords played in the gap before it (len(lines) = outro)
for s, e, l in timeline:
    c = sym(l)
    j = int(np.searchsorted(starts, s - 0.25))
    if j < len(flat) and starts[j] - s <= ATTACH:
        attach[(flat[j][0], flat[j][1])] = c
        continue
    # inside a gap: which line follows?
    nxt = flat[j][0] if j < len(flat) else len(lines)
    prev_end = flat[j - 1][2]["e"] if j > 0 else 0.0
    nxt_start = starts[j] if j < len(flat) else dur
    if nxt_start - prev_end >= GAP:
        instr.setdefault(nxt, []).append(c)
    elif j < len(flat):
        attach.setdefault((flat[j][0], flat[j][1]), c)

def collapse(seq):
    n = len(seq)
    for p in range(1, n // 2 + 1):
        if n % p == 0 and seq == seq[:p] * (n // p):
            return seq[:p], n // p
    return seq, 1

def render_line(li):
    L = lines[li]
    if not L["words"]: return L["text"]
    out = ""
    for k, w in enumerate(L["words"]):
        t = w["w"]
        if k == 0: t = t.lstrip()
        c = attach.get((li, k))
        if c:
            lead = len(t) - len(t.lstrip())
            t = t[:lead] + f"[{c}]" + t[lead:]
        out += t
    return out

def chords_in(tl, s, e):
    return [triad_l for triad_l in (triad(l) for a_, b_, l in tl if b_ > s and a_ < e)]

CHECK_MIN = 0.5   # flag a line when the two sources agree for less than this share of its duration
def check(li):
    """Compare the chosen timeline against the local one over the line's span (time-weighted)."""
    L = lines[li]
    if not source.startswith("chordify"): return None
    i, j = int(L["s"] / GRID), int(L["e"] / GRID) + 1
    A = grid_labels([(s, e, l) for s, e, l in timeline])[i:j]
    B = grid_labels([(s, e, l) for s, e, l in mad_tl])[i:j]
    mask = (A != "N") & (B != "N")
    if mask.sum() == 0 or (A[mask] == B[mask]).mean() >= CHECK_MIN: return None
    dedup = lambda q: [x for k, x in enumerate(q) if k == 0 or q[k - 1] != x]
    return " ".join(dedup(list(B[B != "N"])))

def sec_kind(name):
    n = name.lower()
    if n.startswith("ritornello"): return "chorus"
    return "verse"

key = a.key
if not key and cfe:
    key = sym(cfe["chordInfo"]["derivedKey"])
if not key and mad.get("key"):
    root, mode = mad["key"].split()
    root = {"D#": "Eb", "A#": "Bb", "G#": "Ab"}.get(root, root)
    key = root + ("m" if mode == "minor" else "")
key = key or "TODO"

out = [f"{{title: {a.title}}}", f"{{artist: {a.artist}}}", f"{{album: {a.album}}}", f"{{key: {key}}}", ""]
checks = 0
def instr_block(chords):
    seq, n = collapse([x for i, x in enumerate(chords) if i == 0 or chords[i - 1] != x])
    line = " ".join(f"[{c}]" for c in seq) + (f" (x{n})" if n > 1 else "")
    return ["{start_of_verse}", line, "{end_of_verse}", ""]

seen_chorus = {}
for si, sec in enumerate(secs):
    idx = [i for i, L in enumerate(lines) if L["sec"] == si]
    if idx and idx[0] in instr: out += instr_block(instr[idx[0]])
    kind = sec_kind(sec["name"])
    key_text = tuple(sec["lines"])
    if kind == "chorus":
        # exact repeat -> recall; repeat plus extra lines (e.g. extended last chorus) -> recall + tail block
        prefix = next((p for p in seen_chorus if key_text[:len(p)] == p), None)
        if prefix:
            out += ["{chorus}", ""]
            idx = idx[len(prefix):]
            if not idx: continue
            kind = "verse"
    out.append("{start_of_%s}" % kind)
    if kind == "chorus": out.append("{comment: RIT}"); seen_chorus[key_text] = True
    for i in idx:
        if i != idx[0] and i in instr:   # mid-section gap: inline chord line
            seq, n = collapse([x for k, x in enumerate(instr[i]) if k == 0 or instr[i][k - 1] != x])
            out.append(" ".join(f"[{c}]" for c in seq) + (f" (x{n})" if n > 1 else ""))
        c = check(i)
        if c: out.append(f"# check local: {c}"); checks += 1
        out.append(render_line(i))
    out += ["{end_of_%s}" % kind, ""]
if len(lines) in instr: out += instr_block(instr[len(lines)])

SHARP_KEYS = {"G", "D", "A", "E", "B", "F#", "C#", "Em", "Bm", "F#m", "C#m", "G#m", "D#m", "A#m"}
TO_SHARP = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
TO_FLAT = {v: k for k, v in TO_SHARP.items()}
def respell(ch):
    """Spell accidentals to match the key signature (sharps in sharp keys, flats otherwise)."""
    m = re.match(r"([A-G][#b]?)(.*)", ch)
    if not m: return ch
    root, rest = m.groups()
    table = TO_SHARP if key in SHARP_KEYS else TO_FLAT
    return table.get(root, root) + rest
def finish(line):
    line = line.replace("([?])", "(?)").replace("[?]", "(?)")   # Genius placeholder for unintelligible words
    if line.startswith("# check local:"):
        return "# check local: " + " ".join(respell(c) for c in line[len("# check local:"):].split())
    if line.startswith("{"): return line
    return re.sub(r"\[([^\]]+)\]", lambda m: "[" + respell(m.group(1)) + "]", line)
key = respell(key) if key != "TODO" else key
out = out[:3] + [f"{{key: {key}}}"] + [finish(l) for l in out[4:]]

os.makedirs("out", exist_ok=True)
open(f"out/{a.slug}.cho", "w").write("\n".join(out).rstrip() + "\n")
rep = {"slug": a.slug, "source": source, "rejected": rejected, "key": key, "alternatives": source.startswith("chordify") and alternatives or None, "offset": round(offset, 2), "agreement": agree and round(agree, 3),
       "beat_len": round(beat_len, 3), "lines": len(lines), "check_lines": checks,
       "low_conf_words": sum(1 for w in words if w["p"] is not None and w["p"] < 0.3)}
json.dump(rep, open(f"out/{a.slug}.report.json", "w"))
print(json.dumps(rep))
