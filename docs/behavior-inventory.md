# Legacy Flask Behavior Inventory

This document records the observed behavior of the original
Top Ten Movies Flask application before its FastAPI rebuild.

The purpose is to preserve expected functionality, document
existing defects, and establish a baseline for future tests.

## 1. Route Walk

### Verification chronology note

Section 1 was built incrementally as the
legacy Flask behavior audit progressed.

Some earlier entries contain statements
such as "Pending verification" or
"requires separate verification."

These statements describe the status
at the time each entry was written.

Where a later subsection independently
documents the same scenario, the later
verification result supersedes the
earlier pending-status statement.

Historical observations and test results
are retained for traceability.

A scenario must not be considered verified
solely because a later related scenario
was tested.

Use the specific recorded evidence to
determine which behaviors, exceptions,
HTTP responses, and database outcomes
were actually verified.

The completed defect register in Section 3
summarizes the 16 verified defect IDs.

Unresolved design questions remain
separate from completed legacy testing.

### GET `/` — Homepage

- **Inputs:** No required parameters.
- **Observed HTTP status:** 200 OK.
- **Response:** Renders `index.html` with the movie list.
- **Database operation:** Reads all Movie records, ordered by rating ascending.
- **TMDB requests:** None.
- **Side effects:** Updates the global `all_movies` list and prints the record count; no database writes.
- **Verified behavior:** All 10 original movies displayed successfully.
- **Missing, unknown, or non-numeric ID:** Not applicable; this route does not accept an ID.

#### Ranking behavior

- Rankings are calculated when movie records are retrieved.
- The lowest-rated movie receives the largest rank number.
- The highest-rated movie receives rank #1.
- The stored `Movie.ranking` column is ignored.
- No explicit tie-breaking rule is implemented.
- No ten-movie limit is applied by this query.

**Source:** `main.py`, lines 56–60 and 125–143.

**Future test:** `test_homepage_displays_movies_in_rating_order` (proposed).

### GET `/delete` — Delete a movie

- **Input:** Movie ID supplied through the `id` query parameter.
- **Success status:** Confirmed HTTP 302 redirect to `/` when deleting an existing movie. Tested against the isolated database.
- **Response:** Redirects to the homepage after successful deletion.
- **Database operation:** Looks up a movie by ID, deletes it, and commits the transaction.
- **TMDB requests:** None.
- **Side effects:** Permanently removes a movie record and prints its title.
- **Missing ID:** Confirmed HTTP 500 when requesting `GET /delete` without an `id` parameter. Tested against the isolated database on 2026-10-19. The movie count remained 10 before and after the request. Source inspection indicates an `AttributeError` from accessing `.title` on `None`.
- **Unknown ID:** Confirmed HTTP 500 for `GET /delete?id=99999999`. The ID was verified as nonexistent before the request. Tested against the isolated database; movie count remained unchanged (10 → 10).
- **Non-numeric ID:** Confirmed HTTP 500 for `GET /delete?id=abc`. Tested using Flask's test client against the isolated database. Movie count remained unchanged (10 → 10).

#### Known concerns

- The route allows database deletion using GET.
- No check confirms that the movie exists before accessing `.title`.
- Missing or invalid IDs are not handled gracefully.

**Source:** `main.py`, lines 63–70.

**Future tests (proposed):**
- `test_delete_existing_movie`
- `test_delete_missing_id`
- `test_delete_unknown_id`
- `test_delete_nonnumeric_id`

**Verification status:** Complete for the four primary Delete-route scenarios. All tests independently reproduced using Flask's test client against an isolated database.

**Observed results:**
- Missing ID: HTTP 500; movie count 10 → 10.
- Unknown ID (`99999999`): HTTP 500; movie count 10 → 10.
- Non-numeric ID (`abc`): HTTP 500; movie count 10 → 10.
- Valid ID (`2`, The Matrix): HTTP 302 redirect to `/`; movie count 10 → 9; deleted record no longer exists.

**Test cleanup:** Temporary database restored from the original ten-movie database. SHA-256 file hashes matched.

**Conclusion:** Valid deletion works, but missing, unknown, and non-numeric IDs cause HTTP 500 errors. Deletion through GET is also a known design concern.

### GET `/edit` - Display movie editing form

- **Input:** Optional `id` query parameter.
- **Success status:** HTTP 200.
- **Response:** Renders `edit.html` with a blank `RateMovieForm`.
- **Database operation:** None on GET.
- **TMDB requests:** None.
- **Side effects:** No database writes.
- **Page heading:** Displays the hardcoded text `Movie Title`, rather than the selected movie's title.

#### Observed GET behavior

All tests were performed using Flask's test client against an isolated database.

| Scenario | HTTP status | Movie count |
|---|---|---|
| Valid ID (`2`) | 200 | 10 → 10 |
| Missing ID | 200 | 10 → 10 |
| Unknown ID (`99999999`) | 200 | 10 → 10 |
| Non-numeric ID (`abc`) | 200 | 10 → 10 |

#### Known concerns

- The GET handler does not validate the movie ID.
- Missing, unknown, and non-numeric IDs still return HTTP 200.
- The form does not display or prefill information from the selected movie.
- The template uses a hardcoded `Movie Title` heading.

**Source:** `main.py`, lines 73-87; `templates/edit.html`, lines 13-19.

**Future tests (proposed):**
- `test_edit_get_existing_movie`
- `test_edit_get_missing_id`
- `test_edit_get_unknown_id`
- `test_edit_get_nonnumeric_id`

**Verification status:** Four GET scenarios independently tested. POST behavior remains pending.

### POST `/edit` - Missing CSRF token

- **Input:** Movie ID `2`, rating `7.5`, review `CSRF test`.
- **CSRF token:** Omitted intentionally.
- **Observed HTTP status:** 200.
- **Response:** The edit form is returned rather than a successful-update redirect.
- **Database operation:** No changes persisted.
- **Movie count:** 10 → 10.
- **Rating/review changed:** False.
- **TMDB requests:** None.

#### Observations

The POST request did not update the movie, even though the submitted rating and review were otherwise valid-looking.

This behavior is consistent with Flask-WTF rejecting the missing CSRF token. The exact form-validation error has not yet been independently inspected.

**Source:** `main.py`, lines 73-87; `RateMovieForm`, lines 24-27.

**Future test (proposed):**
- `test_edit_post_rejects_missing_csrf`

**Verification status:** HTTP response and unchanged database values independently confirmed using Flask's test client against an isolated database.

**Pending verification:** Explicit CSRF error, successful POST with valid CSRF, rating boundaries, and invalid movie IDs.

### POST `/edit` - Valid CSRF token

- **Input:** Movie ID `2`, rating `7.5`, review `Valid CSRF test`.
- **CSRF token:** Valid token obtained from GET `/edit?id=2` using the same test client.
- **GET HTTP status:** 200.
- **POST HTTP status:** 302.
- **Redirect:** `/`.
- **Database operation:** Updates the existing movie's rating and review, then commits the transaction.
- **Movie count:** 10 → 10.
- **Rating/review changed:** True.
- **Rating after update:** 7.5.
- **TMDB requests:** None.

#### Observed behavior

A valid CSRF token was extracted from the rendered editing form and submitted with a valid rating and review.

Flask-WTF accepted the form submission, and the application executed the database update.

The application redirected to the homepage after saving the changes.

The movie count remained unchanged because the operation updated an existing record rather than inserting or deleting one.

#### Test isolation and cleanup

The test used the isolated database under the temporary `top-ten-movies-behavior-*` directory.

After testing, the temporary database was restored from the original ten-movie database.

SHA-256 file hashes were compared and matched.

**Source:** `main.py`, lines 73-87; `RateMovieForm`, lines 24-27; `templates/edit.html`.

**Future test (proposed):**
- `test_edit_post_valid_csrf_updates_movie`

**Verification status:** Successful POST, HTTP 302 redirect, updated database values, and database restoration independently verified.

**Pending verification:** Rating boundaries, invalid movie IDs on POST, and explicit CSRF validation errors.

### POST `/edit` - Zero rating validation

- **Input:** Movie ID `2`, rating `0`, review `Zero rating test`.
- **CSRF token:** Valid token obtained from GET `/edit?id=2`.
- **GET HTTP status:** 200.
- **POST HTTP status:** 200.
- **Database operation:** No changes persisted.
- **Movie count:** 10 → 10.
- **Rating/review changed:** False.
- **Rating after request:** 9.2.
- **TMDB requests:** None.

#### Observed behavior

The legacy application rejected a rating of zero despite receiving a valid CSRF token and a nonempty review.

The edit form was returned without redirecting to the homepage.

The movie retained its original rating and review.

This behavior is consistent with WTForms `DataRequired()` treating numeric zero as an empty or false value. The specific validation error has not yet been inspected.

#### Target design decision

Movie ratings must follow the IMDb-inspired scale of 1 to 10, inclusive. Decimal ratings are allowed.

**Decision:** Zero must remain invalid in the modernized application.

**Reason:** Preserve the original application's intended rating scale.

**Source:** `main.py`, `RateMovieForm`, lines 24-27; Edit route, lines 73-87.

**Future test (proposed):**
- `test_edit_post_rejects_zero_rating`

**Verification status:** Zero-rating rejection and unchanged database values confirmed using Flask's test client against the isolated database.

**Pending verification:** Explicit validation error and other rating boundaries.

### POST `/edit` - Minimum valid rating of 1

- **Input:** Movie ID `2`, rating `1`, review `Minimum rating test`.
- **CSRF token:** Valid token obtained from GET `/edit?id=2`.
- **GET HTTP status:** 200.
- **POST HTTP status:** 302.
- **Redirect:** `/`.
- **Database operation:** Successfully updated the existing movie.
- **Movie count:** 10 → 10.
- **Rating/review changed:** True.
- **Rating after update:** 1.0.
- **TMDB requests:** None.

#### Observed behavior

The legacy Flask application accepted a rating of 1 with a valid CSRF token and a nonempty review.

The application updated the movie's rating and review, committed the transaction, and redirected to the homepage.

The database stored the rating as `1.0` because the rating column uses a floating-point data type.

The movie count remained unchanged because the operation updated an existing record.

#### Target design decision

A rating of 1 is the minimum valid rating under the IMDb-inspired 1-to-10 rating system.

**Decision:** The modernized application must accept ratings of 1.

**Reason:** Preserve the original application's intended rating scale.

#### Test isolation and cleanup

The test was performed against the isolated database in the temporary `top-ten-movies-behavior-*` directory.

After testing, the temporary database was restored from the original ten-movie database.

SHA-256 file hashes were compared and matched.

**Source:** `main.py`, `RateMovieForm`, lines 24-27; Edit route, lines 73-87.

**Future test (proposed):**
- `test_edit_post_accepts_minimum_rating`

**Verification status:** Successful POST, HTTP 302 redirect, saved rating of 1.0, unchanged movie count, and database restoration independently verified.

**Pending verification:** Maximum valid rating of 10 and out-of-range ratings.

### POST `/edit` - Maximum valid rating of 10

- **Input:** Movie ID `2`, rating `10`, review `Maximum rating test`.
- **CSRF token:** Valid token obtained from GET `/edit?id=2`.
- **GET HTTP status:** 200.
- **POST HTTP status:** 302.
- **Redirect:** `/`.
- **Database operation:** Successfully updated the existing movie.
- **Movie count:** 10 → 10.
- **Rating/review changed:** True.
- **Rating after update:** 10.0.
- **TMDB requests:** None.

#### Observed behavior

The legacy Flask application accepted a rating of 10 with a valid CSRF token and a nonempty review.

The application updated the movie's rating and review, committed the transaction, and redirected to the homepage.

The database stored the rating as `10.0` because the rating column uses a floating-point data type.

The movie count remained unchanged because the operation updated an existing record.

#### Target design decision

A rating of 10 is the maximum valid rating under the IMDb-inspired 1-to-10 rating system.

**Decision:** The modernized application must accept ratings of 10.

**Reason:** Preserve the original application's intended rating scale.

#### Test isolation and cleanup

The test was performed against the isolated database in the temporary `top-ten-movies-behavior-*` directory.

After testing, the temporary database was restored from the original ten-movie database.

SHA-256 file hashes were compared and matched.

**Source:** `main.py`, `RateMovieForm`, lines 24-27; Edit route, lines 73-87.

**Future test (proposed):**
- `test_edit_post_accepts_maximum_rating`

**Verification status:** Successful POST, HTTP 302 redirect, saved rating of 10.0, unchanged movie count, and database restoration independently verified.

**Pending verification:** Out-of-range ratings above 10 and below 1.

### POST `/edit` - Rating above maximum (11)

**Defect ID:** D-R01 - Missing upper rating boundary validation.

#### Test input and results

- **Input:** Movie ID `2`, rating `11`, review `Above maximum rating test`.
- **CSRF token:** Valid token obtained from GET `/edit?id=2`.
- **GET HTTP status:** 200.
- **POST HTTP status:** 302.
- **Redirect:** `/`.
- **Database operation:** Incorrectly accepted and saved the rating.
- **Movie count:** 10 → 10.
- **Rating/review changed:** True.
- **Rating after update:** 11.0.
- **TMDB requests:** None.

#### Observed behavior

The legacy Flask application accepted a rating of 11 even though the intended rating scale is 1 to 10.

Flask-WTF accepted the submitted form, and the application updated the movie's rating and review.

The database stored `11.0`, and the application redirected to the homepage.

This behavior violates the application's intended rating rules.

#### Reproduction steps

1. Use an isolated copy of the original ten-movie database.
2. Request GET `/edit?id=2` and obtain a valid CSRF token.
3. Submit POST `/edit?id=2` with rating `11`, a nonempty review, and the CSRF token.
4. Observe HTTP 302 and the redirect to `/`.
5. Query movie ID `2` and confirm its saved rating is `11.0`.

#### Root cause

`RateMovieForm` uses `FloatField` with `DataRequired()`.

`DataRequired()` does not enforce a numeric range.

The form has no explicit validation requiring ratings to be between 1 and 10.

#### Target design decision

**Decision:** The modernized application must reject ratings greater than 10.

**Reason:** Preserve the intended IMDb-inspired rating scale of 1 to 10, inclusive, while allowing decimal ratings.

Server-side validation must enforce both the minimum and maximum boundaries.

#### Test isolation and cleanup

The test was performed against the isolated database in the temporary `top-ten-movies-behavior-*` directory.

After testing, the temporary database was restored from the original ten-movie database.

SHA-256 file hashes were compared and matched.

**Source:** `main.py`, `RateMovieForm`, lines 24-27; Edit route, lines 73-87.

**Future test (proposed):**
- `test_edit_post_rejects_rating_above_ten`

**Verification status:** Defect independently reproduced using Flask's test client. Database restoration verified.

**Pending verification:** Ratings below 1, including negative values.

### POST `/edit` - Negative rating (-2)

**Defect ID:** D-R02 - Missing lower rating boundary validation.

#### Test input and results

- **Input:** Movie ID `2`, rating `-2`, review `Negative rating test`.
- **CSRF token:** Valid token obtained from GET `/edit?id=2`.
- **GET HTTP status:** 200.
- **POST HTTP status:** 302.
- **Redirect:** `/`.
- **Database operation:** Incorrectly accepted and saved the negative rating.
- **Movie count:** 10 → 10.
- **Rating/review changed:** True.
- **Rating after update:** -2.0.
- **TMDB requests:** None.

#### Observed behavior

The legacy Flask application accepted a rating of -2 even though the intended rating scale is 1 to 10.

The application updated the movie's rating and review, committed the transaction, and redirected to the homepage.

The database stored `-2.0`, violating the application's intended rating rules.

#### Reproduction steps

