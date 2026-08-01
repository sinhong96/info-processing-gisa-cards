const test = require("node:test");
const assert = require("node:assert");
const C = require("../templates/cloud.js");

const CFG = {url: "https://abc.supabase.co", anonKey: "anon-key"};

// A JWT is header.payload.signature; only the payload is read, and only for
// `sub` and `email`. Signature verification is the server's job.
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

test("parseAuthHash returns null for unrelated or partial fragments", () => {
  assert.equal(C.parseAuthHash("", 1000), null);
  assert.equal(C.parseAuthHash("#some=thing", 1000), null);
  assert.equal(C.parseAuthHash("#access_token=x", 1000), null);
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
  await assert.rejects(() => C.sendMagicLink(CFG, "a@b.c", "https://site/"), /429/);
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

test("session storage round-trips and clears", () => {
  const m = {};
  const st = {
    getItem: k => (k in m ? m[k] : null),
    setItem: (k, v) => { m[k] = String(v); },
    removeItem: k => { delete m[k]; },
  };
  assert.equal(C.loadSession(st), null);
  const sess = {access_token: "at", refresh_token: "rt", expires_at: 9,
                user_id: "u1", email: "a@b.c"};
  C.saveSession(st, sess);
  assert.deepEqual(C.loadSession(st), sess);
  C.clearSession(st);
  assert.equal(C.loadSession(st), null);
});
