// Minimal simulation of the Pages host for server.js: shared collections,
// `inputs` reads (equality `where`), atomic `writes`, server-set author and
// created_at. Used by the Node tests and, in the browser, as window.pages.
(function (root) {
  function makeHost(serverSource, slugs, opts) {
    opts = opts || {};
    const APP = new Function("__SLUGS__", serverSource.split("__FILM_SLUGS__").join("__SLUGS__") + "\nreturn APP;")(slugs);
    const db = opts.db || {};
    let seq = opts.seq || 0;
    let clock = opts.clock || 0;
    const rowsOf = c => (db[c] = db[c] || []);
    const copy = x => JSON.parse(JSON.stringify(x));
    function read(spec) {
      return rowsOf(spec.collection).filter(r => Object.entries(spec.where || {}).every(([k, v]) =>
        k === "id" ? String(r.id) === String(v) : k === "author" ? r.author === v : r.data[k] === v)).map(copy);
    }
    async function call(action, args, actor) {
      const def = APP[action];
      if (!def) throw new Error("unknown action " + action);
      const spec = typeof def === "function" ? { run: def } : def;
      const specs = spec.inputs ? spec.inputs(args || {}) : {};
      const rows = {};
      const read_ids = new Set();
      for (const [k, s] of Object.entries(specs)) {
        rows[k] = read(s);
        rows[k].forEach(r => read_ids.add(s.collection + ":" + r.id));
      }
      const ids = Array.from({ length: 5 }, () => "id" + (++seq));
      const out = spec.run(copy(args || {}), actor, rows, ids.slice(), null);
      const writes = out.writes || [];
      for (const w of writes) {   // validate everything before applying anything
        if (w.op === "create" && !ids.includes(w.id)) throw new Error("create must use a host id");
        if ((w.op === "update" || w.op === "remove") && !read_ids.has(w.collection + ":" + w.id)) throw new Error("update/remove must name a row read in the same call");
      }
      clock += 1;
      const stamp = String(clock).padStart(8, "0");
      for (const w of writes) {
        const col = rowsOf(w.collection);
        if (w.op === "create") col.push({ id: w.id, data: copy(w.data), author: actor, created_at: stamp, updated_at: stamp });
        else if (w.op === "update") { const r = col.find(x => String(x.id) === String(w.id)); r.data = copy(w.data); r.updated_at = stamp; }
        else if (w.op === "remove") col.splice(col.findIndex(x => String(x.id) === String(w.id)), 1);
      }
      return copy(out.result);
    }
    return { call, db };
  }
  root.makeHost = makeHost;
  if (typeof module !== "undefined") module.exports = { makeHost };
})(typeof window !== "undefined" ? window : globalThis);