1. Use an isolated copy of the original ten-movie database.
2. Request GET `/edit?id=2` and obtain a valid CSRF token.
3. Submit POST `/edit?id=2` with rating `-2`, a nonempty review, and the CSRF token.
4. Observe HTTP 302 and the redirect to `/`.
5. Query movie ID `2` and confirm its saved rating is `-2.0`.

#### Root cause

`RateMovieForm` uses `FloatField` with `DataRequired()`.

`DataRequired()` accepts nonzero numeric values, including negative numbers.

The form has no explicit minimum or maximum numerical range validation.

This defect shares its underlying cause with D-R01.

#### Target design decision

**Decision:** The modernized application must reject negative ratings and all other ratings below 1.

**Reason:** Preserve the intended IMDb-inspired rating scale of 1 to 10, inclusive, while allowing decimal ratings.

Server-side validation must explicitly enforce both rating boundaries.

#### Test isolation and cleanup

The test was performed against the isolated database in the temporary `top-ten-movies-behavior-*` directory.

After testing, the temporary database was restored from the original ten-movie database.

SHA-256 file hashes were compared and matched.

**Source:** `main.py`, `RateMovieForm`, lines 24-27; Edit route, lines 73-87.

**Future tests (proposed):**
- `test_edit_post_rejects_negative_rating`
- `test_edit_post_rejects_rating_below_one`

**Verification status:** Negative rating of -2 independently accepted and saved using Flask's test client. HTTP 302 redirect, unchanged movie count, and database restoration verified.

**Verification update:** A positive fractional rating of 0.5 was independently tested and incorrectly accepted. See the additional test below.

#### Additional D-R02 verification - Rating of 0.5

**Defect ID:** D-R02 - Missing lower rating boundary validation.

**Test input:**
- Movie ID: `2`
- Rating: `0.5`
- Review: `Below minimum fractional rating test`
- CSRF token: Valid token obtained from GET `/edit?id=2`

**Observed results:**
- GET HTTP status: 200
- POST HTTP status: 302
- Redirect: `/`
- Movie count: 10 → 10
- Rating/review changed: True
- Rating after update: 0.5
- TMDB requests: None

**Reproduction steps:**

1. Start with an isolated copy of the original ten-movie database.
2. Request GET `/edit?id=2` and obtain a valid CSRF token.
3. Submit POST `/edit?id=2` with rating `0.5`, a nonempty review, and the CSRF token.
4. Observe HTTP 302 and the redirect to `/`.
5. Query movie ID `2` and confirm the saved rating is `0.5`.

**Observed behavior:**

The legacy Flask application incorrectly accepted a positive
fractional rating below the intended minimum of 1.

The application updated the movie's rating and review, committed
the transaction, and redirected to the homepage.

This confirms that rejecting zero through `DataRequired()` does
not enforce the application's minimum rating of 1.

**Target behavior:**

The modernized application must reject all ratings below 1,
including positive fractions such as 0.5.

**Test isolation and cleanup:**

The test used the isolated temporary database.

After testing, the temporary database was restored from the
original ten-movie database.

SHA-256 hashes matched after restoration.

**Future test (proposed):**
- `test_edit_post_rejects_fractional_rating_below_one`

**Verification status:** Defect independently reproduced and
database restoration verified.

### GET `/add` - Display Add Movie form

- **Inputs:** No required parameters.
- **Observed HTTP status:** 200 OK.
- **Response:** Renders `add.html` with an `AddMovieForm`.
- **Form field:** `new_movie` (movie title).
- **Database operation:** None on GET.
- **TMDB requests:** None.
- **Side effects:** No database writes.
- **Missing, unknown, or non-numeric ID:** Not applicable; this route does not require a movie ID.

#### Observed behavior

The Add Movie page loads successfully and displays
the movie title input field.

The route does not add any movies when accessed
through a GET request.

#### Test results

| Test | Result |
|---|---|
| HTTP status | 200 |
| Movie title field present | True |
| Movies before | 10 |
| Movies after | 10 |

#### Test isolation

The test used Flask's test client against the
isolated temporary database.

The original movie database was not modified.

**Source:** `main.py`, lines 90-100;
`templates/add.html`.

**Future test (proposed):**
- `test_add_get_displays_movie_form`

**Verification status:** GET `/add` independently
verified using Flask's test client.

### POST `/add` - Search for a movie

- **Input:** Movie title submitted through the `new_movie` form field.
- **CSRF token:** Valid token obtained from GET `/add`.
- **Observed HTTP status:** 200 OK.
- **Response:** Renders `select.html` with the movie search results.
- **Database operation:** No database writes.
- **TMDB interaction:** Calls `movie_search_request()` with the submitted title.
- **Side effects:** Prints the submitted title and search results to the console.
- **Movie ID:** Not required for this route.

#### Observed behavior

The user submits a movie title through the Add Movie form.

The application calls `movie_search_request()` with the
submitted title and receives matching movie results.

The results are rendered in `select.html`, allowing the
user to choose which movie to add.

The application does not insert a movie during this step.

#### Test results

The test used a mocked TMDB search result for `The Matrix`.

| Test | Result |
|---|---|
| GET `/add` status | 200 |
| POST `/add` status | 200 |
| Submitted movie title | The Matrix |
| Mock search call | `call('The Matrix')` |
| Selection contains The Matrix | True |
| Movies before | 10 |
| Movies after | 10 |
| Actual TMDB network requests | None |

#### Test isolation

The test used Flask's test client against the
isolated temporary database.

The TMDB search function was mocked using
Python's `unittest.mock.patch`.

No real TMDB API request was made.

The original movie database was not modified.

#### Known concerns

- Empty movie titles require separate verification.
- TMDB API failures require separate verification.
- Empty TMDB search results require separate verification.
- This route does not prevent a user from searching for
  a movie already present in the database.

**Source:** `main.py`, lines 90-100;
`movie_search_request()`; `templates/select.html`.

**Future tests (proposed):**
- `test_add_post_displays_movie_search_results`
- `test_add_post_rejects_empty_title`
- `test_add_post_handles_empty_search_results`
- `test_add_post_handles_tmdb_failure`

**Verification status:** Successful POST with a valid CSRF
token and mocked TMDB response independently verified
using Flask's test client.

### POST `/add` - Empty movie title validation

- **Input:** Empty string submitted as `new_movie`.
- **CSRF token:** Valid token obtained from GET `/add`.
- **GET HTTP status:** 200.
- **POST HTTP status:** 200.
- **Response:** Returns the Add Movie form.
- **Redirect:** None.
- **TMDB search function called:** False.
- **Database operation:** None.
- **Movie count:** 10 → 10.

#### Observed behavior

The legacy Flask application rejected an empty movie title.

The form submission did not pass validation, and the
application returned the Add Movie form instead of
rendering movie search results.

The TMDB search function was not called.

No database records were inserted, modified, or deleted.

#### Test isolation

The test used Flask's test client against an isolated
temporary database.

A valid CSRF token was submitted to isolate title
validation from CSRF validation.

The TMDB search function was mocked using
`unittest.mock.patch`.

No live TMDB request was made.

The original database was not modified.

#### Target behavior

The modernized application must reject empty movie titles
and must not contact TMDB when title validation fails.

**Reason:** Avoid unnecessary API requests and prevent
invalid movie searches.

**Source:** `main.py`, `AddMovieForm`, lines 30-32;
Add route, lines 90-100.

**Future test (proposed):**
- `test_add_post_rejects_empty_title`

**Verification status:** Empty-title rejection, unchanged
movie count, and absence of TMDB calls independently
confirmed using Flask's test client.

**Pending verification:** User-visible validation feedback
and whitespace-only movie titles.

### POST `/add` - Empty TMDB search results

- **Input:** Movie title `NonexistentMovieXYZ123`.
- **CSRF token:** Valid token obtained from GET `/add`.
- **GET HTTP status:** 200.
- **POST HTTP status:** 200.
- **TMDB search function:** Called with the submitted title.
- **Mocked search response:** Empty list `[]`.
- **Response:** Renders `select.html` with no movie results.
- **Selection page heading present:** True.
- **Redirect:** None.
- **Movie count:** 10 → 10.
- **Actual TMDB network requests:** None.

#### Observed behavior

The legacy Flask application successfully processed
a movie search that returned zero matching results.

The application rendered the Select Movie page
with an empty movie list.

No error occurred, and the application returned HTTP 200.

The rendered page text contained:

`Select Movie Select Movie`

No user-visible message explaining that no movies
were found was observed.

#### Known UX concern

The application does not appear to provide useful
feedback when TMDB returns an empty result list.

Users may see a blank selection page without
understanding why no movies are displayed.

#### Target design decision

**Decision:** The modernized application should display
a clear message when no matching movies are found.

**Suggested message:**
"No movies found. Please try another title."

**Reason:** Improve usability while preserving successful
handling of empty search results.

#### Test isolation

The test used Flask's test client against the
isolated temporary database.

The TMDB search function was mocked to return
an empty list using `unittest.mock.patch`.

No real TMDB API request was made.

The original movie database was not modified.

#### Future tests (proposed)

- `test_add_post_handles_empty_search_results`
- `test_add_post_displays_no_results_message`

**Source:** `main.py`, lines 90-100;
`movie_search_request()`; `templates/select.html`.

**Verification status:** Empty search response,
HTTP 200, rendered selection page, unchanged movie
count, and absence of redirect independently verified.

### POST `/add` - TMDB service failure

**Defect ID:** D-T01 - Unhandled TMDB search failure.

#### Test input and results

- **Input:** Movie title `The Matrix`.
- **CSRF token:** Valid token obtained from GET `/add`.
- **GET HTTP status:** 200.
- **Simulated TMDB failure:** HTTPError representing HTTP 503.
- **POST HTTP status:** 500.
- **Mock search call:** `call('The Matrix')`.
- **Response:** Internal Server Error.
- **Redirect:** None.
- **Movie count:** 10 → 10.
- **Actual TMDB network requests:** None.

#### Observed behavior

The legacy Flask application did not handle the
simulated TMDB search exception.

The exception propagated from `movie_search_request()`
and Flask returned HTTP 500.

No movie records were added or deleted.

#### Reproduction steps

1. Use the isolated temporary database.
2. Request GET `/add` and obtain a valid CSRF token.
3. Mock `movie_search_request()` to raise HTTPError.
4. Submit POST `/add` with title `The Matrix` and the token.
5. Observe HTTP 500 with an Internal Server Error response.
6. Confirm the movie count remains 10.

#### Root cause

The POST `/add` handler calls `movie_search_request()`
without exception handling for TMDB request failures.

#### Target design decision

**Decision:** The modernized application must handle
TMDB service failures gracefully.

**Reason:** An unavailable external service should not
cause an unhandled application error.

The user should receive a clear message, such as:

"Movie search is temporarily unavailable. Please try again."

The application should log errors securely without
exposing API credentials.

#### Test isolation and limitations

The test used Flask's test client against an isolated
temporary database.

The search function was mocked using `unittest.mock.patch`.

Fake credentials were used. Exception logging was suppressed
for this test.

The test did not make a real TMDB request or verify
API-key exposure in exception messages.

#### Future tests (proposed)

- `test_add_post_handles_tmdb_failure`
- `test_tmdb_errors_do_not_expose_api_key`

**Source:** `main.py`, POST `/add` handler,
and `movie_search_request()`.

**Verification status:** Simulated TMDB HTTPError,
application HTTP 500, and unchanged movie count
independently confirmed using Flask's test client.

### POST `/add` - Whitespace-only movie title validation

- **Input:** Three spaces (`"   "`) submitted as `new_movie`.
- **CSRF token:** Valid token obtained from GET `/add`.
- **GET HTTP status:** 200.
- **POST HTTP status:** 200.
- **Response:** Returns the Add Movie form.
- **Redirect:** None.
- **TMDB search function called:** False.
- **Movie count:** 10 → 10.
- **Actual TMDB network requests:** None.

#### Observed behavior

The legacy Flask application rejected a movie title
containing only three whitespace characters.

The submitted form did not pass validation.

The application returned the Add Movie form without
performing a TMDB search or redirecting.

The movie count remained unchanged.

#### Validation explanation

`AddMovieForm` uses WTForms `DataRequired()`.

This validator rejects whitespace-only string input.

The observed behavior is consistent with the validator's
treatment of whitespace-only values as empty.

#### Target behavior

**Decision:** Preserve whitespace-only title rejection
in the modernized application.

**Reason:** Movie searches must contain meaningful text.
Invalid input should not trigger unnecessary TMDB requests.

The backend must enforce this validation independently
of browser-side validation.

#### Test isolation

The test used Flask's test client against the isolated
temporary database.

A valid CSRF token was supplied.

`movie_search_request()` was mocked, and no actual
TMDB network request occurred.

The original movie database was not modified.

#### Future test (proposed)

- `test_add_post_rejects_whitespace_only_title`

**Source:** `main.py`, `AddMovieForm`, lines 30-32;
POST `/add` handler, lines 90-100.

**Verification status:** Whitespace-only title rejection,
HTTP 200 response, unchanged movie count, and absence
of TMDB calls independently confirmed.

**Pending verification:** User-visible validation feedback.

### GET `/select` - Select and insert a movie

- **Input:** TMDB movie ID supplied through the `id` query parameter.
- **Test ID:** `987654` (fictional test movie).
- **Observed HTTP status:** 302.
- **Redirect:** `/edit?id=16`.
- **Database operation:** Inserts and commits a new Movie record.
- **TMDB interaction:** Calls `movie_detail_request()` with the selected ID.
- **Actual TMDB network requests:** None; response mocked.
- **Side effects:** Creates a movie record and prints movie information.

#### Observed behavior

The legacy Flask application successfully retrieved mocked
movie details and inserted a new movie into SQLite.

The application then redirected to the Edit Movie page
using the newly generated database ID.

#### Test results

| Test | Result |
|---|---|
| GET `/select` status | 302 |
| Mock detail request | `call('987654')` |
| Movies before | 10 |
| Movies after | 11 |
| Movie inserted | True |
| New movie ID | 16 |
| Redirect | `/edit?id=16` |
| Stored title | Behavior Inventory Test Film |
| Stored year | 2024 |
| Stored rating | 7.4 |
| Stored ranking | 10 |
| Stored review | Testing without touching production data. |
| Temporary database restored | True |

#### Known concerns

- The route inserts database records using HTTP GET.
- No hard ten-movie limit is enforced during insertion.
- Missing, unknown, and non-numeric IDs require verification.
- Duplicate movie selection requires separate verification.
- TMDB detail request failures require separate verification.
- The legacy application stores TMDB's `original_title`
  as the movie title.

#### Target behavior

**Decision:** Movie insertion must use HTTP POST
in the modernized application.

**Reason:** GET requests should not modify application data.

The modernized application should preserve the workflow
of selecting a movie, saving its details, and then allowing
the user to enter a personal rating and review.

#### Test isolation and cleanup

The test used Flask's test client against an isolated
temporary database.

`movie_detail_request()` was mocked using
`unittest.mock.patch`.

The temporary database was restored from the original
ten-movie database after testing.

SHA-256 file hashes matched after restoration.

The original database was not modified.

#### Future tests (proposed)

- `test_select_existing_tmdb_movie_creates_record`
- `test_select_redirects_to_edit_page`
- `test_select_missing_id`
- `test_select_unknown_id`
- `test_select_nonnumeric_id`
- `test_select_prevents_duplicate_movie`

**Source:** `main.py`, lines 103-122;
`movie_detail_request()`.

**Verification status:** Successful movie insertion,
HTTP 302 redirect, saved database values, and temporary
database restoration independently confirmed.

### GET `/select` - Missing movie ID

