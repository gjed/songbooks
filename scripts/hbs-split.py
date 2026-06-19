#!/usr/bin/env python3
"""
Split hbs-eng/raw.txt into individual ChordPro .cho files.
Each song is identified by its title from the INDEX section.
"""

import re
import os
import sys

RAW = "songbooks/hbs-eng/raw.txt"
OUT = "songbooks/hbs-eng"

# Song list from index, in alphabetical order, with slugs
SONGS = [
    ("500 Miles",                        "500-miles",                    "The Proclaimers"),
    ("7 Years",                          "7-years",                      "Lukas Graham"),
    ("A Horse with no Name",             "a-horse-with-no-name",         "America"),
    ("A Million Dreams",                 "a-million-dreams",             "The Greatest Showman"),
    ("Adventure Time",                   "adventure-time",               "Pendleton Ward"),
    ("All Together Now",                 "all-together-now",             "The Beatles"),
    ("Always Look on the Bright Side of Life", "always-look-on-the-bright-side", "Monty Python"),
    ("Another Brick in the Wall",        "another-brick-in-the-wall",    "Pink Floyd"),
    ("Auld Lang Syne",                   "auld-lang-syne",               "Robert Burns"),
    ("Blowin' in the Wind",              "blowin-in-the-wind",           "Bob Dylan"),
    ("California dreamin'",              "california-dreamin",           "The Mamas & The Papas"),
    ("Can You Feel the Love Tonight",    "can-you-feel-the-love-tonight","Disney's The Lion King"),
    ("Can't Help Falling In Love With You", "cant-help-falling-in-love", "Elvis Presley"),
    ("Cat's in the Craddle",             "cats-in-the-cradle",           "Ugly Kid Joe"),
    ("Circle of Life",                   "circle-of-life",               "Disney's The Lion King"),
    ("Do You Hear the People Sing?",     "do-you-hear-the-people-sing",  "Les Misérables"),
    ("Don't Worry Be Happy",             "dont-worry-be-happy",          "Bobby McFerrin"),
    ("Dreaming of You",                  "dreaming-of-you",              "The Corals"),
    ("Drunken Sailor",                   "drunken-sailor",               "Irish Folk"),
    ("Dumb Ways to Die",                 "dumb-ways-to-die",             "Metro Trains"),
    ("Facing West",                      "facing-west",                  "The Staves"),
    ("Far Over the Misty Mountains",     "far-over-the-misty-mountains", "The Hobbit"),
    ("Fireflies",                        "fireflies",                    "Owl City"),
    ("Greensleeves",                     "greensleeves",                 "English Folk"),
    ("Guaranteed",                       "guaranteed",                   "Eddie Vedder"),
    ("Hallelujah",                       "hallelujah",                   "Rufus Wainwright"),
    ("Hey Brother",                      "hey-brother",                  "Avicii"),
    ("Hey, Soul Sister",                 "hey-soul-sister",              "Train"),
    ("Hey There Delilah",                "hey-there-delilah",            "Plain White T's"),
    ("Hey Ya",                           "hey-ya",                       "Outkast"),
    ("Hit The Road Jack",                "hit-the-road-jack",            "Ray Charles"),
    ("Ho Hey",                           "ho-hey",                       "Lumineers"),
    ("House of the Rising Sun",          "house-of-the-rising-sun",      "The Animals"),
    ("How Far I'll Go",                  "how-far-ill-go",               "Disney's Moana"),
    ("I Love The Mountains",             "i-love-the-mountains",         "Barney & Friends"),
    ("I' ll Make a Man Out of You",      "ill-make-a-man-out-of-you",    "Disney's Mulan"),
    ("I'm a Believer",                   "im-a-believer",                "The Monkees"),
    ("If I Had a Boat",                  "if-i-had-a-boat",              "James Vincent McMorrow"),
    ("If You're Happy and You Know It",  "if-youre-happy-and-you-know-it","Nursery Rhyme"),
    ("Il Pescatore -",                   "il-pescatore",                 "Fabrizio De André"),
    ("Imagine",                          "imagine",                      "John Lennon"),
    ("Johnny I Hardly Knew Ye",          "johnny-i-hardly-knew-ye",      "The Irish Rovers"),
    ("Jolene",                           "jolene",                       "Dolly Parton"),
    ("King of the Bongo",                "king-of-the-bongo",            "Manu Chao"),
    ("Knocking On Heaven's Door",        "knocking-on-heavens-door",     "Bob Dylan"),
    ("La Bamba",                         "la-bamba",                     "Los Lobos"),
    ("La Vie en Rose",                   "la-vie-en-rose",               "Louis Armstrong"),
    ("Land of the Silver Birch",         "land-of-the-silver-birch",     "Nursery Rhyme"),
    ("Lava Song",                        "lava-song",                    "Pixar"),
    ("Lemon Tree",                       "lemon-tree",                   "Fool's Garden"),
    ("Let It Be",                        "let-it-be",                    "The Beatles"),
    ("Light My Fire",                    "light-my-fire",                "The Doors"),
    ("Little Boxes",                     "little-boxes",                 "Walk off the Earth"),
    ("Little Talks",                     "little-talks",                 "Of Monsters And Men"),
    ("Loch Lomond",                      "loch-lomond",                  "Scottish Folk"),
    ("Long Nights",                      "long-nights",                  "Eddie Vedder"),
    ("Losing My Religion",               "losing-my-religion",           "R.E.M"),
    ("Lost",                             "lost",                         "Coldplay"),
    ("Mad World",                        "mad-world",                    "Gary Jules"),
    ("Mamma Mia",                        "mamma-mia",                    "Abba"),
    ("Mr Tambourine Man",                "mr-tambourine-man",            "Bob Dylan"),
    ("My Bonnie Lies Over the Ocean",    "my-bonnie-lies-over-the-ocean","Scottish Folk"),
    ("My Heart Will Go On",              "my-heart-will-go-on",          "Celine Dion"),
    ("Oh my Darling Clementine",         "oh-my-darling-clementine",     "American Folk"),
    ("Old MacDonald Had a Farm",         "old-macdonald-had-a-farm",     "Nursery Rhyme"),
    ("Oo De Lally",                      "oo-de-lally",                  "Disney's Robin Hood"),
    ("Over and Done With",               "over-and-done-with",           "The Proclaimers"),
    ("Perfect",                          "perfect",                      "Ed Sheeran"),
    ("Postcards From Italy",             "postcards-from-italy",         "Beirut"),
    ("Reality",                          "reality",                      "Lost Frequencies"),
    ("Renegades",                        "renegades",                    "X Ambassadors"),
    ("Riptide",                          "riptide",                      "Vance Joy"),
    ("Rise",                             "rise",                         "Eddie Vedder"),
    ("Riverside",                        "riverside",                    "Agnes Obel"),
    ("Run",                              "run",                          "Daughter"),
    ("Scarborough Fair",                 "scarborough-fair",             "English Folk"),
    ("Society",                          "society",                      "Eddie Vedder"),
    ("Somebody that I Used to Know",     "somebody-that-i-used-to-know", "Gotye"),
    ("Stand By Me",                      "stand-by-me",                  "Ben E. King"),
    ("Summer Nights",                    "summer-nights",                "Grease"),
    ("Sunrise",                          "sunrise",                      "Norah Jones"),
    ("Sweet Home Alabama",               "sweet-home-alabama",           "Lynyrd Skynyrd"),
    ("Take Me Home Country Roads",       "take-me-home-country-roads",   "John Denver"),
    ("The Bare Necessities",             "the-bare-necessities",         "Disney's The Jungle Book"),
    ("The Boxer",                        "the-boxer",                    "Simon & Garfunkel"),
    ("The Cave",                         "the-cave",                     "Mumford & Sons"),
    ("The Drunken Scotsman",             "the-drunken-scotsman",         "Bryan Bowers"),
    ("The Lion Sleeps Tonight",          "the-lion-sleeps-tonight",      "The Tokens"),
    ("The Passenger",                    "the-passenger",                "Iggy Pop"),
    ("The Penalty",                      "the-penalty",                  "Beirut"),
    ("The Sound of Silence",             "the-sound-of-silence",         "Simon & Garfunkel"),
    ("The Wellerman",                    "the-wellerman",                "The Longest Johns"),
    ("The Wild Rover",                   "the-wild-rover",               "The Dubliners"),
    ("They Call Me Trinity",             "they-call-me-trinity",         "Franco Micalizzi"),
    ("Three Little Birds",               "three-little-birds",           "Bob Marley"),
    ("Viva La Vida",                     "viva-la-vida",                 "Coldplay"),
    ("We know the Way",                  "we-know-the-way",              "Disney's Moana"),
    ("Whatever You Want",                "whatever-you-want",            "Status Quo"),
    ("Whiskey in the Jar",               "whiskey-in-the-jar",           "Irish Folk"),
    ("Winter Winds",                     "winter-winds",                 "Mumford & Sons"),
    ("Wish You Were Here",               "wish-you-were-here",           "Pink Floyd"),
    ("Yo Ho Ho and a Bottle of Rum",     "yo-ho-ho",                     "Young Ewing Allison"),
    ("You are my Sunshine",              "you-are-my-sunshine",          "Kevin Devine"),
]

