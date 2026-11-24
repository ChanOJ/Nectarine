/* Nectarine archive: colour theme chooser (default theme), client-side search, the site's own
   small scripts (collapsible boxes) without the popups of the live site.
   Source: scripts/nec.js, copied to site/js/nec.js by scripts/statify.py (the theme list is filled in).
   No cookie: the chosen theme is kept in localStorage. No inline script needed (CSP friendly). */
(function () {
  "use strict";
  var THEMES = ["default", "gem", "amiga", "amiga13", "mini", "newspaper", "kohina", "irix", "beos", "atari8", "amiga2", "os", "pouet", "phpbb", "sand"];
  var KEY = "nec_theme";
  function load(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } }
  function store(k, v) {
    try { if (v === null) { window.localStorage.removeItem(k); } else { window.localStorage.setItem(k, v); } }
    catch (e) { /* storage disabled: the choice is simply not remembered */ }
  }
  function applyTheme(name) {
    if (THEMES.indexOf(name) < 0) { return; }
    var links = document.getElementsByTagName("link");
    for (var i = 0; i < links.length; i++) {
      var h = links[i].getAttribute("href") || "";
      var m = h.match(/^(.*\/)([a-z0-9]+)\.css$/);
      if (m && THEMES.indexOf(m[2]) >= 0) { links[i].setAttribute("href", m[1] + name + ".css"); }
    }
  }
  var current = load(KEY);
  if (current) { applyTheme(current); }

  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function fold(s) {
    s = String(s || "").toLowerCase();
    return s.normalize ? s.normalize("NFD").replace(/[\u0300-\u036f]/g, "") : s;
  }
  function param(name) {
    var m = window.location.search.match(new RegExp("[?&]" + name + "=([^&]*)"));
    return m ? decodeURIComponent(m[1].replace(/\+/g, " ")) : "";
  }
  var cache = {};
  function index(type, done) {
    if (cache[type]) { done(cache[type]); return; }
    var x = new XMLHttpRequest();
    x.open("GET", "/idx/" + type + ".json");
    x.onload = function () { if (x.status === 200) { cache[type] = JSON.parse(x.responseText); done(cache[type]); } };
    x.send();
  }
  function go(type, q) {
    window.location.href = "/nec-search.htm?t=" + encodeURIComponent(type) + "&q=" + encodeURIComponent(q);
  }

  document.addEventListener("DOMContentLoaded", function () {
    // Search fields of the pages: Enter or the button opens the results page
    var boxes = document.querySelectorAll(".nec-search");
    Array.prototype.forEach.call(boxes, function (box) {
      var input = box.querySelector("input[type=text], input[type=TEXT]") || box.querySelector("input");
      var sel = box.querySelector("select.nec-type");
      var btn = box.querySelector("input[type=button], input[type=BUTTON]");
      function run() {
        var t = sel ? sel.value : box.getAttribute("data-t");
        if (box.id === "nec-box") { show(t, input.value); } else { go(t, input.value); }
      }
      if (btn) { btn.addEventListener("click", run); }
      if (input) { input.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); run(); } }); }
    });
    var out = document.getElementById("nec-results");
    function show(type, q) {
      var words = fold(q).split(/\s+/).filter(Boolean);
      if (!out) { return; }
      if (!words.length) { out.innerHTML = ""; return; }
      out.innerHTML = "Searching...";
      index(type, function (rows) {
        var hits = rows.filter(function (r) {
          var t = fold(r[1] + " " + r[2] + " " + r[3]);
          return words.every(function (w) { return t.indexOf(w) >= 0; });
        });
        var html = "<p>" + hits.length + " result" + (hits.length > 1 ? "s" : "") + (hits.length > 300 ? " (300 shown)" : "") + "</p>";
        hits.slice(0, 300).forEach(function (r) {
          var title = r[0] ? '<a href="' + esc(r[0]) + '">' + esc(r[1]) + "</a>" : esc(r[1]);
          html += "<p>" + title + (r[2] ? " <span class=\"author\">" + esc(r[2]) + "</span>" : "") +
            (r[3] && type === "news" ? "<br>" + esc(r[3]) : "") + "</p>";
        });
        out.innerHTML = html;
      });
    }
    if (out) {
      var t = param("t") || "songs", q = param("q");
      var box = document.getElementById("nec-box");
      if (box) {
        var sel = box.querySelector("select.nec-type"); if (sel) { sel.value = t; }
        var inp = box.querySelector("input[type=TEXT], input[type=text]"); if (inp) { inp.value = q; }
      }
      if (q) { show(t, q); }
    }
    // Theme chooser page
    var tb = document.getElementById("nec-theme-go");
    if (tb) {
      var radios = document.querySelectorAll("input[name=nec-theme]");
      Array.prototype.forEach.call(radios, function (r) { r.checked = r.value === (current || "default"); });
      tb.addEventListener("click", function () {
        var c = document.querySelector("input[name=nec-theme]:checked");
        if (!c) { return; }
        store(KEY, c.value === "default" ? null : c.value);
        current = c.value;
        applyTheme(c.value);
      });
    }
  });
})();
