/* ============== CLUBS ============== */
/* Shared film club feeds. State lives on the Pages host (server.js); this is
 * the suggestion rule and the view. */
const SHORT_MAX_MIN = 40;   // runtime of this or less is a short
const LONG_MAX_MIN = 180;   // runtime above this is too long

/* The club's rule: most picked, from a director not already taken, not a
 * short, at most LONG_MAX_MIN. `feedSlugs` are every film already in the
 * club's feed (watched, current or upcoming): never suggested again, and
 * their directors are taken. Each suggestion's directors become taken for the
 * next one, so the list reads as a schedule. */
function clubQueue(films, filmBy, feedSlugs, n = 8) {
  const feed = new Set(feedSlugs);
  const taken = new Set();
  for (const slug of feed) for (const d of (filmBy.get(slug)?._directors || [])) taken.add(d);
  const candidates = films
    .filter(f => f._pickCount > 0 && !feed.has(f.film_slug) && f._directors.length &&
      f.runtime_min != null && f.runtime_min > SHORT_MAX_MIN && f.runtime_min <= LONG_MAX_MIN)
    .sort((a, b) => b._pickCount - a._pickCount || (b.avg_rating || 0) - (a.avg_rating || 0) ||
      (a.film_year || 0) - (b.film_year || 0) || (a.film_title || "").localeCompare(b.film_title || ""));
  const out = [];
  for (const f of candidates) {
    if (out.length >= n) break;
    if (f._directors.some(d => taken.has(d))) continue;
    out.push(f);
    f._directors.forEach(d => taken.add(d));
  }
  return out;
}

const CLUB = { clubs: null, id: null, data: null, error: "", busy: false, search: "", addDate: "" };

const hostCall = (action, args) => window.pages.call(action, {
  by_name: window.pages.currentUser?.()?.name || "", ...args });
const todayStr = () => new Date().toLocaleDateString("sv-SE");
const whoOf = row => row.data.by_name || "someone";
const fmtWhen = s => s ? s.replace("T", " ") : "";

/* A response only counts if the user is still looking at the club it was
 * asked for, and it is the latest request for it. */
let clubLoadSeq = 0;
async function clubAct(clubId, action, args) {
  CLUB.busy = true; CLUB.error = "";
  try {
    await hostCall(action, { club_id: clubId, ...args });
    await loadClub(clubId);
  } catch (e) {
    if (CLUB.id === clubId) CLUB.error = e.message || String(e);
  }
  CLUB.busy = false;
  renderView();
}
async function loadClubs() {
  try { CLUB.clubs = await window.pages.call("list_clubs", {}); }
  catch (e) { CLUB.clubs = []; CLUB.error = e.message || String(e); }
}
/* Resolves true when `id`'s data was stored, false when the response was stale. */
async function loadClub(id) {
  const seq = ++clubLoadSeq;
  const stale = () => seq !== clubLoadSeq || CLUB.id !== id;
  let data;
  try {
    data = await window.pages.call("club_state", { club_id: id });
  } catch (e) {
    if (stale()) return false;   // an old request failing must not disturb the current view
    throw e;
  }
  if (stale()) return false;
  CLUB.data = data;
  return true;
}

function renderClubs(root) {
  if (!window.pages || !window.pages.call) {
    root.append(el("section", { class: "club" },
      el("h2", {}, "Film clubs"),
      el("p", { class: "club-note" }, "Clubs keep shared state on the Pages host, so they only work in the published Pages app.")));
    return;
  }
  const body = el("section", { class: "club" });
  root.append(body);
  const paint = () => { body.innerHTML = ""; CLUB.id ? paintClub(body) : paintClubList(body); };
  if (CLUB.id && !CLUB.data) {
    body.append(el("p", { class: "club-note" }, "Loading club…"));
    const id = CLUB.id;
    loadClub(id).then(
      ok => { if (ok && CLUB.id === id) paint(); },
      e => { if (CLUB.id === id) { CLUB.error = e.message; CLUB.id = null; writeHash(); renderView(); } });
  } else if (!CLUB.id && !CLUB.clubs) {
    body.append(el("p", { class: "club-note" }, "Loading clubs…"));
    loadClubs().then(() => { if (!CLUB.id) paint(); });
  } else paint();
}

const appendAll = (parent, ...kids) => parent.append(...kids.filter(Boolean));

function clubError() {
  return CLUB.error ? el("p", { class: "club-error", role: "alert" }, CLUB.error) : null;
}

function paintClubList(body) {
  const input = el("input", { type: "text", placeholder: "Name your club", maxlength: 80, "aria-label": "New club name" });
  appendAll(body,
    el("h2", {}, "Film clubs"),
    el("p", { class: "club-note" }, "Anyone here can open a club, pick films, tick them off and rate them. Every action is logged with who did it."),
    clubError(),
    el("div", { class: "club-grid" }, (CLUB.clubs || []).map(c =>
      el("button", { class: "club-tile", onclick: () => openClub(c.id) }, el("span", { class: "club-name" }, c.name)))),
    el("div", { class: "club-row" }, input,
      el("button", { class: "btn", onclick: async () => {
        const name = input.value.trim(); if (!name) return;
        try { const r = await hostCall("create_club", { name }); CLUB.clubs = null; openClub(r.id); }
        catch (e) { CLUB.error = e.message; renderView(); }
      } }, "Create club")));
}

