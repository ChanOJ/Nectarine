"""Data macros of Nectarine (`E:NEC:*`, `B:NEC:*`, `E:ID3:*`) over SQLite.

Nectarine ran on the classic ASP engine id3: `id3/nec_exec.asp` (E: macros), `id3/nec_queries.asp`
(B: loops) and `id3/nec_funcs.asp` (value functions such as `sectotxt_`), over two SQL Server
databases: NECTARINE (songs, playlist, votes, comments, requests, news, oneliner) and OJUICE
(people = the Nectarine accounts, countries, parties, links), attached here as `oj`.

Only read paths are implemented, for an anonymous visitor (not logged in) with the server clock
frozen at `NOW`; session, admin, write and live-stream macros return nothing.

Privacy: every row goes through `redact()` (passwords, logins, IPs, host names, user agents,
departments, birth years removed; e-mails reduced to `local@????`), so templates never see the
private values.
"""
import re
import sqlite3
from datetime import datetime

from engine import vstr

MASK = "????"

DROP = {"PASSWORD", "DEPARTMENT", "DEPARTMENT_NUM", "IP", "USER_AGENT", "MAILING", "NECTARINE_TRANSACID",
        "NECTARINE_STATUS", "NECTARINE_SKIN", "IDLOGIN", "IDSESSION", "DTLASTLOGIN", "NBLOGINS", "NBLOGOUTS",
        "TOTAL_LOGIN_TIME", "OJUID", "SEX_SIZE", "LOGIN", "COOKIE", "IP_ADDR", "SALT", "USER_CODE"}


USER_TEXT = {"COMMENT", "TXT", "SENTENCE"}       # free text typed by listeners
SAFE_TAG = re.compile(r"(?i)</?(?:b|i|u|br|strong|em)\s*/?>|</a\s*>|<a\s+href\s*=\s*\"https?://[^\"<>\s]*\"\s*>")


def user_text(v):
    """Listeners' texts were shown as typed: simple formatting and http(s) links are kept, any
    other `<` is shown as text (`<Jeff>` in pasted IRC logs), so no script or handler survives."""
    v = re.sub(r"(?i)\b(ftp|https?)://[^/@\s\"'<>]*:[^/@\s\"'<>]*@", r"\1://", v)     # no user:password@ in URLs
    out, pos = [], 0
    for m in SAFE_TAG.finditer(v):
        out.append(v[pos:m.start()].replace("<", "&lt;").replace(">", "&gt;"))
        out.append(m.group(0))
        pos = m.end()
    out.append(v[pos:].replace("<", "&lt;").replace(">", "&gt;"))
    return "".join(out)


def redact(row):
    out = {}
    for k, v in row.items():
        K = k.upper()
        if K in DROP:
            continue
        if K in ("BIRTHYEAR", "DT_BIRTH"):
            v = MASK if v not in (None, "", 0) else None
        elif K in USER_TEXT and isinstance(v, str):
            v = user_text(v)
        elif K == "HOSTNAME":
            v = MASK if v else v
        elif K in ("EMAIL", "AUTHOR_EMAIL") and v:
            local = str(v).split("@")[0].strip()
            v = f"{local}@{MASK}" if local else None
        out[K] = v
    return out


DATE_RE = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d(\.\d+)?$")