def normalize(s):
    # Normalize unicode quotes/dashes to ASCII equivalents
    s = s.replace('\u2019', "'").replace('\u2018', "'")
    s = s.replace('\u201c', '"').replace('\u201d', '"')
    s = s.replace('\u2013', '-').replace('\u2014', '-')
    return re.sub(r'\s+', ' ', s).strip().lower()

def find_song_blocks(raw_text, song_titles):
    """Find start line of each song in the raw text."""
    lines = raw_text.split('\n')
    title_to_line = {}
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        for title, slug, artist in song_titles:
            if normalize(stripped) == normalize(title):
                if title not in title_to_line:
                    title_to_line[title] = i
    
    return lines, title_to_line

def extract_song(lines, start, end):
    """Extract song lines from start+1 to end (exclusive)."""
    # Skip the title line itself
    block = lines[start+1:end]
    # Strip trailing blank lines
    while block and not block[-1].strip():
        block.pop()
    return block

def lines_to_chordpro(title, artist, body_lines):
    """Convert raw lines to ChordPro format."""
    out = []
    out.append(f"{{title: {title}}}")
    out.append(f"{{artist: {artist}}}")
    out.append(f"{{album: HBS Songbook}}")
    out.append(f"{{key: C}}")
    out.append("")
    
    in_section = False
    
    for line in body_lines:
        stripped = line.strip()
        
        # Detect section headers
        low = stripped.lower()
        if low in ('chorus:', 'chorus') or low.startswith('chorus:') or low.startswith('chorus '):
            if in_section:
                out.append("{end_of_verse}")
                in_section = False
            out.append("{start_of_chorus}")
            out.append("{comment: Chorus}")
            in_section = True
            continue
        
        if low in ('verse:', 'verse') or re.match(r'^verse\s*\d*:?$', low):
            if in_section:
                out.append("{end_of_chorus}" if 'chorus' in low else "{end_of_verse}")
                in_section = False
            out.append("{start_of_verse}")
            in_section = True
            continue
        
        if low.startswith('bridge:') or low == 'bridge':
            if in_section:
                out.append("{end_of_verse}")
                in_section = False
            out.append("{start_of_verse}")
            out.append("{comment: Bridge}")
            in_section = True
            continue
        
        if low.startswith('intro:') or low.startswith('intro ') or low == 'intro':
            out.append(f"{{comment: {stripped}}}")
            continue
        
        if low.startswith('outro:') or low == 'outro':
            if in_section:
                out.append("{end_of_verse}")
                in_section = False
            out.append(f"{{comment: {stripped}}}")
            continue
        
        # Convert chord lines: lines where most content is chords
        # A chord line has chords above lyrics — in raw they're on separate lines
        # We keep them as-is (ChordPro inline format not possible without manual work)
        # Just output as comment if it looks like a pure chord line
        if stripped and re.match(r'^[A-G][^\s]*(\s+[A-G][^\s]*)*\s*$', stripped):
            # Pure chord line — wrap in comment
            out.append(f"{{comment: {stripped}}}")
            continue
        
        # Convert inline chords: "Am G Am G" style above lyrics
        # Detect lines that are mostly chord names
        tokens = stripped.split()
        if tokens and all(re.match(r'^[A-G][#b]?(m|maj|min|dim|aug|sus|add|7|9|11|13|6|5|4|2|\/[A-G])*[#b]?(\d)?$', t) for t in tokens if t):
            out.append(f"{{comment: {stripped}}}")
            continue
        
        out.append(stripped if stripped else "")
    
    if in_section:
        out.append("{end_of_verse}")
    
    return '\n'.join(out)

