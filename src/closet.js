/* ============== MY CLOSET ============== */
/* A person's own picks, kept in the Pages shared data (server.js: closet_picks),
 * public inside the page. The "For you" list is the existing co-pick ranking
 * (computeRecommendations) seeded with the closet. */
/* One shared state for every consumer (the closet view and the popup toggles): `rows` once
 * loaded, `loading` while a load is in flight, `loadError` if the latest load failed, `error`
 * for a failed action, `busy` while an action runs (controls are disabled and a second action
 * is ignored). Whenever one of these changes, notifyClosets() repaints all consumers. */
const CLOSET = { rows: null, error: "", loadError: "", loading: false, busy: false, viewing: null, search: "" };
let closetLoadSeq = 0;

const hasHost = () => !!(window.pages && window.pages.call);
const closetMe = () => (window.pages && window.pages.currentUser ? window.pages.currentUser()?.id : null) || null;

/* Group raw rows into people: {author, name, slugs:Set, latest}. Unknown films are ignored; the
 * name shown is the one on the person's latest row. */
function groupClosets(rows) {
  const people = new Map();
  for (const r of rows || []) {
    if (!DB.filmBy.has(r.film_slug)) continue;
    let p = people.get(r.author);
    if (!p) people.set(r.author, p = { author: r.author, name: "", slugs: new Set(), latest: "" });
    p.slugs.add(r.film_slug);
    if (String(r.created_at) >= p.latest) { p.latest = String(r.created_at); p.name = r.by_name || p.name; }
  }
  for (const p of people.values()) p.name = p.name || "someone";
  return people;
}

/* The real visitors whose closets overlap `mine` most: shared picks, then smaller closet (a
 * more focused match), then name. */
function nearestVisitors(mine, n = 5) {
  const out = [];
  for (const v of DB.visits) {
    const shared = v._picks.filter(p => mine.has(p.film_slug)).length;
    if (shared) out.push({ visit: v, shared, size: v._picks.length });
  }
  out.sort((a, b) => b.shared - a.shared || a.size - b.size || (a.visit.visitor || "").localeCompare(b.visit.visitor || ""));
  return out.slice(0, n);
}

/* Everyone else's closets, most picks in common first, then name. */
function otherClosets(people, meId, mine) {
  const out = [];
  for (const p of people.values()) {
    if (p.author === meId) continue;
    let shared = 0;
    for (const s of p.slugs) if (mine.has(s)) shared++;
    out.push({ person: p, shared });
  }
  out.sort((a, b) => b.shared - a.shared || a.person.name.localeCompare(b.person.name));
  return out;
}

function notifyClosets() {
  refreshClosetToggles();
  if (STATE.view === "closet") renderView();
}

/* Only the latest load counts; superseded loads, successes and failures alike, are ignored. */
async function loadClosets() {
  const seq = ++closetLoadSeq;
  CLOSET.loading = true; CLOSET.loadError = "";
  let ok = false;
  try {
    const rows = await window.pages.call("closets", {});
    if (seq !== closetLoadSeq) return false;
    CLOSET.rows = rows; ok = true;
  } catch (e) {
    if (seq !== closetLoadSeq) return false;
    CLOSET.loadError = e.message || String(e);
  }
  CLOSET.loading = false;
  notifyClosets();
  return ok;
}
function ensureClosets() {
  if (!CLOSET.rows && !CLOSET.loading) loadClosets();
}

async function closetAct(action, slug) {
  if (CLOSET.busy) return;                       // one action at a time
  CLOSET.busy = true; CLOSET.error = "";
  notifyClosets();                               // disables every control at once
  try {
    await window.pages.call(action, { film_slug: slug, by_name: window.pages.currentUser?.()?.name || "" });
    await loadClosets();
  } catch (e) {
    CLOSET.error = e.message || String(e);
  }
  CLOSET.busy = false;
  notifyClosets();
}

const myClosetSet = () => {
  const me = closetMe();
  const p = me && CLOSET.rows ? groupClosets(CLOSET.rows).get(me) : null;
  return p ? p.slugs : new Set();
};