**Defect ID:** D-S01 - Missing movie ID is not validated.

#### Test input and results

- **Request:** GET `/select`
- **ID parameter:** Missing.
- **Python value:** `None`.
- **Simulated TMDB error:** HTTP 404.
- **Observed Flask HTTP status:** 500.
- **Mock HTTP request called:** True.
- **Requested URL:** `https://api.themoviedb.org/3/movie/None`
- **Response:** Internal Server Error.
- **Redirect:** None.
- **Movie count:** 10 → 10.
- **Temporary database restored:** True.

#### Observed behavior

The legacy application accepts a request to `/select`
without a movie ID.

The route passes `None` to `movie_detail_request()`.

The application constructs a TMDB details URL ending
in `/movie/None` and attempts an HTTP request.

When the mocked request raises an HTTPError,
Flask returns HTTP 500.

No movie record is inserted.

#### Reproduction steps

1. Use an isolated copy of the ten-movie database.
2. Mock `requests.get()` to return a response whose
   `raise_for_status()` raises HTTPError.
3. Request GET `/select` without an `id` parameter.
4. Observe that the attempted URL ends in `/movie/None`.
5. Confirm Flask returns HTTP 500.
6. Confirm the movie count remains 10.
7. Restore the temporary database and compare SHA-256 hashes.

#### Root cause

The `/select` route retrieves the movie ID using
`request.args.get('id')` without checking whether
the parameter exists.

It passes the value directly to
`movie_detail_request()`.

#### Target design decision

**Decision:** The modernized application must validate
the movie ID before attempting a TMDB request.

**Reason:** Missing or invalid input should produce a
controlled client error, not an internal server error.

A missing movie ID should return an appropriate
HTTP 400 response.

The application must not contact TMDB when
the required movie ID is absent.

#### Test isolation and limitations

The test used Flask's test client against an isolated
temporary database.

The HTTP request was mocked, so no real TMDB
network request occurred.

The simulated HTTP 404 does not establish
TMDB's actual response to the malformed URL.

Exception logging was suppressed during the test.

The temporary database was restored successfully,
and SHA-256 file hashes matched.

#### Future tests (proposed)

- `test_select_missing_id_returns_400`
- `test_select_missing_id_does_not_call_tmdb`

**Source:** `main.py`, `/select` route,
lines 103-122; `movie_detail_request()`.

**Verification status:** Missing ID, attempted TMDB
URL, simulated HTTP error, Flask HTTP 500, unchanged
movie count, and database restoration independently
confirmed using Flask's test client.

### GET `/select` - Non-numeric movie ID

**Defect ID:** D-S02 - Non-numeric movie ID is not validated.

#### Test input and results

- **Request:** GET `/select?id=abc`
- **ID parameter:** `abc`.
- **Simulated TMDB error:** HTTP 404.
- **Observed Flask HTTP status:** 500.
- **Mock HTTP request called:** True.
- **Requested URL:** `https://api.themoviedb.org/3/movie/abc`
- **Response:** Internal Server Error.
- **Redirect:** None.
- **Movie count:** 10 → 10.
- **Temporary database restored:** True.

#### Observed behavior

The legacy Flask application accepted a non-numeric
movie ID from the URL query parameter.

The route passed `abc` directly to
`movie_detail_request()`.

The application constructed a TMDB details URL
ending in `/movie/abc` without validating the ID.

When the mocked HTTP response raised an HTTPError,
Flask returned HTTP 500.

No movie record was inserted.

#### Reproduction steps

1. Use an isolated copy of the original ten-movie database.
2. Mock `requests.get()` to simulate an HTTP 404 error.
3. Request GET `/select?id=abc`.
4. Confirm the requested URL ends in `/movie/abc`.
5. Observe Flask HTTP 500.
6. Confirm the movie count remains 10.
7. Restore the temporary database and verify SHA-256 hashes.

#### Root cause

The `/select` route retrieves the movie ID using
`request.args.get('id')` without checking whether
the value is numeric.

The value is passed directly to
`movie_detail_request()`.

This defect is related to D-S01 (missing movie ID).

#### Target design decision

**Decision:** The modernized application must validate
movie IDs before contacting TMDB.

**Reason:** Invalid identifiers should produce controlled
client errors rather than unhandled server exceptions.

Non-numeric IDs must be rejected with an appropriate
HTTP 400 response.

TMDB must not be contacted when ID validation fails.

#### Test isolation and limitations

The test used Flask's test client against an isolated
temporary database.

The HTTP request was mocked using `unittest.mock.patch`.

No real TMDB API request occurred.

The simulated HTTP 404 does not establish
TMDB's actual response to a non-numeric ID.

Exception logging was suppressed during the test.

The temporary database was restored from the
original ten-movie database.

SHA-256 file hashes matched after restoration.

#### Future tests (proposed)

- `test_select_nonnumeric_id_returns_400`
- `test_select_nonnumeric_id_does_not_call_tmdb`

**Source:** `main.py`, `/select` route,
lines 103-122; `movie_detail_request()`.

**Verification status:** Non-numeric ID, attempted TMDB
URL, simulated HTTP error, Flask HTTP 500, unchanged
movie count, and temporary database restoration
independently confirmed using Flask's test client.

### GET `/select` - Unknown numeric movie ID

**Defect ID:** D-S03 - Unhandled TMDB movie-not-found response.

#### Test input and results

- **Request:** GET `/select?id=99999999`
- **ID parameter:** `99999999`.
- **ID format:** Numeric.
- **Simulated TMDB error:** HTTP 404.
- **Observed Flask HTTP status:** 500.
- **Mock HTTP request called:** True.
- **Requested URL:** `https://api.themoviedb.org/3/movie/99999999`
- **Mock HTTP error triggered:** True.
- **Response:** Internal Server Error.
- **Redirect:** None.
- **Movie count:** 10 → 10.
- **Temporary database restored:** True.
- **Original database unchanged:** True.

#### Observed behavior

The legacy Flask application accepted the
numeric movie ID and passed it directly to
`movie_detail_request()`.

The application constructed a TMDB details URL
using the supplied ID.

When the mocked TMDB response raised HTTPError
to simulate HTTP 404, Flask returned HTTP 500.

No movie record was inserted.

#### Reproduction steps

1. Use an isolated copy of the original database.
2. Mock `requests.get()` to simulate HTTP 404.
3. Request GET `/select?id=99999999`.
4. Confirm the attempted URL contains the numeric ID.
5. Observe Flask HTTP 500.
6. Confirm the movie count remains 10.
7. Restore the temporary database.
8. Verify SHA-256 hashes for both databases.

#### Root cause

The `/select` workflow does not gracefully handle
an HTTPError raised during the TMDB detail request.

Unlike D-S01 and D-S02, this scenario involves
a correctly formatted numeric ID.

The defect concerns handling a movie-not-found
response rather than validating the ID format.

#### Target design decision

**Decision:** The modernized application must handle
TMDB movie-not-found responses gracefully.

**Reason:** A correctly formatted ID may not correspond
to an existing TMDB movie.

When TMDB confirms that a movie does not exist,
the application should return a controlled HTTP 404
response with a helpful user-facing message.

No database record should be created.

#### Test isolation and limitations

The test used Flask's test client and an isolated
temporary database.

The HTTP request was mocked using
`unittest.mock.patch`.

No actual TMDB network request occurred.

The test does not establish that ID `99999999`
is nonexistent in the live TMDB service.

The temporary database was restored successfully.

SHA-256 verification confirmed the restoration
and that the original database remained unchanged.

#### Future tests (proposed)

- `test_select_unknown_numeric_id_returns_404`
- `test_select_tmdb_404_does_not_insert_movie`

**Source:** `main.py`, `/select` route,
lines 103-122; `movie_detail_request()`.

**Verification status:** Numeric ID forwarded to TMDB,
simulated HTTP 404, Flask HTTP 500, unchanged movie
count, and database integrity independently verified.

### GET `/select` - Duplicate movie selection

**Defect ID:** D-S04 - Duplicate movie selection causes HTTP 500.

#### Test input and results

- **Request:** GET `/select?id=603`
- **Selected movie:** The Matrix.
- **TMDB response:** Mocked movie details.
- **Observed HTTP status:** 500.
- **Mock TMDB call:** `call('603')`.
- **Movies before:** 10.
- **Movies after:** 10.
- **Matching titles before:** 1.
- **Matching titles after:** 1.
- **Redirect:** None.
- **Response:** Internal Server Error.
- **Temporary database restored:** True.
- **Original database unchanged:** True.

#### Observed behavior

The legacy Flask application attempted to add
The Matrix even though a record with that title
already existed in the database.

The route retrieved the mocked TMDB movie details
and attempted to create a new Movie record.

Flask returned HTTP 500.

The total movie count remained unchanged at 10.

The number of records titled The Matrix remained 1.

The application did not redirect to the editing page.

#### Reproduction steps

1. Use an isolated copy of the original database.
2. Confirm The Matrix already exists.
3. Mock `movie_detail_request()` to return
   details for The Matrix.
4. Request GET `/select?id=603`.
5. Observe HTTP 500.
6. Confirm the movie count remains 10.
7. Confirm only one record titled The Matrix exists.
8. Restore the temporary database.
9. Verify SHA-256 file hashes.

#### Verified root cause

The Movie model declares `title` with `unique=True`.

Read-only SQLite inspection independently confirmed
that the existing database enforces this constraint.

- **SQLite index:** `sqlite_autoindex_movie_1`
- **Unique:** True.
- **Index origin:** `u` (UNIQUE constraint).
- **Indexed column:** `title`.

A duplicate insertion was independently reproduced
using Flask's test client with exception propagation enabled.

**Captured SQLAlchemy exception:** `IntegrityError`.

**Underlying SQLite exception:** `IntegrityError`.

**Database error message:**
`UNIQUE constraint failed: movie.title`

The `/select` route does not check for an existing
movie before attempting insertion.

When SQLite rejects the duplicate title, the exception
is not handled by the legacy application.

This produces the HTTP 500 response observed in Step 72.

**Conclusion:** The database uniqueness constraint
functions correctly. The application defect is its
failure to detect or gracefully handle duplicate selection.

#### Target design decision

**Decision:** The modernized application must
handle duplicate movie selection gracefully.

**Reason:** Selecting an existing movie should
not produce an unhandled HTTP 500 error.

The application should detect existing movies
before attempting insertion.

The user should receive a helpful message,
such as:

"This movie is already in your list."

Database uniqueness constraints should remain
in place to protect data integrity.

The target design should consider using
TMDB movie IDs for duplicate identification
rather than relying solely on movie titles.

#### Test isolation and cleanup

The test used Flask's test client against
an isolated temporary database.

TMDB movie details were mocked.

No real TMDB network request occurred.

The temporary database was restored from
the original ten-movie database.

SHA-256 hashes confirmed successful restoration.

The original database remained unchanged.

#### Future tests (proposed)

- `test_select_duplicate_movie_handled_gracefully`
- `test_select_duplicate_movie_does_not_insert`
- `test_database_enforces_movie_title_uniqueness`

**Source:** `main.py`, Movie model, lines 34-43;
`/select` route, lines 103-122.

**Verification status:** Complete.

- Duplicate selection independently reproduced.
- HTTP 500 confirmed with Flask's test client.
- SQLite title uniqueness constraint independently verified.
- SQLAlchemy `IntegrityError` captured.
- Underlying SQLite `IntegrityError` confirmed.
- Exact error: `UNIQUE constraint failed: movie.title`.
- Movie count unchanged at 10.
- Only one record titled `The Matrix` remains.
- Temporary database restored successfully.
- Original database verified unchanged using SHA-256 hashes.

**Root cause status:** Verified.

**Future remediation:** Handle duplicate movie selection
gracefully while preserving database uniqueness protection.

### GET `/select` - Missing TMDB release date

**Defect ID:** D-S05 - Missing release date causes HTTP 500.

#### Test input and results

- **Request:** GET `/select?id=987654`
- **TMDB response:** Mocked movie details.
- **Movie title:** Missing Release Date Test Film.
- **Release date field:** Omitted entirely.
- **Observed HTTP status:** 500.
- **Mock TMDB call:** `call('987654')`.
- **Movie count:** 10 → 10.
- **Test movie inserted:** False.
- **Redirect:** None.
- **Response:** Internal Server Error.
- **Temporary database restored:** True.
- **Original database unchanged:** True.

#### Observed behavior

The legacy Flask application received mocked
TMDB movie details without a `release_date` field.

The `/select` route attempted to process the
incomplete movie details.

Flask returned HTTP 500.

No movie record was inserted.

The existing ten-movie database remained unchanged.

#### Reproduction steps

1. Use an isolated copy of the original database.
2. Mock `movie_detail_request()` to return movie
   details without the `release_date` key.
3. Request GET `/select?id=987654`.
4. Observe HTTP 500.
5. Confirm no new movie record was inserted.
6. Confirm the movie count remains 10.
7. Restore the temporary database.
8. Verify SHA-256 database file hashes.

#### Verified root cause

The `/select` route accesses the TMDB release date
using direct dictionary key access.

The relevant expression is:

`str(m_dict['release_date'])[0:4]`

When the mocked TMDB response omitted the
`release_date` key, Python raised a `KeyError`.

The exception was independently captured using
Flask's test client with exception propagation enabled.

**Captured Python exception:** `KeyError`.

**Exception message:** `'release_date'`.

**Exception arguments:** `('release_date',)`.

**Missing key verified:** True.

The legacy application does not validate the
TMDB response before accessing this field.

The exception is not handled by the `/select`
route, producing the HTTP 500 observed in Step 77.

**Conclusion:** Missing TMDB release-date data
causes an unhandled Python `KeyError`.

The application defect is its failure to validate
or gracefully handle incomplete external movie data.

**Root cause status:** Verified.

#### Target design considerations

**Requirement:** The modernized application must
handle incomplete TMDB responses without producing
an unhandled HTTP 500 error.

The application must validate or normalize external
movie data before attempting database insertion.

A missing release date must be handled gracefully.

**Pending design decision:** Determine whether a
missing release date should be represented as an
unknown year or prevent insertion with a helpful
message.

The existing Movie model requires a non-null year,
so supporting an unknown year may require changes
to the database schema.

#### Test isolation and cleanup

The test used Flask's test client against
an isolated temporary database.

`movie_detail_request()` was mocked.

No real TMDB network request occurred.

The temporary database was restored from the
original ten-movie database.

SHA-256 checks confirmed successful restoration
and that the original database remained unchanged.

#### Future tests (proposed)

- `test_select_missing_release_date_handled_gracefully`
- `test_select_missing_release_date_does_not_crash`
- `test_select_missing_release_date_keyerror`

**Source:** `main.py`, `/select` route,
lines 103-122; `movie_detail_request()`.

**Verification status:** Complete for the missing-key scenario.

- Missing `release_date` independently reproduced.
- HTTP 500 confirmed using Flask's test client.
- Python `KeyError` independently captured.
- Missing key confirmed as `release_date`.
- Mock TMDB call verified: `call('987654')`.
- Movie count remained unchanged at 10.
- No test movie was inserted.
- Temporary database restored successfully.
- Original database verified unchanged using
  SHA-256 file hashes.

**Root cause status:** Verified.

**Pending verification:** Behavior when the
`release_date` key exists but contains an
empty string or a null value.

**Future remediation:** Validate or normalize
incomplete TMDB responses before accessing fields
or inserting movie records.

### GET `/select` - Empty TMDB release date

**Defect ID:** D-S06 - Empty release date accepted without validation.

#### Test input and results