def main():
    with open(RAW, 'r', encoding='utf-8') as f:
        raw = f.read()
    
    lines, title_to_line = find_song_blocks(raw, SONGS)
    
    # Build ordered list of (title, line_number)
    found = [(title, title_to_line[title]) for title, slug, artist in SONGS if title in title_to_line]
    found.sort(key=lambda x: x[1])
    
    not_found = [title for title, slug, artist in SONGS if title not in title_to_line]
    if not_found:
        print(f"WARNING: Could not find: {not_found}", file=sys.stderr)
    
    # Extract each song block
    for i, (title, start_line) in enumerate(found):
        end_line = found[i+1][1] if i+1 < len(found) else len(lines)
        body = extract_song(lines, start_line, end_line)
        
        # Find slug and artist
        slug = next(s for t, s, a in SONGS if t == title)
        artist = next(a for t, s, a in SONGS if t == title)
        
        # Number: position in alphabetical SONGS list
        idx = next(i for i, (t, s, a) in enumerate(SONGS) if t == title)
        num = f"{idx+1:02d}"
        
        filename = f"{num}-{slug}.cho"
        filepath = os.path.join(OUT, filename)
        
        content = lines_to_chordpro(title, artist, body)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content + '\n')
        
        print(f"Written: {filename}")

if __name__ == '__main__':
    main()