/* The button in the film popup, with a line for errors. Hidden when there is no Pages host. */
function closetToggleEl(slug) {
  if (!hasHost()) return null;
  const btn = el("button", { class: "btn small closet-toggle", type: "button", "data-slug": slug });
  const msg = el("span", { class: "closet-toggle-msg", role: "alert" });
  const paint = () => {
    const inCloset = myClosetSet().has(slug);
    const failed = !CLOSET.rows && CLOSET.loadError;
    btn.textContent = CLOSET.rows ? (inCloset ? "✓ In my closet" : "+ Add to my closet") : (failed ? "Retry my closet" : "My closet…");
    btn.classList.toggle("ghost", !!inCloset);
    btn.disabled = CLOSET.busy || (!CLOSET.rows && !failed);
    btn.title = inCloset ? "Remove from my closet" : "Pick this film for my closet";
    msg.textContent = CLOSET.error || CLOSET.loadError || "";
  };
  btn.addEventListener("click", () => {
    if (!CLOSET.rows) loadClosets();             // recovery after a failed load
    else closetAct(myClosetSet().has(slug) ? "closet_remove" : "closet_add", slug);
  });
  btn._paint = paint;
  paint();
  ensureClosets();
  return el("span", { class: "closet-toggle-wrap" }, btn, msg);
}
function refreshClosetToggles() {
  for (const b of $$(".closet-toggle")) if (b._paint) b._paint();
}

function renderCloset(root) {
  if (!hasHost()) {
    root.append(el("section", { class: "closet" },
      el("h2", {}, "My closet"),
      el("p", { class: "club-note" }, "Closets keep shared state on the Pages host, so they only work in the published Pages app.")));
    return;
  }
  const body = el("section", { class: "closet" });
  root.append(body);
  if (CLOSET.rows) { paintCloset(body); return; }
  if (CLOSET.loadError) {
    body.append(el("h2", {}, "My closet"),
      el("p", { class: "club-error", role: "alert" }, CLOSET.loadError),
      el("button", { class: "btn small", onclick: () => loadClosets() }, "Retry"));
    return;
  }
  body.append(el("p", { class: "club-note" }, "Loading closets…"));
  ensureClosets();                               // notifyClosets() repaints this view when it arrives
}

function closetPosterGrid(slugs, opts = {}) {
  const grid = el("div", { class: "poster-grid" });
  for (const slug of slugs) {
    const f = DB.filmBy.get(slug);
    if (!f) continue;
    const card = posterCard(f, { onClick: () => openFilmModal(slug), recoTag: opts.tag ? opts.tag(slug) : null, title: "Open details" });
    grid.append(opts.remove
      ? el("div", { class: "closet-item" }, card,
          el("button", { class: "btn small ghost", disabled: CLOSET.busy, onclick: () => closetAct("closet_remove", slug) }, "Remove"))
      : card);
  }
  return grid;
}

