# Club participants

## Goal
A club shows who takes part. A person becomes a participant by pressing a button, or simply by rating a watched film in that club. Each participant is listed by name and, when they have a closet, with a link to it.

## Who counts as a participant
The union of:
- people who **joined** with the button (an explicit row), and
- people who have **rated** a film in this club (derived from the existing `ratings` rows of the club: no extra write, so rating cannot fail because of this feature).

A person in both appears once and is tagged "joined" and "rated". Leaving removes only the explicit row; someone who still has a rating in the club stays listed as "rated" until they clear their ratings. Being the person who added a film or ticked it off does not make anyone a participant.

## Data and actions (shared data, `server.js`)
- Collection `participants`: one row per person and club, `{club_id, by_name}`. Identity is the host-set `author`; `by_name` is informational and claimable, like every other name.
- Ownership is decided only by the trusted `actor`, never by arguments. The read step cannot see the actor, so the actions read the club's participant rows and select the caller's with `row.author === actor` inside `run()`.
- `join_club({club_id, by_name})`: unknown club is an error; if the caller already has a row, nothing is written except that a changed `by_name` is updated on it; otherwise a row is created. A log row `join_club` is written when a row is created (two ids, like adding a film).
- `leave_club({club_id})`: removes the caller's rows for that club (none is fine, nothing written) and logs `leave_club` only when something was removed.
- `club_state` additionally returns the club's `participants` rows. Log actions `join_club` and `leave_club` appear in the club activity like the others.

## Page
- A "Participants" section in the club view, below the header: a list sorted by name; each entry shows the name, a small tag ("joined", "rated" or both) and, if the person has a closet (at least one pick), a link "closet (N)" to `#closet/<author id>` (to `#closet` for yourself, to avoid the self-link). A person without a closet gets no link.
- The name shown for a person is the one on their most recent row across their participant row and their ratings in this club.
- A button "Join this club" / "Leave this club" for the viewer (leave only when they have an explicit row); a hint says that rating a watched film also adds you.
- Closet links need the closets data: the club view uses the shared closet loading state from My closet; when closets finish loading the club view repaints so the links appear. If closets cannot be loaded the list still shows, without links, and the closet error is not shown in the club.
- Same patterns as the rest of the club: actions disable the buttons while running and ignore a second click, errors are shown inline, responses for a club no longer on screen are ignored.

## Testing
Node: join is idempotent and updates a changed name, per-club separation, leave removes only the caller's row, a forged `author` argument is ignored, join/leave log rows, `club_state` returns participants. Browser: joining lists the person; rating alone lists them without a join row; both gives one entry with both tags; leaving; the closet link appears only for people with a closet, goes to `#closet/<id>` (and `#closet` for the viewer) and opens that closet; a failed closets load shows the list without links; a slow join disables the button and ignores a second click; the latest name wins.

## Out of scope
Roles or admin rights, removing other people, inviting by name, notifications, and counting film additions or tick-offs as participation.
