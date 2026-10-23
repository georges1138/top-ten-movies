# Legacy Flask Acceptance Checklist

**Scope:** Top Ten Movies Flask baseline and acceptance criteria for its FastAPI replacement.
**Full evidence log:** Git commit [`f65409e`](https://github.com/georges1138/top-ten-movies/commit/f65409e) (original 4,879-line inventory).
**Revision purpose:** Compact, reviewable index of legacy behavior, security and correctness findings, and target tests. This is a plan, not a claim that FastAPI tests have passed.

## 1. Method and evidence

- Legacy routes were exercised using Flask's test client and an isolated copy of the original ten-record SQLite database; temporary changes were discarded or restored and SHA-256 hashes compared.
- TMDB responses and HTTP failures were mocked. They demonstrate how Flask responds to simulated input, **not** the behavior or availability of live TMDB.
- Database schema, rows and field lengths were inspected with read-only SQLite queries. The reviewer independently replayed selected reproductions and confirmed their results.
- Evidence types below: **T** = observed test result; **S** = source inspection; **DB** = SQLite inspection; **R** = reviewer replay; **G** = Git history. A proposed test name is future work, not an existing passing test.
- Fixed historical findings remain in this index with their fix commit; a commit reference documents the change, not an independent security re-audit. Reviewer sign-off is distinct from test evidence.

## 2. Route acceptance matrix

| Route | Method/case | Observed status | Observable result or side effect | Target acceptance |
|---|---|---|---|---|
| `/` | GET, original data | 200 | Ten existing movies rendered; ranks calculated from rating, not stored `ranking` | Display top 10 using decided ordering; unrated last |
| `/delete` | GET, existing ID | 302 | Deletes one record and redirects to `/` | Mutations only by authenticated, CSRF-protected POST/DELETE |
| `/delete` | GET, missing/unknown/non-numeric ID | 500 | No row removed in isolated tests | Controlled 400/404; no database changes |
| `/edit` | GET, valid ID | 200 | Blank form; placeholder heading `Movie Title` | Show real title and existing values |
| `/edit` | GET, nonexistent ID | 200 (R) | Reviewer replay: form renders although record does not exist | 404 rather than misleading form |
| `/edit` | POST, valid CSRF, rating 7.5 | 302 | Rating and review saved | Update requested movie; validation and auth/CSRF required |
| `/edit` | POST, missing CSRF | 200 | Form returned without updating | Reject mutation; show helpful error |
| `/edit` | POST, rating 0 | 200 (T, R) | Rejected; saved rating remained 9.2 | Explicit decision: require 1–10 inclusive for a personal rating |
| `/edit` | POST, rating 0.5, -2, or 11 | 302 (T, R) | Invalid values stored | Reject outside 1–10 |
| `/edit` | POST, nonexistent ID `9999` | 500 (R) | Reviewer replay: unhandled failure | 404; no mutation |
| `/add` | GET | 200 | Movie search form displayed | Render accessible search form |
| `/add` | POST, valid title | 200 | Mocked TMDB search displayed; no insertion | Render matches without mutating data |
| `/add` | POST, empty/whitespace title | 200 | Validation prevented TMDB call | Reject and display feedback |
| `/add` | POST, empty TMDB results | 200 | Blank selection list, no explanatory message | Clear no-results message |
| `/add` | POST, mocked HTTPError | 500 | Unhandled simulated TMDB failure | Controlled temporary-unavailable response |
| `/select` | GET, valid mocked ID | 302 | Inserted movie, redirected to edit; legacy GET mutates database | Authenticated, CSRF-protected POST insertion |
| `/select` | GET, missing/nonnumeric ID | 500 | Invalid identifier forwarded to mocked TMDB | 400 before external request |
| `/select` | GET, mocked unknown numeric ID | 500 | Simulated TMDB 404 unhandled | Controlled 404; no insertion |
| `/select` | GET, duplicate title | 500 (T, R) | SQLite UNIQUE constraint rejects insert | Controlled 409 or helpful duplicate response |
| `/select` | GET, missing `release_date`/`poster_path` | 500 | `KeyError`; no insert | Normalize optional data before insertion |
| `/select` | GET, empty/null `release_date` | 302 | Empty year or literal `'None'` stored | Year NULL when unavailable |
| `/select` | GET, empty/null `poster_path` | 302 | Invalid image URL stored, including `/None` (R) | Store nullable path; build valid URL only on render |
| `/select` | GET, missing `overview` | 500 (R) | Original test captured `KeyError`; reviewer separately measured HTTP 500 | Graceful omission/NULL handling |
| `/select` | GET, empty `overview` | 302 | Empty description stored | Nullable normalized overview |
| `/select` | GET, null `overview` | 500 (T, R) | SQLite NOT NULL error; no insert | Nullable normalized overview |

## 3. Original database snapshot

**Baseline:** `instance/top-ten-movies.db`, SQLite, one `movie` table, ten original records. Do not modify this source during development or tests.

| Column | SQLite type | NULL allowed | Notes |
|---|---|---|---|
| `id` | INTEGER | No | Primary key |
| `title` | VARCHAR(120) | No | UNIQUE constraint, verified |
| `year` | VARCHAR(80) | No | Legacy stores a string |
| `description` | VARCHAR(250) | No | SQLite does not enforce declared string length |
| `rating` | FLOAT | Yes | Legacy imports TMDB vote average |
| `ranking` | INTEGER | Yes | Every original row stores 10; display ignores it |
| `review` | VARCHAR(250) | Yes | Legacy pre-fills from TMDB tagline |
| `img_url` | VARCHAR(80) | Yes | Existing values must be preserved in migration |

| ID | Original movie title | Year | Rating | Description length |
|---|---|---:|---:|---:|
| 2 | The Matrix | 1999 | 9.2 | 181 |
| 4 | The Cannonball Run | 1981 | 6.7 | 449 |
| 6 | Raiders of the Lost Ark | 1981 | 8.8 | 227 |
| 7 | 기생충 | 2019 | 9.8 | 164 |
| 8 | The Avengers | 2012 | 9.0 | 297 |
| 11 | Elf | 2003 | 8.7 | 322 |
| 12 | The Sixth Sense | 1999 | 9.9 | 146 |
| 13 | Knives Out | 2019 | 9.1 | 369 |
| 14 | The Shawshank Redemption | 1994 | 9.5 | 388 |
| 15 | Short Circuit | 1986 | 7.6 | 349 |

**Per-field lengths (characters, read-only SQLite `LENGTH()`):**

| ID | Title | Year | Description | Review | Poster URL |
|---|---:|---:|---:|---:|---:|
| 2 | 10 | 4 | 181 | 16 | 64 |
| 4 | 18 | 4 | 449 | 39 | 64 |
| 6 | 23 | 4 | 227 | 23 | 64 |
| 7 | 3 | 4 | 164 | 19 | 64 |
| 8 | 12 | 4 | 297 | 48 | 63 |
| 11 | 3 | 4 | 322 | 50 | 64 |
| 12 | 15 | 4 | 146 | 22 | 64 |
| 13 | 10 | 4 | 369 | 23 | 64 |
| 14 | 24 | 4 | 388 | 20 | 64 |
| 15 | 13 | 4 | 349 | 20 | 64 |

**Long descriptions:** Six exceed 250 characters; maximum 449. The reviewer confirmed the earlier count of four was **the reviewer's counting error** (The Avengers and Short Circuit were omitted). Discrepancy closed by reviewer feedback.

**Migration acceptance:** Preserve all ten local IDs and original field values (including Unicode and full descriptions) in an isolated copy. Look up and independently verify the real TMDB ID of each legacy film; do not guess ambiguous matches, and stop before enforcing `NOT NULL UNIQUE` until all ten matches are confirmed. Backfill `created_at` deterministically; reset the PostgreSQL ID sequence after importing original IDs (e.g., `setval`) and test that the next insert cannot collide. Compare data values, not byte-identical database files.

## 4. Unified audit findings and proposed regression tests

Every row has a **canonical ID**. Older D-* IDs are mapped in the `Previous ID` column; the older IDs are not additional findings. Status `Fixed` means reported as addressed by the cited Git commit; `Needs fix` means a target issue still requires implementation; `Design` means a deliberate modernization change. Tests are proposed acceptance checks, not executed FastAPI tests.

### Security

| ID | Previous ID | Finding / compact evidence | Status | Proposed test or check |
|---|---|---|---|---|
| SEC-01 | — | No authentication protects movie-changing routes (S: `main.py` route handlers) | Needs fix | test_write_requires_authentication |
| SEC-02 | — | GET `/delete` and `/select` change data without CSRF protection (S, T) | Needs fix | test_get_read_only_and_write_csrf_required |
| SEC-03 | — | Hard-coded application/TMDB secrets in legacy code; env-based loading added (G: `cfa7f8b`) | Fixed `cfa7f8b` | test_configuration_requires_environment_secrets |
| SEC-04 | — | Legacy unconditional `debug=True`; env-controlled debug flag added (G: `cfa7f8b`, S) | Fixed `cfa7f8b` | test_production_debug_disabled |
| SEC-05 | — | TMDB key sent as URL `api_key` parameter; may appear in HTTPError/URL logs (S) | Needs fix | test_tmdb_uses_authorization_header_and_redacts_errors |
| SEC-06 | — | No timeout on either outbound `requests.get()` (S) | Needs fix | test_tmdb_requests_have_timeout |
| SEC-07 | — | Prior audit found 38 dependency vulnerabilities across seven packages; change records 0 (G: `7791b08`) | Fixed `7791b08` | check_dependency_audit_clean |
| SEC-08 | — | Original repository tracked local `.db` and `.idea/` files; tracking removed (G: `16099c8`) | Fixed `16099c8` | check_git_tracks_no_local_db_or_ide_files |

### Correctness

| ID | Previous ID | Finding / compact evidence | Status | Proposed test or check |
|---|---|---|---|---|
| BUG-01 | D-R01 | Rating 11 saved despite intended range (T, R) | Needs fix | test_reject_rating_above_ten |
| BUG-02 | D-R02 | Rating -2 and 0.5 saved (T, R); rating 0 rejected | Needs fix | test_reject_rating_below_one |
| BUG-03 | D-T01 | Mocked TMDB search HTTPError gives HTTP 500 (T) | Needs fix | test_tmdb_search_error_is_handled |
| BUG-04 | D-S01 | Absent TMDB ID forwarded as `None`, mocked 404 becomes 500 (T) | Needs fix | test_select_missing_id_returns_400 |
| BUG-05 | D-S02 | Nonnumeric TMDB ID forwarded, mocked 404 becomes 500 (T) | Needs fix | test_select_invalid_id_returns_400 |
| BUG-06 | D-S03 | Unknown numeric TMDB ID, mocked 404 becomes 500 (T) | Needs fix | test_tmdb_not_found_returns_404 |
| BUG-07 | D-S04 | Duplicate selection raises SQLite UNIQUE error and returns 500 (T, R) | Needs fix | test_duplicate_movie_is_handled |
| BUG-08 | — | Missing/unknown/nonnumeric `/delete` ID returns 500 (T) | Needs fix | test_delete_invalid_id_no_500 |
| BUG-09 | — | `GET /edit` nonexistent ID returns 200 and placeholder form (R) | Needs fix | test_edit_missing_movie_returns_404 |
| BUG-10 | — | `POST /edit?id=9999` returns 500 (R) | Needs fix | test_edit_post_missing_movie_returns_404 |
| BUG-11 | — | TMDB `original_title` used as display title; Parasite appears as 기생충 (S, DB) | Needs fix | test_import_keeps_display_and_original_titles |
| BUG-12 | — | TMDB tagline is inserted as the user's review (S) | Needs fix | test_import_review_defaults_to_null |
| BUG-13 | — | TMDB `vote_average` pre-fills personal rating, potentially 0 (S) | Needs fix | test_import_rating_defaults_to_null |
| BUG-14 | — | Edit page shows hard-coded `Movie Title` heading (S) | Needs fix | test_edit_page_shows_movie_title |
| BUG-15 | — | No helpful message for zero TMDB search results (T) | Needs fix | test_empty_search_shows_message |
| BUG-16 | — | No ten-item display limit or explicit tie rule in legacy ranking (S) | Design | test_top_ten_sort_ties_and_unrated |
| BUG-17 | — | Edit form does not prefill saved rating and review (S: `/edit`, template) | Needs fix | test_edit_form_prefills_current_values |

### Data and TMDB normalization

| ID | Previous ID | Finding / compact evidence | Status | Proposed test or check |
|---|---|---|---|---|
| DATA-01 | D-S05 | Missing `release_date` causes KeyError and HTTP 500 (T) | Needs fix | test_missing_release_date_maps_to_null_year |
| DATA-02 | D-S06 | Empty `release_date` persists empty year (T) | Needs fix | test_empty_release_date_maps_to_null_year |
| DATA-03 | D-S07 | Null `release_date` persists string `None` (T) | Needs fix | test_null_release_date_maps_to_null_year |
| DATA-04 | D-S08 | Missing `poster_path` causes KeyError and HTTP 500 (T) | Needs fix | test_missing_poster_path_allowed |
| DATA-05 | D-S09 | Null `poster_path` persists URL ending `/None` (T, R) | Needs fix | test_null_poster_does_not_generate_url |
| DATA-06 | D-S10 | Empty `poster_path` persists image URL without filename (T) | Needs fix | test_empty_poster_does_not_generate_url |
| DATA-07 | D-S11 | Missing overview causes KeyError; HTTP 500 confirmed by reviewer replay (T, R) | Needs fix | test_missing_overview_allowed |
| DATA-08 | D-S12 | Empty overview persists empty description (T) | Needs fix | test_empty_overview_normalized |
| DATA-09 | D-S13 | Null overview causes IntegrityError and HTTP 500 (T, R) | Needs fix | test_null_overview_allowed |
| DATA-10 | — | Legacy poster base/path join produces double slash (`w500//...`) (DB/R) | Needs fix | test_poster_url_has_single_separator |
| DATA-11 | — | Stored `ranking` always 10; displayed ranking recalculated (DB, S) | Design | test_rank_is_derived_not_stored |
| DATA-12 | — | Six descriptions exceed `VARCHAR(250)` (max 449); `img_url` is declared `VARCHAR(80)` and must preserve existing URLs (DB) | Design | test_migration_preserves_long_descriptions_and_poster_urls |

### Maintainability

| ID | Previous ID | Finding / compact evidence | Status | Proposed test or check |
|---|---|---|---|---|
| MNT-01 | — | Global `all_movies` is mutated during GET `/` (S) | Needs fix | test_homepage_does_not_mutate_shared_state |
| MNT-02 | — | Routes and TMDB helpers use `print()` debugging (S) | Needs fix | test_sensitive_data_not_logged |
| MNT-03 | — | Legacy `flask_bootstrap.Bootstrap` uses old Bootstrap 3 UI (S; reviewer audit) | Design | test_pages_render_without_flask_bootstrap |
| MNT-04 | — | Historical fresh-clone database initialization failure without `db.create_all()`; startup creation added (G: `cfa7f8b`) | Fixed `cfa7f8b` | test_fresh_database_created_by_migrations |

### Completeness and duplicate-control notes

- Original defect crosswalk: `D-R01–D-R02` → BUG-01–02; `D-T01` → BUG-03; `D-S01–D-S04` → BUG-04–07; `D-S05–D-S13` → DATA-01–09. All 16 original IDs occur **once** in the Previous ID column.
- Authentication is SEC-01; unsafe GET mutations and missing CSRF protections are combined under SEC-02 to avoid duplicate IDs for the same route-level exposure.
- **Original audit crosswalk (reviewer-confirmed):** 1→SEC-03; 2→SEC-07; 3→SEC-01; 4→SEC-02; 5→SEC-08; 6→BUG-08, BUG-10, BUG-04, BUG-05; 7→BUG-07; 8→DATA-12; 9→BUG-11; 10→DATA-10, DATA-05, DATA-02; 11→SEC-06, BUG-03, SEC-05; 12a→BUG-01, BUG-02; 12b→BUG-14; 12c→BUG-17; 12d→BUG-16; 13→MNT-01, MNT-02, MNT-03.
- **Five later audit findings (reviewer-confirmed):** rating-zero behavior→BUG-02; unused ranking→DATA-11; absent startup `db.create_all()`→MNT-04; former `debug=True`→SEC-04; original title/long descriptions/tagline→BUG-11, DATA-12, BUG-12. Additional key-in-error-text exposure→SEC-05.
- Some audit items legitimately map to several IDs because they bundled separate problems. Coverage means every issue is represented, each ID describes a coherent issue, and no single problem is double-counted. The reviewer supplied this crosswalk in feedback on PR #1.
- Replayer attribution: reviewer independently confirmed rating 0, 0.5, -2, 11; duplicate insert; null overview; null poster; missing overview HTTP 500; and invalid edit GET/POST behaviors. These are reviewer-reported reproductions, not new tests performed by this document's author.

## 5. Target decisions and acceptance rules

These are **Decided** target requirements approved by George, including the reviewer-recommended optional-data, authentication, title, rating, and tagline rules, and the top-ten ordering rule. They are not claims of implementation or passing FastAPI tests. Every target test in §4 should follow these rules.

| ID | Status | Decision (target behavior) | Reason / acceptance rule |
|---|---|---|---|
| DEC-01 | Decided | Require authentication for mutations and CSRF protection on browser write requests; GET is read-only | No anonymous state change; reject missing/invalid CSRF and unauthorized writes |
| DEC-02 | Decided | Use POST (or DELETE for an API) for add/delete and POST/PATCH for edit | Correct HTTP semantics; no DB writes during GET |
| DEC-03 | Decided | Use TMDB bearer authorization in a header; configure secrets from environment; disable production debug | Prevent query-string credential exposure; redact errors/logs |
| DEC-04 | Decided | Apply TMDB timeouts, controlled upstream error handling, and no secret-bearing error messages | External failures never become unhandled 500s |
| DEC-05 | Decided | Every target movie has a local `id`, `title`, `original_title`, and verified `tmdb_id NOT NULL UNIQUE`; match and backfill all ten legacy TMDB IDs during isolated migration before enforcing this constraint | Preserve original local IDs and titles; verify TMDB matches against each movie, never invent IDs; stop migration if any match is ambiguous or unavailable |
| DEC-06 | Decided | `year` is nullable integer; `overview` is nullable Text; `poster_path` is nullable; absent values map to NULL; render year `—` and optional placeholders | Permit legitimate movies with incomplete TMDB data without storing invalid strings/URLs |
| DEC-07 | Decided | `rating` and `review` start as NULL on TMDB import; never copy TMDB `vote_average` or tagline into personal fields; entered rating must be 1–10 inclusive | Separate external metadata from a user's rating/review; range is our target rule, not proven legacy validation |
| DEC-08 | Decided | Store unlimited saved movies; **display only top 10**, ordered rated first (`rating` DESC), then `created_at` ASC for ties; unrated last | Ensure `created_at` is populated/backfilled deterministically for legacy rows |
| DEC-09 | Decided | Compute rank when querying/rendering; enforce `tmdb_id NOT NULL UNIQUE` after verified legacy backfill, and return controlled duplicate feedback for existing TMDB IDs | All ten legacy rows must have verified TMDB IDs before enforcement, so imported duplicates cannot bypass the constraint through NULL IDs |
| DEC-10 | Decided | Preserve all ten existing records, Unicode, IDs, and complete descriptions; test on isolated DB and mock TMDB | Do not truncate or overwrite source data; regression tests cover each audit row and core workflow |

**Completion gate:** All 41 unique canonical IDs cover the reviewer-confirmed crosswalk; every canonical finding has an outcome (fixed with evidence or addressed by a passing FastAPI test), original audit ID coverage is reviewed, core route tests and migration checks pass, and reviewer accepts this checklist. No FastAPI implementation, migration, or regression-test execution is claimed here.
