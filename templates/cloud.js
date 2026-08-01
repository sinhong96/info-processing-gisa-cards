/* Supabase access over plain fetch: GoTrue for auth, PostgREST for the one
   progress row. No SDK — pulling one from a CDN would break offline loading,
   and vendoring a bundle to call four endpoints is not worth the blob.
   (Do not write the banned tag name here; test_build asserts on it.) */

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