class DB:
    """NECTARINE (main) + OJUICE (attached as `oj`), read-only."""

    # The extractions have no secondary indexes: the databases are copied in memory (about
    # 300 MB) and indexed there; the files are never written.
    INDEXES = ["TITLES(id)", "TITLES(auteur)", "PLAYLIST(dt_play)", "PLAYLIST(idsong)", "VOTES(idsong)", "VOTES(idnick)",
               "COMMENTS(idsong)", "COMMENTS(idnick)", "REQUESTS(idsong)", "REQUESTS(idnick)", "REQUESTS(dt)",
               "ONELINER(auteur)", "ONELINER(dt)", "ONELINER(substr(dt, 1, 10))", "FAVOURITES(idsong)", "FAVOURITES(idnick)", "PARTY(idsong)",
               "NEWSCOMMENTS(idnews)", "NEWS(idnews)", "RELATION(author_name)", "oj.PEOPLE(id)", "oj.LINKS(id)",
               "oj.COUNTRIES(id)", "oj.PARTIES(id)"]

    def __init__(self, nec_path, oj_path, now):
        self.con = sqlite3.connect(":memory:")
        src = sqlite3.connect(f"file:{nec_path}?mode=ro", uri=True)
        src.backup(self.con)
        src.close()
        self.con.execute("ATTACH DATABASE ':memory:' AS oj")
        src = sqlite3.connect(f"file:{oj_path}?mode=ro", uri=True)
        tables = [r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        src.close()
        self.con.execute("ATTACH DATABASE ? AS ojsrc", (f"file:{oj_path}?mode=ro",))
        for t in tables:
            if t.upper() in ("PEOPLE", "LINKS", "COUNTRIES", "PARTIES", "COMPUTERS", "LINKSCATEGORIES", "_COLUMNS"):
                self.con.execute(f'CREATE TABLE oj."{t}" AS SELECT * FROM ojsrc."{t}"')
        self.con.execute("DETACH DATABASE ojsrc")
        for i, ix in enumerate(self.INDEXES):
            schema, _, rest = ix.rpartition(".")
            table, col = rest[:-1].split("(", 1)
            self.con.execute(f"CREATE INDEX {schema + '.' if schema else ''}ix{i} ON {table}({col})")
        self.con.row_factory = sqlite3.Row
        self.now = now
        self.con.create_function("NOW", 0, lambda: now.strftime("%Y-%m-%d %H:%M:%S"))
        self.con.create_function("HOURDIFF", 2, self._hourdiff)
        self.con.create_function("DAYDIFF", 2, self._daydiff)
        self.con.execute(
            "CREATE TEMP VIEW vsceners AS SELECT p.*, l1.name AS group1, l2.name AS group2, c.country AS country,"
            " c.language AS language, c.flag AS flag FROM oj.PEOPLE p LEFT JOIN oj.LINKS l1 ON p.idgroup1 = l1.id"
            " LEFT JOIN oj.LINKS l2 ON p.idgroup2 = l2.id INNER JOIN oj.COUNTRIES c ON p.idcountry = c.id")
        self.types = {}
        for schema in ("main", "oj"):
            for name, t in self.con.execute(f"SELECT name, sql_type FROM {schema}._columns"):
                self.types.setdefault(name.upper(), set()).add(t.split("(")[0])

    @staticmethod
    def _parse(s):
        return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S") if s else None

    def _daydiff(self, a, b):
        a, b = self._parse(a), self._parse(b)
        return None if a is None or b is None else (b.date() - a.date()).days

    def _hourdiff(self, a, b):
        a, b = self._parse(a), self._parse(b)
        if a is None or b is None:
            return None
        return int((b.replace(minute=0, second=0) - a.replace(minute=0, second=0)).total_seconds() // 3600)

    def convert(self, k, v):
        if v is None:
            return None
        t = self.types.get(k.upper(), ())
        if isinstance(v, str) and DATE_RE.match(v) and ("datetime" in t or "smalldatetime" in t or not t):
            return datetime.strptime(v[:19], "%Y-%m-%d %H:%M:%S")
        if t and t <= {"bit"} and isinstance(v, int):
            return bool(v)
        return v

    def rows(self, sql, params=()):
        return [redact({k: self.convert(k, r[k]) for k in r.keys()}) for r in self.con.execute(sql, params)]

    def scalar(self, sql, params=()):
        r = self.con.execute(sql, params).fetchone()
        return r[0] if r else None


def is_int(v):
    return v is not None and re.fullmatch(r"-?\d+", str(v).strip()) is not None


def odbc_week(d):
    """{fn WEEK(d)} of SQL Server: week of the year, weeks starting on Sunday, week 1 = Jan 1st's."""
    jan1 = d.replace(month=1, day=1)
    offset = (jan1.weekday() + 1) % 7          # Sunday = 0
    return (d.timetuple().tm_yday - 1 + offset) // 7 + 1


def two(n):
    return f"{int(n):02d}"


def sectotxt_(v):
    """nec_funcs.asp sectotxt_: seconds -> hh:mm:ss."""
    try:
        s = int(float(vstr(v).replace(",", ".")))
    except ValueError:
        return "00:00:00"
    if not s:
        return "00:00:00"
    return f"{two(s // 3600)}:{two(s // 60 % 60)}:{two(s % 60)}"


def sectodte_(v):
    try:
        s = int(float(vstr(v)))
    except ValueError:
        s = 0
    if not s:
        return "00:00:00:00"
    return f"{two(s // 86400)} days {two(s // 3600 % 24)} hours {two(s // 60 % 60)} mn {two(s % 60)} seconds"


def groups_(s):
    if s is None or s == "":
        return ""
    s = str(s)
    i = s.find("(")
    if i >= 0:
        s = s[:i].rstrip()
    return " / " + s


def necnick_factory(db):
    cache = {}

    def necnick_(v):
        """nec_funcs.asp necnick_: OJUICE people id -> nick ("Dj Randomly" when unknown)."""
        k = vstr(v)
        if k not in cache:
            nick = db.scalar("SELECT nick FROM oj.PEOPLE WHERE id = ?", (int(k),)) if is_int(k) else None
            cache[k] = nick if nick is not None else "Dj Randomly"
        return cache[k]
    return necnick_


class NecMacros:
    """Macro sets `NEC` and `ID3` for an anonymous visitor."""

    def __init__(self, db, nick_photos=()):
        self.db = db
        self.now = db.now
        self.nick_photos = set(nick_photos)
        self.cache = {}
        self.unknown = set()
        self.functions = {"sectotxt_": sectotxt_, "sectodte_": sectodte_, "necnick_": necnick_factory(db),
                          "groups_": groups_, "One2Two_": lambda v: two(v) if is_int(v) else vstr(v)}

    def canonical_author(self, v):
        """One spelling per author (SQL Server compared names case-insensitively, without trailing
        spaces): the one the author lists show, so each author has one page."""
        if "AUTHORS" not in self.cache:
            m = {}
            for (a,) in self.db.con.execute("SELECT MIN(auteur) FROM TITLES GROUP BY rtrim(auteur) COLLATE NOCASE"):
                m[a.rstrip().lower()] = a.rstrip()
            self.cache["AUTHORS"] = m
        return self.cache["AUTHORS"].get(v.rstrip().lower(), v)

    def photo_ok(self, r):
        return f"{r['ID']}.{r['PIC_EXT']}".lower() in self.nick_photos

    # Macros that need a logged-in visitor, write, count or talk to the streaming server: an
    # anonymous visitor of a read-only archive gets nothing from them.
    SESSION_E = {"NEC:SESSIONOK", "NEC:SENDSESSION", "NEC:MOVESESSION", "NEC:TOTALSESSION", "NEC:ADDSESSION",
                 "NEC:BROKENLINK", "NEC:LINKIN", "NEC:GOLINK", "NEC:YOURADVICE", "NEC:IDSKIN", "NEC:PENDING",
                 "NEC:USTATS", "NEC:DISPLAYMESSAGE", "NEC:DELMESSAGE", "NEC:YOU", "NEC:NEWSAC", "NEC:SLAC", "NEC:BLAC",
                 "NEC:LINKSAC", "NEC:PSAC", "NEC:DONORS", "NEC:COUNTCON", "NEC:CHANGENEWS", "NEC:DONREQ", "NEC:GAME",
                 "NEC:LOGOUT", "NEC:LOGGEDINFOS", "NEC:TOTUSER", "NEC:LOGADMIN", "NEC:ISADMIN", "NEC:USERVOTE",
                 "NEC:NBREQ", "NEC:ARTHUR1", "NEC:AVGUSER", "NEC:REQUSER", "NEC:SAMLINKS", "NEC:DELCOMMENT",
                 "NEC:DELCNEWS", "NEC:DELNEWS", "NEC:SAMADDSONG", "NEC:FAVORITES", "NEC:CONVERT", "NEC:KB",
                 "NEC:TEST1", "NEC:TEST2", "NEC:TEST3", "NEC:TEST4", "NEC:REQUEST", "NEC:FIXDB", "NEC:SITE1",
                 "ID3:NOCACHE", "ID3:NOUACACHE", "NEC:NECSTATS"}
    SESSION_B = {"NEC:LISTFAVREQ", "NEC:OWNLINKS", "NEC:LISTLOGGED", "NEC:VISITS", "NEC:PENDINGADMIN", "NEC:QUEUE2",
                 "NEC:ADMINPOUET", "NEC:XCHANGEMSG", "NEC:UPLOADAPPLETU", "NEC:UPLOADAPPLETR", "NEC:UPLOADAPPLET",
                 "NEC:RENAME", "NEC:PENDVOTE", "NEC:PENDCOMM", "NEC:LISTMESSAGES", "NEC:FADMIN", "NEC:MYPENDING",
                 "NEC:PENDING", "NEC:PENDING2", "NEC:PENDING3", "NEC:REPORTED", "NEC:UPDMEMBER", "NEC:NADMIN",
                 "NEC:ADMINLIST", "NEC:BASEPERSOV", "NEC:BASEPERSOR", "NEC:BASEPERSOL", "NEC:BASEPERSOI",
                 "NEC:BASEPERSOF", "NEC:BASEPERSOC", "NEC:LISTMOTIFNET", "NEC:PARTYLIST", "NEC:COMPOTITLE",
                 "NEC:MEMBERLIST", "NEC:LOVE"}

    # ------------------------------------------------------------------------------- E: macros
    def exec(self, name, a, page):
        if name in self.SESSION_E:
            return None
        fn = getattr(self, "e_" + name.replace(":", "_").lower(), None)
        if fn is None:
            self.unknown.add("E:" + name)
            return None
        return fn(a, page)

    def e_nec_datenow(self, a, page):
        page.dic["NEC:DATENOW:DA"] = self.now.day
        page.dic["NEC:DATENOW:MO"] = self.now.month
        page.dic["NEC:DATENOW:YE"] = self.now.year
        return None

    def e_nec_stats(self, a, page):
        # Listener figures of the streaming server: the radio is off the air (frozen as 0)
        for k in ("STATSL", "STATSS", "STATSM", "STATSX"):
            page.dic[f"NEC:STATS:{k}"] = 0
        return None

    def _info(self, n):
        key = ("INFO", n)
        if key not in self.cache:
            self.cache[key] = self.db.rows("SELECT * FROM INFO WHERE id = ?", (n,))
        return self.cache[key]

    def _played(self, name, page):
        rows = self._info(1)
        if rows:
            page.dic[name + ":DUREESTART"] = "00:00"
            page.dic[name + ":DUREELEFT"] = "00:00"     # off the air: nothing left to play
            who = self.db.scalar("SELECT nick FROM REQUESTS WHERE idsong = ? ORDER BY dt DESC, id DESC LIMIT 1",
                                 (rows[0]["IDSONG"],))
            page.dic[name + ":WHO"] = who if who is not None else "Yes"
        return rows

    def e_nec_playedsong(self, a, page):
        return self._played("NEC:PLAYEDSONG", page)

    def e_nec_playedsong2(self, a, page):
        return self._played("NEC:PLAYEDSONG2", page)

    def e_nec_nextsong(self, a, page):
        return self._info(2)

    def e_nec_nextsong2(self, a, page):
        return self._info(2)

    def e_nec_queueduree(self, a, page):
        return [{"DUREE": 0}]       # off the air: nothing queued any more (live: SUM of the queued requests)

    def e_nec_file(self, a, page):
        page.dic["NEC:FILE:FILES"] = str(self.db.scalar("SELECT COUNT(id) FROM TITLES"))
        return None

    def e_nec_last(self, a, page):
        return self.db.rows("SELECT * FROM TITLES ORDER BY inserted DESC, id DESC LIMIT 1")

    def e_nec_song(self, a, page):
        idsong = page.req.get("idsong")
        if not is_int(idsong):
            return None
        rows = self.db.rows("SELECT * FROM TITLES WHERE id = ?", (int(idsong),))
        if not rows:
            return None
        r = rows[0]
        link = vstr(r.get("LINK"))
        if len(link) > 6:
            parts = link.split("/")
            host = parts[2].rsplit("@", 1)[-1] if len(parts) > 2 else ""      # no user:password@ of FTP links
            page.dic["NEC:SONG:WEBHOST"] = parts[0] + "//" + host if parts[0] in ("http:", "ftp:") and host else "invalid link"
        r.pop("URL", None)       # path of the file on the streaming server
        return rows

    def e_nec_average(self, a, page):
        idsong = page.req.get("idsong")
        if is_int(idsong):
            m = self.db.scalar("SELECT moyenne FROM TITLES WHERE id = ?", (int(idsong),))
            page.dic["NEC:AVERAGE:RESULTS"] = round(m, 2) if m is not None else 0
        return None

    def e_nec_cdc(self, a, page):
        idsong = page.req.get("idsong")
        if is_int(idsong):
            n = self.db.scalar("SELECT COUNT(*) FROM FAVOURITES WHERE idsong = ?", (int(idsong),))
            page.dic["NEC:CDC:CDC"] = 1 if n and n >= 10 else 0
        return None

    def e_nec_nick(self, a, page):
        if not is_int(a[1]):
            return None
        rows = self.db.rows("SELECT a.*, c.computer FROM vsceners a, oj.COMPUTERS c WHERE a.idcomputer = c.id AND a.id = ?",
                            (int(a[1]),))
        if not rows:
            page.redirect = "/index.htm"
            return None
        r = rows[0]
        fn = "".join("/" + f for f in ("ANS", "ASC", "COD", "GFX", "RAY", "ORG", "SWP", "SYS", "WEB", "ZIK")
                     if r.get("IS" + f)).replace("//", "/")
        if len(fn) > 1:
            page.dic["NEC:NICK:FUNCTIONS"] = fn[1:]
        if r.get("PIC_EXT") and not self.photo_ok(r):
            r["PIC_EXT"] = None
        return rows

    # ------------------------------------------------------------------------------- B: loops
    def loop(self, stored, name, a, page, select_top):
        if stored in self.SESSION_B:
            return None
        fn = getattr(self, "b_" + stored.replace(":", "_").lower(), None)
        if fn is None:
            self.unknown.add("B:" + stored)
            return None
        rows = fn(a, page)
        return None if rows is None else (rows, None, False)

    def cached(self, key, sql, params=()):
        if key not in self.cache:
            self.cache[key] = self.db.rows(sql, params)
        return self.cache[key]

    def b_nec_last5song(self, a, page):
        return self.cached("LAST5", "SELECT * FROM TITLES ORDER BY dt_lst_play DESC, id DESC LIMIT 6")[1:]

    def b_nec_news(self, a, page):
        nid = page.req.get("id")
        if is_int(nid):
            return self.db.rows("SELECT * FROM NEWS WHERE idnews = ?", (int(nid),))
        rows = self.cached("NEWS", "SELECT v.nick AS nick, n.* FROM NEWS n LEFT JOIN oj.PEOPLE v ON v.id = n.idnick"
                           " WHERE n.state = 1 ORDER BY n.dt DESC, n.idnews DESC")
        for r in rows:
            r.setdefault("TOTAL", self.db.scalar("SELECT COUNT(idnews) FROM NEWSCOMMENTS WHERE idnews = ?", (r["IDNEWS"],)))
        return rows

    def b_nec_oneliner(self, a, page):
        return self.cached("OL", "SELECT a.dt, a.sentence, b.id, c.country, c.flag, b.nick FROM ONELINER a"
                           " LEFT JOIN oj.PEOPLE b ON a.auteur = b.id LEFT JOIN oj.COUNTRIES c ON b.idcountry = c.id"
                           " ORDER BY a.dt DESC, a.id DESC LIMIT 20")

    def b_nec_requestlist(self, a, page):
        return self.cached("REQ", "SELECT d.dt, d.nick, a.auteur, a.titre, a.cat, a.id FROM REQUESTS d, TITLES a"
                           " WHERE a.id = d.idsong ORDER BY d.dt DESC, d.id DESC LIMIT 20")

    def b_nec_forumlist(self, a, page):
        return []      # the forums are not archived

    def b_nec_bestrank2(self, a, page):
        return self.cached("BR2", "SELECT * FROM TITLES WHERE nbvotes > 20 ORDER BY moyenne DESC, nbvotes DESC, id LIMIT 10")

    def b_nec_birthday(self, a, page):
        md = f"{self.now.month:02d}{self.now.day:02d}"
        return self.cached("BD", "SELECT a.id, a.nick, a.country, a.flag FROM vsceners a WHERE a.birthmd = ?"
                           " ORDER BY a.nick, a.id", (md,))

    def _idsong(self, page):
        v = page.req.get("idsong")
        return int(v) if is_int(v) else None

    def b_nec_disvote(self, a, page):
        i = self._idsong(page)
        return None if i is None else self.db.rows(
            "SELECT p.nick, a.dt, a.vote, c.country, c.flag FROM VOTES a INNER JOIN oj.PEOPLE p ON a.idnick = p.id"
            " INNER JOIN oj.COUNTRIES c ON p.idcountry = c.id WHERE a.idsong = ? ORDER BY a.dt DESC, a.id DESC", (i,))

    def b_nec_discomment(self, a, page):
        i = self._idsong(page)
        return None if i is None else self.db.rows(
            "SELECT a.id, a.idnick, p.nick, a.dt, a.comment, c.country, c.flag FROM COMMENTS a"
            " LEFT JOIN oj.PEOPLE p ON a.idnick = p.id LEFT JOIN oj.COUNTRIES c ON p.idcountry = c.id"
            " WHERE a.idsong = ? ORDER BY a.id DESC", (i,))

    def b_nec_amazone(self, a, page):
        """"You may also like": 5 songs of the same format and category with a close average
        vote. The original drew them at random (RAND()); the archive takes a fixed pick per song."""
        i = self._idsong(page)
        if i is None:
            return None
        r = self.db.rows("SELECT idformat, cat, moyenne FROM TITLES WHERE id = ?", (i,))
        if not r:
            return None
        m = r[0]["MOYENNE"] or 0
        lo = max(m - 0.5, 0)
        return self.db.rows("SELECT id, auteur, titre, duration FROM TITLES WHERE idformat IS ? AND cat IS ? AND id <> ?"
                            " AND moyenne > ? AND moyenne < ? ORDER BY (id * 2654435761 + ?) % 4294967296 LIMIT 5",
                            (r[0]["IDFORMAT"], r[0]["CAT"], i, lo, m + 0.5, i))

    def b_nec_infoparty(self, a, page):
        i = self._idsong(page)
        return None if i is None else self.db.rows(
            "SELECT a.cat, a.rank, b.nick, c.dt_begin, c.name, d.flag FROM PARTY a INNER JOIN oj.PEOPLE b ON a.idnick = b.id"
            " INNER JOIN oj.PARTIES c ON a.idparty = c.id INNER JOIN oj.COUNTRIES d ON c.id_country = d.id"
            " WHERE a.idsong = ?", (i,))

    def b_nec_authorinfo(self, a, page):
        au = page.req.get("author")
        return None if au is None else self.db.rows("SELECT * FROM RELATION WHERE rtrim(author_name) = rtrim(?) COLLATE NOCASE"
                                                    " ORDER BY id", (au,))

    BEST_SQL = {
        "1": "SELECT COUNT(*) counteur, v.nick, v.flag, v.country FROM TITLES a INNER JOIN vsceners v ON a.nickpouet = v.id"
             " GROUP BY v.id ORDER BY COUNT(*) DESC, v.nick LIMIT 25",
        "2": "SELECT COUNT(*) counteur, v.nick, v.flag FROM TITLES a INNER JOIN vsceners v ON a.nicklink = v.id"
             " GROUP BY v.id ORDER BY COUNT(*) DESC, v.nick LIMIT 25",
        "3": "SELECT COUNT(*) counteur, v.nick, v.flag FROM VOTES a INNER JOIN vsceners v ON a.idnick = v.id"
             " GROUP BY v.id ORDER BY COUNT(*) DESC, v.nick LIMIT 25",
        "4": "SELECT COUNT(*) counteur, v.nick, v.flag FROM COMMENTS a INNER JOIN vsceners v ON a.idnick = v.id"
             " GROUP BY v.id ORDER BY COUNT(*) DESC, v.nick LIMIT 25",
        "5": "SELECT COUNT(*) counteur, v.nick, v.flag FROM REQUESTS a INNER JOIN vsceners v ON a.idnick = v.id"
             " GROUP BY v.id ORDER BY COUNT(*) DESC, v.nick LIMIT 25",
        # "6" listed the donors: not published (who gave money)
        "7": "SELECT COUNT(*) counteur, v.nick, v.flag FROM ONELINER a INNER JOIN vsceners v ON a.auteur = v.id"
             " GROUP BY v.id ORDER BY COUNT(*) DESC, v.nick LIMIT 25",
    }

    def b_nec_best(self, a, page):
        sql = self.BEST_SQL.get(page.req.get("id") or "")
        return None if sql is None else self.cached(("BEST", sql), sql)

    def b_nec_bestrank(self, a, page):
        return self.cached("BR", "SELECT * FROM TITLES WHERE nbvotes > 20 ORDER BY moyenne DESC, nbvotes DESC, id LIMIT 50")

    def b_nec_charts_req4(self, a, page):
        rech = page.req.get("author") or "a"
        if rech == "other":
            return self.cached(("AU", rech), "SELECT MIN(auteur) auteur, COUNT(auteur) counteur2 FROM TITLES WHERE substr(auteur, 1, 1)"
                               " BETWEEN '0' AND '9' GROUP BY rtrim(auteur) COLLATE NOCASE ORDER BY 1 COLLATE NOCASE")
        if not re.fullmatch(r"[a-z]", rech):
            return None
        return self.cached(("AU", rech), "SELECT MIN(auteur) auteur, COUNT(auteur) counteur2 FROM TITLES WHERE auteur LIKE ?"
                           " GROUP BY rtrim(auteur) COLLATE NOCASE ORDER BY 1 COLLATE NOCASE", (rech + "%",))

    # Charts of fullstats2..7.htm: `cast(x as char(50))` pads to 50 characters, as SQL Server did
    def b_nec_xcharts(self, a, page):
        return self.cached("XC", "SELECT id, printf('%10.6f', moyenne) moyenne, printf('%-50.50s', auteur) || ' - ' ||"
                           " printf('%-50.50s', titre) titre, '(' || printf('%-30s', nbvotes) || ' votes)' votes FROM TITLES"
                           " WHERE nbvotes > 5 ORDER BY moyenne, nbvotes DESC, id LIMIT 100")

    def b_nec_bestreq(self, a, page):
        return self.cached("BQ", "SELECT COUNT(*) total, t.titre, t.auteur, r.idsong FROM REQUESTS r INNER JOIN TITLES t"
                           " ON r.idsong = t.id GROUP BY r.idsong ORDER BY COUNT(*) DESC, r.idsong LIMIT 50")

    def b_nec_xcharts4(self, a, page):
        return self.cached("XC4", "SELECT c.idsong, COUNT(*) num, printf('%-50.50s', t.titre) || ' by ' || printf('%-50.50s', t.auteur)"
                           " titre FROM TITLES t, COMMENTS c WHERE c.idsong = t.id GROUP BY c.idsong ORDER BY num DESC, c.idsong LIMIT 100")

    def b_nec_xcharts5(self, a, page):
        return self.cached("XC5", "SELECT id, nbplay, printf('%-50.50s', titre) || ' by ' || printf('%-50.50s', auteur) titre"
                           " FROM TITLES ORDER BY nbplay DESC, id LIMIT 100")

    def b_nec_lessplayed(self, a, page):
        return self.cached("LP", "SELECT id, auteur, titre FROM TITLES WHERE url NOT LIKE '%''%' ORDER BY nbplay, id LIMIT 100")

    def b_nec_chartstopcharts(self, a, page):
        """WEEKCHART: authors most requested during the previous week ({fn WEEK()}: weeks start on
        Sunday, week 1 holds January 1st), on the frozen clock."""
        rows = []
        y, w = self.now.year, odbc_week(self.now) - 1
        for r in self.db.con.execute("SELECT dt, idsong FROM REQUESTS WHERE dt >= ? AND dt < ?", (f"{y}-01-01", f"{y + 1}-01-01")):
            rows.append(r)
        counts = {}
        auteur = dict(self.db.con.execute("SELECT id, auteur FROM TITLES"))
        for dt, idsong in rows:
            if odbc_week(datetime.strptime(dt[:10], "%Y-%m-%d")) == w and idsong in auteur:
                counts[auteur[idsong]] = counts.get(auteur[idsong], 0) + 1
        top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20]
        return [{"LASTWEEK": n, "AUTEUR": au} for au, n in top]

    def b_nec_comnews(self, a, page):
        i = page.req.get("id")
        return None if not is_int(i) else self.db.rows(
            "SELECT a.*, b.nick FROM NEWSCOMMENTS a LEFT JOIN oj.PEOPLE b ON b.id = a.idnick WHERE a.idnews = ?"
            " ORDER BY a.dtcomment, a.id", (int(i),))

    def b_nec_linkcat(self, a, page):
        return self.cached("LC", "SELECT * FROM oj.LINKSCATEGORIES ORDER BY id")

    def b_nec_linkdisplay(self, a, page):
        c = page.req.get("cat")
        return None if not is_int(c) else self.db.rows(
            "SELECT l.clicksin, l.id, l.isactive, l.idcategory, l.url, l.name, l.description, l.clicks, c.flag, c.country"
            " FROM oj.LINKS l INNER JOIN oj.COUNTRIES c ON l.idcountry = c.id WHERE l.isactive = 1 AND l.idcategory = ?"
            " AND l.url LIKE 'http%' ORDER BY l.clicksin DESC, l.name COLLATE NOCASE, l.id", (int(c),))

    def b_nec_queue(self, a, page):
        return []       # off the air: the request queue is empty

    def b_nec_rechplay(self, a, page):
        au = page.req.get("author")
        if au is None:
            return None     # the searches are client-side in the archive
        return self.db.rows("SELECT * FROM TITLES WHERE rtrim(auteur) = rtrim(?) COLLATE NOCASE ORDER BY titre COLLATE NOCASE, id", (au,))

    def b_nec_timepls(self, a, page):
        return None         # played-songs history by day: a form of the live site

    def b_nec_onelinerhisto(self, a, page):
        """Oneliner of one day (`olhistory.htm?m=&d=&y=`), newest first."""
        m, d, y = (page.req.get(k) for k in ("m", "d", "y"))
        if not (is_int(m) and is_int(d) and is_int(y)):
            return None
        day = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
        return self.db.rows("SELECT o.dt, p.nick, c.flag, o.sentence FROM ONELINER o LEFT JOIN oj.PEOPLE p ON p.id = o.auteur"
                            " LEFT JOIN oj.COUNTRIES c ON c.id = p.idcountry WHERE substr(o.dt, 1, 10) = ? ORDER BY o.id DESC",
                            (day,))

    def oneliner_days(self):
        """Days that have oneliner messages, oldest first, as (year, month, day)."""
        if "OLDAYS" not in self.cache:
            self.cache["OLDAYS"] = [tuple(int(x) for x in r[0].split("-")) for r in
                                    self.db.con.execute("SELECT DISTINCT substr(dt, 1, 10) FROM ONELINER ORDER BY 1")]
        return self.cache["OLDAYS"]

    def b_nec_muri(self, a, page):
        return []           # last referers: web statistics database, not kept

    b_nec_muri2 = b_nec_muri

    def e_nec_album(self, a, page):
        """A random production with a pouet.net screenshot; the archive takes a fixed one per page."""
        ids = self.cached("ALB", "SELECT id FROM TITLES WHERE extens IS NOT NULL AND trim(extens) <> '' ORDER BY id")
        if not ids:
            return None
        import zlib
        pick = ids[zlib.crc32(page.req.path.encode()) % len(ids)]["ID"]
        return self.db.rows("SELECT * FROM TITLES WHERE id = ?", (pick,))

    def e_nec_lstupd(self, a, page):
        return self.cached("LU", "SELECT inserted FROM UPDATETEMP ORDER BY id DESC LIMIT 1")

    def e_nec_lstupd2(self, a, page):
        return self.cached("LU2", "SELECT inserted FROM TITLES ORDER BY id DESC LIMIT 1")

    # -- multipage ------------------------------------------------------------------------------
    def multipage(self, link, page, nbpages, pg):
        """id3 multipage (cgi/_f.asp, maxpages 10 in DefaultOJ, no modifier sub for Nectarine)."""
        maxp = 10
        first = page if page - maxp > 0 else 1
        last = first + maxp - 1
        if last > nbpages:
            last = nbpages
            first = max(nbpages - (maxp - 1), 1)
        s = "[ "
        if page > 1:
            s += f'<A href="{link}{page - 1}">&lt;</A> / '
        for j in range(first, last + 1):
            if j > 1:
                s += " / "
            s += str(j) if j == page else f'<A href="{link}{j}">{j}</A>'
        if page < nbpages:
            s += f' / <A href="{link}{page + 1}">&gt;</A>'
        s += " ]"
        return s.replace("&", "&amp;").replace("&amp;gt;", "&gt;").replace("&amp;lt;", "&lt;")
