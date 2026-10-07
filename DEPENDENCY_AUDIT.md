# Dependency Security Audit — 2026-09-18

## Context

`nccrd-server` had never had a dependency vulnerability review — this was the
first pass. No GitHub token was available to query the Dependabot Alerts API
directly, so this used `pip-audit` (PyPI Advisory DB / OSV) against
`requirements.txt` instead, which surfaces the same CVE data.

## Before

`pip-audit -r requirements.txt` found **35 known vulnerabilities across 7
packages**: `click`, `starlette` (14 entries, 7 distinct advisories), `h11`,
`idna`, `mako`, `pyjwt` (12 entries, 6 distinct advisories), `pytest`.

## Applicability review

Raw vulnerability counts overstate real risk — several only matter if the
app actually exercises the vulnerable code path. Checked each before
deciding what to prioritize:

**`pyjwt`** — `nccrd/api/lib/auth.py` calls plain `jwt.encode()`/`jwt.decode()`
with an explicit `algorithms=[...]` allow-list; there is no `PyJWKClient` or
`PyJWK` object anywhere in the codebase. Of the 6 distinct pyjwt advisories,
4 (PYSEC-2026-179, -175, -177, -176) are specifically about
`PyJWKClient`/JWK-based verification and don't apply to how this app uses
the library. Upgraded anyway (2.10.1 → 2.14.0) since it's free and closes
latent risk, but this was not an exploitable gap as deployed.

**`starlette`** — the two most applicable issues are genuinely serious for
this app:
- **PYSEC-2026-1941**: parsing a multipart upload above the default spool
  size blocks the event loop. `nccrd-server` accepts file uploads at
  `POST /submission/{id}/progress_reports` and
  `POST /submission/create_submission_upload-xlsx/` — both authenticated
  (`RequirePermission`), so exploitable only by a credentialed user, but a
  real DoS vector for accidental large uploads too.
- **PYSEC-2026-1942**: a crafted `Range` header on `FileResponse`/
  `StaticFiles` triggers quadratic-time processing — CPU exhaustion per
  request. `nccrd-server` mounts `/uploads/progress_reports` via
  `StaticFiles` with **no auth dependency on the mount at all** — this one
  was unauthenticated and directly exploitable by anyone who could reach
  the API.

  Remaining 5 distinct starlette advisories (see "Blocked" below) are lower
  applicability here: PYSEC-2026-2281 is a Windows-only UNC/SMB issue
  (deployment is Linux-only, `python:3.10-slim`); PYSEC-2026-2280 requires
  starlette's class-based `HTTPEndpoint` (this codebase only uses FastAPI's
  function-based `@router.get`/`@router.post` routers); PYSEC-2026-161/-248
  (Host-header / request-path URL reconstruction inconsistency) and
  PYSEC-2026-249 (`urlencoded` form field-count DoS) are real defects
  worth fixing but lower severity for an internal government-data API with
  no host-based routing/redirect logic and no large-scale public traffic.

**`click`/`h11`/`idna`/`mako`** — transitive dependencies (via `uvicorn`,
`httpcore`/`uvicorn`, `httpx`, `alembic` respectively), no applicability
concerns specific to this app, upgraded as routine hygiene.

**`pytest`** — dev/test-only, not on the request-handling path of the
running service, but is installed in the production image today since
`requirements.in` doesn't separate dev from runtime deps (see "Also found"
below). Upgraded (8.3.5 → 9.1.1) since it's independent of every other
constraint here.

## Fixed

`requirements.in`/`requirements.txt` updated:

| Package | Before | After | Fixes |
|---|---|---|---|
| `fastapi` | 0.115.11 | 0.125.0 | (enables the starlette bump below) |
| `starlette` | 0.46.0 | 0.50.0 | PYSEC-2026-1941, -1942 (both applicable ones above) |
| `pyjwt` | 2.10.1 | 2.14.0 | all 6 distinct advisories (none were exploitable as used, see above) |
| `click` | 8.1.8 | 8.5.0 | PYSEC-2026-2132 |
| `h11` | 0.14.0 | 0.16.0 | PYSEC-2026-348 |
| `idna` | 3.10 | 3.20 | PYSEC-2026-215 |
| `mako` | 1.3.9 | 1.4.1 | PYSEC-2026-2617 |
| `pytest` | 8.3.5 | 9.1.1 | PYSEC-2026-1845 |
| `httpcore` | 1.0.8 | 1.0.9 | (transitive requirement to let h11 reach 0.16.0) |

`pip-audit` after: **5 known vulnerabilities in 1 package** (down from 35 in
7), all in `starlette`, all genuinely blocked — see below.