function openClub(id) {
  clubLoadSeq++;
  CLUB.id = id; CLUB.data = null; CLUB.search = ""; CLUB.error = "";
  writeHash(); renderView();
}

function filmLine(slug) {
  const f = DB.filmBy.get(slug);
  if (!f) return el("span", {}, slug);
  return el("span", { class: "club-film" },
    el("a", { href: "#", onclick: e => { e.preventDefault(); openFilmModal(slug); } }, f.film_title),
    ` (${f.film_year ?? "?"}) · ${f._directors.join(", ")} · ${f.runtime_min ?? "?"} min`);
}

function filmThumb(slug) {
  const f = DB.filmBy.get(slug);
  const box = el("div", { class: "club-thumb" });
  if (f && f.poster_url) {
    const img = el("img", { alt: "", loading: "lazy" });
    img.addEventListener("error", () => img.remove(), { once: true });
    img.src = f.poster_url;
    box.append(img);
  }
  return box;
}

function paintClub(body) {
  const d = CLUB.data;
  const entries = d.entries;
  const cid = d.club.id;   // every action below is bound to the club this data belongs to
  const current = entries.find(e => e.data.state === "current");
  const upcoming = entries.filter(e => e.data.state === "upcoming").sort((a, b) =>
    (a.data.scheduled_for ? 0 : 1) - (b.data.scheduled_for ? 0 : 1) ||
    (a.data.scheduled_for || "").localeCompare(b.data.scheduled_for || "") ||
    String(a.created_at).localeCompare(String(b.created_at)));
  const watched = entries.filter(e => e.data.state === "watched").sort((a, b) => (b.data.watched_on || "").localeCompare(a.data.watched_on || ""));
  const act = (action, e, extra) => clubAct(cid, action, { entry_id: e.id, ...extra });

  const timeInput = e => {
    const t = el("input", { type: "datetime-local", value: e.data.scheduled_for || "", "aria-label": "Watch time" });
    return el("span", { class: "club-inline" }, t,
      el("button", { class: "btn small", disabled: CLUB.busy, onclick: () => act("set_time", e, { scheduled_for: t.value || null }) }, "Set time"));
  };
  const watchedControl = e => {
    const dt = el("input", { type: "date", value: todayStr(), "aria-label": "Date watched" });
    return el("span", { class: "club-inline" }, dt,
      el("button", { class: "btn small", disabled: CLUB.busy, onclick: () => act("mark_watched", e, { watched_on: dt.value }) }, "Mark watched"));
  };

  appendAll(body,
    el("button", { class: "btn small ghost", onclick: () => { clubLoadSeq++; CLUB.id = null; CLUB.data = null; CLUB.clubs = null; writeHash(); renderView(); } }, "← All clubs"),
    el("h2", {}, d.club.data.name),
    el("p", { class: "club-meta" }, "Link to this club: add ",
      el("code", { class: "club-link" }, "#clubs/" + encodeURIComponent(cid)), " to the end of the page address"),
    clubError(),
    el("h3", {}, "Current"),
    current
      ? el("div", { class: "club-current" }, filmThumb(current.data.film_slug),
          el("div", {}, el("div", { class: "club-title" }, filmLine(current.data.film_slug)),
            current.data.scheduled_for ? el("div", { class: "club-when" }, "Scheduled " + fmtWhen(current.data.scheduled_for)) : el("div", { class: "club-when" }, "No time set"),
            el("div", { class: "club-actions" }, timeInput(current), watchedControl(current),
              el("button", { class: "btn small ghost", disabled: CLUB.busy, onclick: () => act("remove_entry", current) }, "Remove"))))
      : el("p", { class: "club-note" }, "Nothing current. Pick a film from the suggestions or search below."),
    el("h3", {}, "Up next"),
    upcoming.length ? el("ul", { class: "club-list" }, upcoming.map(e => el("li", {},
      filmThumb(e.data.film_slug),
      el("div", {}, filmLine(e.data.film_slug),
        e.data.scheduled_for ? el("div", { class: "club-when" }, "Scheduled " + fmtWhen(e.data.scheduled_for)) : null,
        el("div", { class: "club-actions" },
          el("button", { class: "btn small", disabled: CLUB.busy, onclick: () => act("make_current", e) }, "Make current"),
          timeInput(e), watchedControl(e),
          el("button", { class: "btn small ghost", disabled: CLUB.busy, onclick: () => act("remove_entry", e) }, "Remove")))))) :
      el("p", { class: "club-note" }, "Nothing queued."),
    suggestionsEl(entries, cid),
    searchEl(entries, cid),
    el("h3", {}, "Watched"),
    watched.length ? el("ul", { class: "club-list" }, watched.map(e => watchedEl(e, act))) : el("p", { class: "club-note" }, "Nothing watched yet. Add films you have already seen below, with a past date."),
    el("h3", {}, "Activity"),
    el("ul", { class: "club-log" }, d.log.slice(0, 30).map(l => el("li", {},
      `${whoOf(l)} · ${l.data.action.replace("_", " ")}${l.data.film_slug ? " · " + (DB.filmBy.get(l.data.film_slug)?.film_title || l.data.film_slug) : ""}${l.data.detail && l.data.action !== "create_club" ? " (" + l.data.detail + ")" : ""}`)))
  );
}

