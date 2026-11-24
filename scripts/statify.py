#!/usr/bin/env python3
"""Statify Nectarine (www.scenemusic.net / nectarine.ojuice.net, demoscene radio, 2000-2006) into plain static HTML.

    python3 -I scripts/statify.py [--out site] [--raw PATH]

Reads ONLY the shared raw store of the id3/id3x sites (`RAW`, default ~/Code/id3x/raw, never
written): the skin `id3/z/n/`, the user media `id3/zi/` and the SQLite extractions of the
NECTARINE and OJUICE databases (`db/NECTARINE.sqlite`, `db/OJUICE.sqlite`). The output folder is
emptied and rebuilt on every run; the output is deterministic (sorted traversal, stable SQL
ordering, no timestamps).

How it works (docs/data-model.md):
  * `id3render/engine.py` reimplements the id3 template engine ($$MACRO$$ language, includes,
    loops, filters, image relocation) and `id3render/nec.py` the data macros of the site over
    SQLite (SQL of id3/nec_exec.asp and nec_queries.asp), with the server clock frozen at NOW;
  * the site is crawled like a visitor would: from the home page, every internal link of every
    rendered page is resolved to (template, path, query) as IIS + id3 did, rendered, and its
    links followed. Pages whose URL carried a query string get a static name
    (`/info.htm?idsong=51362` -> `/info-song51362.htm`), listed in build-meta/url-map.json for
    the Edge Script;
  * forms, logins, votes, requests, counters and third-party scripts are removed (an "archived"
    notice or plain text replaces them), the radio streams are frozen as offline, searches become
    client-side (/js/nec.js + /idx/*.json);
  * personal data is redacted at the source (nec.py `redact`) and again in the output (e-mails).

The 16 colour themes of the site (`*.css`, chosen per account) are switched in the browser by
/js/nec.js (localStorage, no cookie): every page is rendered once, with the default theme.
Python 3.9+, standard library only. Pages are written in iso-8859-1 like the original.
"""
import argparse
import fnmatch
import hashlib
import html
import json
import os
import re
import shutil
import sys
import zlib
from collections import deque
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "id3render"))
import engine  # noqa: E402
import nec     # noqa: E402

engine.URL_ENCODING = "cp1252"     # id3 classic ASP: Server.URLEncode in the page codepage

# --- settings ---------------------------------------------------------------------------------
RAW = Path(os.environ.get("ID3X_RAW", "~/Code/id3x/raw")).expanduser()   # the one raw-path setting
REPO = Path(__file__).resolve().parent.parent
ENC = "iso-8859-1"
NOW = datetime(2006, 9, 7, 23, 59, 59)     # server clock: last day of the NECTARINE database (2006-09-07)
HOST = "www.scenemusic.net"
OWN_HOSTS = ("www.scenemusic.net", "scenemusic.net", "www.scenemusic.org", "scenemusic.org", "nectarine.ojuice.net",
             "nectarine.scenemusic.net")
DEFAULT_SKIN = "n"
SKINS = ["n"]
FALLBACK = {}
MASK = "????"
ARCHIVED = "/archived.htm"
SEARCH_PAGE = "/nec-search.htm"
JS = "/js/nec.js"
META_CHARSET = '<META http-equiv="Content-Type" content="text/html; charset=iso-8859-1">'
# Colour themes of z/n (nectarine_skin of the account -> stylesheet), switched by /js/nec.js
THEMES = [("default", "Default"), ("gem", "GEM"), ("amiga", "Amiga 2.0"), ("amiga13", "Amiga 1.3"), ("mini", "Mini"),
          ("newspaper", "Newspaper"), ("kohina", "Kohina"), ("irix", "Irix"), ("beos", "BeOS"), ("atari8", "Atari 8-bit"),
          ("amiga2", "Amiga 2"), ("os", "OS"), ("pouet", "Pouet"), ("phpbb", "phpBB"), ("sand", "Sand")]

# ---- removal-request footer (same as the other archives): nearly every Nectarine page shows
# nicknames (oneliner, requests, votes, comments, charts, birthdays), so every page gets it.
REMOVAL_MARK = 'id="removal-note"'
REMOVAL_NOTE = (
    '<div id="removal-note" style="clear:both;margin:28px auto 8px;padding:6px 8px 0;width:60%;'
    'border-top:1px solid #808080;text-align:center;font:10px/14px Verdana,Arial,Helvetica,sans-serif;'
    'color:#808080;background:transparent">To be removed from this page, '
    '<a href="mailto:chandra_oj@pm.me" style="color:#808080;text-decoration:underline">contact me</a>.</div>'
)
_BODY_END = re.compile(r"(?is)</body\s*>(?!.*</body\s*>)")


def add_removal_note(text):
    if REMOVAL_MARK in text:
        return text
    m = _BODY_END.search(text)
    if m:
        return text[: m.start()] + REMOVAL_NOTE + "\n" + text[m.start():]
    return text + "\n" + REMOVAL_NOTE + "\n"


