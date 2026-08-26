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
     cannot see the data-theme attribute. So while the visitor is following
     the OS we leave the auto file alone (it is already correct, and it
     stays correct if they change the OS setting mid-session). The moment
     they make an explicit choice we point the link at the matching
     single-theme file instead.

     Every href comes from data attributes emitted by
     partials/head-icons.html through relURL, so nothing here hardcodes a
     path — baseURL is a subpath and this file must not know that. */
  function syncFavicon(theme) {
    var link = document.querySelector('link[data-role="favicon-svg"]');
    if (!link) return;

    var explicit = null;
    try {
      var saved = localStorage.getItem("theme");
      if (saved === "day" || saved === "night") explicit = saved;
    } catch (e) {
      /* storage unavailable — treat as "following the OS" */
    }

    var href = explicit
      ? link.getAttribute("data-icon-" + (theme === "night" ? "night" : "day"))
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

    /* No toggle on this page: there is still a saved choice to honour, so
       reconcile the icon once and stop. */
    if (!toggles.length) {
      syncFavicon(currentTheme());
      return;
    }

    function render() {
      var theme = currentTheme();
      toggles.forEach(function (btn) {
        var label = theme === "night" ? btn.getAttribute("data-label-day") : btn.getAttribute("data-label-night");
        if (label) btn.textContent = label;
        btn.setAttribute("aria-pressed", theme === "night" ? "true" : "false");
      });
      syncFavicon(theme);
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

  document.addEventListener("DOMContentLoaded", function () {
    initTheme();
    initHome();
    initSongIndex();
  });
})();
