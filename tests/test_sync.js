const test = require("node:test");
const assert = require("node:assert");
const S = require("../templates/sync.js");

function fakeStorage(init) {
  const m = Object.assign({}, init || {});
  return {
    getItem: k => (k in m ? m[k] : null),
    setItem: (k, v) => { m[k] = String(v); },
    removeItem: k => { delete m[k]; },
    _raw: m,
  };
}

test("markKey namespaces by user and falls back to anon", () => {
  assert.equal(S.markKey("u1"), "gisa-cards-v2:u1");
  assert.equal(S.markKey(null), "gisa-cards-v2:anon");
  assert.equal(S.markKey(undefined), "gisa-cards-v2:anon");
});

test("migrateV1 timestamps legacy marks with t:1", () => {
  assert.deepEqual(S.migrateV1({"001": "hard", "002": "known"}),
    {"001": {s: "hard", t: 1}, "002": {s: "known", t: 1}});
});

test("migrateV1 drops unknown states and bad input", () => {
  assert.deepEqual(S.migrateV1({"001": "bogus"}), {});
  assert.deepEqual(S.migrateV1(null), {});
  assert.deepEqual(S.migrateV1("nope"), {});
});

test("mergeMarks unions ids from both sides", () => {
  const out = S.mergeMarks({"001": {s: "hard", t: 5}}, {"002": {s: "known", t: 5}});
  assert.deepEqual(Object.keys(out).sort(), ["001", "002"]);
});

test("mergeMarks takes the higher timestamp regardless of argument order", () => {
  const older = {"001": {s: "hard", t: 10}};
  const newer = {"001": {s: "known", t: 20}};
  assert.deepEqual(S.mergeMarks(older, newer), {"001": {s: "known", t: 20}});
  assert.deepEqual(S.mergeMarks(newer, older), {"001": {s: "known", t: 20}});
});

test("mergeMarks breaks timestamp ties toward needs-review", () => {
  const known = {"001": {s: "known", t: 1}};
  const hard = {"001": {s: "hard", t: 1}};
  assert.deepEqual(S.mergeMarks(known, hard), {"001": {s: "hard", t: 1}});
  assert.deepEqual(S.mergeMarks(hard, known), {"001": {s: "hard", t: 1}});
});

test("mergeMarks prefers hard over unsure on a tie", () => {
  const unsure = {"001": {s: "unsure", t: 1}};
  const hard = {"001": {s: "hard", t: 1}};
  assert.deepEqual(S.mergeMarks(unsure, hard), {"001": {s: "hard", t: 1}});
  assert.deepEqual(S.mergeMarks(hard, unsure), {"001": {s: "hard", t: 1}});
});

test("mergeMarks ignores malformed entries instead of adopting them", () => {
  const good = {"001": {s: "hard", t: 5}};
  const bad = {"001": {s: "nope", t: 9}, "002": "hard", "003": {s: "known"}};
  assert.deepEqual(S.mergeMarks(good, bad), {"001": {s: "hard", t: 5}});
});

test("mergeMarks tolerates null and non-object arguments", () => {
  assert.deepEqual(S.mergeMarks(null, undefined), {});
  assert.deepEqual(S.mergeMarks({"001": {s: "hard", t: 2}}, null),
    {"001": {s: "hard", t: 2}});
});

test("loadMarks reads only the requested user's bucket", () => {
  const st = fakeStorage({
    "gisa-cards-v2:u1": JSON.stringify({"001": {s: "hard", t: 3}}),
    "gisa-cards-v2:u2": JSON.stringify({"002": {s: "known", t: 3}}),
    "gisa-cards-v2:anon": JSON.stringify({"003": {s: "unsure", t: 3}}),
  });
  assert.deepEqual(S.loadMarks(st, "u1"), {"001": {s: "hard", t: 3}});
  assert.deepEqual(S.loadMarks(st, "u2"), {"002": {s: "known", t: 3}});
  assert.deepEqual(S.loadMarks(st, null), {"003": {s: "unsure", t: 3}});
});

test("loadMarks returns empty for a missing or corrupt bucket", () => {
  assert.deepEqual(S.loadMarks(fakeStorage(), "u1"), {});
  assert.deepEqual(S.loadMarks(fakeStorage({"gisa-cards-v2:u1": "{{{"}), "u1"), {});
});

test("saveMarks round-trips through loadMarks", () => {
  const st = fakeStorage();
  const marks = {"001": {s: "unsure", t: 42}};
  assert.equal(S.saveMarks(st, "u1", marks), true);
  assert.deepEqual(S.loadMarks(st, "u1"), marks);
});

test("saveMarks reports failure when storage throws", () => {
  const st = {getItem: () => null, setItem: () => { throw new Error("quota"); },
              removeItem: () => {}};
  assert.equal(S.saveMarks(st, "u1", {}), false);
});

test("runV1Migration moves legacy marks into the anon bucket and clears v1", () => {
  const st = fakeStorage({"gisa-cards-v1": JSON.stringify({"001": "hard"})});
  assert.equal(S.runV1Migration(st), true);
  assert.deepEqual(S.loadMarks(st, null), {"001": {s: "hard", t: 1}});
  assert.equal(st.getItem("gisa-cards-v1"), null);
});

test("runV1Migration merges into an existing anon bucket without clobbering", () => {
  const st = fakeStorage({
    "gisa-cards-v1": JSON.stringify({"001": "known"}),
    "gisa-cards-v2:anon": JSON.stringify({"002": {s: "hard", t: 99}}),
  });
  S.runV1Migration(st);
  assert.deepEqual(S.loadMarks(st, null),
    {"001": {s: "known", t: 1}, "002": {s: "hard", t: 99}});
});

test("runV1Migration is a no-op when there is no v1 data", () => {
  const st = fakeStorage();
  assert.equal(S.runV1Migration(st), false);
  assert.equal(st.getItem("gisa-cards-v2:anon"), null);
});

test("stateOf reads the state out of a v2 mark", () => {
  assert.equal(S.stateOf({"001": {s: "hard", t: 9}}, "001"), "hard");
  assert.equal(S.stateOf({}, "001"), undefined);
  assert.equal(S.stateOf({"001": {s: "bogus", t: 9}}, "001"), undefined);
});

test("applyMark sets a state with the supplied timestamp", () => {
  assert.deepEqual(S.applyMark({}, "001", "hard", 1000),
    {"001": {s: "hard", t: 1000}});
});

test("applyMark toggles the same state off", () => {
  const m = {"001": {s: "hard", t: 1000}};
  assert.deepEqual(S.applyMark(m, "001", "hard", 2000), {});
});

test("applyMark replaces a different state rather than toggling", () => {
  const m = {"001": {s: "hard", t: 1000}};
  assert.deepEqual(S.applyMark(m, "001", "known", 2000),
    {"001": {s: "known", t: 2000}});
});

test("applyMark does not mutate its input", () => {
  const m = {"001": {s: "hard", t: 1000}};
  S.applyMark(m, "001", "known", 2000);
  assert.deepEqual(m, {"001": {s: "hard", t: 1000}});
});
