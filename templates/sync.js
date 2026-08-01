/* Pure progress-sync logic: no DOM, no network, no globals of its own beyond
   these functions. Everything here is unit-testable in node, which matters
   because build.py inlines it into a 3.4MB index.html where it would otherwise
   be untestable. */

var MARK_PREFIX = "gisa-cards-v2";
var V1_KEY = "gisa-cards-v1";

/* Timestamp ties are broken toward "not mastered yet", so a migrated 어려움 is
   never silently upgraded into 암기함. Re-seeing a known card is cheap; losing
   track of a hard one is not. */
var STATE_RANK = {hard: 3, unsure: 2, known: 1};

/* A single shared bucket would let one user's marks be inherited by whoever
   signs in next on the same browser. */
function markKey(userId) {
  return MARK_PREFIX + ":" + (userId || "anon");
}

function validMark(m) {
  return !!m && typeof m === "object" && !!STATE_RANK[m.s] &&
         typeof m.t === "number" && isFinite(m.t);
}

/* v1 stored a bare state string per card. t:1 marks these as "oldest known",
   so any later timestamped mark beats them. */
function migrateV1(v1) {
  var out = {};
  if (!v1 || typeof v1 !== "object") return out;
  Object.keys(v1).forEach(function (id) {
    if (STATE_RANK[v1[id]]) out[id] = {s: v1[id], t: 1};
  });
  return out;
}

/* Per-card last-write-wins. Commutative, so both devices can run it
   independently and converge with no server-side logic. */
function mergeMarks(a, b) {
  var out = {};
  [a, b].forEach(function (o) {
    if (!o || typeof o !== "object") return;
    Object.keys(o).forEach(function (id) {
      var m = o[id];
      if (!validMark(m)) return;
      var cur = out[id];
      if (!cur || m.t > cur.t ||
          (m.t === cur.t && STATE_RANK[m.s] > STATE_RANK[cur.s])) {
        out[id] = {s: m.s, t: m.t};
      }
    });
  });
  return out;
}

function loadMarks(storage, userId) {
  try {
    var o = JSON.parse(storage.getItem(markKey(userId)) || "{}");
    var out = {};
    Object.keys(o).forEach(function (id) { if (validMark(o[id])) out[id] = o[id]; });
    return out;
  } catch (e) { return {}; }
}

function saveMarks(storage, userId, marks) {
  try {
    storage.setItem(markKey(userId), JSON.stringify(marks));
    return true;
  } catch (e) { return false; }
}

/* One-time lift of v1 into the anon bucket, merged rather than assigned so a
   half-migrated device cannot lose marks. Returns true if anything moved. */
function runV1Migration(storage) {
  try {
    var raw = storage.getItem(V1_KEY);
    if (raw === null) return false;
    var migrated = migrateV1(JSON.parse(raw || "{}"));
    saveMarks(storage, null, mergeMarks(loadMarks(storage, null), migrated));
    storage.removeItem(V1_KEY);
    return Object.keys(migrated).length > 0;
  } catch (e) { return false; }
}

function stateOf(marks, id) {
  var m = marks[id];
  return validMark(m) ? m.s : undefined;
}

/* Returns a new map. Re-applying the state a card already has clears it, which
   is how the footer buttons have always toggled. */
function applyMark(marks, id, s, now) {
  var out = {};
  Object.keys(marks).forEach(function (k) { out[k] = marks[k]; });
  if (stateOf(out, id) === s) delete out[id];
  else out[id] = {s: s, t: now};
  return out;
}

/* Present only under node --test; absent in the browser, where build.py has
   already inlined these onto the script's scope. */
if (typeof module !== "undefined" && module.exports) {
  module.exports = {MARK_PREFIX: MARK_PREFIX, V1_KEY: V1_KEY, STATE_RANK: STATE_RANK,
    markKey: markKey, validMark: validMark, migrateV1: migrateV1,
    mergeMarks: mergeMarks, loadMarks: loadMarks, saveMarks: saveMarks,
    runV1Migration: runV1Migration, stateOf: stateOf, applyMark: applyMark};
}
