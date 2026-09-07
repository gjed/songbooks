/* Canzonieri — progressive-enhancement behaviour.
   Everything here is optional: with this file absent, every list still
   renders, already A–Z, nothing is broken. This script only adds live
   search, live re-sort and the day/night toggle. */
(function () {
  "use strict";

  function debounce(fn, wait) {
    var t;
    return function () {
      var args = arguments;
      clearTimeout(t);
      t = setTimeout(function () {
        fn.apply(null, args);
      }, wait);
    };
  }

  function toArray(nodeList) {
    return Array.prototype.slice.call(nodeList);
  }

  function fillTemplateCount(el, n) {
    if (!el) return;
    var tmpl = n === 1 ? el.getAttribute("data-tmpl-one") : el.getAttribute("data-tmpl-other");
    if (tmpl) el.textContent = tmpl.replace("#", String(n));
  }

  /* ---- day / night toggle ------------------------------------------- */

  /* The SVG favicon carries both colourways behind an internal
     @media (prefers-color-scheme: dark), which tracks the OS only — it
     cannot see the data-theme attribute. So the auto file is correct
     exactly while the page itself is still following the OS, and a pinned
     page needs the matching single-theme file instead.

     data-theme is that pin, and it is the same signal the stylesheet
     selects on (:root:not([data-theme="day"]):not([data-theme="night"])).
     Reading the attribute rather than localStorage matters in two cases
     where the two disagree: theme-init.html pins data-theme="night" on a
     dark-OS first paint with nothing saved, so a later OS switch to light
     would flip the icon while CSS held the page dark; and a toggle whose
     localStorage.setItem() throws still sets the attribute, so the page
     moves and storage does not.

     Every href comes from data attributes emitted by
     partials/head-icons.html through relURL, so nothing here hardcodes a
     path — baseURL is a subpath and this file must not know that. */
  function syncFavicon() {
    var link = document.querySelector('link[data-role="favicon-svg"]');
    if (!link) return;

    var pinned = document.documentElement.getAttribute("data-theme");
    if (pinned !== "day" && pinned !== "night") pinned = null;

    var href = pinned
      ? link.getAttribute("data-icon-" + pinned)
      : link.getAttribute("data-icon-auto");
    if (!href || link.getAttribute("href") === href) return;

    /* Some browsers only re-read the icon when the element itself changes,
       so replace the node rather than mutating href in place. */
    var next = link.cloneNode(false);
    next.setAttribute("href", href);
    if (link.parentNode) link.parentNode.replaceChild(next, link);
  }

  function initTheme() {
    var toggles = toArray(document.querySelectorAll('[data-role="theme-toggle"]'));

    function currentTheme() {
      return document.documentElement.getAttribute("data-theme") === "night" ? "night" : "day";
    }

    /* No toggle on this page: the theme may still be pinned, so reconcile
       the icon once and stop. */
    if (!toggles.length) {
      syncFavicon();
      return;
    }

    function render() {
      var theme = currentTheme();
      toggles.forEach(function (btn) {
        var label = theme === "night" ? btn.getAttribute("data-label-day") : btn.getAttribute("data-label-night");
        if (label) btn.textContent = label;
        btn.setAttribute("aria-pressed", theme === "night" ? "true" : "false");
      });
      syncFavicon();
    }

    toggles.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var next = currentTheme() === "night" ? "day" : "night";
        document.documentElement.setAttribute("data-theme", next);
        try {
          localStorage.setItem("theme", next);
        } catch (e) {
          /* storage unavailable — theme still applies for this load */
        }
        render();
      });
    });

    render();
  }

  /* ---- home: search + sort, mirrored across mobile rows & desktop tiles */

  function initHome() {
    var rowsWrap = document.querySelector('[data-role="book-rows"]');
    var tilesWrap = document.querySelector('[data-role="book-tiles"]');
    if (!rowsWrap && !tilesWrap) return;

    var searches = toArray(document.querySelectorAll('[data-role="book-search"]'));
    var chips = toArray(document.querySelectorAll('[data-role="sort-chip"]'));
    var counts = toArray(document.querySelectorAll('[data-role="book-result-count"]'));
    var emptyStates = toArray(document.querySelectorAll('[data-role="book-empty"]'));

    var state = { query: "", sort: "alpha", visible: 0 };

    function sortItems(items) {
      items.sort(function (a, b) {
        if (state.sort === "count") {
          var ca = parseInt(a.getAttribute("data-count"), 10) || 0;
          var cb = parseInt(b.getAttribute("data-count"), 10) || 0;
          if (cb !== ca) return cb - ca;
          return (a.getAttribute("data-title") || "").localeCompare(b.getAttribute("data-title") || "", "it");
        }
        if (state.sort === "lang") {
          var la = a.getAttribute("data-lang") || "";
          var lb = b.getAttribute("data-lang") || "";
          if (la !== lb) return la.localeCompare(lb);
          return (a.getAttribute("data-title") || "").localeCompare(b.getAttribute("data-title") || "", "it");
        }
        return (a.getAttribute("data-title") || "").localeCompare(b.getAttribute("data-title") || "", "it");
      });
      return items;
    }

    function apply() {
      var q = state.query.trim().toLowerCase();
      var visible = 0;

      [rowsWrap, tilesWrap].forEach(function (wrap) {
        if (!wrap) return;
        var items = toArray(wrap.children);
        items.forEach(function (el) {
          var title = (el.getAttribute("data-title") || "").toLowerCase();
          var desc = (el.getAttribute("data-desc") || "").toLowerCase();
          var match = !q || title.indexOf(q) !== -1 || desc.indexOf(q) !== -1;
          el.hidden = !match;
          if (match) visible += 1;
        });
        sortItems(items).forEach(function (el) {
          wrap.appendChild(el);
        });
      });

      /* both lists hold the same set, so halve the double count when both exist */
      if (rowsWrap && tilesWrap) visible = Math.round(visible / 2);
      state.visible = visible;

      counts.forEach(function (el) {
        fillTemplateCount(el, visible);
      });
      emptyStates.forEach(function (el) {
        el.hidden = visible !== 0;
      });
    }

    searches.forEach(function (input) {
      input.addEventListener(
        "input",
        debounce(function () {
          state.query = input.value;
          searches.forEach(function (other) {
            if (other !== input) other.value = input.value;
          });
          apply();
        }, 60)
      );
    });

    chips.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var key = btn.getAttribute("data-sort");
        state.sort = key;
        chips.forEach(function (c) {
          c.setAttribute("aria-pressed", c.getAttribute("data-sort") === key ? "true" : "false");
        });
        apply();
      });
    });
  }

   /* ---- song index: live search --------------------------------------- */

   function initSongIndex() {
     var wrap = document.querySelector('[data-role="song-rows"]');
     var search = document.querySelector('[data-role="song-search"]');
     if (!wrap || !search) return;

     var count = document.querySelector('[data-role="song-result-count"]');
     var empty = document.querySelector('[data-role="song-empty"]');

     function apply() {
       var q = search.value.trim().toLowerCase();
       var visible = 0;
       toArray(wrap.children).forEach(function (el) {
         var title = (el.getAttribute("data-title") || "").toLowerCase();
         var match = !q || title.indexOf(q) !== -1;
         el.hidden = !match;
         if (match) visible += 1;
       });
       fillTemplateCount(count, visible);
       if (empty) empty.hidden = visible !== 0;
     }

     search.addEventListener("input", debounce(apply, 60));
   }

   /* ---- autoscroll: smooth per-pixel glide on song pages -------------- */

   function initAutoscroll() {
     var wrapper = document.querySelector('[data-role="autoscroll"]');
     if (!wrapper) return;

     /* Reveal the control (progressive enhancement: no JS = no UI) */
     wrapper.removeAttribute("hidden");

     /* Speed level mapping: level 1..10 maps to ~8 px/s at level 1,
        ~110 px/s at level 10 via exponential curve. */
     var MIN_LEVEL = 1;
     var MAX_LEVEL = 10;
     var DEFAULT_LEVEL = 3;
     var SPEED_CURVE = 1.35;
     var BASE_SPEED = 8; /* px/s at level 1 */

     var state = { level: DEFAULT_LEVEL, playing: false, acc: 0, rafId: null };

     /* Read persisted level from storage, clamped to valid range */
     try {
       var stored = parseInt(localStorage.getItem("autoscroll-speed"), 10);
       if (stored >= MIN_LEVEL && stored <= MAX_LEVEL) {
         state.level = stored;
       }
     } catch (e) {
       /* storage unavailable — use default */
     }

     var btnToggle = document.querySelector('[data-role="autoscroll-toggle"]');
     var btnSlower = document.querySelector('[data-role="autoscroll-slower"]');
     var btnFaster = document.querySelector('[data-role="autoscroll-faster"]');
     var levelDisplay = document.querySelector('[data-role="autoscroll-level"]');
     var statusRegion = document.querySelector('[data-role="autoscroll-status"]');

     function getPxPerSec() {
       return BASE_SPEED * Math.pow(SPEED_CURVE, state.level - 1);
     }

     function updateLevelDisplay() {
       if (levelDisplay) {
         levelDisplay.textContent = String(state.level);
       }
     }

     /* Announce the new level to assistive tech as a localized sentence —
        the visible readout is a bare aria-hidden number. Only called on
        user-initiated changes, never on init, so page load stays silent. */
     function announceLevel() {
       if (!statusRegion) return;
       var template = statusRegion.getAttribute("data-status-template") || "%s";
       statusRegion.textContent = template.replace("%s", String(state.level));
     }

      /* The toggle is an action button whose accessible name swaps between
         the two commands (Scroll/Pause) — deliberately NOT aria-pressed: a
         toggle button needs a stable name, and pairing a swapped name with
         aria-pressed reads as "Pause, pressed" in assistive tech. The
         playing state is styled off the wrapper's .is-playing class. */
      function updatePlayButton() {
        wrapper.classList.toggle("is-playing", state.playing);
        if (!btnToggle) return;
        if (state.playing) {
          var pauseLabel = btnToggle.getAttribute("data-label-pause");
          if (pauseLabel) btnToggle.textContent = pauseLabel;
        } else {
          var playLabel = btnToggle.getAttribute("data-label-play");
          if (playLabel) btnToggle.textContent = playLabel;
        }
      }

     function isAtBottom() {
       var tolerance = 2;
       return window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - tolerance;
     }

     var lastTime = null;

     function scroll(timestamp) {
       if (!state.playing) {
         state.rafId = null;
         return;
       }

       if (lastTime === null) {
         lastTime = timestamp;
       }

       var dt = Math.min(timestamp - lastTime, 100); /* clamp to 100ms to guard against background tabs */
       lastTime = timestamp;

       var pxPerSec = getPxPerSec();
       state.acc += pxPerSec * (dt / 1000);
       var whole = Math.floor(state.acc);

       if (whole > 0) {
         window.scrollBy(0, whole);
         state.acc -= whole;
       }

       /* Stop if document bottom is reached */
       if (isAtBottom()) {
         state.playing = false;
         lastTime = null;
         updatePlayButton();
         state.rafId = null;
         return;
       }

       state.rafId = requestAnimationFrame(scroll);
     }

     if (btnToggle) {
       btnToggle.addEventListener("click", function () {
         state.playing = !state.playing;
         updatePlayButton();
         if (state.playing) {
           lastTime = null;
           state.acc = 0;
           state.rafId = requestAnimationFrame(scroll);
         } else if (state.rafId) {
           cancelAnimationFrame(state.rafId);
           state.rafId = null;
         }
       });
     }

     if (btnSlower) {
       btnSlower.addEventListener("click", function () {
         if (state.level > MIN_LEVEL) {
           state.level -= 1;
           try {
             localStorage.setItem("autoscroll-speed", String(state.level));
           } catch (e) {
             /* storage unavailable */
           }
           updateLevelDisplay();
         }
         announceLevel();
       });
     }

     if (btnFaster) {
       btnFaster.addEventListener("click", function () {
         if (state.level < MAX_LEVEL) {
           state.level += 1;
           try {
             localStorage.setItem("autoscroll-speed", String(state.level));
           } catch (e) {
             /* storage unavailable */
           }
           updateLevelDisplay();
         }
         announceLevel();
       });
     }

     updateLevelDisplay();
     updatePlayButton();
   }

   /* ---- chord diagrams: the fretbox renderer -------------------------
      A fretbox is drawn in abstract units and handed to the page as an
      <svg> with a viewBox and no width/height, so ONE geometry serves both
      the ~68px tile in the row and the big one in the popover — CSS decides
      the size, the drawing scales. Nothing here knows about pixels.

      Colour comes from CSS: the dots and the ○/× markers paint in
      `currentColor` (set on the svg by chordpro.css), the grid in --rule
      and the nut in --ink. That is what makes the same markup correct in
      both themes and under every per-songbook accent without a re-render
      on theme change.

      Vertical layout — strings left-to-right as columns, frets as rows —
      because that is how a ukulele or guitar neck is drawn in every chord
      book, and the tile has to be readable at a glance mid-song. */

   var FB_CELL = 10;     /* string spacing, and one fret row's height */
   var FB_HEAD = 11;     /* the ○/× band above the nut */
   var FB_PAD = 5;       /* side gutters, enough for a marker's radius */
   var FB_LABEL = 11;    /* extra left gutter for the "3fr" base-fret label */
   var FB_MIN_ROWS = 4;  /* a 4-row grid is the norm; see below */

   function fretboxSvg(entry, strings) {
     var frets = entry.frets || [];
     var base = entry.base > 0 ? entry.base : 1;

     /* The base-fret label's gutter is claimed only when there is a label to
        put in it. Reserving it unconditionally cost nothing in code and a
        lot on screen: every open-position chord — which is nearly all of
        them — rendered visibly shoved to the right inside its own tile. */
     var padL = base > 1 ? FB_LABEL : FB_PAD;

     /* Grow past four rows only if a dot actually needs the space. With a
        sane `base` almost nothing does, so tiles across a row stay the same
        shape; when one does, its viewBox is taller and CSS's `meet` fit
        scales it down a notch rather than cropping it. */
     var rows = FB_MIN_ROWS;
     var i;
     for (i = 0; i < frets.length; i++) {
       if (frets[i] > rows) rows = frets[i];
     }

     var top = FB_HEAD;
     var gridW = (strings - 1) * FB_CELL;
     var w = padL + gridW + FB_PAD;
     var h = top + rows * FB_CELL + 1;
     var bottom = top + rows * FB_CELL;

     var svg = [];
     svg.push(
       '<svg class="fretbox" viewBox="0 0 ' + w + " " + h + '" ' +
         'preserveAspectRatio="xMidYMid meet" focusable="false" aria-hidden="true">'
     );

     /* Grid first, so dots always land on top of it. */
     svg.push('<g stroke="var(--rule)" stroke-width="0.7" fill="none">');
     for (i = 0; i < strings; i++) {
       var sx = padL + i * FB_CELL;
       svg.push('<line x1="' + sx + '" y1="' + top + '" x2="' + sx + '" y2="' + bottom + '"/>');
     }
     for (i = 1; i <= rows; i++) {
       var fy = top + i * FB_CELL;
       svg.push('<line x1="' + padL + '" y1="' + fy + '" x2="' + (padL + gridW) + '" y2="' + fy + '"/>');
     }
     svg.push("</g>");

     /* The nut. Thick and in --ink when the grid starts at fret 1 — that
        heavy bar IS the "this is the top of the neck" signal, and drawing
        it when base > 1 would be a lie about where your hand goes. Higher
        up the neck it is a plain fret line and the base label carries the
        position instead. */
     svg.push(
       '<line x1="' + padL + '" y1="' + top + '" x2="' + (padL + gridW) + '" y2="' + top + '" ' +
         (base === 1
           ? 'stroke="var(--ink)" stroke-width="2.6"'
           : 'stroke="var(--rule)" stroke-width="0.7"') +
         "/>"
     );

     if (base > 1) {
       svg.push(
         '<text x="' + (padL - 3.5) + '" y="' + (top + FB_CELL * 0.5) + '" ' +
           'text-anchor="end" dominant-baseline="central" font-size="5.4" ' +
           'fill="var(--ink2)" font-family="inherit">' + base + "fr</text>"
       );
     }

     /* Open and muted strings, in the band above the nut. */
     var my = top - 5.4;
     for (i = 0; i < strings; i++) {
       var mx = padL + i * FB_CELL;
       var f = frets[i];
       if (f === 0) {
         svg.push('<circle cx="' + mx + '" cy="' + my + '" r="2.4" fill="none" stroke="currentColor" stroke-width="0.9"/>');
       } else if (f < 0) {
         var d = 2.2;
         svg.push(
           '<g stroke="var(--ink2)" stroke-width="1.1" stroke-linecap="round">' +
             '<line x1="' + (mx - d) + '" y1="' + (my - d) + '" x2="' + (mx + d) + '" y2="' + (my + d) + '"/>' +
             '<line x1="' + (mx - d) + '" y1="' + (my + d) + '" x2="' + (mx + d) + '" y2="' + (my - d) + '"/>' +
             "</g>"
         );
       }
     }

     /* The barre: one finger laid flat across the neck. Drawing it as four
        or five loose dots is a materially worse diagram rather than just a
        plainer one — a guitar F or Gm7 reads as five unrelated fingerings
        until you notice they share a row — and every chord book prints the
        bar, so print the bar. The dots still go on top of it, which is also
        how it is printed: the bar says "one finger", the dots keep the
        string count legible at tile size.

        Getting the TEST right took three tries against the real tables, and
        the two rejected versions are worth recording, because both look
        obviously correct until you check them:

          "three adjacent strings on the same fret" — matched almost nothing
          real. In a guitar F, [1,3,3,2,1,1], the barred fret shows up on
          strings 1, 5 and 6 with higher notes stacked on top of it between.

          "lowest row held on 2+ strings spanning 3+ positions" — matched a
          guitar Esus4 ([0,2,2,2,0,0]) and Dmaj7 ([-1,-1,0,2,2,2]), which
          are ordinary finger shapes nobody bars.

        What actually identifies one: the lowest fretted row is held on more
        than one string, nothing between those strings is OPEN (an open
        string is one a bar must not touch), and either the row reaches from
        the first sounding string to the last — a finger across the whole
        neck — or it holds three-plus strings in a shape with no open string
        anywhere, which is a bar higher up the neck. Verified against 21
        hand-checked shapes plus every entry in both generated tables. */
     var lowest = 0;
     var first = -1;
     var last = -1;
     var held = 0;
     var lowStr = -1;      /* first sounding (non-muted) string */
     var highStr = -1;     /* last sounding string */
     var anyOpen = false;
     for (i = 0; i < strings; i++) {
       if (frets[i] > 0 && (lowest === 0 || frets[i] < lowest)) lowest = frets[i];
       if (frets[i] >= 0) {
         if (lowStr < 0) lowStr = i;
         highStr = i;
       }
       if (frets[i] === 0) anyOpen = true;
     }
     for (i = 0; lowest > 0 && i < strings; i++) {
       if (frets[i] !== lowest) continue;
       if (first < 0) first = i;
       last = i;
       held += 1;
     }
     var isBarre = held >= 2;
     for (i = first + 1; isBarre && i < last; i++) {
       if (frets[i] === 0) isBarre = false;
     }
     if (isBarre) {
       isBarre = (first === lowStr && last === highStr) || (held >= 3 && !anyOpen);
     }
     if (isBarre) {
       var by = top + (lowest - 0.5) * FB_CELL;
       svg.push(
         '<line x1="' + (padL + first * FB_CELL) + '" y1="' + by + '" ' +
           'x2="' + (padL + last * FB_CELL) + '" y2="' + by + '" ' +
           'stroke="currentColor" stroke-width="6.4" stroke-linecap="round"/>'
       );
     }

     /* Fretted notes. Centred in their row, not on the fret line — the dot
        means "press here in this space", the way it is printed on paper. */
     for (i = 0; i < strings; i++) {
       var fv = frets[i];
       if (!(fv > 0)) continue;
       svg.push(
         '<circle cx="' + (padL + i * FB_CELL) + '" ' +
           'cy="' + (top + (fv - 0.5) * FB_CELL) + '" r="3.4" fill="currentColor"/>'
       );
     }

     svg.push("</svg>");
     return svg.join("");
   }

   /* ---- chord diagrams: the row, the switch and the lyric popover -----
      Three faces of one feature, so they share one init and one in-memory
      chord table:
        1. a scrollable strip of fretboxes above the lyrics, one per
           distinct chord, in order of first appearance;
        2. any chord inside the lyrics is tappable and opens that chord's
           diagram in place, so nobody has to scroll back up mid-song;
        3. a ukulele/guitar switch that redraws everything, remembered in
           localStorage the same way autoscroll remembers its speed.

      The chord list is read OUT of the rendered lyrics rather than passed
      in as front matter: .ch spans are already the authoritative list of
      what this song uses, and reading them keeps this feature completely
      out of the ChordPro pipeline. The lyric markup is never modified —
      tappable chords get attributes and a class, never a new wrapper. */

   function initChordDiagrams() {
     var box = document.querySelector('[data-role="chord-diagrams"]');
     var lyrics = document.querySelector(".chordpro");
     if (!box || !lyrics || !window.fetch) return;

     var strip = box.querySelector('[data-role="chord-strip"]');
     var pop = document.querySelector('[data-role="chord-popover"]');
     var popName = pop && pop.querySelector('[data-role="chord-popover-name"]');
     var popFigure = pop && pop.querySelector('[data-role="chord-popover-figure"]');
     var popClose = pop && pop.querySelector('[data-role="chord-popover-close"]');
     var buttons = toArray(box.querySelectorAll('[data-role="chord-instrument"]'));
     var nameTemplate = box.getAttribute("data-label-diagram") || "%s";
     var unavailable = box.getAttribute("data-label-unavailable") || "";
     var openWord = box.getAttribute("data-label-open") || "0";
     var mutedWord = box.getAttribute("data-label-muted") || "x";
     var fretWord = box.getAttribute("data-label-fret") || "%s";

     /* Which instruments actually have a generated table. The JSON URLs are
        emitted by song.html behind `with`, so on a tree where the generator
        has never run there is no attribute, no fetch and no feature. */
     var urls = {};
     var available = [];
     ["ukulele", "guitar"].forEach(function (inst) {
       var url = box.getAttribute("data-chords-" + inst);
       if (url) {
         urls[inst] = url;
         available.push(inst);
       }
     });
     if (!available.length) return;

     /* Distinct chords, first-appearance order. The span text carries a
        trailing no-break space from the ChordPro renderer; empty spans sit
        on unchorded lines (every line gets a chord row, chorded or not) and
        N.C. is an instruction, not a chord. */
     var chords = [];
     var seen = {};
     var spans = toArray(lyrics.querySelectorAll(".ch"));
     spans.forEach(function (span) {
       var text = (span.textContent || "").replace(/[\s\u00a0]+/g, " ").trim();
       if (!text || text === "N.C." || text === "NC") return;
       span.setAttribute("data-chord", text);
       if (seen[text]) return;
       seen[text] = true;
       chords.push(text);
     });
     if (!chords.length) return;

     var state = {
       instrument: available.indexOf("ukulele") !== -1 ? "ukulele" : available[0],
       anchor: null
     };
     var tables = {};   /* instrument -> parsed JSON, or null once it failed */

     try {
       var saved = localStorage.getItem("chord-instrument");
       if (saved && available.indexOf(saved) !== -1) state.instrument = saved;
     } catch (e) {
       /* storage unavailable — ukulele it is */
     }

     /* ---- lookup ---- */

     /* An entry counts as usable only if it actually has a fretting. The
        generated tables carry a KEY for every chord name the notation can
        spell — hundreds of them — but a `frets: []` for the ones no shape
        was found for (Gb(maj7) and friends). Drawing those would produce a
        bare grid with no dots, which is not "unknown", it reads as a real
        chord you play by touching nothing. Treat them as absent so they
        fall through to the alias lookup and then to the honest placeholder. */
     function usable(entry) {
       return !!(entry && entry.frets && entry.frets.length);
     }

     function entryFor(name) {
       var table = tables[state.instrument];
       if (!table) return null;
       var byName = table.chords || {};
       if (usable(byName[name])) return byName[name];
       var alias = (table.aliases || {})[name];
       return (alias && usable(byName[alias]) && byName[alias]) || null;
     }

     function figureHtml(name) {
       var table = tables[state.instrument];
       if (!table) return "";
       var entry = entryFor(name);
       if (!entry) return "";
       return fretboxSvg(entry, table.strings || (entry.frets || []).length || 4);
     }

     /* A fretbox in words, because the SVG is aria-hidden and a label of
        "how to play C" over an invisible graphic answers nothing. The
        tuning array gives the string names, so this reads the way a person
        would say it out loud: "G open, C 2nd fret, E open, A open". Frets
        are absolute (base + row − 1), not grid rows — a row number is
        meaningless without the picture it belongs to. */
     function spellOut(name) {
       var table = tables[state.instrument];
       var entry = table && entryFor(name);
       if (!entry) return "";
       var tuning = table.tuning || [];
       var frets = entry.frets || [];
       var base = entry.base > 0 ? entry.base : 1;
       var parts = [];
       for (var i = 0; i < frets.length; i++) {
         /* Note names come out of the JSON as scientific pitch (G4, C4) —
            drop the octave digit, nobody says "G-four string". */
         var str = String(tuning[i] || i + 1).replace(/\d+$/, "");
         var f = frets[i];
         parts.push(
           str + " " +
             (f < 0 ? mutedWord : f === 0 ? openWord : fretWord.replace("%s", base + f - 1))
         );
       }
       return parts.join(", ");
     }

     /* ---- the row ----
        Built once, from the chord list, and revealed immediately — before
        any JSON has landed. Each tile ships its name and an empty figure
        box that CSS already gives its final height, so filling in the
        diagrams when the fetch resolves repaints inside the tiles and never
        moves the lyrics. One reveal, one shift, same as the autoscroll bar
        above it. */
     var tiles = {};

     function buildStrip() {
       chords.forEach(function (name) {
         var li = document.createElement("li");
         li.className = "chordbox__tile";
         var fig = document.createElement("span");
         fig.className = "chordbox__figure";
         /* The drawing is aria-hidden, so the tile carries the diagram in
            words instead — filled in by paintStrip once the table lands.
            Visually hidden, not display:none: it has to stay readable. */
         var spoken = document.createElement("span");
         spoken.className = "chordbox__spoken";
         var label = document.createElement("span");
         label.className = "chordbox__name";
         label.textContent = name;
         li.appendChild(fig);
         li.appendChild(label);
         li.appendChild(spoken);
         strip.appendChild(li);
         tiles[name] = { li: li, fig: fig, spoken: spoken };
       });
     }

     function paintStrip() {
       /* The table itself failed to load or arrived malformed. Every tile
          would go blank, which is twenty dashed boxes saying nothing —
          worse than no row. Fold the whole thing away and leave the lyrics
          exactly as they were, tappable chords included: the popover gives
          the same honest "no diagram" answer per chord. */
       if (!tables[state.instrument]) {
         box.setAttribute("hidden", "");
         return;
       }
       box.removeAttribute("hidden");

       chords.forEach(function (name) {
         var tile = tiles[name];
         if (!tile) return;
         var html = figureHtml(name);
         tile.fig.innerHTML = html;
         /* No diagram for this chord in this instrument's table: the tile
            stays, muted, holding the name. Dropping it would be worse —
            the row is a checklist of what the song needs, and a silent gap
            reads as "you already know this one". */
         tile.li.classList.toggle("is-blank", !html);
         tile.spoken.textContent = html
           ? nameTemplate.replace("%s", name) + ": " + spellOut(name)
           : nameTemplate.replace("%s", name) + ": " + unavailable;
       });
     }

     /* ---- the popover ----
        A positioned div in document coordinates, not the native Popover
        API: it has to be anchored to a chord that lives inside a lyric
        section, and those sections are `overflow-x: auto` + `contain:
        inline-size` scroll containers. A top-layer popover cannot be
        anchored to something inside one without anchor positioning (still
        not everywhere), and a plain absolute child of the section would be
        clipped at its edge. So site.js moves this element to <body> and
        places it at page coordinates: vertical scrolling — including
        autoscroll — carries it along for free, and it is never clipped. */

     /* Moving it out of .song-page leaves the songbook's accent behind:
        that colour arrives as an inline --accent-raw on .song-page, and
        main.css re-derives the contrast-floored tokens from it on any
        element carrying .has-accent. Carry both across, or the popover
        paints in the site's default fuchsia on every songbook. */
     if (pop && pop.parentNode !== document.body) {
       var page = pop.closest(".song-page");
       if (page) {
         var raw = page.style.getPropertyValue("--accent-raw");
         if (raw) {
           pop.style.setProperty("--accent-raw", raw);
           pop.classList.add("has-accent");
         }
       }
       document.body.appendChild(pop);
     }

     function closePop() {
       if (!pop || pop.hidden) return;
       pop.hidden = true;
       var anchor = state.anchor;
       state.anchor = null;
       if (anchor) anchor.classList.remove("is-open");
     }

     function openPop(span) {
       if (!pop) return;
       var name = span.getAttribute("data-chord");
       if (!name) return;

       /* Second tap on the same chord closes it — the affordance that makes
          this feel like a tooltip rather than a dialog you have to dismiss. */
       if (state.anchor === span && !pop.hidden) {
         closePop();
         return;
       }
       closePop();

       var html = figureHtml(name);
       popName.textContent = name;
       if (html) {
         /* The drawing plus the same words the strip's tiles carry — this
            box is a live region, so a sighted-plus-audio reader hears the
            chord they just tapped rather than silence. */
         popFigure.innerHTML = html + '<span class="chordbox__spoken">' + spellOut(name) + "</span>";
         popFigure.classList.remove("is-blank");
       } else {
         popFigure.textContent = unavailable;
         popFigure.classList.add("is-blank");
       }

       /* Measure after the content is in but before it is placed: the
          element is display:block while hidden only in the sense that
          [hidden] wins, so unhide first, then read its size. */
       pop.hidden = false;
       state.anchor = span;
       span.classList.add("is-open");

       var rect = span.getBoundingClientRect();
       var w = pop.offsetWidth;
       var h = pop.offsetHeight;
       var margin = 8;

       /* Horizontally centred on the chord, then pushed back inside the
          viewport — chords at the end of a line would otherwise hang off
          the right edge and widen the document. */
       var left = rect.left + rect.width / 2 - w / 2;
       var maxLeft = document.documentElement.clientWidth - w - margin;
       if (left > maxLeft) left = maxLeft;
       if (left < margin) left = margin;

       /* Below the chord by default, above it when there is no room below —
          the reader's finger is on the chord, so below is the side that
          isn't already covered. */
       var top = rect.bottom + 6;
       if (top + h > window.innerHeight - margin && rect.top - h - 6 > margin) {
         top = rect.top - h - 6;
       }

       pop.style.left = left + window.pageXOffset + "px";
       pop.style.top = top + window.pageYOffset + "px";

       /* Focus is deliberately NOT moved in. The anchor is a plain <span>,
          not a control, so there is nowhere to return focus to on close,
          and taking it would leave a keyboard user stranded mid-song. The
          close button is inside and reachable by Tab from wherever focus
          currently is; Escape works because that listener is on document. */
     }

     /* One delegated listener for every chord in the song rather than one
        per span — a long song has a few hundred of them. */
     lyrics.addEventListener("click", function (event) {
       var span = event.target.closest ? event.target.closest(".ch.is-tappable") : null;
       if (!span || !lyrics.contains(span)) return;
       openPop(span);
     });

     document.addEventListener("click", function (event) {
       if (!pop || pop.hidden) return;
       if (pop.contains(event.target)) return;
       if (event.target.closest && event.target.closest(".ch.is-tappable")) return;
       closePop();
     });

     document.addEventListener("keydown", function (event) {
       if (event.key === "Escape") closePop();
     });

     if (popClose) popClose.addEventListener("click", closePop);

     /* A lyric section scrolled sideways moves the chord out from under its
        popover, and the popover is anchored to the page, not the section.
        Rather than re-follow it, close: the reader is looking for the rest
        of the line, not for the diagram. Capture phase because `scroll`
        does not bubble. Page scroll is excluded — the popover rides that
        correctly, and autoscroll depends on it not closing. */
     document.addEventListener(
       "scroll",
       function (event) {
         var target = event.target;
         if (!pop || pop.hidden) return;
         if (!target || target.nodeType !== 1 || !target.closest) return;
         if (target.closest(".chordpro")) closePop();
       },
       true
     );

     /* ---- data ---- */

     function load(instrument, done) {
       if (tables.hasOwnProperty(instrument)) {
         done();
         return;
       }
       fetch(urls[instrument])
         .then(function (res) {
           return res.ok ? res.json() : null;
         })
         .then(function (data) {
           tables[instrument] = data && data.chords ? data : null;
           done();
         })
         .catch(function () {
           tables[instrument] = null;
           done();
         });
     }

     /* ---- the instrument switch ---- */

     function renderButtons() {
       buttons.forEach(function (btn) {
         var inst = btn.getAttribute("data-instrument");
         /* No table for this instrument on this build: hide the button
            rather than offer a switch that lands on an empty row. */
         btn.hidden = available.indexOf(inst) === -1;
         btn.setAttribute("aria-pressed", inst === state.instrument ? "true" : "false");
       });
       /* A switch with one option is just a label. */
       if (available.length < 2) {
         var group = box.querySelector(".chordbox__switch");
         if (group) group.hidden = true;
       }
     }

     buttons.forEach(function (btn) {
       btn.addEventListener("click", function () {
         var inst = btn.getAttribute("data-instrument");
         if (!inst || inst === state.instrument || available.indexOf(inst) === -1) return;
         state.instrument = inst;
         try {
           localStorage.setItem("chord-instrument", inst);
         } catch (e) {
           /* storage unavailable — the choice still holds for this page */
         }
         box.setAttribute("data-instrument", inst);
         renderButtons();
         closePop();
         /* Fetched on first switch only, then kept in memory: the page
            loads exactly one table and never both up front. */
         load(inst, paintStrip);
       });
     });

     /* ---- go ---- */

     buildStrip();
     renderButtons();
     box.setAttribute("data-instrument", state.instrument);
     box.removeAttribute("hidden");

     /* Chords become tappable only now, once there is something behind the
        tap. A class on the existing spans — the .cl/.clx alignment markup is
        never restructured.

        Deliberately NOT role="button" + tabindex="0", which was the first
        version and was worse. A song has one chord span per chorded word:
        this page has 34, a long one has a few hundred. Promoting each to a
        button puts every one of them in the tab order and in the
        screen-reader control list, so reaching the foot of the page by
        keyboard costs hundreds of stops and the song is announced as a wall
        of buttons. That is a real regression for the people it is supposed
        to help, traded against nothing: the chord row above holds a diagram
        for every chord in the song, is fully keyboard- and
        screen-reader-reachable, and reaching it is one Shift+Tab from the
        lyrics. Tapping a chord in the text is a pointer shortcut to
        something already available, not the only way there. */
     spans.forEach(function (span) {
       if (span.getAttribute("data-chord")) span.classList.add("is-tappable");
     });

     load(state.instrument, paintStrip);
   }

   document.addEventListener("DOMContentLoaded", function () {
     initTheme();
     initHome();
     initSongIndex();
     initAutoscroll();
     initChordDiagrams();
   });
})();
