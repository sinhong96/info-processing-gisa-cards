# Cross-Device Progress Sync — Design

**Date:** 2026-08-01
**Status:** Approved

## Problem

Card marks (😵 어려움 / 🤔 애매함 / ✅ 암기함) are stored in `localStorage` under the key
`gisa-cards-v1` (`templates/app.html:103-105`) as a flat `{cardId: state}` map. localStorage
is scoped per browser, per device. Nothing about GitHub Pages hosting or iCloud syncs it.

Sin Hong studies on iPhone Safari; the marks he makes there are invisible on his MacBook.
This is expected behavior of the current design, not a bug.

A second requirement shapes the solution: the deck may later open to multiple users, each
with independent marks.

## Goals

- Marks made on one device appear on the other.
- The app keeps working fully offline, exactly as it does today.
- No mark is ever silently lost to a sync conflict.
- The architecture supports multiple users without a rewrite.
- No user can ever see or inherit another user's marks, including on a shared device.

## Non-Goals

Per-user decks, user-authored cards, deck sharing, user profiles, realtime cross-tab sync,
and any offline write queue beyond localStorage itself.

## Backend Decision

**Supabase.** Multi-user inverts the usual trade-offs:

| Option | Verdict |
| --- | --- |
| GitHub Gist + PAT | **Rejected.** Depends on each user creating a personal access token. The OAuth alternative (each user writes to their own gist) needs a server for the client-secret exchange, so it costs a Worker *and* a GitHub account per user. |
| Cloudflare Worker + KV | **Rejected.** Storage was never the hard part; identity is. Signup, login, sessions, and per-user isolation would all be hand-rolled. |
| Supabase | **Chosen.** Ships auth and row-level security, which is the entire multi-user requirement. |

Single-user today is the same schema with one row, so choosing Supabase now costs nothing
if multi-user never happens, and requires no migration if it does.

### Schema

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

The RLS policy is what makes the public anon key safe to ship in `index.html`. Consequence:
**no per-device credential setup** — the user only signs in.

## Architecture

**localStorage remains the source of truth for rendering; the cloud is a sync layer on top.**
The app must keep working with no network, no account, and Supabase unreachable. Sync is
additive and may always fail without breaking studying. This matters because phone study
happens on transit and in dead zones.

### Data model

`mark[id] = "hard"` becomes:

```js
mark[id] = { s: "hard", t: 1754000000 }   // state + unix seconds
```

A bare state cannot merge — there is no way to tell which device is newer. At 324 cards this
is roughly 15KB of JSON, small enough to move the whole blob on every sync with no per-card
requests.

### localStorage key namespacing

A single shared `gisa-cards-v2` key would let one user's marks be inherited by whoever signs
in next on that browser. Keys are therefore namespaced by identity:

| Key | Holds |
| --- | --- |
| `gisa-cards-v2:<user_id>` | Marks for a signed-in user. Read and written only while that user is signed in. |
| `gisa-cards-v2:anon` | Marks made before any sign-in. Destination of the one-time `v1` migration. |

Signing out leaves every bucket intact and separate; signing back in loads only that user's
own bucket. No bucket is ever read across identities.

### Merge rule

Per-card last-write-wins, not whole-blob. Whole-blob LWW loses data in a scenario that will
occur in practice: mark cards on the phone while offline, use the Mac, phone reconnects and
flattens the Mac's work.

1. Union of all card ids from both sides.
2. On conflict, higher `t` wins.
3. On equal `t`, needs-review beats known — `hard`/`unsure` win over `known`.

Rule 3 covers migrated marks. Legacy `v1` marks have no timestamp and receive `t: 1`, so if
both devices carry legacy marks the tie must break somewhere. It breaks toward the cheap
error: re-seeing a known card, rather than losing a card the user was struggling with.

Within rule 3, `hard` and `unsure` tied against each other resolve to `hard`, for the same
reason — both mean "review this", and the more conservative label survives.

The merge is commutative, so both devices run it independently and converge with no server
logic.

### Sync triggers

- On load, after auth resolves.
- Debounced ~2s after a mark.
- On `pagehide` and on `visibilitychange` → hidden.

Not on every mark — that is rate limits and phone battery for no benefit.

### Auth

Email magic link. Supabase Site URL and Redirect URLs must allowlist the Pages URL
(`https://sinhong96.github.io/info-processing-gisa-cards/`). Header shows 로그인, or the
signed-in email.

Signup is disabled in the Supabase dashboard so Sin Hong is the only account. Opening the
deck to other users later is a dashboard toggle, not a code change.

Anonymous or device-scoped identities are explicitly unsuitable: an identity tied to a
browser cannot follow the user from iPhone to MacBook, which is the original problem.

