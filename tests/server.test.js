const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { makeHost } = require("./host_sim.js");

const source = fs.readFileSync(path.join(__dirname, "../src/server.js"), "utf8");
const SLUGS = ["a", "b", "c", "d"];

function setup() {
  const host = makeHost(source, SLUGS);
  const as = actor => (action, args) => host.call(action, { by_name: actor.toUpperCase(), ...args }, actor);
  return { host, ann: as("ann"), bob: as("bob") };
}
async function club(s) { return (await s.ann("create_club", { name: "Cinema Club" })).id; }
async function state(s, club_id) { return s.ann("club_state", { club_id }); }
const states = st => Object.fromEntries(st.entries.map(e => [e.data.film_slug, e.data.state]));

test("first add becomes current, later adds upcoming, re-adding is a no-op", async () => {
  const s = setup(); const c = await club(s);
  await s.ann("add_entry", { club_id: c, film_slug: "a" });
  await s.bob("add_entry", { club_id: c, film_slug: "b" });
  const again = await s.bob("add_entry", { club_id: c, film_slug: "a" });
  assert.equal(again.existing, true);
  assert.deepEqual(states(await state(s, c)), { a: "current", b: "upcoming" });
});

test("rejects unknown film, unknown club, bad dates and bad times", async () => {
  const s = setup(); const c = await club(s);
  await assert.rejects(s.ann("add_entry", { club_id: c, film_slug: "nope" }), /unknown film/);
  await assert.rejects(s.ann("add_entry", { club_id: "zzz", film_slug: "a" }), /unknown club/);
  await assert.rejects(s.ann("add_entry", { club_id: c, film_slug: "a", watched_on: "2026-13-40" }), /real date/);
  const { id } = await s.ann("add_entry", { club_id: c, film_slug: "a" });
  await assert.rejects(s.ann("set_time", { club_id: c, entry_id: id, scheduled_for: "tomorrow" }), /real date and time/);
  await assert.rejects(s.ann("create_club", { name: "  " }), /needs a name/);
});

test("scheduling never changes which entry is current", async () => {
  const s = setup(); const c = await club(s);
  await s.ann("add_entry", { club_id: c, film_slug: "a" });
  const b = await s.ann("add_entry", { club_id: c, film_slug: "b" });
  await s.ann("set_time", { club_id: c, entry_id: b.id, scheduled_for: "2026-01-01T19:00" });
  assert.deepEqual(states(await state(s, c)), { a: "current", b: "upcoming" });
});

test("make_current swaps and keeps exactly one current", async () => {
  const s = setup(); const c = await club(s);
  await s.ann("add_entry", { club_id: c, film_slug: "a" });
  const b = await s.ann("add_entry", { club_id: c, film_slug: "b" });
  await s.ann("make_current", { club_id: c, entry_id: b.id });
  assert.deepEqual(states(await state(s, c)), { a: "upcoming", b: "current" });
  await assert.rejects(s.ann("make_current", { club_id: c, entry_id: b.id }), /only an upcoming/);
});

test("marking current watched promotes earliest scheduled, then untimed by creation order", async () => {
  const s = setup(); const c = await club(s);
  const a = await s.ann("add_entry", { club_id: c, film_slug: "a" });
  await s.ann("add_entry", { club_id: c, film_slug: "b" });
  const cc = await s.ann("add_entry", { club_id: c, film_slug: "c" });
  const d = await s.ann("add_entry", { club_id: c, film_slug: "d" });
  await s.ann("set_time", { club_id: c, entry_id: d.id, scheduled_for: "2026-05-02T19:00" });
  await s.ann("set_time", { club_id: c, entry_id: cc.id, scheduled_for: "2026-05-01T19:00" });
  await s.ann("mark_watched", { club_id: c, entry_id: a.id, watched_on: "2026-04-30" });
  assert.deepEqual(states(await state(s, c)), { a: "watched", b: "upcoming", c: "current", d: "upcoming" });
});

test("watching an upcoming entry leaves the current one alone; no upcoming leaves no current", async () => {
  const s = setup(); const c = await club(s);
  const a = await s.ann("add_entry", { club_id: c, film_slug: "a" });
  const b = await s.ann("add_entry", { club_id: c, film_slug: "b" });
  await s.ann("mark_watched", { club_id: c, entry_id: b.id, watched_on: "2026-04-30" });
  assert.deepEqual(states(await state(s, c)), { a: "current", b: "watched" });
  await s.ann("mark_watched", { club_id: c, entry_id: a.id, watched_on: "2026-05-01" });
  assert.deepEqual(states(await state(s, c)), { a: "watched", b: "watched" });
});

test("unwatched becomes current only when the club has none", async () => {
  const s = setup(); const c = await club(s);
  const a = await s.ann("add_entry", { club_id: c, film_slug: "a", watched_on: "2026-01-01" });
  assert.equal(a.state, "watched");
  assert.equal((await s.ann("mark_unwatched", { club_id: c, entry_id: a.id })).state, "current");
  const b = await s.ann("add_entry", { club_id: c, film_slug: "b", watched_on: "2026-01-02" });
  assert.equal((await s.ann("mark_unwatched", { club_id: c, entry_id: b.id })).state, "upcoming");
});