# Templates of write paths, logins, admin, counters, member-only pages and dead services: never
# rendered; links to them go to /archived.htm.
REMOVED = {
    "account.htm", "addfav.htm", "addlinks.htm", "addlinksok.htm", "addnews.htm", "addsession.htm", "adm_links.htm",
    "admin.htm", "answer.htm", "brokenlink.htm", "checkup.htm", "close.htm", "contact.htm", "delete.htm", "dcnews.htm",
    "dnews.htm", "editnews.htm", "editsong.htm", "fav.htm", "favreq.htm", "favreq2.htm", "favreq3.htm", "fixdb.htm",
    "form_contact_ok.htm", "fullstats.htm", "golink.htm", "guestbook.htm", "in.htm", "inbox.htm", "inbox_del.htm",
    "inbox_read.htm", "inprogress.htm", "irc.htm", "lastinserted.htm", "listeners.htm", "locked.htm", "login_pass.htm",
    "login_passok.htm", "loginlist.htm", "logout.htm", "memberlist.htm", "message_popup.htm", "message_write.htm",
    "move.htm", "myinprogress.htm", "newsvalidate.htm", "nick_edit.htm", "ok.htm", "pending.htm", "pending2.htm",
    "personaldbc.htm", "personaldbf.htm", "personaldbi.htm", "personaldbl.htm", "personaldbr.htm", "personaldbv.htm",
    "rename.htm", "reported.htm", "req.htm", "reqdj.htm", "sam.htm", "sam2.htm", "sendsession.htm", "test.htm",
    "teststats.htm", "updatevalidationprocess.htm", "updmember.htm", "upload.htm", "validation2.htm", "validation3.htm",
    "vote.htm", "voteerror.htm", "voteok.htm", "votepopup.htm", "xchange.htm", "refused.htm", "quarion.htm",
    "nodemo.htm", "noplatform.htm", "plshistory.htm", "stats.htm", "stats2.htm", "queue.htm", "infokb.htm", "listtable.htm",
}
# Query parameters that select content (kept, in this order, in the static name); paging
# parameters (<LOOP>pg) are kept too. Every other parameter is dropped.
QUERY_KEYS = {"idsong": "song", "id": "id", "author": "author", "cat": "cat", "y": "y", "m": "m", "d": "d"}
# Parameters of the original searches: the link goes to the client-side search page
SEARCH_KEYS = {"recherche": "songs", "sl": None, "q": None}
# The stream relays of the radio (gone): links to them are removed, like any .pls playlist
RELAY_HOSTS = ("ipsyn.net", "oulu.fi", "alldas.org", "esuna.co.uk", "sexes.ch", "scenemusic.eu", "streamer.org")
DEAD_HOSTS = RELAY_HOSTS + ("mirabilis.com", "icq.com", "google-analytics.com", "googlesyndication.com", "amazon.com",
              "paypal.com", "soundbomb.net")


# Pictures the final skin references but lacks (broken on the live site): the copy of the older skin
ASSET_FALLBACK = {"/z/n/data/spacer_002.gif": "/z/nectarinev4/data/spacer_002.gif"}


EXCLUDE_GLOBS = [g.strip() for g in (REPO / "scripts" / "exclude-globs.txt").read_text(encoding="utf-8").splitlines()
                 if g.strip() and not g.startswith("#")]


def excluded(path):
    """A path that scripts/exclude-globs.txt forbids: never copied, the link is removed."""
    rel = path.lstrip("/")
    for g in EXCLUDE_GLOBS:
        if g.endswith("/"):
            if rel.startswith(g) or ("/" + g) in ("/" + rel):
                return True
        elif "/" in g:
            if rel == g:
                return True
        elif fnmatch.fnmatchcase(rel.rsplit("/", 1)[-1], g):
            return True
    return False


def slug(s):
    """File-name form of a free-text value (author names): ASCII letters and digits, a short hash
    when the text is not already a plain lower-case slug (keeps distinct authors apart)."""
    t = re.sub(r"[^a-z0-9]+", "-", engine.vire_accents(s).lower()).strip("-")[:40].strip("-") or "x"
    return t if t == s else f"{t}-{zlib.crc32(s.encode('cp1252', 'replace')) & 0xffffff:06x}"


# --- archive pages (rendered in the skin's layout like any template) -------------------------------
FRAME = """$$DYN:ID3:NOFOOTER$$
$$SET:PAGE:TITLE=Nectarine - %(title)s$$
$$INCL:CL-META.HTM$$
$$INCL:CL-MENU.HTM$$
<table class="tablecontent">
<tr>
<td class="leftcontent">
	$$INCL:BL-LASTSONGS.HTM$$
</td>
<td class="centercontent">
<div class="modulebig">
<div class="moduleTitlebig">%(title)s</div>
<div class="moduleContentbig">
%(body)s
</div>
</div>
</td>
</tr>
</table>
<table class="tablefooter">
<tr>
<td class="footer">
$$INCL:CL-FOOTER.HTM$$
</td>
</tr>
</table>
</body>
</html>
"""
OFF_AIR = ('<span class="warning">Nectarine is off the air: the radio stopped in September 2006. '
           'Below, the last song it played and the next one in the queue.</span><br/><br/>')
ARCHIVE_NOTE = ("This is a static, read-only archive of Nectarine, the demoscene radio (www.scenemusic.net, 2000-2006). "
                "The radio streams, logins, requests, votes, comments, uploads and the oneliner are no longer available.")


def virtual_pages(skins):
    themes = "".join(f'<INPUT type="radio" name="nec-theme" value="{k}"> {t}<BR>' for k, t in THEMES)
    pages = {
        "archived.htm": ("Archive", f'{ARCHIVE_NOTE}<BR><BR><A href="/index.htm">Back to the home page</A>'),
        "themes.htm": ("Themes", '<DIV id="nec-themes">Choose the colours of the archive (kept in this browser, '
                       f'no cookie):<BR><BR>{themes}<BR><INPUT type="button" id="nec-theme-go" value="Use this theme"></DIV>'),
        "nec-search.htm": ("Search",
                           '<SPAN class="nec-search" id="nec-box" data-t="songs"><SELECT class="nec-type">'
                           '<OPTION value="songs">songs</OPTION><OPTION value="authors">authors</OPTION>'
                           '<OPTION value="news">news</OPTION></SELECT> '
                           '<INPUT type="TEXT" size=30 maxlength=100 value=""> <INPUT type="BUTTON" value="go"></SPAN>'
                           '<NOSCRIPT><BR>The search of the archive needs JavaScript.</NOSCRIPT><DIV id="nec-results"></DIV>'),
        "404.htm": ("Not found", "This page is not in the archive.<BR><BR>"
                    f'{ARCHIVE_NOTE}<BR><BR><A href="/index.htm">Back to the home page</A>'),
    }
    return {k: FRAME % {"title": t, "body": b} for k, (t, b) in pages.items()}