## Error Handling

The header gains a small status dot: synced / pending / offline.

| Failure | Behavior |
| --- | --- |
| Offline or fetch failure | Keep working from localStorage. Dot shows offline. Retry on next trigger. |
| Auth expired | Prompt re-login. Marks continue to save locally. |
| Supabase paused or down | Same as offline. |
| Malformed cloud payload | Discard it, keep local, report pending. Never overwrite local with garbage. |

No failure path blocks the UI and no failure path discards a local mark.

## Build Integration

`index.html` is generated by `build.py` from `templates/app.html`. The merge logic is the
only part with real reasoning in it, and would otherwise be trapped inside a 3.4MB generated
file.

Two new sources under `templates/`, inlined by `build.py` via `/*__SYNC__*/` and
`/*__CLOUD__*/` placeholders — the same pattern as the existing `/*__CARDS__*/`. Single-file
deployment is preserved; the logic becomes testable.

- `sync.js` — pure merge, migration, and storage-key logic. No DOM, no network.
- `cloud.js` — Supabase access over plain `fetch`, plus the pure token/fragment parsing.

**No Supabase JS SDK.** A CDN `<script src>` would break offline loading, which is the
premise of the architecture, and vendoring a bundle to call four endpoints is not worth the
blob. The GoTrue and PostgREST calls needed here are roughly 90 lines of `fetch`.

## Testing

- `tests/test_sync.js` (node:test): union, timestamp precedence, tie-break in both
  directions, `hard` vs `unsure` tie, v1 migration, empty input, malformed input, and key
  namespacing — that reading user A's bucket never returns user B's or the anon bucket's marks.
- `tests/test_cloud.js` (node:test): JWT claim decoding, magic-link fragment parsing, session
  expiry, auth-error classification, and each REST call against a stubbed `fetch`.

CommonJS rather than ESM: the sources are inlined into a `<script>` by `build.py`, so they
cannot use `import`/`export`. A `module.exports` tail guarded by `typeof module` lets
`node --test` require them, and `build.py` strips that tail from the browser bundle.
- `tests/test_build.py`: new case asserting the sync source is inlined into the built HTML.

Auth and network paths are not unit tested; they are verified manually against the deployed
Pages URL, since magic link does not work from `file://`.

## Operations

### Supabase free-tier pause

Free-tier projects pause after roughly 7 days of inactivity and need a manual unpause. Daily
studying never trips this; a two-week break does, producing a dead sync until unpaused. Local
marks keep working throughout — this is an availability problem, not a data-loss one.

Handled two ways:

1. **Keepalive.** A weekly GitHub Action pings the Supabase REST endpoint so the project never
   idles out. Caveat: GitHub disables scheduled workflows after 60 days of *repo* inactivity,
   so this covers the realistic case but not a multi-month hiatus.
2. **Runbook.** A README section covering the pause window, how to recognize it (sync dot
   stuck on offline), and how to unpause.

### Local development

Magic link requires a real origin. Local testing uses `python3 -m http.server` rather than
opening `index.html` directly.

## Migration Path for Existing Marks

Sin Hong currently has real marks on his iPhone under `gisa-cards-v1`. These migrate once,
into `gisa-cards-v2:anon`, converted to the timestamped shape with `t: 1`.

### Claiming the anon bucket

When a user signs in and `gisa-cards-v2:anon` is non-empty, the app asks:

> 이 기기에 로그인 전 학습 기록이 있습니다. 내 계정에 합칠까요?

- **예** — the anon marks are merged into that user's bucket and synced, then the anon bucket
  is cleared.
- **아니오** — the anon bucket is left untouched and the user starts from their own cloud
  copy. The prompt may appear again on a later sign-in, since the data is still there.

Claiming is never silent. A silent claim is the specific mechanism by which one user inherits
another's marks on a shared browser, so the decision belongs to the person who knows whose
data it is. On Sin Hong's iPhone this is a single 예 on first sign-in; a second user on the
same browser answers 아니오 and starts clean.

Merges always use the rule from *Merge rule* above, so nothing is replaced wholesale and
legacy `t: 1` marks lose to any later timestamped mark. Sign-in order does not need to be
correct for this to be safe.

## User Isolation

Two independent layers, both required:

1. **Server-side.** The RLS policy `auth.uid() = user_id` is enforced by Postgres, not by the
   app. A user holding the public anon key and crafting their own requests can still only read
   and write their own row.
2. **Device-side.** Namespaced localStorage keys plus the explicit claim prompt, so a shared
   browser never leaks marks between accounts.

Server-side isolation alone is insufficient: it says nothing about what the client uploads
into a legitimately-owned row.
