// Test of the legacy redirects of infra/edge/redirects.js (Node >= 18, no dependency):
//   node scripts/test_edge_script.mjs
// Loads the pure resolve() part of the script (between the BEGIN/END resolve markers), then checks
// every old query URL of build-meta/url-map.json, edge cases, and (when site/ exists) that every
// redirect target is a file of the build.
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const src = readFileSync(path.join(repo, "infra/edge/redirects.js"), "utf8");
const m = /\/\/ BEGIN resolve[^\n]*\n([\s\S]*)\/\/ END resolve/.exec(src);
if (!m) throw new Error("BEGIN/END resolve markers not found");
const resolve = new Function(m[1] + "\nreturn resolve;")();
const map = JSON.parse(readFileSync(path.join(repo, "build-meta/url-map.json"), "utf8"));
const site = path.join(repo, "site");
const hasSite = existsSync(path.join(site, "index.htm"));

let failures = 0;
const fail = (msg) => { failures++; if (failures <= 30) console.log("FAIL " + msg); };

function run(old) {
  const u = new URL(old, "https://example.test");
  return resolve(u.pathname, u.search);
}

function expect(old, want) {
  const got = run(old);
  const ok = want === null ? got === null
    : want === 404 ? got && got.status === 404
    : got && got.status === 301 && got.location === want;
  if (!ok) fail(`${old}: got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`);
}

function exists(loc) {
  const p = decodeURIComponent(loc.split("?")[0]);
  return existsSync(path.join(site, p.endsWith("/") ? p + "index.html" : p));
}

// 1. Every old query URL of the build.
let n = 0;
for (const [old, want] of Object.entries(map.urls)) {
  n++;
  expect(old, want);
  if (hasSite && !exists(want)) fail(`${old}: target ${want} missing from site/`);
}

// 2. Edge cases.
const cases = [
  // static paths, pictures and the archive's own query URLs are never touched
  ["/", null], ["/index.htm", null], ["/info-song51362.htm", null], ["/z/n/pic/trans.gif", null],
  ["/js/nec.js?v=abc", null], ["/idx/songs.json", null], ["/nec-search.htm?t=songs&q=4mat", null],
  // capitals (IIS was case-insensitive)
  ["/FAQ.htm", "/faq.htm"], ["/Index.htm", "/index.htm"],
  // content parameters, in any case and order, extra and empty ones dropped
  ["/info.htm?idsong=51362", "/info-song51362.htm"], ["/info.htm?IDSONG=51362&x=1", "/info-song51362.htm"],
  ["/disvotes.htm?idsong=51362", "/disvotes-song51362.htm"],
  ["/authors.htm?author=a", "/authors-authora.htm"],
  ["/research.htm?author=4+Mat", "/research-author4-mat-7db735.htm"],
  ["/research.htm?author=4%20Mat", "/research-author4-mat-7db735.htm"],
  ["/olhistory.htm?m=9&d=7&y=2006", "/olhistory-y2006-m9-d7.htm"],
  ["/plshistory.htm?year=2006&month=9&day=7", "/archived.htm"],
  ["/chartsuser.htm?id=5", "/chartsuser-id5.htm"], ["/chartsuser.htm?id=6", "/archived.htm"],
  // searches, counters, removed pages
  ["/research.htm?type=1", "/nec-search.htm?t=songs"],
  ["/research.htm?recherche=amiga&type=1", "/nec-search.htm?t=songs&q=amiga"],
  ["/upload.htm", null], ["/upload.htm?x=1", "/archived.htm"], ["/nick_edit.htm?x=1", "/archived.htm"],
  ["/golink.htm?url=http%3a%2f%2fevil.example%2f", 404], ["/golink.htm?id=1", 404],
  ["/golink.htm?url=http%3a%2f%2fwww.scenemusic.net%2finfo.htm%3fidsong%3d51362", "/info-song51362.htm"],
];
for (const [old, want] of cases) expect(old, want);

console.log(`${n} url-map entries and ${cases.length} edge cases checked${hasSite ? " (targets in site/)" : ""}: ` +
            (failures ? `${failures} failure(s)` : "OK"));
process.exit(failures ? 1 : 0);