def page_key(path, query):
    """Canonical (path, query items) of an internal page request."""
    return path, tuple(sorted(query.items()))


def static_name(path, query):
    """Static file path of a page request: query parameters folded into the file name."""
    if not query:
        return path
    stem, dot, ext = path.rpartition(".")
    parts = []
    for k in QUERY_KEYS:
        if k in query:
            parts.append(QUERY_KEYS[k] + (slug(query[k]) if k == "author" else query[k]))
    for k, v in sorted(query.items()):
        if k.endswith("pg"):
            parts.append("p" + v)
    return f"{stem}-{'-'.join(parts)}.{ext}"


class Site:
    def __init__(self, args, skin, prefix, macros, skins):
        self.args, self.skin, self.prefix, self.macros, self.skins = args, skin, prefix, macros, skins
        fallback = FALLBACK.get(skin)
        self.files = engine.SkinFiles(RAW / "id3" / "z", skin, fallback,
                                      virtual_pages(skins) if fallback or skin == DEFAULT_SKIN else None)
        if not (fallback or skin == DEFAULT_SKIN):
            # v2 / scene.org: the archive pages use the default skin's frame
            self.files.virtual = {}
            self.vfiles = engine.SkinFiles(RAW / "id3" / "z", DEFAULT_SKIN, None, virtual_pages(skins))
        self.pages = {}            # static path -> html
        self.seen = {}             # page key -> static path (or None: not a page)
        self.queue = deque()
        self.redirects = {}        # static path of a page that redirected -> target
        self.assets = set()        # /z/... and /zi/... paths referenced
        self.unlinked = []
        self.dropped = []
        self.url_map = {}          # original URL with query -> static path
        self.unknown_filters = set()

    # -- requests -----------------------------------------------------------------------------
    def resolve(self, url, base):
        """(new_url, why) for a link found in a page at original path `base` (memoized)."""
        key = (url, base if not url.startswith("/") or url.startswith("//") else "")
        memo = self.__dict__.setdefault("_memo", {})
        r = memo.get(key)
        if r is None:
            r = self._resolve(url, base)
            if r[1] in ("ok", "external", "search") and not (r[0] or "").startswith("/archived") or r[0] is None:
                memo[key] = r
        return r

    def _resolve(self, url, base):
        url = html.unescape(url.strip())
        if not url or url.startswith("#"):
            return url, "ok"
        low = url.lower()
        if re.match(r"(?i)^ftp://[^/@\s]*:[^/@\s]*@", url):
            return None, "credentials in URL"
        if low.startswith(("javascript:", "mailto:", "news:", "ftp:", "irc:", "telnet:")):
            return url, "external"
        if low.startswith("//"):
            url = "http:" + url
        try:
            sp = urlsplit(urljoin("http://%s%s" % (HOST, base), url))
            sp.hostname
        except ValueError:
            return None, "malformed URL"
        host = (sp.hostname or "").lower()
        if host not in OWN_HOSTS:
            if host in ("forums.scenemusic.net", "forums.scenemusic.org"):
                return None, "forums not archived"
            if any(host == h or host.endswith("." + h) for h in DEAD_HOSTS):
                return None, "dead third party"
            return url, "external"
        path = re.sub(r"/{2,}", "/", unquote(sp.path) or "/")
        if re.match(r"^/skin/[^/]+/", path):      # a link to another skin of the archive (skins page)
            return path, "ok"
        query = {k.lower(): v for k, v in parse_qsl(sp.query, keep_blank_values=True, encoding="cp1252", errors="replace")}
        frag = "#" + sp.fragment if sp.fragment else ""
        if re.match(r"(?i)^/z/[^/]+/[^/]+\.html?$", path):
            return self.page("/" + path.rsplit("/", 1)[-1], query, frag)    # a template served by its skin path
        if path.startswith(("/z/", "/zi/")) or re.search(r"\.(gif|jpe?g|png|css|js|swf|ico|zip|rar|txt|mid|mod|xm|mp3|avi|bmp)$", path, re.I):
            return self.asset(path), "ok" if self.asset(path) else "missing asset"
        return self.page(path, query, frag)

    def asset(self, path):
        memo = self.__dict__.setdefault("_amemo", {})
        if path not in memo:
            memo[path] = self._asset(path)
        if memo[path]:
            self.assets.add(memo[path])
        return memo[path]

    def real_case(self, rel):
        """The on-disk spelling of a raw path (IIS was case-insensitive, bunny.net is not), or None."""
        cache = self.__dict__.setdefault("_dirs", {})
        cur, parts = RAW / "id3", []
        for seg in rel.strip("/").split("/"):
            if cur not in cache:
                cache[cur] = {n.lower(): n for n in sorted(os.listdir(cur))} if cur.is_dir() else {}
            name = cache[cur].get(seg.lower())
            if name is None:
                return None
            parts.append(name)
            cur = cur / name
        return "/" + "/".join(parts) if cur.is_file() else None

    def _asset(self, path):
        """Published path of a skin or media file referenced by a page, in its on-disk spelling."""
        if path.lower().endswith((".rar", ".exe", ".pls")) or excluded(path):
            return None             # archives that cannot be checked for executables, playlists, private files
        if path.startswith(("/z/", "/zi/")):
            cands = [path]
            m = re.match(r"^/z/[^/]+/(.*)$", path)
            if m:                   # a picture missing from the skin: the default skin's copy
                cands.append(f"/z/{DEFAULT_SKIN}/{m.group(1)}")
        else:                       # any other file: id3 (cgi/404.asp) served the skin file of that name
            cands = [f"/z/{self.skin}/{path.lstrip('/')}", f"/z/{self.skin}/{path.rsplit('/', 1)[-1]}"]
        cands += [ASSET_FALLBACK[c] for c in cands if c in ASSET_FALLBACK]
        for c in cands:
            if excluded(c):
                return None
            real = self.real_case(c)
            if real:
                return real
        return None

    def golink(self, path, query):
        """golink.htm?id=&url= (click counter + redirect): the link goes straight to its target."""
        url = query.get("url")
        if not url and re.fullmatch(r"\d+", query.get("id", "")):
            url = self.macros.db.scalar("SELECT url FROM oj.LINKS WHERE id = ? AND isactive = 1", (int(query["id"]),))
        if not url:
            return None, "redirector without target"
        url = url.strip()
        if re.match(r"(?i)^(mailto:)?[\w.+-]+@[\w.-]+$", url):
            return None, "e-mail target"
        if re.match(r"(?i)^www\.", url):
            url = "http://" + url
        return self.resolve(url, "/")

    def page(self, path, query, frag=""):
        if path.endswith("/"):
            path += "index.htm"
        path = path.lower()
        name = path.rsplit("/", 1)[-1]
        if name in ("index.html", "default.htm", "default.asp"):
            path, name = path[: -len(name)] + "index.htm", "index.htm"
        if not name.endswith((".htm", ".html")):
            return None, "not a page"
        for k, kind in SEARCH_KEYS.items():
            if query.get(k):
                return self.prefix + (SEARCH_PAGE + f"?t={kind}" if kind else ARCHIVED), "search"
        if name == "golink.htm":
            return self.golink(path, query)
        if name in REMOVED:
            return self.prefix + ARCHIVED, "ok"
        if name == "research.htm" and not query.get("author"):
            return SEARCH_PAGE, "search"       # song searches: client-side
        if name == "chartsuser.htm" and query.get("id") == "6":
            return self.prefix + ARCHIVED, "ok"    # the list of donors is not published
        if self.files.find(name) is None and not (hasattr(self, "vfiles") and self.vfiles.find(name) == name):
            return None, "no template"
        if "REP:" not in (self.files.load(name) or "REP:"):
            path = "/" + name       # the template ignores the folders of its URL: one page
        q = {}
        for k, v in query.items():
            if k == "author" and v.strip():
                q[k] = self.macros.canonical_author(v.strip()) if name in ("research.htm", "authorinfo.htm") else v.strip()
            elif k in QUERY_KEYS and v.strip() and re.fullmatch(r"-?\d+", v.strip()):
                q[k] = v.strip()
            elif k.endswith("pg") and re.fullmatch(r"\d+", v.strip() or "x") and int(v) > 1:
                q[k.lower()] = str(int(v))
        key = page_key(path, q)
        if key not in self.seen:
            self.seen[key] = static_name(path, q)
            self.queue.append((path, q))
        target = self.seen[key]
        if target is None:
            return None, "not rendered"
        target = self.redirects.get(target, target)
        return self.prefix + target + frag, "ok"

    # -- crawl ---------------------------------------------------------------------------------
    def crawl(self, seeds, query_seeds=()):
        for s in seeds:
            self.page(s, {})
        for s, q in query_seeds:
            self.page(s, q)
        while self.queue:
            path, q = self.queue.popleft()
            if len(self.pages) % 2000 == 1999:
                print(f"  {self.skin}: {len(self.pages) + 1} pages, {len(self.queue)} queued", flush=True)
            out = static_name(path, q)
            req = engine.Request(path, q)
            files = self.vfiles if hasattr(self, "vfiles") and self.vfiles.virtual.get(req.page_name) else self.files
            pg = engine.Page(files, self.macros, req, {"host": HOST, "now": NOW, "locale": "fr"})
            text = pg.render(req.page_name)
            self.unknown_filters |= pg.unknown_filters
            if text is None:
                self.seen[page_key(path, q)] = None
                continue
            if pg.out_of_range and pg.out_of_range.lower() in q:
                canon = {k: v for k, v in q.items() if k != pg.out_of_range.lower()}
                tgt = self.page(path, canon)[0]
                self.redirects[out] = tgt[len(self.prefix):] if tgt else "/index.htm"
                continue
            used = {k for k in q if k in req.used}
            if used != set(q):   # a parameter the page does not read: same page as without it
                canon = {k: v for k, v in q.items() if k in used}
                tgt = self.page(path, canon)[0]
                self.redirects[out] = tgt[len(self.prefix):] if tgt else "/"
                continue
            if pg.redirect:
                tgt, _ = self.page(pg.redirect, {})
                self.redirects[out] = (tgt or "/index.htm")[len(self.prefix):]
                continue
            self.pages[out] = (path, q, text)
            for am in self.ATTR_RE.finditer(remove_dead_scripts(text)):
                self.resolve(next(g for g in am.groups()[1:] if g is not None), path)
        # links are rewritten once every page is known (redirect targets resolved)
        self._memo = {}
        done = {}
        for out in sorted(self.pages):
            path, q, text = self.pages[out]
            done[out] = self.finalize(text, path, out)
            if q:
                self.url_map[path + "?" + urlencode(sorted(q.items()))] = out
        if self.queue:
            raise RuntimeError(f"pages found only while rewriting links: {list(self.queue)[:5]}")
        self.pages = done

    # -- output rewriting --------------------------------------------------------------------------
    ATTR_RE = re.compile(r"""(?is)\b(href|src|background|action|lowsrc)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""")
    TAG_RE = re.compile(r"(?s)<([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>")

    def finalize(self, text, base, out):
        text = remove_dead_scripts(text)
        # the colour themes (chosen per account on the live site): a link in the top menu
        text = text.replace('<a href="/credits.htm">Credits</a>',
                            '<a href="/credits.htm">Credits</a>\r\n&nbsp;&raquo;&nbsp;<a href="/themes.htm">Themes</a>', 1)
        # "On air": the stream relays are gone, the box says so
        text = re.sub(r'(?is)<span class="subject">Main Relays, Click on a flag.*?<br/><br/>', OFF_AIR, text)
        # the "help Nectarine" donation popup, shown once per visitor through a cookie
        text = re.sub(r"(?is)<script\b[^>]*>(?:(?!</script).)*dejapopup.*?</script\s*>", "", text)
        text = neutralize_forms(text, self, out)
        text = redact_emails(text)
        text = self.rewrite_links(text, base, out)
        text = self.sweep_own_host(text, base)
        text = redact_emails(text)
        text = re.sub(r"/\*setTimeout\(.*?\*/", "", text)     # the disabled auto-refresh of every page
        text = mask_ips(text)
        text = re.sub(r"(?i)(charset\s*=\s*)(?:windows-1252|cp1252|us-ascii|(?=[\"'>\s]))", r"\1iso-8859-1", text)
        if JS not in text:
            tag = f'<SCRIPT src="{JS}"></SCRIPT>\r\n'
            i = text.lower().rfind("</body>")
            text = text[:i] + tag + text[i:] if i >= 0 else text + "\r\n" + tag
        if not re.search(r"(?i)charset\s*=", text):
            m = re.search(r"(?i)<head[^>]*>", text) or re.search(r"(?i)<html[^>]*>", text)
            text = text[:m.end()] + "\r\n" + META_CHARSET + text[m.end():] if m else META_CHARSET + "\r\n" + text
        return text

    OWN_URL_RE = re.compile(r"(?i)https?://(?:(?:www\.)?scenemusic\.(?:net|org)|nectarine\.ojuice\.net)(?::80)?(?:/[^\s\"'<>)]*)?")

    def sweep_own_host(self, text, base):
        """http://www.scenemusic.net/... left in tags, handlers and scripts (status bar texts,
        window.open...) -> archive path. Plain text mentions of the address stay as they are."""
        def fn(m):
            new, why = self.resolve(m.group(0), base)
            return new if new and why != "external" else "/index.htm"

        def inside(m):
            return self.OWN_URL_RE.sub(fn, m.group(0))
        text = re.sub(r"(?is)<script\b.*?</script\s*>", inside, text)
        return re.sub(r"(?s)<[a-zA-Z][^<>]*>", inside, text)

    def rewrite_links(self, text, base, out):
        def anchor(m):
            open_tag, label = m.group(1), m.group(2)
            hm = re.search(r"""(?is)\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""", open_tag)
            if not hm:
                return m.group(0)
            val = next(g for g in hm.groups() if g is not None)
            new, why = self.resolve(val, base)
            if new is None:
                self.unlinked.append((out, val, why))
                return label
            return m.group(0)
        text = outside_scripts(text, lambda t: re.sub(r"(?is)(<a\b[^>]*>)(.*?)</a\s*>", anchor, t))

        def tag(m):
            name, attrs = m.group(1).lower(), m.group(2)
            drop = []

            def one(am):
                val = next(g for g in am.groups()[1:] if g is not None)
                new, why = self.resolve(val, base)
                if why == "external":
                    if am.group(1).lower() in ("src", "background", "lowsrc") and re.match(r"(?i)^\s*(https?:)?//", val):
                        drop.append(val)
                    if new != html.unescape(val.strip()):     # a redirector resolved to its target
                        return '%s="%s"' % (am.group(1), html.escape(new, quote=True).replace("&#x27;", "'"))
                    return am.group(0)
                if new is None:
                    self.unlinked.append((out, val, why))
                    drop.append(val)
                    return ""
                return '%s="%s"' % (am.group(1), html.escape(new, quote=True).replace("&#x27;", "'"))
            new_attrs = self.ATTR_RE.sub(one, attrs)
            if drop and name in ("img", "embed", "script", "input", "iframe", "frame", "bgsound"):
                self.dropped.append((out, "%s %s" % (name, drop[0][:80])))
                return "" if name != "script" else "<script>"
            if drop:
                new_attrs = re.sub(r"""(?is)\b(src|background|lowsrc)\s*=\s*(?:"(?:https?:)?//[^"]*"|'(?:https?:)?//[^']*'|(?:https?:)?//[^\s"'>]+)""",
                                   "", new_attrs)
            return "<%s%s>" % (m.group(1), new_attrs)
        text = outside_scripts(text, lambda t: self.TAG_RE.sub(tag, t))
        text = re.sub(r"(?is)<script>\s*</script\s*>", "", text)

        def lit(m):     # image file names in scripts and event handlers (rollovers)
            val = m.group(2)
            if re.match(r"(?i)^(https?:)?//", val) and not self.OWN_URL_RE.match(val):
                return m.group(0)
            new, why = self.resolve(val, base)
            return m.group(1) + new + m.group(1) if new and why == "ok" else m.group(0)
        return re.sub(r"""(["'])([^"'<>\s()]+\.(?:gif|jpe?g|png|swf))\1""", lit, text, flags=re.I)


