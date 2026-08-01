# Cross-Device Progress Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Card marks made on one device appear on the user's other devices, with each user's progress fully isolated from every other user's.

**Architecture:** localStorage stays the source of truth for rendering and keeps working with no network. A Supabase row per user is a sync layer on top, reconciled by a per-card last-write-wins merge. All pure logic lives in two new build-inlined JS sources so it can be unit tested outside the 3.4MB generated `index.html`.

**Tech Stack:** Vanilla JS (no framework, no bundler), Python 3 `build.py` for assembly, Supabase (GoTrue auth + PostgREST) accessed over plain `fetch`, `node --test` for JS tests, `unittest` for Python tests.

**Spec:** `docs/superpowers/specs/2026-08-01-cross-device-sync-design.md`

## Running the tests

```bash
python3 -m unittest tests.test_build tests.test_classify tests.test_extract
node --test tests/test_sync.js tests/test_cloud.js
```

`pytest` is not installed and `tests/` has no `__init__.py`, so
`unittest discover` cannot import it — name the modules explicitly.

## Global Constraints

- **No external script or link tags.** `index.html` must load and run fully offline. All JS is inlined by `build.py`. The Supabase JS SDK is deliberately *not* used — see Task 4 rationale.
- **The only `https://` permitted in the output** is the Supabase project origin. No `http://` anywhere. `tests/test_build.py::test_build_emits_self_contained_html` enforces this and is updated in Task 3.
- **localStorage keys are namespaced by identity.** `gisa-cards-v2:<user_id>` for signed-in users, `gisa-cards-v2:anon` for pre-login marks. No bucket is ever read across identities.
- **Mark shape is `{s: "hard"|"unsure"|"known", t: <unix seconds>}`.** Never a bare string. Legacy v1 marks migrate with `t: 1`.
- **Merge is per-card last-write-wins:** union of ids; higher `t` wins; on equal `t`, `hard` > `unsure` > `known`.
- **Never silently claim the anon bucket.** Claiming requires an explicit user answer.
- **No sync failure may block the UI or discard a local mark.**
- **All user-facing strings are Korean**, matching the existing header/footer copy.
- **Supabase config is optional at build time.** With no `supabase.json`, the build must succeed and produce a working offline-only app.

---

### Task 1: Pure sync logic module

Creates the merge/migration logic as a standalone, unit-tested source file and teaches `build.py` to inline it. No app behavior changes yet.

**Files:**
- Create: `templates/sync.js`
- Create: `tests/test_sync.js`
- Modify: `build.py:63-67` (the `build()` template substitution)
- Modify: `templates/app.html:100-101` (add the placeholder)
- Test: `tests/test_sync.js`, `tests/test_build.py`

**Interfaces:**
- Consumes: nothing.
- Produces, all on the global scope once inlined:
  - `markKey(userId: string|null) -> string`
  - `migrateV1(v1: object) -> {[id]: {s, t}}`
  - `validMark(m: any) -> boolean`
  - `mergeMarks(a: object, b: object) -> {[id]: {s, t}}`
  - `loadMarks(storage: Storage, userId: string|null) -> {[id]: {s, t}}`
  - `saveMarks(storage: Storage, userId: string|null, marks: object) -> boolean`
  - `runV1Migration(storage: Storage) -> boolean`
  - `STATE_RANK: {hard: 3, unsure: 2, known: 1}`

- [ ] **Step 1: Write the failing test**

Create `tests/test_sync.js`:

```js
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/test_sync.js`
Expected: FAIL with `Cannot find module '../templates/sync.js'`

- [ ] **Step 3: Write the implementation**

Create `templates/sync.js`:

```js
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

/* Present only under node --test; absent in the browser, where build.py has
   already inlined these onto the script's scope. */
if (typeof module !== "undefined" && module.exports) {
  module.exports = {MARK_PREFIX: MARK_PREFIX, V1_KEY: V1_KEY, STATE_RANK: STATE_RANK,
    markKey: markKey, validMark: validMark, migrateV1: migrateV1,
    mergeMarks: mergeMarks, loadMarks: loadMarks, saveMarks: saveMarks,
    runV1Migration: runV1Migration};
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/test_sync.js`
Expected: PASS, 16 tests

- [ ] **Step 5: Add the placeholder to the app template**

In `templates/app.html`, replace line 101:

```js
const CARDS = /*__CARDS__*/;
```

with:

```js
const CARDS = /*__CARDS__*/;
/*__SYNC__*/
```

- [ ] **Step 6: Write the failing build test**

Add to `tests/test_build.py`, inside `class TestBuild`:

```python
    def test_build_inlines_the_sync_module(self):
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        html = build.build(cards, 1)
        self.assertIn("function mergeMarks(", html)
        self.assertIn("gisa-cards-v2", html)
        self.assertNotIn("/*__SYNC__*/", html)

    def test_build_strips_the_node_only_module_export(self):
        # The CommonJS tail exists for `node --test`. Leaving it in the browser
        # bundle is harmless but dead; assert we drop it so it cannot rot.
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        html = build.build(cards, 1)
        self.assertNotIn("module.exports", html)
```

- [ ] **Step 7: Run it to verify it fails**

Run: `python3 -m unittest tests.test_build -v`
Expected: FAIL — `/*__SYNC__*/` still present, `mergeMarks` absent

- [ ] **Step 8: Teach build.py to inline the module**

In `build.py`, add this helper above `def build(`:

```python
def read_js(name):
    """Inline a templates/*.js source, minus its node-only CommonJS tail."""
    path = os.path.join(HERE, "templates", name)
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    # The `if (typeof module !== "undefined")` block exists only so node --test
    # can require the file. It is dead weight in the browser, so drop it.
    return re.split(r'\nif \(typeof module !== "undefined"', src)[0].rstrip() + "\n"
```

Then in `build()`, change the final line from:

```python
    return tmpl.replace("/*__CARDS__*/", data)
```

to:

```python
    out = tmpl.replace("/*__CARDS__*/", data)
    return out.replace("/*__SYNC__*/", read_js("sync.js"))
```

- [ ] **Step 9: Run the full test suite**

Run: `python3 -m unittest tests.test_build tests.test_classify tests.test_extract && node --test tests/test_sync.js`
Expected: PASS, all tests

- [ ] **Step 10: Rebuild and confirm the app still works**

Run: `python3 build.py && python3 -c "print(open('index.html').read().count('mergeMarks'))"`
Expected: prints `1` or more, and the build prints its usual per-subject summary

- [ ] **Step 11: Commit**

```bash
git add templates/sync.js tests/test_sync.js templates/app.html build.py tests/test_build.py index.html
git commit -m "feat: add pure progress-merge logic and inline it at build time"
```

---

### Task 2: Namespaced v2 storage in the app

Switches the app from the bare-string v1 map to timestamped, per-identity marks. Still entirely offline — no network code yet. After this task the app behaves identically to today, but its data is sync-ready and the user's existing iPhone marks have migrated.

**Files:**
- Modify: `templates/app.html:102-105` (storage init), `:122-124` (`needsReview`), `:186-190` (`updateToc`), `:236-253` (`render` badge/count and `setMark`), `:290-294` (reset handler)
- Test: `tests/test_sync.js`

**Interfaces:**
- Consumes: `loadMarks`, `saveMarks`, `mergeMarks`, `runV1Migration`, `markKey` from Task 1.
- Produces, in `sync.js`:
  - `stateOf(marks: object, id: string) -> "hard"|"unsure"|"known"|undefined`
  - `applyMark(marks: object, id: string, s: string, now: number) -> object` — returns a new map; re-applying the current state clears it
