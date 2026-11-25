# Nectarine: data model and static rendering

Nectarine ran on the in-house engine id3 (classic ASP, `id3/cgi/_f.asp`) with SQL Server 2000:
database NECTARINE (songs, playlist, votes, comments, requests, news, oneliner) and OJUICE
(the accounts, shared with Orange Juice: people, countries, parties, links). This file describes,
in public-safe terms, what `scripts/statify.py` reads and how it renders the archive. No secret,
personal data or IP address is reproduced here.

Inputs (shared raw store `~/Code/id3x/raw`, setting `RAW` / `$ID3X_RAW`, read-only):

| Input | Content |
| --- | --- |
| `id3/z/n/` | Final skin (2005-06 to 2006-09): templates (`*.htm`, `incl_bl-*.htm`), 15 colour themes (`*.css`), scripts, pictures |
| `id3/zi/` | Media shared with Orange Juice: ID photos (`nicks/`), smilies |
| `db/NECTARINE.sqlite`, `db/OJUICE.sqlite` | Extractions of the two databases (state of 2006-09-07), incl. `_procedures`, `_columns` |
| `id3/nec_exec.asp`, `nec_queries.asp`, `nec_funcs.asp` | Macro sources: read to reimplement them, never published |

Other databases and skins, not rendered: SCENEMUSIC (one table of listener accounts, scenemusic.net v6
project), NFORUM and the skins `nforum`, `nectarineforum` (Web Wiz Forums), `nectarinev4` (the
2003-2005 design), `amigateot` (an older copy of `n`), `amigatest` (static mock-up of v6).

## 1. Template engine (`scripts/id3render/engine.py`)

The engine of OrangeJuiceV3, with the classic ASP behaviours of id3 (checked on Wayback captures):
French dates (`SetLocale("fr")`: `date 2` = `30/10/2005`, `date 3` = `09:50:00`), URL encoding in
the page codepage (cp1252, `Server.URLEncode`), the id3 multipage `[ < / 1 / 2 / ... / > ]`.
Any file request (`.css`, `.js`) was served from the skin folder by its name; `script.js` started
with `$$DYN:ID3:TOJS$$` (sent as `document.write`): the archive serves the plain script, with the
state of the collapsible boxes in localStorage instead of a cookie.

## 2. Data macros (`scripts/id3render/nec.py`)

The SQL of `nec_exec.asp` / `nec_queries.asp` and their stored procedures, translated to SQLite.
SQL Server's case-insensitive comparisons are reproduced with `COLLATE NOCASE` (and trailing spaces
ignored); ties are broken by id. Random picks (`AMAZONE` "you may also like", `ALBUM`) are fixed
per page.

| Macro | Tables | Notes |
| --- | --- | --- |
| `E:NEC:SONG`, `AVERAGE`, `CDC` | TITLES, FAVOURITES | song page; the file path on the stream server is dropped |
| `B:NEC:DISVOTE`, `DISCOMMENT`, `INFOPARTY`, `AMAZONE` | VOTES, COMMENTS, PARTY, PEOPLE, PARTIES | votes, comments, party ranking, similar songs |
| `B:NEC:RECHPLAY` (author), `CHARTS_REQ4`, `AUTHORINFO` | TITLES, RELATION | songs of an author, authors by letter, author information (e-mail as `local@????`) |
| `B:NEC:BEST`, `BESTRANK`, `BESTRANK2` | TITLES, VOTES, COMMENTS, REQUESTS, ONELINER | charts; the donors list (`chartsuser.htm?id=6`) is not published |
| `B:NEC:NEWS`, `COMNEWS` | NEWS, NEWSCOMMENTS | news and their comments |
| `B:NEC:ONELINER`, `REQUESTLIST`, `LAST5SONG`, `BIRTHDAY` | ONELINER, REQUESTS, TITLES, PEOPLE | home page boxes, on the frozen clock |
| `E:NEC:PLAYEDSONG`, `NEXTSONG` | INFO | the last song played and the next one, shown off the air (`00:00 left`) |
| `E:NEC:NICK` | PEOPLE | people sheet, same fields and masks as OrangeJuiceV3 |
| `B:NEC:ONELINERHISTO` | ONELINER, PEOPLE | oneliner of one day (`/olhistory-y2006-m9-d7.htm`, 1,791 days): nick, country, time, message; the day picker (a form) becomes previous / next day links and `/olhistory-days.htm` |

Listeners' texts (oneliner, song and news comments) keep simple formatting (`b`, `i`, `u`,
`br`, http links); any other `<` is shown as text, so no script or handler of a visitor survives.

Not rendered (anonymous visitor of a read-only site): played-songs history by day (owner
decision 2026-11-24), session, login, admin, write and upload
macros, DJ sessions, private messages, listener statistics (frozen at 0), web statistics
(`VISITS`, `MURI`: database not kept), logged-in list, queue (empty), forums.

Clock: frozen at 2006-09-07 23:59:59, the last day of the database.

## 3. Pages, URLs and the crawl

The build starts at `/index.htm` (and the archive pages) and follows every internal link of every
rendered page. Paths are lower-cased; a template that does not read its folders (`REP:n`) is one
page whatever the folders of the link. Query strings that select content become part of the file
name; other parameters are dropped:

| Old URL | Archive |
| --- | --- |
| `/info.htm?idsong=51362` (also `disvotes.htm`, `discomments.htm`) | `/info-song51362.htm` |
| `/authors.htm?author=a` | `/authors-authora.htm` |
| `/research.htm?author=4 Mat`, `/authorinfo.htm?author=...` | `/research-author4-mat-7db735.htm` (ASCII slug + CRC-32 of the cp1252 name when it differs) |
| `/chartsuser.htm?id=5`, `/commentnews.htm?id=12`, `/links.htm?cat=3` | `/chartsuser-id5.htm`, `/commentnews-id12.htm`, `/links-cat3.htm` |
| `/research.htm?type=1&recherche=...` (searches) | `/nec-search.htm?t=songs&q=...` (client-side, `/idx/*.json`) |

`build-meta/url-map.json` lists every old query URL of the crawl; the Edge Script applies the same
rules (slug included) and its test checks every entry.

## 4. Redactions

- Columns never handed to a template (`nec.py` `redact`): passwords, logins, IPs, host names, user
  agents, departments, birth years (`????`), e-mail domains (`local@????`), skin and status of the
  account, payment ids.
- Output: no `mailto:` (except the removal-request footer), no e-mail address, public IPv4 masked, two login/password strings redacted, FTP
  credentials and the stream server address never rendered (admin blocks), Google Analytics and
  AdSense scripts removed; third-party pictures are kept as links (pouet.net screenshots) except those of dead hosts.
- Not published at all: donations and the donors list, the guestbook, the member list, private
  messages, the forums (pending a privacy review).