- **Request:** GET `/select?id=987654`
- **TMDB response:** Mocked movie details.
- **Movie title:** Empty Release Date Audit Film.
- **Release date key present:** True.
- **Release date value:** Empty string (`''`).
- **Observed HTTP status:** 302.
- **Mock TMDB call:** `call('987654')`.
- **Movie count:** 10 → 11.
- **Test movie inserted:** True.
- **New movie ID:** 16.
- **Stored year:** Empty string (`''`).
- **Redirect:** `/edit?id=16`.
- **Internal Server Error:** False.
- **Temporary database restored:** True.
- **Original database unchanged:** True.

#### Observed behavior

The legacy Flask application received mocked
TMDB movie details containing an empty release date.

The `/select` route processed the response without
raising an exception.

The application inserted a new Movie record with
an empty string stored in the year column.

The database transaction committed successfully.

Flask returned HTTP 302 and redirected to the
editing page for the newly created movie.

#### Reproduction steps

1. Use an isolated copy of the original database.
2. Mock `movie_detail_request()` to return movie
   details containing `"release_date": ""`.
3. Request GET `/select?id=987654`.
4. Observe HTTP 302.
5. Confirm the movie count increases from 10 to 11.
6. Query the inserted movie and verify its year is `''`.
7. Confirm the redirect to `/edit?id=16`.
8. Restore the temporary database.
9. Verify SHA-256 database file hashes.

#### Verified root cause

The `/select` route extracts the release year using:

`str(m_dict['release_date'])[0:4]`

When `release_date` contains an empty string,
the expression returns another empty string.

No exception is raised.

The existing SQLite year column is defined as
`VARCHAR(80) NOT NULL`.

SQLite's NOT NULL constraint does not reject
empty strings.

The legacy application does not explicitly
validate whether the release year contains
meaningful information.

**Conclusion:** The application accepts and stores
an empty release year without validation.

**Root cause status:** Verified.

#### Target design considerations

**Requirement:** The modernized application must
handle empty TMDB release dates explicitly.

**Reason:** An empty string does not represent
a meaningful movie release year.

The application should normalize or validate
release-date information before database insertion.

**Pending design decision:** Determine whether
movies without known release dates should be
allowed with an unknown year or rejected with
a helpful message.

This decision should be consistent with D-S05.

#### Test isolation and cleanup

The test used Flask's test client against an
isolated temporary database.

TMDB details were mocked using
`unittest.mock.patch`.

No real TMDB network request occurred.

The temporary database was restored from the
original ten-movie database.

SHA-256 hashes confirmed successful restoration
and that the original database remained unchanged.

#### Future tests (proposed)

- `test_select_empty_release_date_handled_gracefully`
- `test_select_empty_release_date_validation`
- `test_select_does_not_store_empty_year`

**Source:** `main.py`, `/select` route,
lines 103-122; Movie model, lines 34-43.

**Verification status:** Complete for the
empty-string release-date scenario.

- HTTP 302 confirmed.
- Movie insertion independently verified.
- Empty year stored in SQLite.
- Movie count increased from 10 to 11.
- Redirect to editing page confirmed.
- Temporary database restored successfully.
- Original database verified unchanged.

**Pending verification:** Behavior when the
`release_date` key contains a null value.

### GET `/select` - Null TMDB release date

**Defect ID:** D-S07 - Null release date stored as literal text.

#### Test input and results

- **Request:** GET `/select?id=987654`
- **TMDB response:** Mocked movie details.
- **Movie title:** Null Release Date Audit Film.
- **Release date key present:** True.
- **Release date value:** Python `None`.
- **Observed HTTP status:** 302.
- **Mock TMDB call:** `call('987654')`.
- **Movie count:** 10 → 11.
- **Test movie inserted:** True.
- **New movie ID:** 16.
- **Stored year:** `'None'`.
- **Stored year type:** `str`.
- **Redirect:** `/edit?id=16`.
- **Internal Server Error:** False.
- **Temporary database restored:** True.
- **Original database unchanged:** True.

#### Observed behavior

The legacy Flask application received mocked
TMDB movie details containing a null release date.

The `release_date` key existed, but its value
was Python `None`.

The `/select` route processed this value without
raising an exception.

The application inserted a new Movie record.

The database stored the literal string `'None'`
in the year column.

Flask returned HTTP 302 and redirected to the
editing page for the newly inserted movie.

#### Reproduction steps

1. Use an isolated copy of the original database.
2. Mock `movie_detail_request()` to return
   movie details containing `"release_date": None`.
3. Request GET `/select?id=987654`.
4. Observe HTTP 302.
5. Confirm the movie count increases from 10 to 11.
6. Query the inserted movie.
7. Verify that the stored year is the string `'None'`.
8. Confirm the redirect to `/edit?id=16`.
9. Restore the temporary database.
10. Verify SHA-256 database file hashes.

#### Verified root cause

The `/select` route extracts the release year using:

`str(m_dict['release_date'])[0:4]`

When `release_date` contains Python `None`,
the `str()` conversion produces the string `'None'`.

Slicing the first four characters preserves
the entire string.

The Movie model stores the result in a string column.

The database therefore accepts the value even
though it does not represent a valid release year.

The legacy application does not validate or
normalize null release-date information.

**Conclusion:** The application converts a null
release date into the literal string `'None'`
and persists that string in the database.

**Root cause status:** Verified.

#### Target design considerations

**Requirement:** The modernized application must
handle null TMDB release dates explicitly.

**Reason:** The literal string `'None'` is not
a meaningful release year.

Missing, empty, and null release dates should
follow a consistent validation or normalization policy.

The application must not store placeholder strings
such as `'None'` as release years.

**Pending design decision:** Determine whether
movies with unknown release years should be
accepted using an appropriate representation
or rejected with a helpful message.

This decision must remain consistent with
D-S05 and D-S06.

#### Test isolation and cleanup

The test used Flask's test client against
an isolated temporary database.

TMDB movie details were mocked using
`unittest.mock.patch`.

No real TMDB network request occurred.

The temporary database was restored from
the original ten-movie database.

SHA-256 hashes confirmed successful restoration.

The original database remained unchanged.

#### Future tests (proposed)

- `test_select_null_release_date_handled_gracefully`
- `test_select_null_release_date_normalized`
- `test_select_does_not_store_none_as_year`

**Source:** `main.py`, `/select` route,
lines 103-122; Movie model, lines 34-43.

**Verification status:** Complete for the
null release-date scenario.

- HTTP 302 confirmed.
- Movie insertion independently verified.
- Literal string `'None'` stored in SQLite.
- Stored year type confirmed as `str`.
- Movie count increased from 10 to 11.
- Redirect to editing page confirmed.
- Temporary database restored successfully.
- Original database verified unchanged.

**Future remediation:** Normalize or validate
null release dates before database insertion.

### GET `/select` - Missing TMDB poster path

**Defect ID:** D-S08 - Missing poster information causes HTTP 500.

#### Test input and results

- **Request:** GET `/select?id=987654`
- **TMDB response:** Mocked movie details.
- **Movie title:** Missing Poster Audit Film.
- **Poster path field:** Omitted entirely.
- **Poster key present:** False.
- **Observed HTTP status:** 500.
- **Mock TMDB call:** `call('987654')`.
- **Movie count:** 10 → 10.
- **Test movie inserted:** False.
- **Redirect:** None.
- **Response:** Internal Server Error.
- **Temporary database restored:** True.
- **Original database unchanged:** True.

#### Observed behavior

The legacy Flask application received mocked
TMDB movie details without a `poster_path` field.

The `/select` route attempted to process the
incomplete movie details.

Flask returned HTTP 500.

No new Movie record was inserted.

The movie count remained unchanged at 10.

The application did not redirect to the editing page.

#### Reproduction steps

1. Use an isolated copy of the original ten-movie database.
2. Mock `movie_detail_request()` to return movie
   details without the `poster_path` key.
3. Request GET `/select?id=987654`.
4. Observe HTTP 500.
5. Confirm that no new movie record was inserted.
6. Confirm the movie count remains 10.
7. Restore the temporary database.
8. Verify SHA-256 database file hashes.

#### Verified root cause

The `/select` route constructs a poster URL using
the `poster_path` field from the TMDB response.

The route accesses this value using direct
dictionary key access:

`m_dict['poster_path']`

When the mocked TMDB response omitted the
`poster_path` key, Python raised a `KeyError`.

The exception was independently captured using
Flask's test client with exception propagation enabled.

**Captured Python exception:** `KeyError`.

**Exception message:** `'poster_path'`.

**Exception arguments:** `('poster_path',)`.

**Missing key verified:** True.

The legacy application does not validate the
TMDB response before accessing poster information.

The exception is not handled by the `/select`
route, producing the HTTP 500 observed in Step 85.

**Conclusion:** Missing TMDB poster information
causes an unhandled Python `KeyError`.

The application defect is its failure to validate
or gracefully handle incomplete external movie data.

**Root cause status:** Verified.

#### Target design considerations

**Requirement:** The modernized application must
handle missing TMDB poster information gracefully.

**Reason:** A movie should not necessarily require
poster artwork to be added to the user's collection.

Missing poster information should not cause an
unhandled HTTP 500 error.

The application should validate or normalize
external movie data before database insertion.

**Proposed behavior:** Allow movies without poster
artwork and display a default placeholder image.

**Pending design decision:** Confirm whether
placeholder artwork should be used when TMDB
does not provide a poster.

#### Test isolation and cleanup

The test used Flask's test client against
an isolated temporary database.

TMDB movie details were mocked using
`unittest.mock.patch`.

No real TMDB network request occurred.

The temporary database was restored from the
original ten-movie database.

SHA-256 file hashes confirmed successful restoration.

The original database remained unchanged.

#### Future tests (proposed)

- `test_select_missing_poster_handled_gracefully`
- `test_select_missing_poster_keyerror`
- `test_select_missing_poster_uses_placeholder`

**Source:** `main.py`, `/select` route,
lines 103-122; `movie_detail_request()`.

**Verification status:** Complete for the
missing-poster-key scenario.

- Missing `poster_path` independently reproduced.
- HTTP 500 confirmed using Flask's test client.
- Python `KeyError` independently captured.
- Missing key confirmed as `poster_path`.
- Exception arguments verified as `('poster_path',)`.
- Mock TMDB call verified: `call('987654')`.
- Movie count remained unchanged at 10.
- No test movie was inserted.
- No redirect occurred in the HTTP 500 test.
- Temporary database restored successfully.
- Original database verified unchanged using
  SHA-256 file hashes.

**Root cause status:** Verified.

**Verification update:** Empty poster-path behavior
has been independently confirmed under D-S10.

**Verification update:** Null poster-path behavior
has been independently confirmed under D-S09.

**Future remediation:** Validate or normalize
missing poster information before constructing
poster URLs or inserting movie records.

### GET `/select` - Null TMDB poster path

**Defect ID:** D-S09 - Null poster path produces
an invalid poster URL.

#### Test input and results

- **Request:** GET `/select?id=987654`
- **TMDB response:** Mocked movie details.
- **Movie title:** Null Poster Audit Film.
- **Poster path key present:** True.
- **Poster path value:** Python `None`.
- **Observed HTTP status:** 302.
- **Mock TMDB call:** `call('987654')`.
- **Movie count:** 10 → 11.
- **Test movie inserted:** True.
- **New movie ID:** 16.
- **Stored poster URL:** `https://image.tmdb.org/t/p/w500/None`.
- **Stored poster URL type:** `str`.
- **URL ends with `/None`:** True.
- **Redirect:** `/edit?id=16`.
- **Internal Server Error:** False.
- **Temporary database restored:** True.
- **Original database unchanged:** True.

#### Observed behavior

The legacy Flask application received mocked
TMDB movie details containing a null poster path.

The `poster_path` key existed, but its value
was Python `None`.

The `/select` route processed the response
without raising an exception.

The application constructed a poster URL by
converting the null value into the literal
string `None`.

The database stored:

`https://image.tmdb.org/t/p/w500/None`

The application inserted the movie successfully.

Flask returned HTTP 302 and redirected to
the newly created movie's editing page.

The test did not independently request the
generated image URL.

#### Reproduction steps

1. Use an isolated copy of the original database.
2. Mock `movie_detail_request()` to return
   movie details containing `"poster_path": None`.
3. Request GET `/select?id=987654`.
4. Observe HTTP 302.
5. Confirm the movie count increases from 10 to 11.
6. Query the inserted movie.
7. Confirm the stored poster URL ends with `/None`.
8. Confirm the redirect to `/edit?id=16`.
9. Restore the temporary database.
10. Verify SHA-256 database file hashes.

#### Verified root cause

The `/select` route constructs the poster URL using:

`f"{MOVIE_POSTER_SITE_URL}/{m_dict['poster_path']}"`

When `poster_path` contains Python `None`,
the formatted string converts that value into
the literal text `None`.

The resulting URL ends with `/None`.

The legacy application does not validate
or normalize null poster-path information.

The Movie model accepts the generated URL
as a string.

**Conclusion:** Null TMDB poster information
is converted into an inappropriate poster URL
and stored without validation.

**Root cause status:** Verified.

#### Target design considerations

**Requirement:** The modernized application
must handle null TMDB poster paths gracefully.

**Reason:** Missing poster artwork should not
produce an invalid or misleading image URL.

The application should normalize missing
poster information before database insertion.

**Proposed behavior:** Allow movies without
poster artwork and display a default placeholder.

**Pending design decision:** Confirm the
placeholder-image strategy during the FastAPI
design phase.

This decision should remain consistent with D-S08.

#### Test isolation and cleanup

The test used Flask's test client against
an isolated temporary database.

TMDB movie details were mocked using
`unittest.mock.patch`.

No real TMDB network request occurred.

The temporary database was restored from
the original ten-movie database.

SHA-256 file hashes confirmed successful restoration.

The original database remained unchanged.

#### Future tests (proposed)

- `test_select_null_poster_handled_gracefully`
- `test_select_null_poster_uses_placeholder`
- `test_select_does_not_store_none_poster_url`

**Source:** `main.py`, `/select` route,
lines 103-122; Movie model, lines 34-43.

**Verification status:** Complete for the
null poster-path scenario.

- HTTP 302 confirmed.
- Movie insertion independently verified.
- URL ending in `/None` stored in SQLite.
- Stored URL type confirmed as `str`.
- Movie count increased from 10 to 11.
- Redirect to editing page confirmed.
- Temporary database restored successfully.
- Original database verified unchanged.

**Verification update:** Empty poster-path behavior
has been independently confirmed under D-S10.

**Future remediation:** Normalize missing
poster information and use appropriate
placeholder artwork.

### GET `/select` - Empty TMDB poster path

**Defect ID:** D-S10 - Empty poster path produces
a URL without a poster filename.

#### Test input and results

- **Request:** GET `/select?id=987654`
- **TMDB response:** Mocked movie details.
- **Movie title:** Empty Poster Audit Film.
- **Poster path key present:** True.
- **Poster path value:** Empty string (`''`).
- **Observed HTTP status:** 302.
- **Mock TMDB call:** `call('987654')`.
- **Movie count:** 10 → 11.
- **Test movie inserted:** True.
- **New movie ID:** 16.
- **Stored poster URL:** `https://image.tmdb.org/t/p/w500/`.
- **Stored poster URL type:** `str`.
- **URL ends with `/`:** True.
- **Redirect:** `/edit?id=16`.
- **Internal Server Error:** False.
- **Temporary database restored:** True.
- **Original database unchanged:** True.

#### Observed behavior

The legacy Flask application received mocked
TMDB movie details containing an empty poster path.

The `poster_path` key existed, but its value
was an empty string.

The `/select` route processed the response
without raising an exception.

The application constructed and stored:

`https://image.tmdb.org/t/p/w500/`

The generated URL contained no poster filename.