- Produces, in `app.html`:
  - `currentUser: string|null` — global, `null` until Task 5 signs someone in.
  - `state(id: string) -> "hard"|"unsure"|"known"|undefined` — thin wrapper over `stateOf(mark, id)`; every render path uses this instead of touching `mark[id]` directly.
  - `mark: {[id]: {s, t}}` — global, always the v2 shape.
  - `save() -> void` — persists `mark` to the current identity's bucket.
  - `now() -> number` — unix seconds.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_sync.js`:

```js
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/test_sync.js`
Expected: FAIL with `S.stateOf is not a function`

- [ ] **Step 3: Add the two accessors to sync.js**

In `templates/sync.js`, insert above the `module.exports` block:

```js
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
```

And extend the export list with `stateOf: stateOf, applyMark: applyMark,`.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/test_sync.js`
Expected: PASS, 21 tests

- [ ] **Step 5: Switch the app template to v2 storage**

In `templates/app.html`, replace lines 102-105:

```js
const KEY = "gisa-cards-v1";
let mark = {};
try { mark = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { mark = {}; }
const save = () => localStorage.setItem(KEY, JSON.stringify(mark));
```

with:

```js
/* null until a user signs in; marks then move to that user's own bucket so a
   shared browser never leaks progress between accounts. */
let currentUser = null;
runV1Migration(localStorage);
let mark = loadMarks(localStorage, currentUser);
const save = () => saveMarks(localStorage, currentUser, mark);
const state = id => stateOf(mark, id);
const now = () => Math.floor(Date.now() / 1000);
```

- [ ] **Step 6: Update every read of the old bare-string shape**

In `templates/app.html`, replace line 123:

```js
  return mark[id] === "hard" || mark[id] === "unsure";
```

with:

```js
  return state(id) === "hard" || state(id) === "unsure";
```

Replace lines 187-188:

```js
    const m = mark[el.dataset.s];
    el.textContent = m === "hard" ? "😵" : m === "unsure" ? "🤔" : m === "known" ? "✅" : "";
```

with:

```js
    const m = state(el.dataset.s);
    el.textContent = m === "hard" ? "😵" : m === "unsure" ? "🤔" : m === "known" ? "✅" : "";
```

Replace lines 237-240:

```js
  const known = scope.filter(x => mark[x.id] === "known").length;
  const badge = mark[c.id] === "hard" ? " 😵"
    : mark[c.id] === "unsure" ? " 🤔"
    : mark[c.id] === "known" ? " ✅" : "";
```

with:

```js
  const known = scope.filter(x => state(x.id) === "known").length;
  const badge = state(c.id) === "hard" ? " 😵"
    : state(c.id) === "unsure" ? " 🤔"
    : state(c.id) === "known" ? " ✅" : "";
```

- [ ] **Step 7: Update the writer**

In `templates/app.html`, replace lines 247-253:

```js
function setMark(v) {
  const d = activeDeck(); if (!d.length) return;
  const id = d[i].id;
  mark[id] = mark[id] === v ? undefined : v;
  if (mark[id] === undefined) delete mark[id];
  save(); go(1);
}
```

with:

```js
function setMark(v) {
  const d = activeDeck(); if (!d.length) return;
  mark = applyMark(mark, d[i].id, v, now());
  save(); go(1);
}
```

- [ ] **Step 8: Rebuild and verify by hand**

Run: `python3 build.py && python3 -m http.server 8000 --directory .`

In a browser at `http://localhost:8000/index.html`:
1. Mark a card 😵 어려움 — the count badge shows 😵 and the TOC row shows 😵.
2. Reload — the mark survives.
3. In devtools console, run `localStorage.getItem("gisa-cards-v2:anon")` — expect JSON of shape `{"001":{"s":"hard","t":1754...}}`.
4. Run `localStorage.getItem("gisa-cards-v1")` — expect `null`.
5. Press 😵 again on the same card — the mark clears.
6. Click ↺ 초기화 — all marks clear.

Stop the server with Ctrl-C.

- [ ] **Step 9: Verify the migration against real v1 data**

In the devtools console:

```js
localStorage.clear();
localStorage.setItem("gisa-cards-v1", JSON.stringify({"001":"hard","002":"known"}));
location.reload();
```

After reload, run `localStorage.getItem("gisa-cards-v2:anon")`.
Expected: `{"001":{"s":"hard","t":1},"002":{"s":"known","t":1}}`, and `gisa-cards-v1` is gone. Card 001 shows 😵 and 002 shows ✅ in the TOC.

- [ ] **Step 10: Run the full suite**

Run: `python3 -m unittest tests.test_build tests.test_classify tests.test_extract && node --test tests/test_sync.js`
Expected: PASS

- [ ] **Step 11: Commit**

```bash
git add templates/sync.js templates/app.html tests/test_sync.js index.html
git commit -m "feat: namespace marks per identity and timestamp them"
```

---

### Task 3: Supabase configuration plumbing

Gets project credentials into the build without breaking the offline-only build, and relaxes the self-contained test by exactly the one origin we now need.

**Files:**
- Create: `supabase.example.json`
- Modify: `build.py` (`build()` and a new `read_supabase()`)
- Modify: `templates/app.html` (add `/*__SUPABASE__*/`)
- Modify: `tests/test_build.py:test_build_emits_self_contained_html`
- Modify: `.gitignore`
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `SUPA: {url: string, anonKey: string} | null` — global in the built page. `null` means "no cloud configured"; every later task must treat that as a supported state and skip all sync UI.

**Manual prerequisite — do this before Step 1.** These steps happen in the Supabase dashboard and cannot be scripted:

1. Create a free Supabase project. Note its **Project URL** and **anon public** key from Settings → API.
2. In the SQL editor, run:

```sql
create table progress (
  user_id uuid primary key references auth.users on delete cascade,
  data jsonb not null default '{}',
  updated_at timestamptz not null default now()
);
alter table progress enable row level security;
create policy "own row" on progress
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
```

3. Authentication → Providers → Email: enable it, and turn **Confirm email** on.
4. Authentication → Sign In / Providers → **disable "Allow new users to sign up"**. This is the only thing keeping the deck private, and it lives in dashboard config rather than in this repo.
5. Authentication → URL Configuration: set **Site URL** to `https://sinhong96.github.io/info-processing-gisa-cards/` and add both that URL and `http://localhost:8000/index.html` to **Redirect URLs**.
6. Authentication → Users → Add user: create the account with the email you will study under.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_build.py`, inside `class TestBuild`:

```python
    def test_build_without_config_disables_the_cloud(self):
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        html = build.build(cards, 1, supa=None)
        self.assertIn("const SUPA = null", html)
        self.assertNotIn("/*__SUPABASE__*/", html)

    def test_build_with_config_inlines_url_and_key(self):
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        html = build.build(cards, 1, supa={"url": "https://abc.supabase.co",
                                           "anonKey": "anon-key-here"})
        self.assertIn("https://abc.supabase.co", html)
        self.assertIn("anon-key-here", html)
