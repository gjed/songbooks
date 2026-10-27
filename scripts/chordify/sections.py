"""Parse a Genius lyrics file into [{"name": section header, "lines": [...]}]."""
import re


def parse(path):
    secs, cur = [], None
    for line in open(path, encoding="utf-8"):
        s = re.sub(r"[\u2005\u205f\u00a0\u200b]", " ", line).strip()   # Genius odd spaces
        if not s or s == "[?]":
            continue
        m = re.fullmatch(r"\[(.+)\]", s)
        if m:
            if m.group(1).startswith("Testo di"):          # Genius title header, not a section
                continue
            cur = {"name": m.group(1), "lines": []}
            secs.append(cur)
            continue
        if cur is None:
            cur = {"name": "", "lines": []}
            secs.append(cur)
        cur["lines"].append(s)
    return secs