test("removing the current promotes the next; watched entries cannot be removed", async () => {
  const s = setup(); const c = await club(s);
  const a = await s.ann("add_entry", { club_id: c, film_slug: "a" });
  await s.ann("add_entry", { club_id: c, film_slug: "b" });
  await s.ann("remove_entry", { club_id: c, entry_id: a.id });
  assert.deepEqual(states(await state(s, c)), { b: "current" });
  const w = await s.ann("add_entry", { club_id: c, film_slug: "c", watched_on: "2026-01-01" });
  await assert.rejects(s.ann("remove_entry", { club_id: c, entry_id: w.id }), /unwatched/);
});

test("one rating per member, replaced on re-rate, only own can be cleared, validation", async () => {
  const s = setup(); const c = await club(s);
  const a = await s.ann("add_entry", { club_id: c, film_slug: "a", watched_on: "2026-01-01" });
  await s.ann("rate", { club_id: c, entry_id: a.id, score: 7, note: "good" });
  await s.ann("rate", { club_id: c, entry_id: a.id, score: 9, note: "better" });
  await s.bob("rate", { club_id: c, entry_id: a.id, score: 4 });
  let st = await state(s, c);
  assert.deepEqual(st.ratings.map(r => [r.author, r.data.score]).sort(), [["ann", 9], ["bob", 4]]);
  await assert.rejects(s.ann("rate", { club_id: c, entry_id: a.id, score: 11 }), /1 to 10/);
  await assert.rejects(s.ann("rate", { club_id: c, entry_id: a.id, score: 5.5 }), /1 to 10/);
  await assert.rejects(s.ann("rate", { club_id: c, entry_id: a.id, score: 5, note: "x".repeat(1001) }), /1000/);
  assert.equal((await s.ann("clear_rating", { club_id: c, entry_id: a.id })).cleared, true);
  assert.equal((await s.ann("clear_rating", { club_id: c, entry_id: a.id })).cleared, false);
  st = await state(s, c);
  assert.deepEqual(st.ratings.map(r => r.author), ["bob"]);
  const b = await s.ann("add_entry", { club_id: c, film_slug: "b" });
  await assert.rejects(s.ann("rate", { club_id: c, entry_id: b.id, score: 5 }), /only watched/);
});

test("the log records every action with its author and is never modified or removed", async () => {
  const s = setup(); const c = await club(s);
  const a = await s.ann("add_entry", { club_id: c, film_slug: "a" });
  const b = await s.bob("add_entry", { club_id: c, film_slug: "b" });
  await s.bob("make_current", { club_id: c, entry_id: b.id });
  await s.ann("set_time", { club_id: c, entry_id: a.id, scheduled_for: "2026-05-01T19:00" });
  await s.ann("mark_watched", { club_id: c, entry_id: b.id, watched_on: "2026-05-01" });
  await s.bob("rate", { club_id: c, entry_id: b.id, score: 8 });
  await s.bob("clear_rating", { club_id: c, entry_id: b.id });
  await s.ann("mark_unwatched", { club_id: c, entry_id: b.id });
  await s.ann("remove_entry", { club_id: c, entry_id: a.id });
  const st = await state(s, c);
  const actions = st.log.map(l => l.data.action).reverse();
  assert.deepEqual(actions, ["create_club", "add", "add", "make_current", "schedule", "watched", "rate", "clear_rating", "unwatched", "remove"]);
  assert.equal(st.log.find(l => l.data.action === "make_current").author, "bob");
  const before = JSON.stringify(s.host.db.log);
  await s.ann("add_entry", { club_id: c, film_slug: "c" });
  assert.ok(JSON.stringify(s.host.db.log).startsWith(before.slice(0, -1)), "earlier log rows untouched");
});

test("clubs are listed and states are isolated per club", async () => {
  const s = setup();
  const c1 = await club(s);
  const c2 = (await s.bob("create_club", { name: "Other" })).id;
  await s.ann("add_entry", { club_id: c1, film_slug: "a" });
  assert.equal((await state(s, c2)).entries.length, 0);
  assert.deepEqual((await s.ann("list_clubs", {})).map(c => c.name), ["Cinema Club", "Other"]);
});

test("impossible calendar dates and times are rejected and change nothing", async () => {
  const s = setup(); const c = await club(s);
  const a = await s.ann("add_entry", { club_id: c, film_slug: "a" });
  const before = JSON.stringify([s.host.db.entries, s.host.db.log]);
  for (const d of ["2026-02-31", "2027-02-29", "2026-04-31", "2026-00-10", "2026-13-01"]) {
    await assert.rejects(s.ann("add_entry", { club_id: c, film_slug: "b", watched_on: d }), /real date/, d);
    await assert.rejects(s.ann("mark_watched", { club_id: c, entry_id: a.id, watched_on: d }), /real date/, d);
  }
  for (const t of ["2026-02-31T19:00", "2026-05-01T25:00", "2026-05-01T19:60", "2026-05-01 19:00"]) {
    await assert.rejects(s.ann("set_time", { club_id: c, entry_id: a.id, scheduled_for: t }), /real date and time/, t);
  }
  assert.equal(JSON.stringify([s.host.db.entries, s.host.db.log]), before);
  // leap day is real in a leap year
  await s.ann("add_entry", { club_id: c, film_slug: "b", watched_on: "2028-02-29" });
  await s.ann("set_time", { club_id: c, entry_id: a.id, scheduled_for: "2028-02-29T23:59" });
});