The movie was inserted successfully.

Flask returned HTTP 302 and redirected to
the newly created movie's editing page.

The test did not independently request the
generated image URL.

#### Reproduction steps

1. Use an isolated copy of the original database.
2. Mock `movie_detail_request()` to return
   movie details containing `"poster_path": ""`.
3. Request GET `/select?id=987654`.
4. Observe HTTP 302.
5. Confirm the movie count increases from 10 to 11.
6. Query the inserted movie.
7. Verify the stored poster URL is
   `https://image.tmdb.org/t/p/w500/`.
8. Confirm the redirect to `/edit?id=16`.
9. Restore the temporary database.
10. Verify SHA-256 database file hashes.

#### Verified root cause

The `/select` route constructs the poster URL using:

`f"{MOVIE_POSTER_SITE_URL}/{m_dict['poster_path']}"`

When `poster_path` contains an empty string,
the formatted string appends no poster filename.

The resulting URL is:

`https://image.tmdb.org/t/p/w500/`

The legacy application does not validate
or normalize empty poster-path information.

The Movie model accepts the resulting URL
as a string.

**Conclusion:** Empty TMDB poster information
produces a URL without a poster filename,
which is stored without validation.

**Root cause status:** Verified.

#### Target design considerations

**Requirement:** The modernized application
must handle empty TMDB poster paths gracefully.

**Reason:** Missing poster artwork should not
produce a URL without a poster filename.

The application should normalize missing or
empty poster information before database insertion.

**Proposed behavior:** Allow movies without
poster artwork and display a default placeholder.

**Pending design decision:** Confirm the
placeholder-image strategy during the FastAPI
design phase.

This decision should remain consistent
with D-S08 and D-S09.

#### Test isolation and cleanup

The test used Flask's test client against
an isolated temporary database.

TMDB movie details were mocked using
`unittest.mock.patch`.

No real TMDB network request occurred.

The temporary database was restored from
the original ten-movie database.

SHA-256 file hashes confirmed successful restoration.

The original database remained unchanged.

#### Future tests (proposed)

- `test_select_empty_poster_handled_gracefully`
- `test_select_empty_poster_uses_placeholder`
- `test_select_does_not_store_empty_poster_url`

**Source:** `main.py`, `/select` route,
lines 103-122; Movie model, lines 34-43.

**Verification status:** Complete for the
empty poster-path scenario.

- Empty `poster_path` independently reproduced.
- HTTP 302 confirmed.
- Movie insertion independently verified.
- URL without a poster filename stored in SQLite.
- Stored URL type confirmed as `str`.
- Movie count increased from 10 to 11.
- Redirect to editing page confirmed.
- Temporary database restored successfully.
- Original database verified unchanged.

**Root cause status:** Verified.

**Future remediation:** Normalize empty
poster information and use appropriate
placeholder artwork.

### GET `/select` - Missing TMDB overview

**Defect ID:** D-S11 - Missing overview causes
an unhandled Python KeyError.

#### Test input and results

- **Request:** GET `/select?id=987654`
- **TMDB response:** Mocked movie details.
- **Movie title:** Missing Overview Audit Film.
- **Overview field:** Omitted entirely.
- **Overview key present:** False.
- **Mock TMDB call:** `call('987654')`.
- **HTTP status:** None (exception propagation enabled).
- **Movie count:** 10 → 10.
- **Test movie inserted:** False.
- **Exception type:** `KeyError`.
- **Exception message:** `'overview'`.
- **Exception arguments:** `('overview',)`.
- **KeyError captured:** True.
- **Missing overview key verified:** True.
- **Temporary database restored:** True.
- **Original database unchanged:** True.

#### Observed behavior

The legacy Flask application received mocked
TMDB movie details without an `overview` field.

The `/select` route attempted to process the
incomplete response.

With Flask exception propagation enabled,
Python raised `KeyError('overview')`.

The test client propagated the exception
instead of returning an HTTP response.

No movie record was inserted.

The movie count remained unchanged at 10.

#### Reproduction steps

1. Use an isolated copy of the original database.
2. Mock `movie_detail_request()` to return
   movie details without the `overview` key.
3. Enable Flask exception propagation.
4. Request GET `/select?id=987654`.
5. Capture the Python exception.
6. Verify `KeyError('overview')`.
7. Confirm the movie count remains 10.
8. Confirm no test movie was inserted.
9. Restore the temporary database.
10. Verify SHA-256 database file hashes.

#### Verified root cause

The `/select` route accesses the TMDB
movie overview using direct dictionary key access:

`m_dict['overview']`

When the `overview` key is missing,
Python raises a `KeyError`.

The exception was independently captured
using Flask's test client with exception
propagation enabled.

**Captured Python exception:** `KeyError`.

**Exception message:** `'overview'`.

**Exception arguments:** `('overview',)`.

The legacy application does not validate
the TMDB response before accessing
the movie description.

**Conclusion:** Missing TMDB overview information
causes an unhandled Python `KeyError`.

**Root cause status:** Verified.

#### Target design considerations

**Requirement:** The modernized application
must handle missing TMDB overview information
without raising an unhandled exception.

**Reason:** A movie may lack a description
even when other movie details are available.

The application should validate or normalize
external movie information before insertion.

**Proposed behavior:** Permit movies without
an overview and display an appropriate
fallback description.

**Pending design decision:** Determine whether
a missing overview should be represented as
an empty value, a nullable field, or a
user-friendly placeholder.

#### Test isolation and cleanup

The test used Flask's test client against
an isolated temporary database.

TMDB details were mocked using
`unittest.mock.patch`.

No real TMDB network request occurred.

The temporary database was restored from
the original ten-movie database.

SHA-256 hashes confirmed successful restoration
and that the original database remained unchanged.

#### Future tests (proposed)

- `test_select_missing_overview_handled_gracefully`
- `test_select_missing_overview_keyerror`
- `test_select_missing_overview_uses_fallback`

**Source:** `main.py`, `/select` route,
lines 103-122; Movie model, lines 34-43.

**Verification status:** Complete for the
missing-overview exception scenario.

- Missing `overview` independently reproduced.
- Python `KeyError` independently captured.
- Exception arguments confirmed as `('overview',)`.
- Mock TMDB call verified.
- Movie count remained unchanged at 10.
- No test movie was inserted.
- Temporary database restored successfully.
- Original database verified unchanged.

**Pending verification:** HTTP response with
exception propagation disabled.

**Verification update:** Null overview behavior
has been independently confirmed under D-S13.

**Future remediation:** Validate or normalize
missing overview information before database insertion.

### GET `/select` - Empty TMDB overview

**Defect ID:** D-S12 - Empty overview accepted without validation.

#### Test input and results

- **Request:** GET `/select?id=987654`
- **TMDB response:** Mocked movie details.
- **Movie title:** Empty Overview Audit Film.
- **Overview key present:** True.
- **Overview value:** Empty string (`''`).
- **Observed HTTP status:** 302.
- **Mock TMDB call:** `call('987654')`.
- **Movie count:** 10 → 11.
- **Test movie inserted:** True.
- **New movie ID:** 16.
- **Stored description:** Empty string (`''`).
- **Stored description type:** `str`.
- **Description is empty:** True.
- **Redirect:** `/edit?id=16`.
- **Internal Server Error:** False.
- **Temporary database restored:** True.
- **Original database unchanged:** True.

#### Observed behavior

The legacy Flask application received mocked
TMDB movie details containing an empty overview.

The `overview` key existed, but its value
was an empty string.

The `/select` route processed the response
without raising an exception.

The application inserted a new Movie record
with an empty string in the description column.

Flask returned HTTP 302 and redirected to
the newly created movie's editing page.

#### Reproduction steps

1. Use an isolated copy of the original database.
2. Mock `movie_detail_request()` to return
   movie details containing `"overview": ""`.
3. Request GET `/select?id=987654`.
4. Observe HTTP 302.
5. Confirm the movie count increases from 10 to 11.
6. Query the inserted movie.
7. Verify that its description is an empty string.
8. Confirm the redirect to `/edit?id=16`.
9. Restore the temporary database.
10. Verify SHA-256 database file hashes.

#### Verified root cause

The `/select` route accesses the overview using:

`m_dict['overview']`

When the key exists and contains an empty string,
dictionary access succeeds.

The Movie model stores the returned value
in its description column.

The existing SQLite description column is
defined as `VARCHAR(250) NOT NULL`.

SQLite's NOT NULL constraint rejects null values
but permits empty strings.

The legacy application does not explicitly
validate whether the overview contains
meaningful description text.

**Conclusion:** The application accepts and
stores an empty movie description without validation.

**Root cause status:** Verified.

#### Target design considerations

**Requirement:** The modernized application
must handle empty TMDB overview information
explicitly and consistently.

**Reason:** An empty string does not contain
meaningful movie description text.

The application should normalize or validate
external descriptions before database insertion.

**Proposed behavior:** Allow movies without
an overview and display an appropriate
fallback description.

**Pending design decision:** Determine whether
an empty overview should be stored as a nullable
value, an empty string, or a placeholder.

This decision should remain consistent with D-S11.

#### Test isolation and cleanup

The test used Flask's test client against
an isolated temporary database.

TMDB movie details were mocked using
`unittest.mock.patch`.

No real TMDB network request occurred.

The temporary database was restored from
the original ten-movie database.

SHA-256 hashes confirmed successful restoration.

The original database remained unchanged.

#### Future tests (proposed)

- `test_select_empty_overview_handled_gracefully`
- `test_select_empty_overview_uses_fallback`
- `test_select_empty_overview_normalized`

**Source:** `main.py`, `/select` route,
lines 103-122; Movie model, lines 34-43.

**Verification status:** Complete for the
empty-overview scenario.

- HTTP 302 confirmed.
- Movie insertion independently verified.
- Empty description stored in SQLite.
- Stored description type confirmed as `str`.
- Movie count increased from 10 to 11.
- Redirect to editing page confirmed.
- Temporary database restored successfully.
- Original database verified unchanged.

**Verification update:** Null overview behavior
has been independently confirmed under D-S13.

**Future remediation:** Normalize or validate
empty overview information before database insertion.

### GET `/select` - Null TMDB overview

**Defect ID:** D-S13 - Null overview causes a database integrity failure.

#### Test input and results

- **Request:** GET `/select?id=987654`
- **TMDB response:** Mocked movie details.
- **Movie title:** Null Overview Audit Film.
- **Overview key present:** True.
- **Overview value:** Python `None`.
- **HTTP status:** None (exception propagation enabled).
- **Mock TMDB call:** `call('987654')`.
- **Movie count:** 10 → 10.
- **Test movie inserted:** False.
- **Exception type:** SQLAlchemy `IntegrityError`.
- **Underlying exception:** SQLite `IntegrityError`.
- **Database error:** `NOT NULL constraint failed: movie.description`.
- **IntegrityError captured:** True.
- **NOT NULL constraint verified:** True.
- **Temporary database restored:** True.
- **Original database unchanged:** True.

#### Observed behavior

The legacy Flask application received mocked
TMDB movie details with `"overview": None`.

The `overview` key existed, so dictionary
access did not raise a `KeyError`.

The application attempted to insert a Movie
record containing a null description.

SQLite rejected the insertion because the
description column has a NOT NULL constraint.

With exception propagation enabled, Flask's
test client raised SQLAlchemy's `IntegrityError`
instead of returning an HTTP response.

The test explicitly rolled back the failed
database transaction before querying again.

No movie record was inserted.

The movie count remained unchanged at 10.

#### Reproduction steps

1. Use an isolated copy of the original database.
2. Mock `movie_detail_request()` to return
   movie details containing `"overview": None`.
3. Enable Flask exception propagation.
4. Request GET `/select?id=987654`.
5. Capture the SQLAlchemy exception.
6. Confirm the exception is `IntegrityError`.
7. Verify the underlying SQLite constraint error.
8. Roll back the failed database transaction.
9. Confirm the movie count remains 10.
10. Confirm no test movie was inserted.
11. Restore the temporary database.
12. Verify SHA-256 database file hashes.

#### Verified root cause

The `/select` route accesses the overview using:

`m_dict['overview']`

When the key exists with Python `None`,
dictionary access succeeds.

The application passes that null value into
the Movie model's description field.

The existing SQLite schema defines the
description column as:

`description VARCHAR(250) NOT NULL`

SQLite rejects the attempted insertion.

**Captured SQLAlchemy exception:** `IntegrityError`.

**Underlying SQLite exception:** `IntegrityError`.

**Database error message:**

`NOT NULL constraint failed: movie.description`

The database constraint correctly prevents
a null description from being persisted.

The legacy application does not validate
or normalize the overview before insertion.

It also does not gracefully handle the
resulting database integrity exception.

**Conclusion:** Null overview information
causes an unhandled database integrity error.

The defect is in the application's validation
and error handling, not in the database constraint.

**Root cause status:** Verified.

#### Target design considerations

**Requirement:** The modernized application
must handle null TMDB overview information
without raising an unhandled database exception.

**Reason:** External movie data may contain
missing or null descriptions.

The application should normalize or validate
optional movie descriptions before insertion.

**Proposed behavior:** Permit movies without
an overview and display a suitable fallback.

**Pending design decision:** Determine whether
unknown descriptions should be stored as NULL,
an empty string, or a placeholder.

The database schema and application validation
must support the chosen representation consistently.

This decision should remain consistent with
D-S11 and D-S12.

#### Test isolation and cleanup

The test used Flask's test client against
an isolated temporary database.

TMDB movie details were mocked using
`unittest.mock.patch`.

No real TMDB network request occurred.

Exception propagation was enabled to capture
the underlying SQLAlchemy error.

The failed database transaction was rolled back.

The temporary database was restored from
the original ten-movie database.

SHA-256 file hashes confirmed successful restoration.

The original database remained unchanged.

#### Future tests (proposed)

- `test_select_null_overview_handled_gracefully`
- `test_select_null_overview_normalized`
- `test_select_null_overview_does_not_raise_integrity_error`

**Source:** `main.py`, `/select` route,
lines 103-122; Movie model, lines 34-43;
SQLite `movie.description` NOT NULL constraint.

**Verification status:** Complete for the
null-overview exception scenario.

- Null `overview` independently reproduced.
- SQLAlchemy `IntegrityError` captured.
- Underlying SQLite `IntegrityError` confirmed.
- Exact NOT NULL constraint failure verified.
- Mock TMDB call verified.
- Movie count remained unchanged at 10.
- No test movie was inserted.
- Failed transaction rolled back.
- Temporary database restored successfully.
- Original database verified unchanged.


#### Additional verification - HTTP 500 response

A second isolated test independently verified
the HTTP response when Flask exception
propagation was disabled.

**Test:** GET `/select?id=987654`

**TMDB overview value:** Python `None`.

**Flask configuration:**
- `TESTING`: False.
- `PROPAGATE_EXCEPTIONS`: False.

**Observed results:**

- **HTTP status:** 500.
- **Response:** Internal Server Error.
- **Mock TMDB call:** `call('987654')`.
- **Movie count:** 10 → 10.
- **Test movie inserted:** False.
- **Redirect:** None.
- **Internal Server Error:** True.
- **Temporary database restored:** True.
- **Original database unchanged:** True.

The legacy application attempted to insert
a movie with a null description.

SQLite rejected the insertion because
`movie.description` has a NOT NULL constraint.

With exception propagation disabled,
Flask returned HTTP 500.

The movie count remained unchanged and
no test movie was inserted.

The temporary database was restored from
the original ten-movie database.

SHA-256 file hashes independently confirmed
successful restoration and that the original
database remained unchanged.

**Verification status:** Complete.

**Root cause status:** Verified.

