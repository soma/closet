// Film club feeds: server side of the Pages app. Not served to browsers.
// The slug-list placeholder below is replaced at build time with the dataset's film slugs.
const FILM_SLUGS = new Set(__FILM_SLUGS__);

const MAX_NOTE = 1000;
const MAX_NAME = 80;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const TIME_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/;

function fail(message) { throw new Error(message); }

function validDate(s, what) {
  if (typeof s !== "string" || !DATE_RE.test(s) || Number.isNaN(Date.parse(s + "T00:00:00Z"))) fail(`${what} must be YYYY-MM-DD`);
  return s;
}
function validTime(s) {
  if (s == null) return null;
  if (typeof s !== "string" || !TIME_RE.test(s) || Number.isNaN(Date.parse(s + ":00Z"))) fail("time must be YYYY-MM-DDTHH:MM");
  return s;
}
function name(s) { return typeof s === "string" ? s.trim().slice(0, MAX_NAME) : ""; }
function clubId(v) {
  if (typeof v !== "string" && typeof v !== "number") fail("club_id is required");
  return String(v);
}
function slugOf(s) {
  if (typeof s !== "string" || !FILM_SLUGS.has(s)) fail("unknown film");
  return s;
}

const byCreated = (a, b) => String(a.created_at).localeCompare(String(b.created_at)) || String(a.id).localeCompare(String(b.id));

// The next current film: upcoming entries, earliest scheduled time first,
// then the ones without a time in creation order.
function nextCurrent(entries) {
  const upcoming = entries.filter(e => e.data.state === "upcoming");
  const timed = upcoming.filter(e => e.data.scheduled_for).sort((a, b) =>
    a.data.scheduled_for.localeCompare(b.data.scheduled_for) || byCreated(a, b));
  const untimed = upcoming.filter(e => !e.data.scheduled_for).sort(byCreated);
  return timed[0] || untimed[0] || null;
}

const clubInputs = args => ({
  club: { collection: "clubs", where: { id: args.club_id } },
  entries: { collection: "entries", where: { club_id: clubId(args.club_id) } },
});
const clubAndRatings = args => ({
  ...clubInputs(args),
  ratings: { collection: "ratings", where: { club_id: clubId(args.club_id) } },
});

function context(args, actor, rows, ids) {
  if (!rows.club || rows.club.length !== 1) fail("unknown club");
  const cid = clubId(args.club_id);
  const writes = [];
  const nextId = () => ids.shift() ?? fail("no id available");
  const by_name = name(args.by_name);
  const entries = rows.entries.map(e => ({ ...e, data: { ...e.data } }));
  const entryById = id => entries.find(e => String(e.id) === String(id)) || fail("unknown entry");
  const log = (action, entry, detail) => writes.push({
    op: "create", collection: "log", id: nextId(),
    data: { club_id: cid, action, film_slug: entry ? entry.data.film_slug : "", entry_id: entry ? String(entry.id) : "", detail: detail || "", by_name },
  });
  const save = e => writes.push({ op: "update", collection: "entries", id: e.id, data: e.data });
  const hasCurrent = () => entries.some(e => e.data.state === "current");
  return { cid, writes, nextId, by_name, entries, entryById, log, save, hasCurrent };
}

// Make the next upcoming entry current when the club has no current.
function promote(c) {
  if (c.hasCurrent()) return;
  const next = nextCurrent(c.entries);
  if (next) { next.data.state = "current"; c.save(next); }
}