function paintCloset(body) {
  const me = closetMe();
  const people = groupClosets(CLOSET.rows);
  const mineP = me ? people.get(me) : null;
  const mine = mineP ? mineP.slugs : new Set();
  const viewing = CLOSET.viewing && CLOSET.viewing !== me ? CLOSET.viewing : null;
  const append = (...kids) => body.append(...kids.filter(Boolean));
  const msgText = CLOSET.error || CLOSET.loadError;
  const err = msgText ? el("p", { class: "club-error", role: "alert" }, msgText) : null;

  if (viewing) {
    const other = people.get(viewing);
    if (!other) {
      CLOSET.error = "That closet doesn't exist (any more).";
      CLOSET.viewing = null; writeHash(); renderView();
      return;
    }
    const shared = [...other.slugs].filter(s => mine.has(s)).length;
    append(
      el("button", { class: "btn small ghost", onclick: () => { CLOSET.viewing = null; writeHash(); renderView(); } }, "← My closet"),
      el("div", { class: "club-head" }, el("h2", {}, `${other.name}'s closet`),
        shareLinkEl(pageLink("closet/" + encodeURIComponent(viewing)), "Link to this closet")),
      el("p", { class: "club-note" }, `${other.slugs.size} film${other.slugs.size === 1 ? "" : "s"}` + (me ? ` · ${shared} in common with you` : "")),
      err,
      closetPosterGrid([...other.slugs], { tag: s => mine.has(s) ? "in your closet too" : null }));
    return;
  }

  // my closet
  const input = el("input", { type: "search", value: CLOSET.search, placeholder: "Search any film or director to add", "aria-label": "Search films to add to my closet" });
  const results = el("ul", { class: "club-list" });
  const run = () => {
    CLOSET.search = input.value; results.innerHTML = "";
    const q = input.value.trim().toLowerCase();
    if (q.length < 2) return;
    const hits = DB.films.filter(f => !mine.has(f.film_slug) &&
      ((f.film_title || "").toLowerCase().includes(q) || f._directors.some(d => d.toLowerCase().includes(q))))
      .sort((a, b) => b._pickCount - a._pickCount).slice(0, 10);
    if (!hits.length) results.append(el("li", {}, "No films found (or already in your closet)."));
    for (const f of hits) results.append(el("li", {}, el("div", {}, filmLine(f.film_slug), el("div", { class: "club-actions" },
      el("button", { class: "btn small", disabled: CLOSET.busy, onclick: () => closetAct("closet_add", f.film_slug) }, "Add to my closet")))));
  };
  input.addEventListener("input", debounce(run, 200));

  append(
    el("div", { class: "club-head" }, el("h2", {}, "My closet"),
      me ? shareLinkEl(pageLink("closet/" + encodeURIComponent(me)), "Link to my closet") : null),
    el("p", { class: "club-note" }, mine.size
      ? `${mine.size} film${mine.size === 1 ? "" : "s"}. Everyone with this page can see your closet.`
      : "Pick films you love, from any film's details or with the search below. They become your closet, and we'll suggest films from what the visitors with your taste picked. Everyone with this page can see your closet."),
    err,
    el("h3", {}, "Add a film"), input, results);
  if (mine.size) {
    append(el("h3", {}, "My picks"), closetPosterGrid([...mine], { remove: true }));
    const recos = computeRecommendations([...mine], "all", 24);
    append(el("h3", {}, "For you"),
      el("p", { class: "club-note" }, "Films that visitors who share your picks also picked, best match first."));
    if (recos.length) {
      const grid = el("div", { class: "poster-grid" });
      for (const r of recos) {
        const f = DB.filmBy.get(r.slug);
        if (!f) continue;
        const because = r.because ? DB.filmBy.get(r.because) : null;
        grid.append(posterCard(f, {
          onClick: () => openFilmModal(f.film_slug), title: "Open details",
          recoTag: because ? `<em>${safeHtml(because.film_title)}</em><br>picked by ${r.support} visitor${r.support === 1 ? "" : "s"} who took it`
                           : `picked by ${r.support} visitor${r.support === 1 ? "" : "s"} like you`,
        }));
      }
      append(grid);
    } else append(el("p", { class: "club-note" }, "No visitor has picked any of these films yet."));
    const near = nearestVisitors(mine);
    if (near.length) append(el("h3", {}, "Closest visitors"), el("ul", { class: "club-list closet-near" }, near.map(n =>
      el("li", {}, el("div", {}, el("a", { href: "#", onclick: e => { e.preventDefault(); openVisitorModal(n.visit.visit_slug); } }, n.visit.visitor),
        el("span", { class: "club-meta" }, ` · ${n.shared} of your picks, in a closet of ${n.size}`))))));
  }
  const others = otherClosets(people, me, mine);
  append(el("h3", {}, "Other closets"));
  append(others.length
    ? el("ul", { class: "club-list closet-others" }, others.map(o => el("li", {}, el("div", {},
        el("a", { href: "#", onclick: e => { e.preventDefault(); CLOSET.viewing = o.person.author; writeHash(); renderView(); } }, o.person.name),
        el("span", { class: "club-meta" }, ` · ${o.person.slugs.size} film${o.person.slugs.size === 1 ? "" : "s"} · ${o.shared} in common with you`)))))
    : el("p", { class: "club-note" }, "Nobody else has picked anything yet."));
  if (CLOSET.search) setTimeout(run);
}