# --- page clean-up --------------------------------------------------------------------------------
def outside_scripts(text, fn):
    parts = re.split(r"(?is)(<script\b.*?</script\s*>)", text)
    return "".join(p if i % 2 else fn(p) for i, p in enumerate(parts))


ICQ_RE = re.compile(r"(?is)<A href=\"?http://wwp\.mirabilis\.com/scripts/Search\.dll\?to=(\d+)\"?>(.*?)</A>")


def icq_badges(text, skin, sheet):
    """The live ICQ status flower (online.mirabilis.com, gone) becomes the skin's own neutral
    flower p/icq3.gif (its commented-out fallback), the number as tooltip; on a people sheet the
    number is also written out."""
    def fn(m):
        img = re.search(r"(?i)<IMG[^>]*\bwidth=(\d+)[^>]*\bheight=(\d+)", m.group(2))
        w, h = img.groups() if img else ("13", "13")
        badge = (f'<IMG src="/z/{skin}/p/icq3.gif" width={w} height={h} align=top border=0 '
                 f'alt="ICQ #{m.group(1)}" title="ICQ #{m.group(1)}">')
        return f"{badge} <FONT class=aslink>{m.group(1)}</FONT>" if sheet else badge
    return ICQ_RE.sub(fn, text)


def remove_dead_scripts(text):
    """Banner scripts, the logged-in box (tablogged.js), stats beacons and other dynamic scripts.
    The ICQ status badge (people sheets) becomes the ICQ number as text."""

    text = re.sub(r"(?is)<script\b[^>]*\bsrc\s*=\s*[\"']?[^\"'>]*(?:banner\d*\.js|tablogged\.js|/cgi/)[^>]*>.*?</script\s*>", "", text)
    text = re.sub(r"(?is)<script\b[^>]*\bsrc\s*=\s*[\"']?https?://[^>]*>.*?</script\s*>", "", text)
    return text