const APP = {
  list_clubs: {
    inputs: () => ({ clubs: { collection: "clubs" } }),
    run: (args, actor, rows) => ({
      result: rows.clubs.slice().sort(byCreated).map(r => ({ id: r.id, name: r.data.name, author: r.author, created_at: r.created_at })),
    }),
  },

  club_state: {
    inputs: args => ({ ...clubAndRatings(args), log: { collection: "log", where: { club_id: clubId(args.club_id) } } }),
    run: (args, actor, rows) => {
      if (!rows.club || rows.club.length !== 1) fail("unknown club");
      const pick = r => ({ id: r.id, data: r.data, author: r.author, created_at: r.created_at, updated_at: r.updated_at });
      return { result: {
        club: pick(rows.club[0]),
        entries: rows.entries.slice().sort(byCreated).map(pick),
        ratings: rows.ratings.slice().sort(byCreated).map(pick),
        log: rows.log.slice().sort(byCreated).reverse().slice(0, 100).map(pick),
      } };
    },
  },

  create_club: {
    run: (args, actor, rows, ids) => {
      const clubName = name(args.name);
      if (!clubName) fail("a club needs a name");
      const clubIdNew = ids.shift() ?? fail("no id available");
      const logId = ids.shift() ?? fail("no id available");
      return {
        result: { id: clubIdNew },
        writes: [
          { op: "create", collection: "clubs", id: clubIdNew, data: { name: clubName } },
          { op: "create", collection: "log", id: logId, data: { club_id: String(clubIdNew), action: "create_club", film_slug: "", entry_id: "", detail: clubName, by_name: name(args.by_name) } },
        ],
      };
    },
  },

  add_entry: {
    inputs: clubInputs,
    run: (args, actor, rows, ids) => {
      const c = context(args, actor, rows, ids);
      const slug = slugOf(args.film_slug);
      const existing = c.entries.find(e => e.data.film_slug === slug);
      if (existing) return { result: { id: existing.id, existing: true }, writes: [] };
      const watchedOn = args.watched_on == null ? null : validDate(args.watched_on, "watched_on");
      const state = watchedOn ? "watched" : (c.hasCurrent() ? "upcoming" : "current");
      const id = c.nextId();
      c.writes.push({ op: "create", collection: "entries", id, data: {
        club_id: c.cid, film_slug: slug, state, scheduled_for: null, watched_on: watchedOn, by_name: c.by_name } });
      c.log("add", { id, data: { film_slug: slug } }, state);
      return { result: { id, state }, writes: c.writes };
    },
  },

  make_current: {
    inputs: clubInputs,
    run: (args, actor, rows, ids) => {
      const c = context(args, actor, rows, ids);
      const e = c.entryById(args.entry_id);
      if (e.data.state !== "upcoming") fail("only an upcoming entry can be made current");
      const prev = c.entries.find(x => x.data.state === "current");
      if (prev) { prev.data.state = "upcoming"; c.save(prev); }
      e.data.state = "current";
      c.save(e);
      c.log("make_current", e);
      return { result: { id: e.id }, writes: c.writes };
    },
  },

  set_time: {
    inputs: clubInputs,
    run: (args, actor, rows, ids) => {
      const c = context(args, actor, rows, ids);
      const e = c.entryById(args.entry_id);
      if (e.data.state === "watched") fail("a watched entry cannot be scheduled");
      e.data.scheduled_for = validTime(args.scheduled_for);
      c.save(e);
      c.log("schedule", e, e.data.scheduled_for || "cleared");
      return { result: { id: e.id }, writes: c.writes };
    },
  },

  mark_watched: {
    inputs: clubInputs,
    run: (args, actor, rows, ids) => {
      const c = context(args, actor, rows, ids);
      const e = c.entryById(args.entry_id);
      if (e.data.state === "watched") fail("already watched");
      e.data.watched_on = validDate(args.watched_on, "watched_on");
      e.data.state = "watched";
      e.data.scheduled_for = null;
      c.save(e);
      promote(c);
      c.log("watched", e, e.data.watched_on);
      return { result: { id: e.id }, writes: c.writes };
    },
  },

  mark_unwatched: {
    inputs: clubInputs,
    run: (args, actor, rows, ids) => {
      const c = context(args, actor, rows, ids);
      const e = c.entryById(args.entry_id);
      if (e.data.state !== "watched") fail("not watched");
      e.data.state = c.hasCurrent() ? "upcoming" : "current";
      e.data.watched_on = null;
      c.save(e);
      c.log("unwatched", e);
      return { result: { id: e.id, state: e.data.state }, writes: c.writes };
    },
  },

  remove_entry: {
    inputs: clubAndRatings,
    run: (args, actor, rows, ids) => {
      const c = context(args, actor, rows, ids);
      const e = c.entryById(args.entry_id);
      if (e.data.state === "watched") fail("mark it unwatched before removing it");
      const wasCurrent = e.data.state === "current";
      c.entries.splice(c.entries.indexOf(e), 1);
      c.writes.push({ op: "remove", collection: "entries", id: e.id });
      for (const r of rows.ratings) {
        if (String(r.data.entry_id) === String(e.id)) c.writes.push({ op: "remove", collection: "ratings", id: r.id });
      }
      if (wasCurrent) promote(c);
      c.log("remove", e);
      return { result: { id: e.id }, writes: c.writes };
    },
  },

  rate: {
    inputs: clubAndRatings,
    run: (args, actor, rows, ids) => {
      const c = context(args, actor, rows, ids);
      const e = c.entryById(args.entry_id);
      if (e.data.state !== "watched") fail("only watched films can be rated");
      const score = args.score;
      if (!Number.isInteger(score) || score < 1 || score > 10) fail("score must be a whole number from 1 to 10");
      const note = typeof args.note === "string" ? args.note.trim() : "";
      if (note.length > MAX_NOTE) fail(`note must be at most ${MAX_NOTE} characters`);
      const data = { club_id: c.cid, entry_id: String(e.id), score, note, by_name: c.by_name };
      const mine = rows.ratings.find(r => String(r.data.entry_id) === String(e.id) && r.author === actor);
      if (mine) c.writes.push({ op: "update", collection: "ratings", id: mine.id, data });
      else c.writes.push({ op: "create", collection: "ratings", id: c.nextId(), data });
      c.log("rate", e, String(score));
      return { result: { id: e.id }, writes: c.writes };
    },
  },

  clear_rating: {
    inputs: clubAndRatings,
    run: (args, actor, rows, ids) => {
      const c = context(args, actor, rows, ids);
      const e = c.entryById(args.entry_id);
      const mine = rows.ratings.find(r => String(r.data.entry_id) === String(e.id) && r.author === actor);
      if (!mine) return { result: { id: e.id, cleared: false }, writes: [] };
      c.writes.push({ op: "remove", collection: "ratings", id: mine.id });
      c.log("clear_rating", e);
      return { result: { id: e.id, cleared: true }, writes: c.writes };
    },
  },
};