**Conclusion:** D-S13 has been independently
verified at both the database exception
level and the HTTP response level.

**Future remediation:** Normalize or validate
null overview information before attempting
database insertion and handle database errors
gracefully.

## 2. Data Snapshot

### Database location and structure

**Database engine:** SQLite

**Database file:** `instance/top-ten-movies.db`

**Inspection method:** Python `sqlite3` using a read-only connection and SQLite `PRAGMA table_info`.

**Application tables:** 1

**Table name:** `movie`

**Column count:** 8

**Row count:** 10

#### Existing database schema

| Column | SQLite type | NOT NULL | Primary key |
|---|---|---|---|
| id | INTEGER | Yes | Yes |
| title | VARCHAR(120) | Yes | No |
| year | VARCHAR(80) | Yes | No |
| description | VARCHAR(250) | Yes | No |
| rating | FLOAT | No | No |
| ranking | INTEGER | No | No |
| review | VARCHAR(250) | No | No |
| img_url | VARCHAR(80) | No | No |

#### Observations

- The database contains one application table named `movie`.
- The table contains 10 movie records.
- The `id` column is the primary key.
- The `title`, `year`, and `description` columns cannot contain NULL.
- The `rating`, `ranking`, `review`, and `img_url` columns permit NULL.
- SQLite does not normally enforce the declared character lengths of VARCHAR columns.
- Column uniqueness constraints require separate inspection because `PRAGMA table_info` does not report them.

**Source:** Read-only inspection of `instance/top-ten-movies.db`.

**Verification status:** Database location, table structure, and row count confirmed.

### Existing movie data

#### Data inspection summary

**Database:** `instance/top-ten-movies.db`

**Inspection method:** Python `sqlite3` using a read-only connection.

**Total movie records:** 10

**Descriptions exceeding 250 characters:** 6

**Longest description:** 449 characters.

**Distinct non-NULL stored ranking values:** `[10]`

#### Observations

- The database contains 10 movie records.
- Six descriptions exceed the declared `VARCHAR(250)` length.
- The longest description contains 449 characters.
- All ten records have a stored ranking of 10; no rankings are NULL.
- The legacy application calculates displayed rankings
  from movie ratings rather than using the stored ranking column.
- SQLite does not enforce the declared VARCHAR length limits.

#### Complete ten-row movie inventory

The following records were independently inspected using
Python's sqlite3 library with a read-only connection.

Field lengths are measured using SQLite's LENGTH() function.

| ID | Movie | Year | Rating | Stored ranking |
|---|---|---|---|---|
| 2 | The Matrix | 1999 | 9.2 | 10 |
| 4 | The Cannonball Run | 1981 | 6.7 | 10 |
| 6 | Raiders of the Lost Ark | 1981 | 8.8 | 10 |
| 7 | 기생충 | 2019 | 9.8 | 10 |
| 8 | The Avengers | 2012 | 9.0 | 10 |
| 11 | Elf | 2003 | 8.7 | 10 |
| 12 | The Sixth Sense | 1999 | 9.9 | 10 |
| 13 | Knives Out | 2019 | 9.1 | 10 |
| 14 | The Shawshank Redemption | 1994 | 9.5 | 10 |
| 15 | Short Circuit | 1986 | 7.6 | 10 |

#### Individual field lengths

All lengths are in characters.

| ID | Title | Year | Description | Review | img_url |
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

#### Ranking verification

- Total movie records: 10.
- Every stored ranking equals 10.
- NULL ranking count: 0.
- The stored ranking column does not represent the displayed order.
- The legacy application calculates displayed ranks from ratings.

#### Description length verification

Six descriptions exceed 250 characters:

- The Cannonball Run: 449.
- The Avengers: 297.
- Elf: 322.
- Knives Out: 369.
- The Shawshank Redemption: 388.
- Short Circuit: 349.

**Maximum description length:** 449 characters.

**Verification status:** Complete ten-row data inventory
independently confirmed using read-only SQLite queries.

**Future test (proposed):**
- `test_migration_preserves_original_movie_data`

#### Reviewer discrepancy

The reviewer previously reported four descriptions exceeding
250 characters.

Our current read-only inspection found six.

This discrepancy remains to be reconciled against the individual
movie records and the reviewer's database snapshot.

#### Migration considerations

- Preserve all movie descriptions without truncation.
- Select a suitable database column type for longer descriptions.
- Review whether the stored ranking column should be removed.
- Preserve the existing movie records during migration.
- Verify all field lengths before defining the new schema.

**Verification status:** Summary independently confirmed
through read-only inspection of the original SQLite database.

**Verification status:** Complete ten-row inventory and NULL ranking checks verified. Reviewer discrepancy remains open.

## 3. Legacy Defects


### Verified defect register

This register summarizes defects identified during
the legacy Flask behavior audit.

Detailed reproduction steps, observed results,
root-cause evidence, and database integrity checks
are documented in Section 1, Route Walk.

The register distinguishes observed legacy defects
from proposed behavior for the FastAPI rebuild.

#### Rating validation defects

| ID | Defect | Observed behavior |
|---|---|---|
| D-R01 | Missing upper rating boundary | Rating 11 accepted and saved |
| D-R02 | Missing lower rating boundary | Ratings -2 and 0.5 accepted and saved |

#### TMDB search defects

| ID | Defect | Observed behavior |
|---|---|---|
| D-T01 | Unhandled TMDB search failure | Simulated TMDB HTTPError produces HTTP 500 |

#### Movie selection defects

| ID | Defect | Observed behavior |
|---|---|---|
| D-S01 | Missing movie ID | ID becomes None; simulated TMDB failure produces HTTP 500 |
| D-S02 | Non-numeric movie ID | Invalid ID forwarded to TMDB; simulated failure produces HTTP 500 |
| D-S03 | Unknown numeric movie ID | Simulated TMDB 404 produces HTTP 500 |
| D-S04 | Duplicate movie selection | SQLite uniqueness violation produces HTTP 500 |
| D-S05 | Missing release date | Unhandled KeyError and HTTP 500 |
| D-S06 | Empty release date | Empty release year saved |
| D-S07 | Null release date | Literal string 'None' saved as year |
| D-S08 | Missing poster path | Unhandled KeyError and HTTP 500 |
| D-S09 | Null poster path | Poster URL ending in /None saved |
| D-S10 | Empty poster path | Poster URL without filename saved |
| D-S11 | Missing overview | Unhandled KeyError |
| D-S12 | Empty overview | Empty description saved |
| D-S13 | Null overview | SQLite IntegrityError and HTTP 500 |

### Defect evidence limitations

The verified defect register summarizes
multiple forms of legacy test evidence.

An independently captured Python or
SQLAlchemy exception is not automatically
equivalent to an independently measured
HTTP response.

**D-S11 - Missing overview**

The test independently captured
`KeyError('overview')` with Flask exception
propagation enabled.

An HTTP response with exception
propagation disabled was not independently
measured for this scenario.

The defect remains verified at the
exception level.

**D-S13 - Null overview**

Both the database `IntegrityError` and
the HTTP 500 response were independently
verified in separate isolated tests.

**D-S01 through D-S03 - TMDB ID errors**

The HTTP 500 responses were observed
using mocked TMDB HTTP failures.

These tests do not establish how the
live TMDB service would respond to
the tested identifiers.

Severity and priority assignments
remain preliminary recommendations.

Reviewers should use the detailed
scenario evidence in Section 1 when
assessing test coverage and limitations.

### Additional legacy concerns

The following concerns are documented in the
Route Walk but do not yet have dedicated defect IDs.

- Movie deletion uses HTTP GET.
- Movie insertion uses HTTP GET.
- The homepage does not enforce a ten-movie limit.
- Stored ranking values do not reflect displayed order.
- No explicit ranking tie-breaker is implemented.
- Missing or invalid Delete-route IDs produce HTTP 500.
- The Edit GET route does not validate movie IDs.
- The Edit page displays a hardcoded Movie Title heading.
- Empty TMDB search results lack helpful user feedback.
- SQLite permits descriptions longer than the
  declared VARCHAR(250) length.

These concerns require classification during
the modernization design and prioritization phase.

### Verification and remediation principles

- Preserve confirmed legacy behavior unless a
  documented design decision intentionally changes it.
- Do not preserve known defects merely for compatibility.
- Validate external TMDB data before database insertion.
- Validate movie IDs and user input on the server.
- Handle external service failures gracefully.
- Preserve database uniqueness and integrity constraints.
- Prefer safe HTTP methods for state-changing operations.
- Preserve the original ten movie records during migration.
- Convert verified defects into automated regression tests.
- Keep proposed remediation separate from observed behavior.

### Register status

**Verified defect IDs documented:** 16.

**Rating defects:** 2.

**TMDB search defects:** 1.

**Movie selection defects:** 13.

**Source:** Section 1, Route Walk, including
the independently verified Flask test results.

**Status:** Initial legacy defect register completed.

**Documentation update:** Severity classifications
and remediation priorities are now recorded
for all 16 verified defect IDs.

The six target design decision registers
are also documented in Section 4.

**Reviewer approval:** Pending.

**Remediation implementation:** Not started.

### Defect severity and remediation priority

The classifications below are preliminary
recommendations for reviewer consideration.

Severity describes the impact of a defect.
Priority describes the recommended order
for addressing it during modernization.

#### Severity definitions

| Severity | Meaning |
|---|---|
| Critical | Causes major data loss, security exposure, or complete application failure |
| High | Blocks an important workflow or produces unhandled server errors |
| Medium | Permits invalid data or causes significant incorrect behavior |
| Low | Causes minor usability or presentation problems |

#### Remediation priority definitions

| Priority | Meaning |
|---|---|
| P1 | Address before considering the affected workflow ready |
| P2 | Address during the initial modernization implementation |
| P3 | Address after core functionality and higher-risk defects |

Priority assignments consider severity,
frequency, data integrity, dependencies,
and the feasibility of safe remediation.

#### Initial severity and priority register

| Defect ID | Severity | Priority | Rationale |
|---|---|---|---|
| D-R01 | Medium | P1 | Rating 11 violates the required upper boundary and is saved |
| D-R02 | Medium | P1 | Ratings below 1 are accepted and saved |
| D-T01 | High | P1 | TMDB search failure produces an unhandled HTTP 500 |
| D-S01 | High | P1 | Missing TMDB ID is forwarded to the service and leads to HTTP 500 |
| D-S02 | High | P1 | Non-numeric TMDB ID is forwarded without validation and leads to HTTP 500 |
| D-S03 | High | P1 | A simulated TMDB movie-not-found response produces HTTP 500 |
| D-S04 | High | P1 | Duplicate movie selection triggers an unhandled database integrity error and HTTP 500 |
| D-S05 | High | P1 | Missing TMDB release_date raises an unhandled KeyError and produces HTTP 500 |
| D-S06 | Medium | P2 | Empty TMDB release_date is accepted and saved as an empty year |
| D-S07 | Medium | P2 | Null TMDB release_date is converted to the literal string 'None' and saved |
| D-S08 | High | P1 | Missing TMDB poster_path raises an unhandled KeyError and produces HTTP 500 |
| D-S09 | Medium | P2 | Null TMDB poster_path produces and saves a poster URL ending in /None |
| D-S10 | Medium | P2 | Empty TMDB poster_path produces and saves a URL without a poster filename |
| D-S11 | High | P1 | Missing TMDB overview raises an unhandled KeyError and prevents insertion |
| D-S12 | Medium | P2 | Empty TMDB overview is accepted and saved as an empty description |
| D-S13 | High | P1 | Null TMDB overview causes an unhandled database IntegrityError and HTTP 500 |

#### Classification notes

**D-R01 and D-R02**

These defects permit invalid application data
but did not produce unhandled exceptions in
the verified scenarios.

They are rated Medium severity.

P1 is recommended because rating validation
is a basic correctness requirement and must
be enforced before the editing workflow
is considered ready.

**D-T01**

A simulated TMDB service failure causes
the movie-search workflow to return HTTP 500.

This is rated High severity because the
application fails to handle a dependency
error gracefully.

P1 is recommended because an unavailable
external service should not cause an
unhandled application failure.

**D-S01 through D-S04**

These four defects affect the movie-selection
and insertion workflow.

Missing, malformed, and unknown TMDB IDs
can lead to unhandled HTTP 500 responses.

Duplicate selection also produces HTTP 500
when SQLite rejects an existing movie title.

High severity is recommended because these
failures interrupt an important workflow.

P1 is recommended for server-side ID
validation, controlled TMDB errors,
and graceful duplicate handling.

The database uniqueness constraint must
remain effective.

These ratings are preliminary and require
reviewer approval.

**D-S05 through D-S07**

These three defects concern missing or invalid
TMDB release-date information.

D-S05 is rated High because a missing
release_date field raises an unhandled
KeyError and prevents movie insertion.

P1 is recommended to ensure incomplete
TMDB responses cannot crash the workflow.

D-S06 and D-S07 are rated Medium because
they allow invalid year values to be saved
without causing an immediate server error.

P2 is recommended for consistent release-date
normalization during initial modernization.

The policy for unknown release years
remains an open design decision under
TD-T03 and TD-D05.

The classifications require reviewer approval.

**D-S08 through D-S10**

These three defects concern missing or
invalid TMDB poster-path information.

D-S08 is rated High because a missing
poster_path field raises an unhandled
KeyError and prevents movie insertion.

P1 is recommended to prevent missing
optional artwork from crashing the workflow.

D-S09 and D-S10 are rated Medium because
they allow inappropriate poster URLs to be
saved without an immediate server error.

P2 is recommended for consistent poster-path
normalization during initial modernization.

Displaying placeholder artwork remains
a proposed design choice under TD-T04
and TD-U04.

These classifications require reviewer approval.

**D-S11 through D-S13**

These three defects concern missing,
empty, or null TMDB overview information.

D-S11 is rated High because a missing
overview key raises an unhandled KeyError
and prevents movie insertion.

The Python exception was independently
verified. An HTTP response was not
independently measured for this scenario.

D-S12 is rated Medium because an empty
overview is saved as an empty description.

D-S13 is rated High because a null
overview violates the SQLite NOT NULL
constraint and produces HTTP 500.

P1 is recommended for D-S11 and D-S13
to eliminate unhandled application
and database exceptions.

P2 is recommended for D-S12 to normalize
empty descriptions consistently.

The storage representation and user-facing
fallback for missing descriptions remain
proposed or open under TD-T05 and TD-D05.

These classifications require reviewer approval.

#### Classification status

**Verified defect IDs:** 16.

**Defects classified so far:** 16.

**Remaining to classify:** 0.

**Critical:** 0.

**High:** 9.

**Medium:** 7.

**Low:** 0.

**Reviewer approval:** Pending.

**Remediation implementation:** Not started.

**Next:** Consolidated severity and
remediation priority review.

#### Consolidated defect severity summary

All 16 verified legacy defect IDs now have
preliminary severity and priority assignments.

These classifications are recommendations
and require reviewer approval.

| Severity | Defect count |
|---|---:|
| Critical | 0 |
| High | 9 |
| Medium | 7 |
| Low | 0 |
| **Total** | **16** |

#### Consolidated remediation priority summary

| Priority | Defect count |
|---|---:|
| P1 | 11 |
| P2 | 5 |
| P3 | 0 |
| **Total** | **16** |

#### Recommended remediation sequence

**First - P1 correctness and error handling**

Address rating-boundary validation,
TMDB request failures, malformed IDs,
unknown movies, and duplicate selection.

Prevent missing release dates, poster paths,
and overviews from raising unhandled errors.

Handle null descriptions without unhandled
database integrity exceptions.

**Second - P2 external data normalization**

Define and implement consistent handling
for empty and null release dates,
poster paths, and movie overviews.

