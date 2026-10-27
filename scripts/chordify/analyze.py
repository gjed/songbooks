#!/usr/bin/env python3
"""Local audio analysis for one song: chords + key + beats (madmom), vocal stem
(Demucs), and word-level lyric alignment (stable-ts on faster-whisper).

Runs inside the venv from requirements.txt (see the chordify-import skill).

usage: analyze.py --work WORK AUDIO.wav SLUG [--steps chords,align] [--model medium]

reads   WORK/lyrics/SLUG.txt
writes  WORK/local/SLUG.madmom.json  {"key", "chords": [[start, end, label]], "beats": [...]}
        WORK/local/SLUG.align.json   {"sections", "segments", "words": [{w, s, e, p}]}
Existing outputs are kept; delete them to recompute.
"""
import argparse, json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sections import parse


def chords(wav, out):
    from madmom.features.chords import CNNChordFeatureProcessor, CRFChordRecognitionProcessor
    from madmom.features.beats import RNNBeatProcessor, DBNBeatTrackingProcessor
    from madmom.features.key import CNNKeyRecognitionProcessor, key_prediction_to_label
    ch = CRFChordRecognitionProcessor()(CNNChordFeatureProcessor()(wav))
    beats = DBNBeatTrackingProcessor(fps=100)(RNNBeatProcessor()(wav))
    key = key_prediction_to_label(CNNKeyRecognitionProcessor()(wav))
    json.dump({"key": key, "chords": [[float(a), float(b), str(c)] for a, b, c in ch],
               "beats": [float(b) for b in beats]}, open(out, "w"))
    print(f"chords: {len(ch)} segments, {len(beats)} beats, key {key}")


def vocals(wav, work):
    name = os.path.splitext(os.path.basename(wav))[0]
    stem = os.path.join(work, "sep", "htdemucs", name, "vocals.wav")
    if not os.path.exists(stem):
        subprocess.run([sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", "htdemucs",
                        "-j", "4", "-o", os.path.join(work, "sep"), wav], check=True)
    return stem


def align(stem, lyr, out, model):
    import stable_whisper
    secs = parse(lyr)
    lines = [l for s in secs for l in s["lines"]]
    m = stable_whisper.load_faster_whisper(model, device="cpu", compute_type="int8",
                                           cpu_threads=os.cpu_count())
    r = m.align(stem, "\n".join(lines), language="it", original_split=True)
    words = [{"w": w.word, "s": w.start, "e": w.end, "p": w.probability}
             for seg in r.segments for w in seg.words]
    if len(r.segments) != len(lines):
        sys.exit(f"align: {len(lines)} lyric lines but {len(r.segments)} aligned segments")
    json.dump({"sections": secs, "words": words,
               "segments": [{"text": s.text, "s": s.start, "e": s.end} for s in r.segments]},
              open(out, "w"), ensure_ascii=False)
    print(f"align: {len(lines)} lines, {len(words)} words")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", required=True); ap.add_argument("audio"); ap.add_argument("slug")
    ap.add_argument("--steps", default="chords,align"); ap.add_argument("--model", default="medium")
    a = ap.parse_args()
    os.makedirs(os.path.join(a.work, "local"), exist_ok=True)
    base = os.path.join(a.work, "local", a.slug)
    steps = a.steps.split(",")
    if "chords" in steps and not os.path.exists(base + ".madmom.json"):
        chords(a.audio, base + ".madmom.json")
    if "align" in steps and not os.path.exists(base + ".align.json"):
        align(vocals(a.audio, a.work), os.path.join(a.work, "lyrics", a.slug + ".txt"),
              base + ".align.json", a.model)


if __name__ == "__main__":
    main()
