# Nectarine: context for Claude sessions

Static archive of Nectarine, the demoscene radio (www.scenemusic.net, nectarine.ojuice.net,
2000-2006), served by the classic ASP engine id3 over SQL Server 2000 (databases NECTARINE and
OJUICE). Same approach and hosting as `~/Code/OrangeJuiceV3` (template: read its README first).
GitHub repo `ChanOJ/Nectarine` (public), hostname `nectarine.sauthier.family`, bunny storage
and pull zone `nectarine`, Proton Pass item `Nectarine-tofu-state-passphrase` (vault `OldSites`).
Context of the whole id3/id3x family: `~/Code/id3x/CLAUDE.md`.

## Hard rules

- Inputs come only from the shared raw store `~/Code/id3x/raw` (setting `RAW` in
  `scripts/statify.py`, or `$ID3X_RAW`), never from the NAS. It holds the engine sources,
  connection strings and the full databases (e-mails, passwords, IPs, donations): never copy any
  of it into the repository, a commit, a PR or a page, except rendered public data.
- Never publish engine code (`.asp`, `.inc`, DLLs), the upload applets (`.jar`, `.cab`), the
  stream server address or the FTP credentials hard-coded in admin blocks, nor sensitive columns
  (password, logins, IPs, host names, departments, birth years, e-mail domains, donations).
- `site/` is generated on the Mac and **committed**; `private/` (notes, Wayback captures) is git-ignored.
- Process: rebuild locally (`scripts/publish.sh`: build + checks, no deploy), commit `site/` in the
  same PR as the script change, merge = CI deploys (`.github/workflows/deploy.yml`). Never deploy by
  hand, never `git add -A`; a leak in git history is permanent, so `verify_build.py` and
  `check_excludes.py` must pass before any commit of `site/`.

## Layout

- `scripts/id3render/engine.py`: the id3 template engine (port of `id3/cgi/_f.asp`), French
  dates (`SetLocale("fr")`) and cp1252 URL encoding for this classic ASP site.
- `scripts/id3render/nec.py`: the NEC data macros over SQLite (port of `id3/nec_exec.asp`,
  `nec_queries.asp`, `nec_funcs.asp`); `redact()` strips private columns.
- `scripts/statify.py`: crawl, static names, link rewriting, forms, assets, search indexes,
  removal-request footer, then `scripts/seo.py` (robots.txt, sitemap.xml).
- `scripts/mdf/`: MDF reader (with torn-page repair, needed for SCENEMUSIC and NFORUM).
- Checks: `scripts/verify_build.py`, `scripts/check_excludes.py`; build twice, same hashes.