FORM_RE = re.compile(r"(?is)<form\b([^>]*)>(.*?)</form\s*>")
CONTROL_RE = re.compile(r"(?is)<input\b[^>]*>|<select\b.*?</select\s*>|<textarea\b.*?</textarea\s*>|<button\b.*?</button\s*>")
SEARCH_TYPES = [("news", "news, article, jobs"), ("pictures", "picture/photo"), ("people", "scener"), ("groups", "group"),
                ("parties", "party")]


def neutralize_forms(text, site, out):
    """No <form> survives. Search forms become client-side fields (/js/nec.js); forms that write
    (POST, hidden `u=` macro: votes, attendance, edits) keep their content without controls and
    get an 'archived' notice; leftover unpaired form tags are removed."""
    def fn(m):
        attrs, inner = m.group(1), m.group(2)
        if re.search(r"(?i)action\s*=\s*[\"']?olhistory\.htm", attrs):
            return oneliner_nav(site, out)  # the day picker of the oneliner history: links instead
        if re.search(r"(?is)<input\b[^>]*type\s*=\s*[\"']?password", inner):
            site.dropped.append((out, "login form"))
            return ""               # login box: nothing left of it
        if re.search(r"(?i)action\s*=\s*[\"']?https?://", attrs):
            site.dropped.append((out, "external form"))
            return ""               # donations (PayPal), newsletter subscription: gone with the site
        names = {n.lower() for n in re.findall(r"""(?i)\bname\s*=\s*["']?([^"'\s>]+)""", inner)}
        if re.search(r"(?is)<select\b[^>]*name\s*=\s*[\"']?cat\b", inner) and "kw" in names:
            # the "search in" box of every page: a type list and a keyword field
            opts = "".join(f'<OPTION value="{v}">- {t}' for v, t in SEARCH_TYPES)
            inner = re.sub(r"(?is)<select\b([^>]*)>.*?</select\s*>",
                           lambda sm: f'<SELECT class="oj-type"{re.sub(r"(?i)name=[^ >]+", "", sm.group(1))}>{opts}</SELECT>', inner, count=1)
            inner = re.sub(r"(?is)<input\b([^>]*name\s*=\s*[\"']?kw\b[^>]*)>",
                           lambda im: '<INPUT type="TEXT"' + re.sub(r"(?i)\b(type|name|value|onfocus)\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", im.group(1)) + ">", inner)
            inner = re.sub(r"(?is)<input\b[^>]*type\s*=\s*[\"']?(?:hidden|submit|image)[^>]*>", "", inner)
            inner = inner.replace('<INPUT type="TEXT"', '<INPUT type="TEXT" data-oj-kw="1"', 1)
            return inner
        kind = next((v for k, v in SEARCH_KEYS.items() if k in names and v), None)
        is_write = re.search(r"(?i)method\s*=\s*[\"']?post", attrs) or "u" in names or "page_ok" in names
        if kind and not is_write:
            return search_widget(kind)      # the song search box: client-side search of the archive
        act = (re.search(r"""(?i)action\s*=\s*["']?([^"'\s>]+)""", attrs) or [None, ""])[1]
        site.dropped.append((out, "form " + (act or attrs.strip()[:60])))
        had_submit = re.search(r"(?is)<input\b[^>]*type\s*=\s*[\"']?(?:submit|image|button)|<button\b", inner)
        inner = CONTROL_RE.sub("", inner)
        if had_submit:
            inner += '<FONT class=discreet>[ <A href="%s">archived</A>: this form is no longer available ]</FONT>' % ARCHIVED
        return inner
    text = FORM_RE.sub(fn, text)
    text = re.sub(r"(?is)</?form\b[^>]*>", "", text)
    # scripts of the removed forms (find(), focus())
    text = re.sub(r"(?is)<script[^>]*>\s*<!--\s*function find\(\).*?</script\s*>", "", text)
    return re.sub(r"(?is)<script[^>]*>\s*<!--\s*document\.\w+\.\w+\.focus\(\);?\s*//\s*-->\s*</script>", "", text)


MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def oneliner_url(day):
    y, m, d = day     # the URL of the live site (the crawl gives it its static name)
    return f"/olhistory.htm?m={m}&amp;d={d}&amp;y={y}"


def oneliner_nav(site, out):
    """Day picker of /olhistory.htm (a GET form): previous and next day with messages, and the
    list of all days (/olhistory-days.htm)."""
    days = site.macros.oneliner_days()
    mm = re.search(r"-y(\d+)-m(\d+)-d(\d+)\.htm$", out)
    links = []
    if mm:
        cur = tuple(int(x) for x in mm.groups())
        before = [d for d in days if d < cur]
        after = [d for d in days if d > cur]
        if before:
            links.append(f'<a href="{oneliner_url(before[-1])}">&lt; {before[-1][2]:02d}/{before[-1][1]:02d}/{before[-1][0]}</a>')
        if after:
            links.append(f'<a href="{oneliner_url(after[0])}">{after[0][2]:02d}/{after[0][1]:02d}/{after[0][0]} &gt;</a>')
    links.append('<a href="/olhistory-days.htm">All the days of the oneliner</a>')
    return " &nbsp;|&nbsp; ".join(links)


def oneliner_days_body(days):
    out, cur = [], None
    for y, m, d in reversed(days):
        if (y, m) != cur:
            out.append(f'{"</p>" if cur else ""}<p><span class="warning">{MONTHS[m - 1]} {y}</span><br>')
            cur = (y, m)
        out.append(f'<a href="{oneliner_url((y, m, d))}">{d:02d}</a> ')
    return "".join(out) + "</p>"


