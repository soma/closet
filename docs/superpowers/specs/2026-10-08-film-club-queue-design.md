# Film club feeds: shared "what do we watch next" per club

## Goal
Any Auctionet colleague can create a film club. Each club has a feed: a **current** film (until marked watched), upcoming films, and a watched history. The app suggests films using the club's rule, but members can search the whole dataset and pick anything out of band. Members score and comment on each watch. Every action is logged with who did it.

## The suggestion rule (from the user)
Suggested next film = the most-picked film in the closet dataset, from a director the club has not already seen, that is not a short and runs 180 minutes or less.

- Shorts are excluded. A short is a film with `runtime_min` of 40 or less (the usual Academy cutoff; 156 films in the dataset). The eligible runtime range is therefore 41 to 180 minutes inclusive. The bounds are two named constants (`SHORT_MAX_MIN = 40`, `LONG_MAX_MIN = 180`). The user first said to ignore the short clause, then reversed that; this is the final decision.
- Pick count = number of rows in `picks` for the film. Ties: higher `avg_rating`, then earlier `film_year`, then title.
- A film's directors are the `;`-separated names in `directors`. A film is ineligible if **any** of its directors is "taken".
- "Taken" directors = directors of every film in the club's feed that is **watched, current or upcoming** (so suggestions never offer a second film from a director already scheduled). Films already in the club's feed are never suggested again.
- Runtime of 40 or less, or above 180, is excluded; missing runtime or directors is excluded (the current data has none missing). The exclusion applies to suggestions only: members can still pick a short or a long film out of band.
- The page shows the next 8 suggestions as a simulation: take the best, treat it as taken, repeat. Suggestions are advisory and recomputed on every change.
- A club starts empty ("start fresh"): members add films they have already seen via search and mark them watched with a past date.
- An out-of-band pick is allowed even if its director is taken; it just also takes its directors.

## Feed model
- A **club** has a name. Clubs are open to everyone who can open the page (no membership); no secrets are stored.
- An **entry** is a film in a club's feed with a state `current`, `upcoming` or `watched`, an optional `scheduled_for` local date and time (a string `YYYY-MM-DDTHH:MM`), and for watched entries a `watched_on` date (`YYYY-MM-DD`).
- A club has **at most one** `current` entry. It is **pinned**: it stays current until it is marked watched, removed, or another entry is explicitly made current. Scheduling, adding or unwatching other entries never changes which entry is current.
- Transitions, all enforced by the server, which reads the club's entries in each action:
  - Add: the new entry becomes `current` if the club has none, otherwise `upcoming`.
  - Make current (on an `upcoming` entry): it becomes `current`, and the previous current becomes `upcoming`.
  - Mark watched (on `current` or `upcoming`, with a date, default today in the viewer's browser): it becomes `watched`. If it was current, the **next current** is chosen from the club's `upcoming` entries: earliest `scheduled_for` first, then entries without a time in creation order; if none exist, the club has no current.
  - Mark unwatched: the entry becomes `current` if the club has none, otherwise `upcoming`.
  - Remove (on `current` or `upcoming`): the entry is deleted; if it was current, the next current is chosen by the same rule as above.
  - Set or clear the time: changes `scheduled_for` only.
- A **rating** is one per member per entry: score 1 to 10 (integer) and an optional note of at most 1000 characters. Setting it again replaces the member's own rating only. Members can clear their own rating. The entry shows each rating with its author and the mean score.

## Shared state and the log
Uses Pages shared data through `server.js` (not readable by viewers). Collections:
- `clubs`, `entries`, `ratings`, and `log`. `log` is append-only: one row per action (`create_club`, `add`, `make_current`, `schedule`, `watched`, `unwatched`, `remove`, `rate`, `clear_rating`) with `club_id`, `film_slug`, `entry_id` and the detail. The server sets each row's `author` (the trusted actor id) and timestamps; nothing is ever edited or deleted in `log`.
- Names: rows also store the viewer's display name as sent by the page from `window.pages.currentUser()`. Names are informational and client-claimed; the `author` id is the trusted part. The page shows the name and falls back to "someone".
- `server.js` validates every action: known `film_slug` (a slug list is generated into `dist/server.js` at build time from `data/closet.json`), `club_id` exists, entry belongs to the club, score range, note length, date formats, and idempotence (adding a film already in the club's feed is a no-op that returns the existing entry). Writes use the host's atomic `writes`, and an update or remove only names rows read in the same call.
- Clubs cannot be deleted or renamed in this version.

## UI
A new "Clubs" tab in the existing explorer (Pages page 266), reusing its dataset and styling: club list and "new club", then per club the current film, upcoming, suggestions with "pick", search to pick anything, watched history with scores and notes, and the activity log. `clubQueue(...)` is a pure function exposed on `window` for tests.

## Access
Two human steps this session cannot do: an administrator switches shared data on for the page, and its grants widen from "only me" to Auctionet staff (view). Anyone who can view can act ("anyone can admin"). Whether viewers may call write actions, and how other members' names resolve, must be confirmed on the staged preview.

## Build and test
- `scripts/build.py` also writes `dist/server.js` from `src/server.js` plus the slug list. Staged with `index.html`; a human publishes.
- Tests through `script/test`: `clubQueue` (tie breaks, taken directors from watched, current and upcoming, co-directors, shorts at 40 and 41 minutes and long films at 180 and 181 minutes, already-in-feed excluded, out-of-band picks of shorts and long films) via Playwright; `server.js` actions in Node against a simulated host (validation failures, idempotence, every state transition above including the next-current choice and the one-current invariant, one rating per member, log appended for every action, log never modified). `run_page_action` on the staged page before declaring it working.

## Out of scope
RSS/calendar feeds, club membership or privacy, deleting or renaming clubs, reminders, accounts outside Auctionet, and changing grants or enabling shared data.
