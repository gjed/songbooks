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

     function getPxPerSec() {
       return BASE_SPEED * Math.pow(SPEED_CURVE, state.level - 1);
     }

     function updateLevelDisplay() {
       if (levelDisplay) {
         levelDisplay.textContent = String(state.level);
       }
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
       });
     }

     updateLevelDisplay();
     updatePlayButton();
   }

   document.addEventListener("DOMContentLoaded", function () {
     initTheme();
     initHome();
     initSongIndex();
     initAutoscroll();
   });
})();
