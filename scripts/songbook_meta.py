"""Shared reader for `songbooks/<slug>/songbook.yaml`.

Every tool that consumes songbook metadata goes through here so the
locale contract is defined once: `make-cover.py` (print), and
`readme-table.py` (the root README table).

A *locale map* is a mapping keyed only by known locales:

    description:
      it: Canti partigiani italiani…
      en: Italian partisan songs…

`localize()` collapses those maps down to one language. Ordinary nested
objects are keyed by something else (`color`, `url`, `y`) and pass
through untouched, so a whole config tree can be resolved in one pass.

Print runs are monolingual -- the songbook's own `language:` wins -- while
the README is always English. That is the only difference between the
two callers, so it is a plain argument rather than two code paths.
"""

import os

import yaml

METADATA_NAME = "songbook.yaml"

# Locales a songbook.yaml may declare.
LOCALES = ("it", "en")
FALLBACK_LOCALE = "en"


def is_locale_map(value):
    """True when `value` is a mapping keyed purely by known locales.

    A map needs at least one locale key and no foreign ones, so a typo
    like `{en: ..., de: ...}` is left alone rather than silently
    half-resolved -- the stray key survives into the output where it is
    visible, instead of being dropped.
    """
    if not isinstance(value, dict) or not value:
        return False
    return all(key in LOCALES for key in value)


def localize(value, language):
    """Recursively replace locale maps with their `language` entry.

    Falls back to `FALLBACK_LOCALE`, then to any locale present, so a
    half-translated songbook still renders instead of printing a blank.
    """
    if is_locale_map(value):
        for candidate in (language, FALLBACK_LOCALE, *LOCALES):
            if value.get(candidate) is not None:
                return localize(value[candidate], language)
        return None
    if isinstance(value, dict):
        return {k: localize(v, language) for k, v in value.items()}
    if isinstance(value, list):
        return [localize(item, language) for item in value]
    return value


def load_metadata(sb_dir):
    """Return the raw songbook.yaml mapping, or {} when absent."""
    path = os.path.join(sb_dir, METADATA_NAME)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def language_of(meta):
    """Return the songbook's declared primary language."""
    return meta.get("language") or FALLBACK_LOCALE