def search_widget(kind, size=18):
    return ('<SPAN class="nec-search" data-t="%s"><INPUT type="TEXT" size=%d maxlength=100 value="">'
            '<INPUT class="Submit" type="BUTTON" value="Search"></SPAN>' % (kind, size))


MAILTO_A_RE = re.compile(r"<a\b[^>]*href\s*=\s*[\"']?\s*mailto:[^>]*>(.*?)</a\s*>", re.I | re.S)
EMAIL_RE = re.compile(r"([A-Za-z0-9._+-]+)@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")


def redact_emails(text):
    text = MAILTO_A_RE.sub(lambda m: m.group(1), text)
    text = re.sub(r"(?i)mailto:", "", text)
    return EMAIL_RE.sub(lambda m: m.group(1) + "@" + MASK, text)


IPV4 = re.compile(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])")


def mask_ips(text):
    """IPv4 addresses are masked unless they are the host of a URL (public servers of the time)."""
    def fn(m):
        before = text[max(0, m.start() - 12):m.start()].lower()
        return m.group(0) if before.endswith(("://", "@")) else MASK
    return IPV4.sub(fn, text)


def encode_page(text):
    return text.encode(ENC, errors="xmlcharrefreplace")


# --- search indexes and script ---------------------------------------------------------------------
def clean_text(v, limit=0):
    t = html.unescape(re.sub(r"(?s)<[^>]*>", " ", engine.vstr(v)))
    t = redact_emails(re.sub(r"\s+", " ", t).strip())
    return t[:limit].rstrip() + "..." if limit and len(t) > limit else t