Ensure database values and user-facing
fallbacks follow approved design decisions.

**Third - Additional legacy concerns**

Review the documented concerns that do
not yet have dedicated defect IDs.

These include unsafe GET operations,
invalid local movie IDs, ranking behavior,
and presentation improvements.

Do not treat those concerns as already
classified within the 16-defect register.

#### Reviewer acceptance requirements

- Confirm or revise all severity ratings.
- Confirm or revise all remediation priorities.
- Approve handling of incomplete TMDB data.
- Resolve or defer dependent design questions.
- Ensure each defect has a target regression test.
- Confirm preservation of original movie data.

#### Consolidated classification status

**Defects classified:** 16 of 16.

**P1:** 11.

**P2:** 5.

**P3:** 0.

**Reviewer approval:** Pending.

**Remediation implementation:** Not started.

**Next:** Reviewer readiness and open-decision review.

## 4. Target Design Decisions

### Purpose and decision status

This section consolidates the target design decisions
for modernizing the legacy Flask Top Ten Movies
application to FastAPI.

Decisions are based on verified behavior documented
in Section 1, Route Walk, and the defect register
in Section 3, Legacy Defects.

The purpose is to distinguish existing application
behavior, proposed improvements, and unresolved
decisions requiring reviewer input.

### Decision status definitions

- **Established:** A target behavior already explicitly
  documented as a decision in the behavior inventory.
  Final reviewer acceptance is still pending.
- **Proposed:** A recommended target behavior that
  has not yet been formally approved.
- **Open:** A question that requires a decision
  before implementation.
- **Deferred:** A decision intentionally postponed
  until a later modernization phase.

### Decision categories

The modernization decisions will be organized
under the following categories.

#### Application behavior and HTTP methods

Review which existing workflows must be preserved
and which HTTP methods should change.

Key considerations include movie insertion,
movie deletion, editing, and redirect behavior.

##### Application behavior decision register

The decisions below preserve the core movie
management workflow while correcting unsafe
HTTP methods and known validation problems.

| ID | Decision | Status | Evidence |
|---|---|---|---|
| TD-A01 | Preserve homepage movie listing | Established | GET `/` |
| TD-A02 | Use POST for movie insertion | Established | GET `/select` |
| TD-A03 | Use POST or DELETE for movie deletion | Proposed | GET `/delete` |
| TD-A04 | Preserve successful movie rating and review edits | Established | POST `/edit` |
| TD-A05 | Preserve post-insertion navigation to movie editing | Established | GET `/select` |
| TD-A06 | Validate movie identity before deletion | Proposed | GET `/delete` |

##### Decision details

**TD-A01 - Preserve homepage listing**

**Status:** Established.

Preserve the existing ability to display
the saved movie collection on the homepage.

The legacy application orders movies by
rating and displays dynamically calculated
rankings.

Ranking tie-breaking and a possible
ten-movie limit remain separate design
questions.

**TD-A02 - Use POST for movie insertion**

**Status:** Established.

Movie insertion must use HTTP POST rather
than the legacy GET `/select` operation.

The application must not create database
records through a read-only GET request.

**TD-A03 - Use a safe deletion workflow**

**Status:** Proposed.

Replace state-changing GET deletion with
an explicit POST or DELETE operation.

For an HTML form-based interface, POST may
be the simplest initial implementation.

The exact endpoint and HTTP method require
reviewer approval.

**TD-A04 - Preserve successful editing**

**Status:** Established.

Preserve the ability to update a movie's
rating and review through a validated form.

The legacy successful POST returns HTTP 302
and redirects to the homepage.

The modernized application should preserve
the successful user workflow.

**TD-A05 - Preserve navigation after insertion**

**Status:** Established.

After successfully inserting a movie,
continue the workflow by directing the
user to edit its rating and review.

The legacy application redirects to
`/edit?id=<new_movie_id>`.

The target endpoint format may change,
but the workflow should be preserved.

**TD-A06 - Validate movie identity before deletion**

**Status:** Proposed.

The modernized application should confirm
that a selected movie exists before
attempting deletion.

Missing, malformed, or unknown movie IDs
must not cause unhandled HTTP 500 errors.

Appropriate client-error responses and
user-facing feedback require confirmation.

##### Open application behavior questions

- Should the application enforce a strict
  maximum of ten saved movies?
- Should equal ratings use a deterministic
  secondary ranking rule?
- Should the modernized application continue
  redirecting after edits or use an alternative
  response pattern?
- What confirmation or protection should be
  required before a movie is deleted?

##### Application behavior register status

**Decisions documented:** 6.

**Established:** 4.

**Proposed:** 2.

**Open questions:** 4.

**Reviewer acceptance:** Pending.

**Implementation status:** Not started.

**Source:** Section 1, Route Walk,
including GET `/`, GET `/delete`,
POST `/edit`, and GET `/select`.

**Next:** Input validation and error handling.

#### Input validation and error handling

Define consistent validation for movie IDs,
user-submitted ratings, and movie searches.

Specify how invalid input and missing records
should be reported without unhandled exceptions.

##### Input validation decision register

This register consolidates target validation
requirements based on verified legacy defects.

The target application must validate user
input before performing database operations
or making external TMDB requests.

| ID | Decision | Status | Evidence |
|---|---|---|---|
| TD-V01 | Enforce ratings from 1 to 10 inclusive | Established | D-R01, D-R02 |
| TD-V02 | Reject missing or malformed TMDB movie IDs | Established | D-S01, D-S02 |
| TD-V03 | Handle unknown TMDB movie IDs gracefully | Established | D-S03 |
| TD-V04 | Handle duplicate movie selection gracefully | Established | D-S04 |
| TD-V05 | Preserve empty and whitespace-only title rejection | Established | POST `/add` |
| TD-V06 | Validate movie IDs for editing and deletion | Proposed | GET `/edit`, GET `/delete` |

##### Decision details

**TD-V01 - Rating validation**

**Status:** Established.

The modernized application must enforce
a rating range of 1 to 10, inclusive.

Decimal ratings are permitted.

Ratings below 1 or above 10 must be
rejected through server-side validation.

This corrects D-R01 and D-R02 while
preserving valid boundary ratings.

**TD-V02 - TMDB movie ID validation**

**Status:** Established.

Missing or malformed TMDB movie IDs must
be rejected before contacting TMDB.

The target application should use
appropriate client-error responses.

The Route Walk proposes HTTP 400 for
missing and non-numeric movie IDs.

**TD-V03 - Unknown TMDB movie IDs**

**Status:** Established.

A correctly formatted TMDB movie ID
may not correspond to an existing movie.

When TMDB confirms a movie does not exist,
the application should return a controlled
HTTP 404 response with helpful feedback.

No movie record should be inserted.

**TD-V04 - Duplicate movie selection**

**Status:** Established.

The application must detect and handle
duplicate movie selection gracefully.

A duplicate selection must not produce
an unhandled HTTP 500 error.

The target database must preserve
appropriate uniqueness constraints.

The choice between title-based and
TMDB-ID-based identification remains open.

**TD-V05 - Movie search title validation**

**Status:** Established.

Preserve rejection of empty and
whitespace-only movie search titles.

Invalid titles must not trigger
unnecessary TMDB requests.

Validation must be enforced by the
backend rather than relying solely
on browser-side checks.

**TD-V06 - Local movie ID validation**

**Status:** Proposed.

Movie editing and deletion must validate
local database movie IDs.

Missing, malformed, and unknown IDs
must not produce unhandled exceptions.

The exact response codes and
user-facing behavior require approval.

##### Open validation questions

- What HTTP response should an HTML form
  display when validation fails?
- Should invalid local movie IDs result
  in HTTP 400, HTTP 404, or a redirect?
- Should duplicate detection use TMDB IDs
  instead of titles?
- How should validation errors be shown
  consistently across movie forms?

##### Input validation register status

**Decisions documented:** 6.

**Established:** 5.

**Proposed:** 1.

**Open questions:** 4.

**Reviewer acceptance:** Pending.

**Implementation status:** Not started.

**Source:** Section 1, Route Walk,
D-R01, D-R02, D-S01 through D-S04,
POST `/add`, GET `/edit`, and GET `/delete`.

**Next:** TMDB integration and external data.

#### TMDB integration and external data

Define how the application handles TMDB outages,
missing fields, empty values, null values,
and unavailable movie records.

External data must be validated or normalized
before database insertion.

##### TMDB integration decision register

This register defines target behavior for
external TMDB service errors and incomplete
movie data.

The decisions distinguish verified legacy
failures from proposed normalization policies.

| ID | Decision | Status | Evidence |
|---|---|---|---|
| TD-T01 | Handle TMDB service failures gracefully | Established | D-T01 |
| TD-T02 | Handle TMDB movie-not-found responses | Established | D-S03 |
| TD-T03 | Define unknown release-year handling | Open | D-S05, D-S06, D-S07 |
| TD-T04 | Handle missing poster artwork | Proposed | D-S08, D-S09, D-S10 |
| TD-T05 | Handle missing movie overviews | Proposed | D-S11, D-S12, D-S13 |
| TD-T06 | Validate external movie details before insertion | Established | D-S05 through D-S13 |

##### Decision details

**TD-T01 - TMDB service failures**

**Status:** Established.

The modernized application must handle
TMDB service failures without producing
an unhandled application exception.

Users should receive a clear message
when movie search is unavailable.

Errors should be logged securely without
exposing API credentials.

The exact HTTP response and retry policy
require further design review.

**TD-T02 - Movie not found**

**Status:** Established.

When TMDB confirms that a valid numeric
movie ID does not exist, the application
should return a controlled HTTP 404
response with helpful feedback.

No movie record should be inserted.

This requirement complements TD-V03.

**TD-T03 - Unknown release years**

**Status:** Open.

The legacy application has three verified
release-date failure scenarios:

- Missing release_date raises KeyError.
- Empty release_date saves an empty year.
- Null release_date saves literal 'None'.

The modernized application must avoid
these uncontrolled or invalid outcomes.

**Open decision:** Should a movie without
a known release year be accepted using
an explicit unknown-year representation,
or should insertion be rejected with
a helpful message?

If unknown years are allowed, the target
database schema must support the chosen
representation consistently.

**TD-T04 - Missing poster artwork**

**Status:** Proposed.

The legacy application has three verified
poster-path failure scenarios:

- Missing poster_path raises KeyError.
- Null poster_path produces a URL ending /None.
- Empty poster_path produces a URL without
  a poster filename.

**Proposed behavior:** Permit movie insertion
when poster artwork is unavailable.

The user interface should display a
default placeholder image.

The application must not construct invalid
poster URLs from missing, null, or empty
poster-path values.

**Pending approval:** Confirm the placeholder
image strategy and storage representation.

**TD-T05 - Missing movie overviews**

**Status:** Proposed.

The legacy application has three verified
overview scenarios:

- Missing overview raises KeyError.
- Empty overview saves an empty description.
- Null overview causes SQLite IntegrityError
  and HTTP 500.

**Proposed behavior:** Permit movie insertion
without an available overview.

Display an appropriate fallback description
when the overview is unavailable.

**Pending approval:** Decide whether missing
descriptions should be stored as NULL,
an empty string, or placeholder text.

Application validation and database constraints
must support the chosen representation.

**TD-T06 - External data validation**

**Status:** Established.

Validate or normalize external TMDB movie
details before attempting database insertion.

Required data and optional data must be
handled according to explicit rules.

Missing keys, empty strings, and null values
must not cause unhandled application errors.

The application must preserve database
integrity constraints while providing
controlled error handling.

This requirement covers the verified
release-date, poster-path, and overview
defects D-S05 through D-S13.

##### Open TMDB integration questions

- What timeout and retry policy should
  apply to TMDB requests?
- What response should users receive
  during a temporary TMDB outage?
- Should movies with unknown release
  years be accepted or rejected?
- What representation should be used
  for unavailable poster artwork?
- How should unavailable overview text
  be stored and displayed?
- Which TMDB response fields are required
  before a movie can be inserted?

##### TMDB integration register status

**Decisions documented:** 6.

**Established:** 3.

**Proposed:** 2.

**Open:** 1.

**Open questions:** 6.

**Reviewer acceptance:** Pending.

**Implementation status:** Not started.

**Source:** Section 1, Route Walk,
D-T01 and D-S03 through D-S13.

**Next:** Database schema and migration.

#### Database schema and migration

Define the target Movie schema and identify
any required schema changes.

Preserve the original ten movie records and
avoid truncating existing descriptions.

Document uniqueness rules, nullable fields,
release-year representation, and ranking storage.

##### Database schema and migration decision register

This register defines data-preservation requirements
and proposed database changes for the FastAPI rebuild.

The existing SQLite database is the migration baseline.

| ID | Decision | Status | Evidence |
|---|---|---|---|
| TD-D01 | Preserve all ten original movie records | Established | Section 2, Data Snapshot |
| TD-D02 | Preserve full movie descriptions without truncation | Established | Section 2, Data Snapshot |
| TD-D03 | Preserve database integrity and uniqueness constraints | Established | D-S04, D-S13 |
| TD-D04 | Review removal or redesign of stored ranking | Proposed | GET `/`, Section 2 |
| TD-D05 | Define nullable and optional movie fields | Open | D-S05 through D-S13 |
| TD-D06 | Consider storing TMDB movie IDs | Proposed | D-S04 |

##### Decision details

**TD-D01 - Preserve original movie data**

**Status:** Established.

All ten original Movie records must survive migration.

Preserve original movie IDs, titles, years,
descriptions, ratings, reviews, and poster URLs.

Preserve Unicode text, including non-English titles.

Migration tests must verify record counts and
field values before and after migration.

Do not perform destructive tests against the
original database.

**TD-D02 - Preserve complete descriptions**

**Status:** Established.

The existing database contains six movie
descriptions longer than 250 characters.

The longest verified description is 449 characters.

The target schema must support existing
descriptions without truncation or data loss.

A suitable text-capable column type
should be selected.

The reviewer discrepancy concerning the number
of descriptions longer than 250 characters
remains open.

**TD-D03 - Preserve database integrity**

**Status:** Established.

The target database must enforce appropriate
uniqueness and required-field constraints.

The legacy database enforces uniqueness
on movie titles.

The database also rejects NULL descriptions
through a NOT NULL constraint.

Application-level validation must prevent
or gracefully handle constraint violations.

The precise target constraints may change
after optional-field and identity decisions
are approved.

**TD-D04 - Stored ranking representation**

**Status:** Proposed.

The legacy application calculates displayed
rankings dynamically from movie ratings.

All ten existing records store ranking = 10.

The stored ranking column does not represent
the displayed movie order.

**Proposed behavior:** Calculate rankings
dynamically rather than persist redundant values.

**Pending approval:** Determine whether
the ranking column should be retained,
removed, or replaced.

A deterministic ordering rule for tied
ratings also requires a decision.

**TD-D05 - Optional and nullable fields**

**Status:** Open.

The legacy schema requires non-NULL values
for title, year, and description.

Verified TMDB tests show that incomplete
release dates and overviews may cause
invalid stored values or database failures.

**Open decision:** Define the required
and optional fields of the target Movie model.

In particular, determine whether unknown
years and missing descriptions are permitted.

If permitted, choose consistent database
representations and display fallbacks.

Poster artwork should also follow
the approved missing-image policy.

Application validation and database
constraints must agree.

**TD-D06 - TMDB identifiers**

**Status:** Proposed.

The existing database identifies movies
through local database IDs and enforces
uniqueness using movie titles.

Title-based duplicate detection may not
be sufficient for identifying the same
movie across different releases or titles.

**Proposed behavior:** Store a separate
TMDB movie ID for imported movies.

