# My closet: personal picks and recommendations from them

## Goal
A person can "pick" films into their own closet and get recommendations seeded by it, using the picks graph of the real closet visitors. Closets are visible to everyone who can open the page (user decision), so people can browse each other's closets and see how much they overlap.

## What exists
The Recommend tab already ranks films by co-picks: for seed films it finds the visitors who picked them and scores each other film they picked by `overlap² / total picks`, optionally limited to one occupation. Its seeds live only in the URL and in memory. "My closet" adds the missing memory and a person to attach it to.

## Data (Pages shared data, through `server.js`)
- Collection `closet_picks`: one row per person and film, `{film_slug, by_name}`. The row's `author` is set by the host and is the trusted identity; `by_name` is the display name the page sends and is informational and claimable by anyone, like the club names. A person's name shown in lists is the one on their most recent row.
- Closets are therefore public inside the page, and readable by anyone with a data-flow key (a key reads every collection). There is no private mode.
- Ownership is decided only by the trusted `actor` that the host passes to `run()`, never by anything in the arguments (an `author` or similar argument is ignored). The read step cannot see the actor, so each action reads the whole `closet_picks` collection (small: at most 200 rows per person) and selects the caller's rows inside `run()` with `row.author === actor`, the same pattern the rating actions use. Updates and removals name only rows that were read in the same call, as the host requires.
- Actions: `closet_add({film_slug, by_name})` validates the slug against the dataset, is a no-op if the caller already has that film, and refuses a 201st pick (a safety cap of 200 per person, counted over the caller's own rows). `closet_remove({film_slug})` removes only the caller's own row for that film, and does nothing if there is none, even if someone else has it. `closets()` returns every row as `{author, by_name, film_slug, created_at}` for the page to group. No log: the row itself is the record, and removal deletes it.

## Recommendations
`computeRecommendations(seeds, lens)` becomes a pure function of its arguments; the Recommend tab calls it with its own seeds and lens, unchanged results. "For you" calls it with the caller's closet and lens "all", top 24, which never contains a film already in the closet. The existing score and "because you picked X" reason are reused.

## Views and links
- New tab "My closet", address `#closet`. It shows: my picks as a poster grid (open the popup, remove), a search box to add any film, "For you" recommendations, "Closest visitors" (the five real visitors with most picks in common with my closet: shared count and size of their closet, ties by smaller closet first, then name), and "Other closets" (everyone else, most overlap first, then name; overlap = shared picks).
- Someone else's closet opens at `#closet/<author id>`: their picks with the ones I share marked, read-only. An unknown id falls back to my closet with a message.
- The film popup gets a toggle button, "Add to my closet" / "In my closet" (removes), when the Pages host is available. Opening a film link keeps working as before.
- Without the Pages host (the GitHub Pages build) the tab explains that closets need the Pages app, as the Clubs tab does.
- Loading uses the same pattern as clubs: responses for something no longer on screen, and failures of superseded requests, are ignored; buttons are disabled while an action runs; errors are shown inline.

## Testing
Node (`server.js` against the simulated host): add is idempotent, an unknown film is refused, the 200 cap, remove only touches the caller's rows, two people's closets stay separate, `closets()` returns every person's rows, and a forged `author` argument can neither remove another person's pick nor let a person exceed their own cap. Browser: the popup toggle adds and removes; "My closet" lists the picks; "For you" matches an independent Python implementation of the co-pick score for a fixed closet and excludes owned films; the Recommend tab still gives its previous results for fixed seeds; "Closest visitors" and "Other closets" ordering including ties; `#closet/<id>` for someone else's and for an unknown id; stale-response handling; no-host message.

## Out of scope
Private closets, ratings or likes beyond picking, ordering of picks, importing closets from elsewhere, using closets to suggest club films, and notifications.