function suggestionsEl(entries, cid) {
  const picks = clubQueue(DB.films, DB.filmBy, entries.map(e => e.data.film_slug), 8);
  return el("div", {},
    el("h3", {}, "Suggested by the rule"),
    el("p", { class: "club-note" }, `Most picked, a director the club hasn't used, over ${SHORT_MAX_MIN} and up to ${LONG_MAX_MIN} minutes. Each one assumes the ones above it.`),
    el("ol", { class: "club-list suggestions" }, picks.map(f => el("li", {},
      filmThumb(f.film_slug),
      el("div", {}, filmLine(f.film_slug), el("span", { class: "club-meta" }, ` · ${f._pickCount} picks`),
        el("div", { class: "club-actions" },
          el("button", { class: "btn small", disabled: CLUB.busy, onclick: () => clubAct(cid, "add_entry", { film_slug: f.film_slug }) }, "Add to feed")))))));
}

function searchEl(entries, cid) {
  const inFeed = new Set(entries.map(e => e.data.film_slug));
  const input = el("input", { type: "search", value: CLUB.search, placeholder: "Search any film or director", "aria-label": "Search films" });
  const results = el("ul", { class: "club-list" });
  const dateInput = el("input", { type: "date", value: CLUB.addDate || todayStr(), "aria-label": "Date watched for films added as watched" });
  const run = () => {
    CLUB.search = input.value; results.innerHTML = "";
    const q = input.value.trim().toLowerCase();
    if (q.length < 2) return;
    const hits = DB.films.filter(f => !inFeed.has(f.film_slug) &&
      ((f.film_title || "").toLowerCase().includes(q) || f._directors.some(x => x.toLowerCase().includes(q))))
      .sort((a, b) => b._pickCount - a._pickCount).slice(0, 12);
    if (!hits.length) results.append(el("li", {}, "No films found (or already in this club's feed)."));
    for (const f of hits) results.append(el("li", {}, filmThumb(f.film_slug),
      el("div", {}, filmLine(f.film_slug), el("div", { class: "club-actions" },
        el("button", { class: "btn small", disabled: CLUB.busy, onclick: () => clubAct(cid, "add_entry", { film_slug: f.film_slug }) }, "Add to feed"),
        el("button", { class: "btn small ghost", disabled: CLUB.busy, onclick: () => { CLUB.addDate = dateInput.value; clubAct(cid, "add_entry", { film_slug: f.film_slug, watched_on: dateInput.value }); } }, "Add as already watched")))));
  };
  input.addEventListener("input", debounce(run, 200));
  const wrap = el("div", {}, el("h3", {}, "Pick anything else"),
    el("div", { class: "club-row" }, input, el("label", { class: "club-meta" }, "Watched on ", dateInput)), results);
  if (CLUB.search) setTimeout(run);
  return wrap;
}

function watchedEl(e, act) {
  const d = CLUB.data;
  const mine = d.ratings.filter(r => String(r.data.entry_id) === String(e.id));
  const me = window.pages.currentUser?.()?.id;
  const my = mine.find(r => r.author === me);
  const mean = mine.length ? (mine.reduce((s, r) => s + r.data.score, 0) / mine.length).toFixed(1) : null;
  const score = el("select", { "aria-label": "Your score" }, ["", ...Array.from({ length: 10 }, (_, i) => String(i + 1))].map(v =>
    el("option", { value: v, selected: my && String(my.data.score) === v ? "selected" : null }, v || "Score")));
  if (my) score.value = String(my.data.score);
  const note = el("textarea", { maxlength: 1000, rows: 2, placeholder: "Your note (optional)", "aria-label": "Your note" }, my ? my.data.note : "");
  note.value = my ? my.data.note : "";
  return el("li", {}, filmThumb(e.data.film_slug),
    el("div", {}, filmLine(e.data.film_slug),
      el("div", { class: "club-when" }, `Watched ${e.data.watched_on}${mean ? " · mean " + mean + "/10 (" + mine.length + ")" : ""}`),
      el("ul", { class: "club-ratings" }, mine.map(r => el("li", {}, `${whoOf(r)}: ${r.data.score}/10${r.data.note ? " — " + r.data.note : ""}`))),
      el("div", { class: "club-actions" }, score, note,
        el("button", { class: "btn small", disabled: CLUB.busy, onclick: () => { if (score.value) act("rate", e, { score: Number(score.value), note: note.value }); } }, my ? "Update rating" : "Rate"),
        my ? el("button", { class: "btn small ghost", disabled: CLUB.busy, onclick: () => act("clear_rating", e) }, "Clear mine") : null,
        el("button", { class: "btn small ghost", disabled: CLUB.busy, onclick: () => act("mark_unwatched", e) }, "Not watched"))));
}