def write_indexes(site, out):
    """/idx/*.json: [url, title, subtitle, text] rows, only fields shown on public pages and only
    rows whose page is in the build."""
    db, pages = site.macros.db, site.pages
    idx = {}
    idx["songs"] = [[f"/info-song{r['ID']}.htm", clean_text(r["TITRE"]), clean_text(r["AUTEUR"]),
                     " ".join(clean_text(r[k]) for k in ("DEMO", "GROUP1", "GROUP2", "PLATFORM") if r[k])]
                    for r in db.rows("SELECT id, auteur, titre, demo, group1, group2, platform FROM TITLES"
                                     " ORDER BY auteur COLLATE NOCASE, titre COLLATE NOCASE, id")
                    if f"/info-song{r['ID']}.htm" in pages]
    authors = {}
    for r in db.rows("SELECT MIN(auteur) auteur, COUNT(*) nb FROM TITLES GROUP BY rtrim(auteur) COLLATE NOCASE"
                     " ORDER BY 1 COLLATE NOCASE, 1"):
        u = static_name("/research.htm", {"author": r["AUTEUR"]})
        if u in pages:
            authors[u] = [u, clean_text(r["AUTEUR"]), f"{r['NB']} song{'s' if r['NB'] > 1 else ''}", ""]
    idx["authors"] = list(authors.values())
    idx["news"] = [[f"/commentnews-id{r['IDNEWS']}.htm" if f"/commentnews-id{r['IDNEWS']}.htm" in pages else "",
                    clean_text(r["TITLE"]), f"[{r['DT']:%Y-%m-%d}]", clean_text(r["NEWS"], 300)]
                   for r in db.rows("SELECT idnews, dt, title, news FROM NEWS WHERE state = 1 ORDER BY dt DESC, idnews DESC")]
    sizes = {}
    for name, rows in idx.items():
        p = out / "idx" / (name + ".json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rows, ensure_ascii=True, separators=(",", ":")) + "\n", encoding="ascii")
        sizes[name] = (len(rows), p.stat().st_size)
    return sizes


THEME_CSS = [f"/z/n/{k}.css" for k, _ in THEMES]


def rewrite_css(site, path, text):
    """url(...) of a stylesheet (absolute www.scenemusic.net URLs or relative paths) -> the
    archive path of the picture, which is then copied; missing pictures are dropped."""
    def fn(m):
        val = m.group(2).strip()
        url = urljoin("http://%s%s" % (HOST, path), val)
        sp = urlsplit(url)
        if (sp.hostname or "").lower() not in OWN_HOSTS:
            return "url()"
        new = site.asset(unquote(sp.path))
        return f"url({new})" if new else "url()"
    return re.sub(r"(?i)url\(\s*([\"']?)([^\"')]*)\1\s*\)", fn, text)


def transform_asset(path, data):
    """Skin scripts served by id3 through its template engine: `$$DYN:ID3:TOJS$$` turned the file
    (HTML <SCRIPT> blocks) into document.write() calls. The archive serves the plain script, and
    the state of the collapsible boxes is kept in localStorage instead of a cookie."""
    if not path.endswith(".js") or not data.startswith(b"$$DYN:ID3:TOJS$$"):
        return data
    js = data.decode("cp1252")[len("$$DYN:ID3:TOJS$$"):]
    js = re.sub(r"(?i)</?script\b[^>]*>", "", js)
    js = re.sub(r"(?m)^\s*<!--\s*$|^\s*//\s*-->\s*$", "", js)
    js = re.sub(r"(?s)function gcv\(cn\)\{.*?\n\}", "function gcv(cn){ try { return window.localStorage.getItem(cn); } catch (e) { return null; } }", js, count=1)
    js = re.sub(r"(?s)function sc\(cn,cv\)\{.*?\n\}", "function sc(cn,cv){ try { window.localStorage.setItem(cn, cv); } catch (e) { } }", js, count=1)
    if "document.cookie" in js:
        raise RuntimeError(f"cookie left in {path}")
    return js.encode("cp1252")


def write_js(out):
    js = (REPO / "scripts" / "nec.js").read_text(encoding="utf-8").replace("/*THEMES*/[]", json.dumps([k for k, _ in THEMES]))
    js = "".join(c if ord(c) < 128 else "\\u%04x" % ord(c) for c in js)     # ASCII only, whatever the charset
    p = out / JS.lstrip("/")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(js, encoding="utf-8")
    return hashlib.sha256(js.encode()).hexdigest()[:10]


# --- main -----------------------------------------------------------------------------------------
SEEDS = ["/index.htm", "/archived.htm", "/themes.htm", "/nec-search.htm", "/404.htm", "/olhistory-days.htm"]


def song_seeds(db):
    """Every song page existed on the live site (a few songs were linked only from the player, the
    search or the request queue)."""
    return [("/info.htm", {"idsong": str(r[0])}) for r in db.con.execute("SELECT id FROM TITLES ORDER BY id")]


def build(out, raw, jsv):
    global RAW
    RAW = raw
    db = nec.DB(RAW / "db" / "NECTARINE.sqlite", RAW / "db" / "OJUICE.sqlite", NOW)
    photos = sorted(p.name.lower() for p in (RAW / "id3" / "zi" / "nicks").iterdir() if p.is_file())
    macros = nec.NecMacros(db, photos)
    site = Site(None, DEFAULT_SKIN, "", macros, SKINS)
    site.files.virtual["olhistory-days.htm"] = FRAME % {"title": "Oneliner history",
                                                       "body": oneliner_days_body(macros.oneliner_days())}
    site.crawl(SEEDS, song_seeds(db))
    for p, text in sorted(site.pages.items()):
        dst = out / p.lstrip("/")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(encode_page(add_removal_note(text.replace(f'{JS}"', f'{JS}?v={jsv}"'))))
    idx = out / "index.htm"
    if idx.exists():
        shutil.copyfile(idx, idx.with_name("index.html"))
    sizes = write_indexes(site, out)
    print(f"{DEFAULT_SKIN}: {len(site.pages)} pages, {len(site.redirects)} redirects, {len(site.unlinked)} unlinked", flush=True)
    if site.unknown_filters:
        print("unknown filters:", ", ".join(sorted(site.unknown_filters)))
    if macros.unknown:
        print("unimplemented macros:", ", ".join(sorted(macros.unknown)))
    return site, sizes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(REPO / "site"))
    ap.add_argument("--raw", default=None, help="raw store (default: $ID3X_RAW or ~/Code/id3x/raw)")
    a = ap.parse_args(argv)
    raw = Path(a.raw).expanduser() if a.raw else RAW
    out = Path(a.out)
    for _ in range(5):              # macOS may recreate .DS_Store files while the tree is removed
        if out.exists():
            shutil.rmtree(out, ignore_errors=True)
    if out.exists():
        raise SystemExit(f"cannot empty {out}")
    out.mkdir(parents=True)
    jsv = write_js(out)
    site, sizes = build(out, raw, jsv)
    for name, (n, size) in sizes.items():
        print(f"  idx/{name}.json: {n} rows, {size // 1024} KB")
    for css in THEME_CSS:
        site.asset(css)
    css_text = {}
    for p in sorted(a for a in site.assets if a.lower().endswith(".css")):
        css_text[p] = rewrite_css(site, p, (raw / "id3" / p.lstrip("/")).read_bytes().decode("cp1252"))
    for p in sorted(site.assets):
        dst = out / p.lstrip("/")
        dst.parent.mkdir(parents=True, exist_ok=True)
        data = css_text[p].encode("cp1252") if p in css_text else (raw / "id3" / p.lstrip("/")).read_bytes()
        dst.write_bytes(transform_asset(p, data))
    hosting = REPO / "hosting"
    hosting.mkdir(exist_ok=True)
    shutil.copyfile(out / "404.htm", hosting / "404.html")
    meta_dir = REPO / "build-meta"
    meta_dir.mkdir(exist_ok=True)
    url_map = {"comment": "Old www.scenemusic.net URL (lower-case path?query, parameters sorted) -> static file of the archive.",
               "urls": dict(sorted(site.url_map.items()))}
    (meta_dir / "url-map.json").write_text(json.dumps(url_map, indent=1) + "\n")
    with open(meta_dir / "unlinked.tsv", "w") as f:     # one line per (link, reason)
        f.write("link\treason\tpages\tfirst page\n")
        agg = {}
        for page, link, why in sorted(set(site.unlinked)):
            n, first = agg.get((link, why), (0, page))
            agg[(link, why)] = (n + 1, min(first, page))
        for (link, why), (n, first) in sorted(agg.items()):
            f.write(f"{link}\t{why}\t{n}\t{first}\n")
    print(f"assets: {len(site.assets)}")
    import seo
    seo.main(["--site", str(out)])


if __name__ == "__main__":
    main()