Verified via the actual `Dockerfile` build (not just a local venv — an
earlier attempt at this compiled the lockfile under a local Python 3.12
interpreter, which silently *dropped* `exceptiongroup`/`tomli` since neither
is needed on 3.12 but both are real backport dependencies this app's actual
Python 3.10 runtime needs; caught by recompiling with a real 3.10
interpreter and diffing before finalizing). Built the image, ran it against
the real dev Postgres on the actual `nccrd-net` Docker network (not
standalone), and exercised the exact code paths the fixes touch: logged in
(JWT encode/decode), created a submission (Pydantic v1 validation still
firing correctly), uploaded a file via `multipart/form-data`, and fetched
it back with a `Range` header (confirmed `206 Partial Content`).

## Blocked — genuinely, not just deferred

*(Resolved 2026-10-07 by the Pydantic v2 migration: see "Pydantic v2" below.)*

**ESLint 10 / `eslint-plugin-react-hooks` v7 for the frontend had exact
analogues in this audit.** Latest FastAPI (0.126.0+) requires
`pydantic>=2.7`, and this project deliberately pins `pydantic<2`
(`nccrd/config.py` and `nccrd/api/models/*.py` use Pydantic v1 syntax —
`BaseSettings`, `orm_mode`, `.from_orm()` — a v2 migration is a real,
separate effort, not a dependency bump). Scanned FastAPI's version history:
it stayed compatible with `pydantic<2` up through **0.125.0**, which caps
`starlette` at `<0.51.0`. The highest starlette release under that cap is
**0.50.0** — which is what's installed now. The remaining 5 starlette
advisories all require `starlette>=1.0`, which requires `fastapi>=0.126`,
which requires `pydantic>=2`. Revisit together with a real Pydantic v2
migration, not before.

## Also found, not fixed here (separate scope)

- *(Resolved 2026-10-07: test tools now live in `requirements-dev.in`/`.txt`;
  the image installs only `requirements.txt`, 37 → 23 packages.)*
  `requirements.in` doesn't separate runtime from dev/test dependencies —
  `pytest`, `coverage`, `factory-boy`, `faker`, `httpx` all ship in the
  production image today. Splitting this into `requirements.in` +
  `requirements-dev.in` (or an `[test]` extra) would shrink the image and
  reduce attack surface, but is a build-process change, not a vulnerability
  fix — separate task.
- No GitHub token was available in this session to cross-check against the
  actual Dependabot Alerts count (18 alerts: 1 critical, 7 high, 8 moderate,
  2 low, per GitHub's push output). `pip-audit`'s 35→5 covers the same
  underlying CVE data (PyPI Advisory DB / OSV, which GitHub's advisory
  database also draws from) but the exact alert-to-CVE mapping wasn't
  independently confirmed here. Worth a follow-up check once repo/token
  access is available, to make sure nothing GitHub-specific (e.g. a
  GitHub Actions-only advisory) was missed.

## Follow-up — 2026-10-07

GitHub reported 5 open Dependabot alerts on `main` (2 high, 2 moderate,
1 low). `pip-audit -r requirements.txt` found 2 packages:

- **`pyjwt` 2.14.0 → 2.15.0** (PYSEC-2026-4141, CVE-2026-102275). Both are
  in JWK handling: `PyJWKClient`'s pre-verification payload parsing, and
  OKP private JWKs whose public key doesn't match the private key. This
  app uses neither: it signs and checks HS256 tokens with plain
  `jwt.encode`/`jwt.decode`. Upgraded anyway, since it's free and closes
  the latent risk. On Python 3.10, 2.15.0 needs `typing-extensions>=4`,
  which is already pinned (4.12.2). The full test suite passes.
- **`starlette` 0.50.0**: the same 5 advisories as in "Blocked" above. They
  still need `starlette>=1.0`, so they still wait for the Pydantic v2
  migration.

After this, `pip-audit` reports only the blocked `starlette` advisories.

## Pydantic v2 — 2026-10-07

Migrated to Pydantic 2.13 (with pydantic-settings for `nccrd/config.py`),
FastAPI 0.142 and **Starlette 1.7**, which fixes the five Starlette
advisories that were blocked above. `pip-audit` now finds **no known
vulnerabilities** in `requirements.txt` or `requirements-dev.txt`.

How behaviour was kept the same:
- The test suite passes.
- The old and new API answered all 56 read requests (lists with filters,
  project pages of every kind, reports, regions, all vocabulary trees,
  accounts, the pipeline page, the upload template) on the same copy of
  the server's data. The answers were identical apart from one notation:
  timezone-aware timestamps are written `…Z` instead of `…+00:00`. Only
  the pipeline page has them, and browsers read both the same.
- Validation errors (422) keep their v1 shape (`loc`, `msg`, `type`).
  Pydantic 2 would also echo the submitted input, which can include a
  password. Bulk-upload row errors read "field: message".
- Pydantic 2 makes `Optional` fields without a default required, so every
  such field got `= None`, as v1 implied.