**Pending approval:** Determine whether
the TMDB ID should become the primary
duplicate-detection key.

Existing records without known TMDB IDs
must remain valid during migration.

Do not invent TMDB identifiers for
the original ten movies.

##### Open database and migration questions

- Which database engine will the
  FastAPI rebuild use?
- Should the stored ranking column
  be removed or retained?
- How should unknown release years
  be represented?
- Should missing descriptions be stored
  as NULL or normalized text?
- Should TMDB movie IDs be added,
  and how should existing records be handled?
- What uniqueness rules should apply
  after introducing TMDB identifiers?
- How should the six long descriptions
  be preserved in the target schema?
- How will the discrepancy with the
  reviewer's description count be resolved?

##### Migration verification requirements

- Record a baseline of the original database.
- Work against a copy for migration tests.
- Verify the original ten movie IDs remain present.
- Verify all original field values are preserved.
- Verify Unicode titles survive migration.
- Verify complete descriptions are not truncated.
- Verify uniqueness and required-field constraints.
- Confirm migration does not change the source database.
- Document any intentional schema transformations.
- Compare pre-migration and post-migration results.

##### Database migration register status

**Decisions documented:** 6.

**Established:** 3.

**Proposed:** 2.

**Open:** 1.

**Open questions:** 8.

**Reviewer acceptance:** Pending.

**Implementation status:** Not started.

**Source:** Section 2, Data Snapshot;
Section 1, Route Walk; D-S04 through D-S13.

**Next:** Presentation and user experience.

#### Presentation and user experience

Preserve the core movie-list workflow while
improving clarity of user-facing messages.

Review movie rankings, empty search results,
missing poster artwork, and editing forms.

##### Presentation and user experience decision register

This register defines user-facing behavior
to preserve or improve during modernization.

The decisions are based on verified legacy
routes and documented usability concerns.

| ID | Decision | Status | Evidence |
|---|---|---|---|
| TD-U01 | Preserve movie listing and displayed rankings | Established | GET `/` |
| TD-U02 | Show the selected movie's title on its edit page | Proposed | GET `/edit` |
| TD-U03 | Show helpful feedback for empty TMDB searches | Proposed | POST `/add` |
| TD-U04 | Provide a fallback for missing poster artwork | Proposed | D-S08, D-S09, D-S10 |
| TD-U05 | Display clear validation and service-error feedback | Proposed | D-R01, D-R02, D-T01 |
| TD-U06 | Define ranking tie-breaking and list-size behavior | Open | GET `/` |

##### Decision details

**TD-U01 - Movie listing and rankings**

**Status:** Established.

Preserve the homepage movie list and
the ability to rank saved movies by rating.

The legacy application calculates
displayed rankings dynamically.

The highest-rated movie receives rank 1.

The target design must preserve a clear
rating-based display order.

A deterministic tie-breaking rule
requires a separate decision.

**TD-U02 - Edit-page movie title**

**Status:** Proposed.

The legacy edit page displays a hardcoded
Movie Title heading.

It does not identify the selected movie
in the heading.

**Proposed behavior:** Display the actual
selected movie's title on the edit page.

The form should provide enough context
for users to know which movie they
are editing.

**Pending approval:** Confirm whether
existing rating and review values
should also be prefilled.

**TD-U03 - Empty movie search feedback**

**Status:** Proposed.

The legacy application renders a
selection page when TMDB returns
an empty result list.

No helpful explanation was observed.

**Proposed behavior:** Display a clear
message when no movies are found.

Suggested message:

"No movies found. Please try another title."

Allow users to revise the search
without encountering an error.

**TD-U04 - Missing poster artwork**

**Status:** Proposed.

The legacy application can save
invalid poster URLs when TMDB returns
null or empty poster-path values.

A missing poster-path key raises
an unhandled exception.

**Proposed behavior:** Display a
placeholder image when valid artwork
is unavailable.

The interface should not show
broken or misleading poster URLs.

This decision must remain consistent
with TD-T04 and the database schema.

**TD-U05 - Validation and error feedback**

**Status:** Proposed.

Users should receive understandable
feedback for invalid input, duplicate
movie selection, and TMDB failures.

Error messages should help users
correct the issue or retry later.

Internal exception details and API
credentials must not be exposed.

The exact HTTP responses and message
presentation require reviewer approval.

**TD-U06 - Ranking and list-size rules**

**Status:** Open.

The legacy homepage does not enforce
a maximum of ten movie records.

The legacy ranking logic also has
no explicit tie-breaking rule.

**Open decisions:**

- Should the application enforce
  a strict ten-movie maximum?
- How should movies with equal
  ratings be ordered?
- Should the interface display
  all saved movies or only ten?

Any chosen policy must be documented
consistently across insertion,
ranking, and homepage behavior.

##### Open presentation questions

- Should the editing form prefill
  the existing rating and review?
- Should deletion require an
  explicit confirmation?
- How should validation feedback
  appear in HTML forms?
- Which placeholder artwork
  should represent missing posters?
- Should the homepage enforce
  a maximum of ten movies?
- What tie-breaking rule should
  apply to equal ratings?

##### Presentation register status

**Decisions documented:** 6.

**Established:** 1.

**Proposed:** 4.

**Open:** 1.

**Open questions:** 6.

**Reviewer acceptance:** Pending.

**Implementation status:** Not started.

**Source:** Section 1, Route Walk;
GET `/`, GET `/edit`, POST `/add`,
D-R01, D-R02, D-T01, and
D-S08 through D-S10.

**Next:** Testing and verification.

#### Testing and verification

Translate independently verified legacy behavior
and defects into automated regression tests.

Maintain separation between original data,
temporary test data, and migration validation.

##### Testing and verification decision register

This register defines the verification strategy
for the FastAPI modernization.

The existing Flask audit provides baseline
evidence, not proof that the FastAPI rebuild
has implemented or passed these tests.

| ID | Decision | Status | Evidence |
|---|---|---|---|
| TD-Q01 | Convert verified legacy defects into regression tests | Established | Section 3, Legacy Defects |
| TD-Q02 | Preserve successful core workflows in automated tests | Established | Section 1, Route Walk |
| TD-Q03 | Keep tests isolated from the original database | Established | Section 1, Test isolation |
| TD-Q04 | Mock TMDB interactions during automated tests | Established | Section 1, TMDB test results |
| TD-Q05 | Verify complete data preservation during migration | Proposed | Section 2, Data Snapshot |
| TD-Q06 | Define acceptance criteria for unresolved design choices | Open | Section 4, Decision registers |

##### Decision details

**TD-Q01 - Legacy defect regression coverage**

**Status:** Established.

Create automated tests for the 16 verified
legacy defect IDs documented in Section 3.

Test the intended corrected behavior rather
than reproducing defective results as
acceptable outcomes.

Coverage must include:

- Rating boundary enforcement.
- Missing and malformed TMDB movie IDs.
- TMDB movie-not-found handling.
- Duplicate movie selection.
- Missing, empty, and null release dates.
- Missing, empty, and null poster paths.
- Missing, empty, and null overviews.
- TMDB search service failures.

Record links between regression tests
and their corresponding defect IDs.

**TD-Q02 - Core workflow regression coverage**

**Status:** Established.

Preserve and verify successful workflows:

- Homepage movie listing and ranking.
- Displaying the Add Movie form.
- Searching for movies by title.
- Selecting and inserting a movie.
- Redirecting to movie editing.
- Updating a rating and review.
- Deleting an existing movie.

Verify the intended HTTP responses
and database state changes.

Where target behavior intentionally
differs from Flask, tests must follow
the approved target design.

**TD-Q03 - Database test isolation**

**Status:** Established.

Automated tests must never perform
destructive operations against the
original ten-movie database.

Use a separate temporary test database
or equivalent isolated test environment.

Verify record counts and expected
database changes during tests.

Restore or discard temporary test
data after execution.

The original database must remain
unchanged throughout regression testing.

**TD-Q04 - External service mocking**

**Status:** Established.

Automated TMDB tests should use
controlled, mocked service responses.

Do not depend on live TMDB access
for routine regression testing.

Test successful responses, HTTP errors,
missing keys, empty strings, and null values.

Use fake test credentials.

Do not expose real API credentials
in source code, logs, or test reports.

Live integration testing, if required,
must be planned separately.

**TD-Q05 - Migration preservation tests**

**Status:** Proposed.

Build automated migration checks using
the verified ten-row database inventory.

Compare source and migrated records
for field-level preservation.

Coverage should include:

- Ten original records.
- Original local movie IDs.
- Titles, including Unicode text.
- Release years.
- Complete descriptions.
- Ratings and reviews.
- Existing poster URLs.

Document any approved transformations
separately from accidental data changes.

Do not use strict byte-for-byte database
file equality as a migration requirement,
because an approved schema migration
may legitimately change file structure.

**TD-Q06 - Design acceptance criteria**

**Status:** Open.

Some target outcomes cannot be tested
until the reviewer approves design choices.

Examples include:

- Maximum movie-list size.
- Ranking tie-breaking.
- Missing-year representation.
- Missing-overview representation.
- Poster fallback strategy.
- Duplicate identification rules.
- Deletion confirmation workflow.

For each approved decision, define
an expected result and corresponding
automated acceptance test.

Do not label unresolved behavior
as implemented or verified.

##### Verification evidence categories

**Legacy observed:**

Behavior reproduced or inspected in
the original Flask application.

**Target proposed:**

Expected behavior documented for
the FastAPI rebuild.

**Target implemented:**

Behavior implemented in FastAPI,
but not necessarily tested.

**Target verified:**

Behavior independently confirmed
by a passing target-system test.

These categories must not be
treated as interchangeable.

##### Open testing questions

- Which test framework and fixtures
  will the FastAPI rebuild use?
- Which scenarios require HTTP-level
  integration tests?
- Which behaviors can be verified
  through isolated unit tests?
- What minimum coverage is required
  before reviewer acceptance?
- Which unresolved design decisions
  block acceptance-test definitions?
- Will a separate live TMDB integration
  test phase be necessary?

##### Testing and verification register status

**Decisions documented:** 6.

**Established:** 4.

**Proposed:** 1.

**Open:** 1.

**Open questions:** 6.

**Reviewer acceptance:** Pending.

**FastAPI implementation status:** Not started.

**FastAPI regression test status:** Not started.

**Source:** Sections 1 through 4,
including the 16 verified legacy defect IDs
and the ten-record SQLite data snapshot.

**Next:** Consolidated decision register review.

### Decision register status

#### Consolidated decision counts

| Category | Established | Proposed | Open | Total |
|---|---:|---:|---:|---:|
| Application behavior and HTTP methods | 4 | 2 | 0 | 6 |
| Input validation and error handling | 5 | 1 | 0 | 6 |
| TMDB integration and external data | 3 | 2 | 1 | 6 |
| Database schema and migration | 3 | 2 | 1 | 6 |
| Presentation and user experience | 1 | 4 | 1 | 6 |
| Testing and verification | 4 | 1 | 1 | 6 |
| **Total** | **20** | **12** | **4** | **36** |

#### Consolidated review status

**Decision categories completed:** 6 of 6.

**Target decisions documented:** 36.

**Established:** 20.

**Proposed:** 12.

**Open:** 4.

**Open questions recorded:** 34.

**Legacy defect IDs documented:** 16.

**Reviewer acceptance:** Pending.

**FastAPI implementation:** Not started.

**FastAPI regression testing:** Not started.

#### Review requirements

- Confirm or revise the proposed target behaviors.
- Resolve or explicitly defer open design decisions.
- Review priorities for the 16 legacy defects.
- Confirm database migration and data-preservation requirements.
- Approve acceptance criteria before implementation.
- Distinguish verified Flask behavior from untested FastAPI requirements.

#### Section 4 completion status

**Status:** Initial target design decision registers completed.

All six decision categories now contain documented
requirements, proposed improvements, or open decisions.

The recorded statuses describe the current documentation
state, not final reviewer approval.

No FastAPI implementation or target-system test
verification is claimed.

**Next:** Reviewer readiness and open-decision review
in Section 5.

## 5. Reviewer Readiness and Open Decisions

### Review purpose

This section summarizes the decisions and
verification evidence requiring reviewer attention
before the FastAPI implementation begins.

The legacy Flask audit and initial decision
registers are complete.

Reviewer acceptance and target implementation
remain pending.

### Open target decisions

Four target decision IDs are explicitly marked Open.

| Decision ID | Topic | Required reviewer decision |
|---|---|---|
| TD-T03 | Unknown release years | Accept movies with unknown years or reject insertion |
| TD-D05 | Optional database fields | Define nullable fields and representations for unavailable data |
| TD-U06 | Ranking and list size | Approve tie-breaking and maximum movie-list behavior |
| TD-Q06 | Testing acceptance criteria | Define expected results for unresolved target behaviors |

These decisions are related to additional
Proposed decisions and open questions.

They should be resolved or explicitly deferred
before their affected features are implemented.

### Proposed decision review

Twelve target decision IDs are marked Proposed.

The reviewer must approve, revise, reject,
or explicitly defer each proposal.

Proposed behavior must not be described
as approved or implemented.

### Defect priority review

All 16 verified legacy defect IDs have
preliminary severity and remediation priorities.

**High severity:** 9.

**Medium severity:** 7.

**P1 remediation:** 11.

**P2 remediation:** 5.

No severity or priority assignments
have received final reviewer approval.

Additional legacy concerns without dedicated
defect IDs require separate review.

### Data migration readiness

The original database contains ten Movie records.

Migration requirements include preserving
the existing records, Unicode titles,
complete descriptions, and original values.

Six descriptions exceed 250 characters.

The longest verified description is
449 characters.

The reviewer's earlier count of four
long descriptions differs from the
current audit count of six.

This discrepancy remains unresolved.

### Verification readiness

Legacy behavior and defects have been
documented through isolated tests,
source inspection, and read-only
database inspection.

The FastAPI rebuild has not started.

Automated FastAPI regression tests
have not started.

Legacy test evidence must not be
presented as FastAPI test results.

### Residual legacy verification gaps

The legacy audit records 16 verified defect
IDs and the tested core route behaviors.

Some specific scenarios remain unverified
or only partially verified.

**Edit-form validation**

The exact Flask-WTF validation errors for
a missing CSRF token and rejected rating
values were not independently inspected.

Invalid movie IDs on edit-form POST requests
were not independently verified.

**User-facing validation feedback**

The precise validation messages for
invalid movie search titles were not
independently inspected.

**Missing TMDB overview**

D-S11 was verified through an independently
captured Python KeyError.

An HTTP response with exception propagation
disabled was not independently measured
for that scenario.

**Live TMDB behavior**

The documented TMDB failure and incomplete-data
tests used mocked responses.

They do not establish live TMDB behavior
or live service availability.

**Scope of completion**

These gaps do not invalidate the recorded
test evidence or the completed defect register.

They should be evaluated during test planning
and reviewer acceptance.

No additional legacy test execution is
claimed by this documentation update.

### Reviewer checklist

- Review all 36 documented target decisions.
- Resolve or defer the four Open decisions.
- Review the 12 Proposed decisions.
- Confirm all 16 defect severity ratings.
- Confirm all 16 remediation priorities.
- Resolve the description-count discrepancy.
- Approve database migration safeguards.
- Agree on acceptance-test requirements.
- Record decisions before implementation.

### Reviewer readiness status

**Legacy defect classifications:** Complete.

**Target decision registers:** Complete.

**Open target decision IDs:** 4.

**Proposed target decision IDs:** 12.

**Reviewer acceptance:** Pending.

**FastAPI implementation:** Not started.

**FastAPI regression testing:** Not started.

**Next:** Final documentation consistency audit.