```

And replace `test_build_emits_self_contained_html` with:

```python
    def test_build_emits_self_contained_html(self):
        # The page must load and run with no network. Requests to Supabase are
        # made at runtime by fetch; what is banned is anything the *browser*
        # would have to fetch before the app can start.
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        html = build.build(cards, 1, supa={"url": "https://abc.supabase.co",
                                           "anonKey": "k"})
        self.assertNotIn("<script src", html)
        self.assertNotIn("<link ", html)
        self.assertNotIn("http://", html)
        # The Supabase project origin is the only allowed absolute URL.
        for url in re.findall(r"https://[\w.-]+", html):
            self.assertEqual(url, "https://abc.supabase.co", f"unexpected host {url}")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_build -v`
Expected: FAIL — `build() got an unexpected keyword argument 'supa'`

- [ ] **Step 3: Add config loading to build.py**

In `build.py`, add above `def build(`:

```python
def read_supabase():
    """Project credentials, or None when the deck is built offline-only.

    The anon key is safe to publish: the `own row` RLS policy is what enforces
    per-user isolation, not the secrecy of this key.
    """
    path = os.path.join(HERE, "supabase.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    missing = [k for k in ("url", "anonKey") if not cfg.get(k)]
    if missing:
        raise SystemExit(f"supabase.json is missing: {', '.join(missing)}")
    return {"url": cfg["url"].rstrip("/"), "anonKey": cfg["anonKey"]}
```

Change the signature on line 47 from `def build(cards, subjects):` to:

```python
def build(cards, subjects, supa=None):
```

and change the return block to:

```python
    out = tmpl.replace("/*__CARDS__*/", data)
    out = out.replace("/*__SYNC__*/", read_js("sync.js"))
    return out.replace("/*__SUPABASE__*/",
                       json.dumps(supa) if supa else "null")
```

In `main()`, change the write call from `fh.write(build(cards, subjects))` to:

```python
        fh.write(build(cards, subjects, read_supabase()))
```

- [ ] **Step 4: Add the placeholder to the template**

In `templates/app.html`, immediately after the `/*__SYNC__*/` line, add:

```js
/* Supabase project config, or null when built without supabase.json. Null is a
   supported state: the app runs offline-only and shows no sync UI. */
const SUPA = /*__SUPABASE__*/;
```

- [ ] **Step 5: Run the tests**

Run: `python3 -m unittest tests.test_build -v`
Expected: PASS

- [ ] **Step 6: Add the example config and ignore the real one**

Create `supabase.example.json`:

```json
{
  "url": "https://YOUR-PROJECT.supabase.co",
  "anonKey": "YOUR-ANON-PUBLIC-KEY"
}
```

Append to `.gitignore`:

```
supabase.json
```

The anon key is publishable, but the real config is gitignored anyway so a
fork does not silently sync into someone else's project.

- [ ] **Step 7: Create your real config and rebuild**

```bash
cp supabase.example.json supabase.json
# edit supabase.json with the values from the manual prerequisite
python3 build.py
grep -c "supabase.co" index.html
```

Expected: `grep` prints a non-zero count.

- [ ] **Step 8: Commit**

```bash
git add build.py templates/app.html tests/test_build.py supabase.example.json .gitignore index.html
git commit -m "feat: plumb optional Supabase config through the build"
```

---

### Task 4: Supabase REST client

The network layer, split from the UI so its parsing logic can be tested.

**Why no Supabase JS SDK:** the SDK would have to be vendored and inlined (a CDN `<script src>` would break offline loading, which is the whole point of the architecture). We need four endpoints. Hand-rolling them is ~90 lines with no vendored blob, and matches the codebase's dependency-free character.

**Files:**
- Create: `templates/cloud.js`
- Create: `tests/test_cloud.js`
- Modify: `build.py` (`build()` — add the `/*__CLOUD__*/` substitution)
- Modify: `templates/app.html` (add the placeholder)
- Test: `tests/test_cloud.js`, `tests/test_build.py`

**Interfaces:**
- Consumes: `SUPA` from Task 3.
- Produces:
  - `decodeJwt(jwt: string) -> object|null` — the decoded payload
  - `parseAuthHash(hash: string, nowSec: number) -> {access_token, refresh_token, expires_at, user_id, email}|null`
  - `sessionValid(sess: object|null, nowSec: number) -> boolean`
  - `isAuthError(err: Error) -> boolean` — true for 401/403, the "session is dead" signal
  - `loadSession(storage) -> object|null` / `saveSession(storage, sess) -> void` / `clearSession(storage) -> void`
  - `sendMagicLink(cfg, email, redirectTo) -> Promise<true>`
  - `refreshSession(cfg, refreshToken, nowSec) -> Promise<session>`
  - `fetchProgress(cfg, sess) -> Promise<object>` — the stored marks map, `{}` if no row yet
  - `pushProgress(cfg, sess, marks) -> Promise<true>`

A session object is always `{access_token, refresh_token, expires_at, user_id, email}`. `email` is carried so the header can show who is signed in without a second request.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cloud.js`:

```js
const test = require("node:test");
const assert = require("node:assert");
const C = require("../templates/cloud.js");

const CFG = {url: "https://abc.supabase.co", anonKey: "anon-key"};

// A JWT is header.payload.signature; only the payload is read, and only for
// `sub`. Signature verification is the server's job.
function jwt(payload) {
  const b64 = Buffer.from(JSON.stringify(payload)).toString("base64")
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return "h." + b64 + ".s";
}

test("decodeJwt returns the payload claims", () => {
  assert.deepEqual(C.decodeJwt(jwt({sub: "user-123", email: "a@b.c"})),
    {sub: "user-123", email: "a@b.c"});
});

test("decodeJwt returns null on garbage", () => {
  assert.equal(C.decodeJwt("not-a-jwt"), null);
  assert.equal(C.decodeJwt(""), null);
});

test("parseAuthHash reads a magic-link fragment", () => {
  const t = jwt({sub: "user-123", email: "a@b.c"});
  const h = "#access_token=" + t + "&refresh_token=r1&expires_in=3600&type=magiclink";
  assert.deepEqual(C.parseAuthHash(h, 1000), {
    access_token: t, refresh_token: "r1", expires_at: 4600,
    user_id: "user-123", email: "a@b.c",
  });
});

test("parseAuthHash yields no user_id when the token carries no sub", () => {
  const h = "#access_token=" + jwt({email: "a@b.c"}) + "&refresh_token=r1";
  assert.equal(C.parseAuthHash(h, 1000).user_id, null);
});

test("isAuthError fires only on 401 and 403", () => {
  assert.equal(C.isAuthError(new Error("/rest/v1/progress 401")), true);
  assert.equal(C.isAuthError(new Error("/rest/v1/progress 403")), true);
  assert.equal(C.isAuthError(new Error("/rest/v1/progress 500")), false);
  assert.equal(C.isAuthError(new TypeError("Failed to fetch")), false);
});

test("parseAuthHash returns null for unrelated or partial fragments", () => {
  assert.equal(C.parseAuthHash("", 1000), null);
  assert.equal(C.parseAuthHash("#some=thing", 1000), null);
  assert.equal(C.parseAuthHash("#access_token=x", 1000), null);
});

test("sessionValid treats a session near expiry as stale", () => {
  const s = {access_token: "a", refresh_token: "r", expires_at: 1000, user_id: "u"};
  assert.equal(C.sessionValid(s, 800), true);
  assert.equal(C.sessionValid(s, 960), false);  // inside the 60s skew margin
  assert.equal(C.sessionValid(s, 2000), false);
  assert.equal(C.sessionValid(null, 800), false);
});

test("sendMagicLink posts the email to the otp endpoint", async () => {
  const calls = [];
  global.fetch = async (url, opts) => {
    calls.push({url, opts});
    return {ok: true, status: 200, json: async () => ({})};
  };
  await C.sendMagicLink(CFG, "a@b.c", "https://site/index.html");
  assert.match(calls[0].url, /^https:\/\/abc\.supabase\.co\/auth\/v1\/otp\?redirect_to=/);
  assert.equal(calls[0].opts.headers.apikey, "anon-key");
  // create_user is left to the dashboard's signup toggle, so the code does not
  // need editing when the deck opens to other users.
  assert.deepEqual(JSON.parse(calls[0].opts.body),
    {email: "a@b.c", create_user: true});
});

test("sendMagicLink rejects on a non-ok response", async () => {
  global.fetch = async () => ({ok: false, status: 429, json: async () => ({})});
  await assert.rejects(() => C.sendMagicLink(CFG, "a@b.c", "https://site/"),
    /429/);
});

test("fetchProgress returns the stored marks map", async () => {
  global.fetch = async () => ({
    ok: true, status: 200,
    json: async () => ([{data: {"001": {s: "hard", t: 5}}}]),
  });
  const sess = {access_token: "at", user_id: "u1"};
  assert.deepEqual(await C.fetchProgress(CFG, sess), {"001": {s: "hard", t: 5}});
});

test("fetchProgress returns an empty map when the user has no row yet", async () => {
  global.fetch = async () => ({ok: true, status: 200, json: async () => ([])});
  assert.deepEqual(await C.fetchProgress(CFG, {access_token: "at", user_id: "u1"}), {});
});

test("fetchProgress rejects rather than returning junk", async () => {
  global.fetch = async () => ({ok: false, status: 401, json: async () => ({})});
  await assert.rejects(() => C.fetchProgress(CFG, {access_token: "at", user_id: "u1"}),
    /401/);
});

test("pushProgress upserts the row for the signed-in user", async () => {
  const calls = [];
  global.fetch = async (url, opts) => {
    calls.push({url, opts});
    return {ok: true, status: 201, json: async () => ({})};
  };
  const marks = {"001": {s: "known", t: 7}};
  await C.pushProgress(CFG, {access_token: "at", user_id: "u1"}, marks);
  assert.equal(calls[0].url, "https://abc.supabase.co/rest/v1/progress");
  assert.equal(calls[0].opts.headers.Prefer,
    "resolution=merge-duplicates,return=minimal");
  assert.equal(calls[0].opts.headers.Authorization, "Bearer at");
  const body = JSON.parse(calls[0].opts.body);
  assert.equal(body.user_id, "u1");
  assert.deepEqual(body.data, marks);
});

test("refreshSession exchanges a refresh token for a new session", async () => {
  const t = jwt({sub: "user-123", email: "a@b.c"});
  global.fetch = async () => ({
    ok: true, status: 200,
    json: async () => ({access_token: t, refresh_token: "r2", expires_in: 3600}),
  });
  const s = await C.refreshSession(CFG, "r1", 1000);
  assert.equal(s.user_id, "user-123");
  assert.equal(s.email, "a@b.c");
  assert.equal(s.refresh_token, "r2");
  assert.equal(s.expires_at, 4600);
});

test("refreshSession surfaces a dead refresh token as an auth error", async () => {
  global.fetch = async () => ({ok: false, status: 401, json: async () => ({})});
  await assert.rejects(() => C.refreshSession(CFG, "stale", 1000),
    err => C.isAuthError(err));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/test_cloud.js`
Expected: FAIL with `Cannot find module '../templates/cloud.js'`

- [ ] **Step 3: Write the implementation**

Create `templates/cloud.js`:

```js
/* Supabase access over plain fetch: GoTrue for auth, PostgREST for the one
   progress row. No SDK — a CDN <script src> would break offline loading, and
   vendoring a bundle to call four endpoints is not worth the blob. */

var SESSION_KEY = "gisa-cards-session";
var SKEW = 60;  // treat a session expiring within a minute as already stale

/* base64url -> the payload claims. Read, never trusted: the access token is
   verified server-side on every request, and we only use `sub` to pick a
   localStorage bucket and `email` to label the header button. */
function decodeJwt(t) {
  try {
    var b64 = t.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    b64 += "===".slice((b64.length + 3) % 4);
    var json = decodeURIComponent(atob(b64).split("").map(function (c) {
      return "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(""));
    return JSON.parse(json);
  } catch (e) { return null; }
}

function sessionFrom(accessToken, refreshToken, expiresIn, nowSec) {
  var p = decodeJwt(accessToken) || {};
  return {
    access_token: accessToken,
    refresh_token: refreshToken,
    expires_at: nowSec + (expiresIn || 3600),
    user_id: p.sub || null,
    email: p.email || null,
  };
}

/* Supabase hands the session back in the URL fragment after a magic-link
   click. Fragments never reach a server, which is why the tokens ride there. */
function parseAuthHash(hash, nowSec) {
  if (!hash || hash.indexOf("access_token") < 0) return null;
  var p = new URLSearchParams(hash.replace(/^#/, ""));
  var at = p.get("access_token"), rt = p.get("refresh_token");
  if (!at || !rt) return null;
  return sessionFrom(at, rt, parseInt(p.get("expires_in") || "3600", 10), nowSec);
}

function sessionValid(sess, nowSec) {
  return !!sess && !!sess.access_token && nowSec < (sess.expires_at || 0) - SKEW;
}

/* A dead session, as distinct from a dead network. The two need different
   responses: re-login versus retry later. */
function isAuthError(err) {
  return /\b(401|403)$/.test(String((err && err.message) || ""));
}

function loadSession(storage) {
  try { return JSON.parse(storage.getItem(SESSION_KEY) || "null"); }
  catch (e) { return null; }
}
function saveSession(storage, sess) {
  try { storage.setItem(SESSION_KEY, JSON.stringify(sess)); } catch (e) {}
}
function clearSession(storage) {
  try { storage.removeItem(SESSION_KEY); } catch (e) {}
}

function req(cfg, path, opts) {
  var o = opts || {};
  var h = {apikey: cfg.anonKey, "Content-Type": "application/json"};
  Object.keys(o.headers || {}).forEach(function (k) { h[k] = o.headers[k]; });
  return fetch(cfg.url + path, {
    method: o.method || "GET",
    headers: h,
    body: o.body === undefined ? undefined : JSON.stringify(o.body),
  }).then(function (r) {
    if (!r.ok) throw new Error(path.split("?")[0] + " " + r.status);
    return r;
  });
}

/* create_user is always true; whether a new address is accepted is the
   dashboard's "Allow new users to sign up" toggle. Opening the deck to other
   users is therefore config, not a code change. */
function sendMagicLink(cfg, email, redirectTo) {
  return req(cfg, "/auth/v1/otp?redirect_to=" + encodeURIComponent(redirectTo),
             {method: "POST", body: {email: email, create_user: true}})
    .then(function () { return true; });
}

function refreshSession(cfg, refreshToken, nowSec) {
  return req(cfg, "/auth/v1/token?grant_type=refresh_token",
             {method: "POST", body: {refresh_token: refreshToken}})
    .then(function (r) { return r.json(); })
    .then(function (j) {
      return sessionFrom(j.access_token, j.refresh_token, j.expires_in, nowSec);
    });
}

/* RLS scopes this to the caller's own row, so no user_id filter is needed —
   and adding one would not make it any safer. */
function fetchProgress(cfg, sess) {
  return req(cfg, "/rest/v1/progress?select=data",
             {headers: {Authorization: "Bearer " + sess.access_token}})
    .then(function (r) { return r.json(); })
    .then(function (rows) {
      return (rows && rows[0] && rows[0].data) || {};
    });
}

function pushProgress(cfg, sess, marks) {
  return req(cfg, "/rest/v1/progress", {
    method: "POST",
    headers: {
      Authorization: "Bearer " + sess.access_token,
      Prefer: "resolution=merge-duplicates,return=minimal",
    },
    body: {user_id: sess.user_id, data: marks,
           updated_at: new Date().toISOString()},
  }).then(function () { return true; });
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {SESSION_KEY: SESSION_KEY, decodeJwt: decodeJwt,
    sessionFrom: sessionFrom, parseAuthHash: parseAuthHash,
    sessionValid: sessionValid, isAuthError: isAuthError,
    loadSession: loadSession, saveSession: saveSession, clearSession: clearSession,
    sendMagicLink: sendMagicLink, refreshSession: refreshSession,
    fetchProgress: fetchProgress, pushProgress: pushProgress};
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/test_cloud.js`
Expected: PASS, 15 tests

- [ ] **Step 5: Inline it in the build**

In `templates/app.html`, add `/*__CLOUD__*/` on its own line immediately after the `const SUPA = ...;` line.

In `build.py`, change the return block of `build()` to:

```python
    out = tmpl.replace("/*__CARDS__*/", data)
    out = out.replace("/*__SYNC__*/", read_js("sync.js"))
    out = out.replace("/*__CLOUD__*/", read_js("cloud.js"))
    return out.replace("/*__SUPABASE__*/",
                       json.dumps(supa) if supa else "null")
```

Add to `tests/test_build.py`, inside `class TestBuild`:

```python
    def test_build_inlines_the_cloud_module(self):
        cards = json.load(open(os.path.join(ROOT, "cards.json"), encoding="utf-8"))
        html = build.build(cards, 1)
        self.assertIn("function pushProgress(", html)
        self.assertNotIn("/*__CLOUD__*/", html)
```

- [ ] **Step 6: Run the full suite**

Run: `python3 -m unittest tests.test_build tests.test_classify tests.test_extract && node --test tests/test_sync.js tests/test_cloud.js`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add templates/cloud.js tests/test_cloud.js build.py templates/app.html tests/test_build.py index.html
git commit -m "feat: add Supabase REST client for auth and progress"
```

---

### Task 5: Sign-in UI and session lifecycle

Adds the header control, the magic-link round trip, and session restore. No mark syncing yet — signing in only switches which localStorage bucket is active, which is itself observable and reviewable.

**Files:**
- Modify: `templates/app.html` — header markup (~line 82), CSS (~line 22), and the script tail (~line 321)
- Test: manual, against `http://localhost:8000`

**Interfaces:**
- Consumes: `SUPA`, `currentUser`, `mark`, `save`, `loadMarks`, `render` from Tasks 1-4; all of `cloud.js`.
- Produces:
  - `session: object|null` — global.
  - `switchIdentity(userId: string|null) -> void` — repoints `mark` at another bucket and re-renders.
  - `signIn() -> void`, `signOut() -> void`
  - `renderAuth() -> void` — refreshes the header control.

- [ ] **Step 1: Add the header control and its styling**

In `templates/app.html`, replace line 82:

```html
  <span class="count" id="count"></span>
```

with:

```html
  <span class="count" id="count"></span>
  <button id="authbtn" hidden></button>
```

And add to the `<style>` block, after the `select{...}` rule (line 22):

```css
  #authbtn{max-width:38vw;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
```

- [ ] **Step 2: Add the session lifecycle to the script**

In `templates/app.html`, insert immediately before the `buildSubjectSelect();` call at the end of the script:

```js
/* ---- auth ---------------------------------------------------------------
   Signing in only decides which localStorage bucket `mark` points at. The
   cloud round trip is layered on in the next task, so a failed or absent
   sign-in leaves a fully working offline app. */
let session = null;

function switchIdentity(userId) {
  currentUser = userId;
  mark = loadMarks(localStorage, currentUser);
  i = 0; flipped = false;
  render();
}

function renderAuth() {
  const b = document.getElementById("authbtn");
  if (!SUPA) { b.hidden = true; return; }   // built offline-only
  b.hidden = false;
  b.textContent = session ? "🔓 " + (session.email || "로그아웃") : "🔐 로그인";
  b.title = session ? "로그아웃" : "이메일로 로그인";
}

function signIn() {
  const email = prompt("로그인할 이메일 주소를 입력하세요.");
  if (!email) return;
  sendMagicLink(SUPA, email.trim(), location.href.split("#")[0])
    .then(() => alert("로그인 링크를 보냈습니다. 이메일을 확인하세요."))
    .catch(() => alert("링크를 보내지 못했습니다. 잠시 후 다시 시도하세요."));
}

function signOut() {
  clearSession(localStorage);
  session = null;
  switchIdentity(null);
  renderAuth();
}

/* Adopt a session from the magic-link fragment, else restore and refresh a
   stored one. Every failure path lands on "stay signed out and keep working". */
function initAuth() {
  if (!SUPA) { renderAuth(); return Promise.resolve(); }
  const fromLink = parseAuthHash(location.hash, now());
  if (fromLink && fromLink.user_id) {
    history.replaceState(null, "", location.pathname + location.search);
    session = fromLink;
    saveSession(localStorage, session);
    switchIdentity(session.user_id);
    renderAuth();
    return Promise.resolve();
  }
  const stored = loadSession(localStorage);
  if (!stored) { renderAuth(); return Promise.resolve(); }
  if (sessionValid(stored, now())) {
    session = stored;
    switchIdentity(session.user_id);
    renderAuth();
    return Promise.resolve();
  }
  return refreshSession(SUPA, stored.refresh_token, now())
    .then(s => {
      session = s;
      saveSession(localStorage, session);
      switchIdentity(session.user_id);
    })
    .catch(() => { clearSession(localStorage); session = null; })
    .then(renderAuth);
}

document.getElementById("authbtn").onclick = () => session ? signOut() : signIn();
```

Then change the final three lines of the script from:

```js
buildSubjectSelect();
buildToc();
render();
```

to:

```js
buildSubjectSelect();
buildToc();
render();
initAuth();
```

- [ ] **Step 3: Rebuild and verify the offline-only path first**

```bash
mv supabase.json supabase.json.bak && python3 build.py
python3 -m http.server 8000 --directory .
```

At `http://localhost:8000/index.html`: the header shows **no** 로그인 button, and marking cards works exactly as before. This is the "built without config" contract from Task 3.

```bash
mv supabase.json.bak supabase.json && python3 build.py
```

- [ ] **Step 4: Verify the magic-link round trip**

With the server still running, reload `http://localhost:8000/index.html`.

1. The header shows 🔐 로그인.
2. Click it, enter the email you created in the Task 3 prerequisite.
3. Expect the alert "로그인 링크를 보냈습니다."
4. Open the link from your inbox. It must land back on `localhost:8000` with the header now showing 🔓 and your marks reset to that account's (empty) bucket.
5. In the console, `localStorage.getItem("gisa-cards-session")` returns a JSON session, and the URL has **no** `#access_token` left in it.
6. Mark a card, then check `Object.keys(localStorage).filter(k => k.startsWith("gisa-cards-v2"))` — expect both `:anon` and `:<your-uuid>`, with the new mark only in the user bucket.
7. Reload — you stay signed in and the mark is still there.
8. Click 🔓 to sign out — marks revert to the anon bucket's contents, and the user bucket is left untouched on disk.

- [ ] **Step 5: Verify an unknown email is rejected**

Click 로그인 and enter an address that has no Supabase user. Because signup is disabled, expect the failure alert rather than a new account. If a new account *is* created, revisit step 4 of the Task 3 prerequisite — signup is still enabled.

- [ ] **Step 6: Run the full suite**

Run: `python3 -m unittest tests.test_build tests.test_classify tests.test_extract && node --test tests/test_sync.js tests/test_cloud.js`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add templates/app.html index.html
git commit -m "feat: add magic-link sign-in and per-identity bucket switching"
```

---

### Task 6: Sync engine

Wires marks to the cloud: pull-and-merge on sign-in, debounced push after changes, and a status indicator.

**Files:**
- Modify: `templates/app.html` — CSS (~line 22), header markup, script
- Test: `tests/test_sync.js` (debounce-independent logic), manual two-device check

**Interfaces:**
- Consumes: everything from Tasks 1-5.
- Produces:
  - `syncStatus: "off"|"synced"|"pending"|"offline"` — global.
  - `setSyncStatus(s: string) -> void`
  - `pullAndMerge() -> Promise<void>` — fetch remote, merge into local, save, re-render, push back if the merge changed anything.
  - `queuePush() -> void` — debounced, ~2s.
  - `flushPush() -> void` — immediate; used on `pagehide`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_sync.js`:

```js
test("marksDiffer detects an added, changed, or removed card", () => {
  const a = {"001": {s: "hard", t: 1}};
  assert.equal(S.marksDiffer(a, a), false);
  assert.equal(S.marksDiffer(a, {"001": {s: "hard", t: 1}}), false);
  assert.equal(S.marksDiffer(a, {"001": {s: "known", t: 1}}), true);
  assert.equal(S.marksDiffer(a, {"001": {s: "hard", t: 2}}), true);
  assert.equal(S.marksDiffer(a, {}), true);
  assert.equal(S.marksDiffer(a, {"001": {s: "hard", t: 1}, "002": {s: "known", t: 1}}), true);
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `node --test tests/test_sync.js`
Expected: FAIL with `S.marksDiffer is not a function`

- [ ] **Step 3: Implement it**

In `templates/sync.js`, add above the `module.exports` block:

```js
/* Cheap equality over the mark map. Used to decide whether a merge actually
   changed anything, so an unchanged pull does not trigger a pointless push. */
function marksDiffer(a, b) {
  var ka = Object.keys(a), kb = Object.keys(b);
  if (ka.length !== kb.length) return true;
  return ka.some(function (id) {
    return !b[id] || b[id].s !== a[id].s || b[id].t !== a[id].t;
  });
}
```

Extend the export list with `marksDiffer: marksDiffer,`.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/test_sync.js`
Expected: PASS, 22 tests

- [ ] **Step 5: Add the status dot to the header**

In `templates/app.html`, replace the `<button id="authbtn" hidden></button>` line with:

```html
  <span id="syncdot" title="" hidden></span>
  <button id="authbtn" hidden></button>
```

Add to the `<style>` block, after the `#authbtn{...}` rule:

```css
  #syncdot{width:9px;height:9px;border-radius:50%;flex:none;background:var(--muted)}
  #syncdot.synced{background:#2f9e44}
  #syncdot.pending{background:#e8b33a}
  #syncdot.offline{background:#e03131}
```

- [ ] **Step 6: Add the sync engine to the script**

In `templates/app.html`, insert immediately before the `document.getElementById("authbtn").onclick` line:

```js
/* ---- sync ---------------------------------------------------------------
   localStorage is the source of truth; this layer only reconciles it with the
   cloud. Every failure below is swallowed on purpose: a dead network must
   degrade to "offline dot" and never to a lost mark or a blocked UI. */
let syncStatus = "off";
let pushTimer = null;

function setSyncStatus(s) {
  syncStatus = s;
  const d = document.getElementById("syncdot");
  d.hidden = (s === "off");
  d.className = s;
  d.title = s === "synced" ? "동기화됨"
    : s === "pending" ? "동기화 중…"
    : s === "offline" ? "오프라인 — 기기에만 저장됨" : "";
}

/* A 401 means the session died, not that the network did, and the two need
   different responses. Refresh once and retry; if the refresh also fails, the
   session is unrecoverable — drop to signed-out and say so. Marks stay in the
   user's bucket either way, so nothing is lost by being logged out. */
function withAuth(attempt) {
  return attempt().catch(err => {
    if (!isAuthError(err) || !session) throw err;
    return refreshSession(SUPA, session.refresh_token, now())
      .then(s => { session = s; saveSession(localStorage, session); renderAuth(); })
      .then(attempt)
      .catch(err2 => {
        if (!isAuthError(err2)) throw err2;
        signOut();
        alert("로그인이 만료되었습니다. 다시 로그인해 주세요.\n" +
              "표시한 내용은 이 기기에 그대로 남아 있습니다.");
        throw err2;
      });
  });
}

function pullAndMerge() {
  if (!SUPA || !session) return Promise.resolve();
  setSyncStatus("pending");
  return withAuth(() => fetchProgress(SUPA, session))
    .then(remote => {
      const merged = mergeMarks(mark, remote);
      const localChanged = marksDiffer(mark, merged);
      const remoteStale = marksDiffer(remote, merged);
      if (localChanged) { mark = merged; save(); render(); }
      // Only write back when the merge actually taught the server something.
      return remoteStale ? withAuth(() => pushProgress(SUPA, session, merged)) : true;
    })
    .then(() => setSyncStatus("synced"))
    .catch(() => setSyncStatus("offline"));
}

function flushPush() {
  if (!SUPA || !session) return;
  clearTimeout(pushTimer); pushTimer = null;
  setSyncStatus("pending");
  withAuth(() => pushProgress(SUPA, session, mark))
    .then(() => setSyncStatus("synced"))
    .catch(() => setSyncStatus("offline"));
}

/* Debounced: marking runs in bursts, and one request per card would be rate
   limits and phone battery for no benefit. */
function queuePush() {
  if (!SUPA || !session) return;
  setSyncStatus("pending");
  clearTimeout(pushTimer);
  pushTimer = setTimeout(flushPush, 2000);
}

addEventListener("pagehide", flushPush);
addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") flushPush();
});
```

- [ ] **Step 7: Trigger a push whenever marks change**

In `templates/app.html`, change `setMark` to:

```js
function setMark(v) {
  const d = activeDeck(); if (!d.length) return;
  mark = applyMark(mark, d[i].id, v, now());
  save(); queuePush(); go(1);
}
```

And change the 초기화 handler body from `mark = {}; save();` to:

```js
  mark = {}; save(); queuePush();
```

- [ ] **Step 8: Pull on sign-in and on load**

In `templates/app.html`, in `switchIdentity`, replace the final `render();` with:

```js
  render();
  if (currentUser) pullAndMerge(); else setSyncStatus("off");
```

And in `signOut`, add `setSyncStatus("off");` immediately after `session = null;`.

- [ ] **Step 9: Rebuild and verify single-device sync**

```bash
python3 build.py && python3 -m http.server 8000 --directory .
```

At `http://localhost:8000/index.html`, signed in:
1. The dot turns 🟡 then 🟢 shortly after load.
2. Mark a card — the dot goes 🟡, then 🟢 within ~2s.
3. In the Supabase dashboard, Table Editor → `progress`: your row holds the mark.
4. Devtools → Network → set throttling to **Offline**. Mark another card. The dot turns 🔴, the mark still appears in the UI and in localStorage, and nothing throws in the console.
5. Set throttling back to **No throttling** and reload. The dot returns 🟢 and the offline mark is now in the Supabase row.

- [ ] **Step 10: Verify the cross-device merge**

This is the actual goal of the whole plan, so test it for real.

1. On the MacBook, signed in, mark card 001 as 😵.
2. On the iPhone, open the deployed page (or `http://<mac-lan-ip>:8000/index.html`), sign in with the same email.
3. Card 001 shows 😵 on the phone without any manual action.
4. On the phone, mark card 002 as ✅.
5. Back on the MacBook, reload. Card 002 now shows ✅ and card 001 is still 😵.

- [ ] **Step 11: Verify the offline-conflict case**

The scenario the per-card merge exists for:

1. Phone: devtools/airplane mode offline. Mark card 003 as 😵. Leave it offline.
2. Mac: online, mark card 004 as ✅. Wait for 🟢.
3. Phone: back online, reload.
4. Expect **both** 003 😵 and 004 ✅ present on both devices. Neither device's work is lost.

- [ ] **Step 12: Verify the expired-session path**

Forge a dead session and confirm it recovers rather than silently failing. In the console:

```js
const s = JSON.parse(localStorage.getItem("gisa-cards-session"));
s.access_token = "h.eyJzdWIiOiJib2d1cyJ9.s";   // valid shape, rejected by the server
s.refresh_token = "definitely-not-valid";
localStorage.setItem("gisa-cards-session", JSON.stringify(s));
location.reload();
```

Expected: the refresh fails, you land signed out with the alert
"로그인이 만료되었습니다…", the dot returns to hidden, and your marks are still
in `gisa-cards-v2:<uuid>` untouched. Sign in again and they come back.

- [ ] **Step 13: Run the full suite**

Run: `python3 -m unittest tests.test_build tests.test_classify tests.test_extract && node --test tests/test_sync.js tests/test_cloud.js`
Expected: PASS

- [ ] **Step 14: Commit**

```bash
git add templates/sync.js templates/app.html tests/test_sync.js index.html
git commit -m "feat: sync marks to Supabase with per-card merge and status dot"
```

---

### Task 7: Anon bucket claim prompt

The device-side half of user isolation. Without this, a friend signing in on a shared browser inherits whatever marks were made before they arrived.

**Files:**
- Modify: `templates/sync.js`, `templates/app.html`
- Test: `tests/test_sync.js`, manual

**Interfaces:**
- Consumes: `mergeMarks`, `loadMarks`, `saveMarks`, `markKey` from Task 1; `switchIdentity`, `pullAndMerge` from Tasks 5-6.
- Produces:
  - `anonMarkCount(storage) -> number`
  - `claimAnon(storage, userId) -> object` — merges anon into the user's bucket, clears anon, returns the merged map.
  - `maybeClaimAnon() -> void` in the app.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_sync.js`:

```js
test("anonMarkCount counts only the anon bucket", () => {
  const st = fakeStorage({
    "gisa-cards-v2:anon": JSON.stringify({"001": {s: "hard", t: 1}}),
    "gisa-cards-v2:u1": JSON.stringify({"002": {s: "known", t: 1},
                                        "003": {s: "known", t: 1}}),
  });
  assert.equal(S.anonMarkCount(st), 1);
  assert.equal(S.anonMarkCount(fakeStorage()), 0);
});

test("claimAnon merges anon into the user bucket and clears anon", () => {
  const st = fakeStorage({
    "gisa-cards-v2:anon": JSON.stringify({"001": {s: "hard", t: 5}}),
    "gisa-cards-v2:u1": JSON.stringify({"002": {s: "known", t: 5}}),
  });
  const out = S.claimAnon(st, "u1");
  assert.deepEqual(out, {"001": {s: "hard", t: 5}, "002": {s: "known", t: 5}});
  assert.deepEqual(S.loadMarks(st, "u1"), out);
  assert.equal(st.getItem("gisa-cards-v2:anon"), null);
});

test("claimAnon applies the merge rule rather than overwriting", () => {
  const st = fakeStorage({
    "gisa-cards-v2:anon": JSON.stringify({"001": {s: "hard", t: 1}}),
    "gisa-cards-v2:u1": JSON.stringify({"001": {s: "known", t: 99}}),
  });
  // The user's newer 암기함 must survive a legacy t:1 어려움.
  assert.deepEqual(S.claimAnon(st, "u1"), {"001": {s: "known", t: 99}});
});

test("claimAnon leaves other users' buckets untouched", () => {
  const st = fakeStorage({
    "gisa-cards-v2:anon": JSON.stringify({"001": {s: "hard", t: 5}}),
    "gisa-cards-v2:u2": JSON.stringify({"009": {s: "known", t: 5}}),
  });
  S.claimAnon(st, "u1");
  assert.deepEqual(S.loadMarks(st, "u2"), {"009": {s: "known", t: 5}});
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `node --test tests/test_sync.js`
Expected: FAIL with `S.anonMarkCount is not a function`

- [ ] **Step 3: Implement**

In `templates/sync.js`, add above the `module.exports` block:

```js
function anonMarkCount(storage) {
  return Object.keys(loadMarks(storage, null)).length;
}

/* Fold pre-login marks into a signed-in user's bucket. Called only after an
   explicit yes — a silent claim is exactly how one user would inherit
   another's progress on a shared browser. */
function claimAnon(storage, userId) {
  var merged = mergeMarks(loadMarks(storage, userId), loadMarks(storage, null));
  saveMarks(storage, userId, merged);
  try { storage.removeItem(markKey(null)); } catch (e) {}
  return merged;
}
```

Extend the export list with `anonMarkCount: anonMarkCount, claimAnon: claimAnon,`.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/test_sync.js`
Expected: PASS, 26 tests

- [ ] **Step 5: Ask before claiming, in the app**

In `templates/app.html`, add immediately after the `switchIdentity` function:

```js
/* Pre-login marks belong to whoever made them, and only that person knows who
   that is. Asking is what keeps a shared browser from moving one user's
   progress into another user's account. */
function maybeClaimAnon() {
  if (!currentUser || !anonMarkCount(localStorage)) return;
  const n = anonMarkCount(localStorage);
  const ok = confirm(
    "이 기기에 로그인 전 학습 기록이 " + n + "장 있습니다.\n내 계정에 합칠까요?");
  if (!ok) return;
  mark = claimAnon(localStorage, currentUser);
  render();
  queuePush();
}
```

- [ ] **Step 6: Call it on sign-in only, not on every load**

In `templates/app.html`, in `initAuth`, change the magic-link branch so the prompt fires right after the identity switch. Replace:

```js
    switchIdentity(session.user_id);
    renderAuth();
    return Promise.resolve();
  }
  const stored = loadSession(localStorage);
```

with:

```js
    switchIdentity(session.user_id);
    maybeClaimAnon();
    renderAuth();
    return Promise.resolve();
  }
  const stored = loadSession(localStorage);
```

Only the magic-link branch prompts. Restoring a stored session on every reload must not re-ask, or the dialog becomes a permanent nuisance for a user who already said 아니오.

- [ ] **Step 7: Rebuild and verify the claim path**

```bash
python3 build.py && python3 -m http.server 8000 --directory .
```

1. Sign out. Mark three cards. Confirm they land in `gisa-cards-v2:anon`.
2. Sign in via magic link. Expect the dialog "…3장 있습니다. 내 계정에 합칠까요?".
3. Answer 확인. The three marks appear under your account, `gisa-cards-v2:anon` is gone, and the Supabase row now contains them.
4. Reload. **No dialog** — the stored-session path must not re-prompt.

- [ ] **Step 8: Verify the isolation path**

This is the case the whole task exists for.

1. Sign out. Mark two cards (they go to anon).
2. Sign in via magic link and answer **취소**.
3. Your account's marks are unchanged — the two anon marks are *not* present.
4. `gisa-cards-v2:anon` still holds those two marks, and the Supabase row was not written.
5. Sign out. The two anon marks are visible again.

- [ ] **Step 9: Run the full suite**

Run: `python3 -m unittest tests.test_build tests.test_classify tests.test_extract && node --test tests/test_sync.js tests/test_cloud.js`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add templates/sync.js templates/app.html tests/test_sync.js index.html
git commit -m "feat: ask before claiming pre-login marks into an account"
```

---

### Task 8: Keepalive workflow and operations runbook

Stops the Supabase free tier from pausing, and writes down what to do when it pauses anyway.

**Files:**
- Create: `.github/workflows/supabase-keepalive.yml`
- Modify: `README.md`
- Test: manual workflow dispatch

**Interfaces:**
- Consumes: nothing at runtime.
- Produces: nothing consumed by other tasks.

**Manual prerequisite:** in the GitHub repo, Settings → Secrets and variables → Actions, add two **repository secrets**:
- `SUPABASE_URL` — the project URL
- `SUPABASE_ANON_KEY` — the anon public key

They are secrets for tidiness rather than confidentiality; the anon key is already published in `index.html`.

- [ ] **Step 1: Create the workflow**

Create `.github/workflows/supabase-keepalive.yml`:

```yaml
# Supabase pauses free-tier projects after ~7 days of inactivity. A weekly
# read keeps the project warm so a two-week study break does not come back to
# a dead sync.
#
# Limit worth knowing: GitHub disables scheduled workflows after 60 days of
# repo inactivity, so a genuinely long hiatus still needs a manual unpause.
# See the "Supabase 운영" section of README.md.
name: supabase-keepalive

on:
  schedule:
    - cron: "17 3 * * 1"   # 03:17 UTC every Monday
  workflow_dispatch:

jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Ping PostgREST
        env:
          URL: ${{ secrets.SUPABASE_URL }}
          KEY: ${{ secrets.SUPABASE_ANON_KEY }}
        run: |
          set -euo pipefail
          code=$(curl -s -o /dev/null -w '%{http_code}' \
            -H "apikey: $KEY" \
            "$URL/rest/v1/progress?select=user_id&limit=1")
          echo "PostgREST returned $code"
          # 200 = reachable. 401 also proves the project is awake and
          # answering, which is all this job needs to establish.
          case "$code" in
            200|401) exit 0 ;;
            *) echo "::error::project may be paused or unreachable"; exit 1 ;;
          esac
```

- [ ] **Step 2: Run it once by hand**

Push the branch, then in the GitHub UI: Actions → supabase-keepalive → Run workflow.
Expected: green, with `PostgREST returned 200` (or `401`) in the log.

If it fails, check that both repository secrets exist and that `SUPABASE_URL` has no trailing slash.

- [ ] **Step 3: Add the runbook to the README**

Append to `README.md`:

```markdown
## 진도 동기화 (cross-device sync)

카드 상태(😵 / 🤔 / ✅)는 기기의 localStorage에 저장되고, 로그인하면 Supabase의
개인 행(row)과 동기화됩니다. 아이폰에서 표시한 것이 맥북에서도 보입니다.

- **오프라인 우선.** 네트워크가 없어도 앱은 그대로 동작하고, 표시한 내용은
  기기에 저장됩니다. 연결되면 자동으로 합쳐집니다.
- **병합 규칙.** 카드별로 최신 표시가 이깁니다. 시각이 같으면 복습 필요
  (😵 / 🤔)가 암기함(✅)을 이깁니다.
- **헤더의 점.** 🟢 동기화됨 · 🟡 동기화 중 · 🔴 오프라인.

### 처음 설정할 때

1. `cp supabase.example.json supabase.json` 후 프로젝트 URL과 anon key를 입력
2. `python3 build.py`

`supabase.json`이 없으면 동기화 없이 오프라인 전용으로 빌드됩니다.

## Supabase 운영

### 무료 플랜 일시정지 (founder runbook)

무료 플랜 프로젝트는 약 7일간 활동이 없으면 **일시정지(paused)** 됩니다.
매주 월요일에 도는 `.github/workflows/supabase-keepalive.yml`이 이를 막지만,
저장소 자체가 60일간 조용하면 GitHub이 이 스케줄을 꺼버립니다.

**증상:** 로그인은 되는데 헤더의 점이 계속 🔴 오프라인. 표시한 내용은 기기에
남아 있으므로 데이터가 사라진 것은 아닙니다.

**복구:**

1. https://supabase.com/dashboard 에서 프로젝트를 열고 **Restore project** 클릭
2. 몇 분 후 Actions → supabase-keepalive → Run workflow 로 확인
3. 각 기기에서 새로고침 — 점이 🟢 으로 바뀌고 밀려 있던 표시가 올라갑니다

### 다른 사용자에게 열어주기

지금은 Supabase 대시보드에서 신규 가입이 꺼져 있어 등록된 계정만 로그인할 수
있습니다. 열어주려면 Authentication → Sign In / Providers → **Allow new users
to sign up** 을 켜면 됩니다. 코드 변경은 필요 없습니다.

RLS 정책(`auth.uid() = user_id`)이 사용자별 격리를 보장하므로, 다른 사용자의
표시가 섞이지 않습니다.
```

- [ ] **Step 4: Verify the README renders**

Run: `python3 -m unittest tests.test_build tests.test_classify tests.test_extract && node --test tests/test_sync.js tests/test_cloud.js`
Expected: PASS

Then read the new README section on GitHub (or in a Markdown preview) and confirm the code fences and headings are intact.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/supabase-keepalive.yml README.md
git commit -m "chore: add Supabase keepalive workflow and operations runbook"
```

---

## Final verification

- [ ] **Full test suite**

Run: `python3 -m unittest tests.test_build tests.test_classify tests.test_extract && node --test tests/test_sync.js tests/test_cloud.js`
Expected: PASS, no skips

- [ ] **Clean rebuild**

Run: `python3 build.py`
Expected: the usual per-subject summary, all 5 과목 complete

- [ ] **Deploy and confirm on both devices**

Push the branch, merge, and wait for GitHub Pages. Then on the real deployed URL:

1. Sign in on the MacBook, mark a card.
2. Sign in on the iPhone with the same email, answer the claim prompt, confirm the mark is there.
3. Mark a different card on the phone; confirm it reaches the Mac after a reload.

This is the acceptance criterion for the whole plan.
