"use strict";
/* Next Reel: pick services, set filters, spin three, pick one.
   Your setup lives on this device (localStorage). The server answers spins
   (live from TMDB, or the bundled list) and runs watch-party rooms. */

const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const view = $("#view");

const saved = {
  get(k, d) { try { const v = localStorage.getItem("nextreel." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("nextreel." + k, JSON.stringify(v)); } catch { /* private mode: fine */ } },
  del(k) { try { localStorage.removeItem("nextreel." + k); } catch { /* ignore */ } },
};

let CFG = null, SVC = {};
const TITLES = {};                            // every title we've been sent, by id
let prefs = null;
let seen = saved.get("seen", {});            // id -> {verdict, at, title, year}
let spin = { picks: [], spares: [], winner: null, rolling: false, seeds: [] };
let match = { total: null, source: null, key: "" };
let room = saved.get("room", null);          // {code, player, host_token, vote}
let roomState = null, pollTimer = null, myName = saved.get("name", "");

const ACCESS = [["sub", "My subscriptions"], ["free", "Free"], ["rent", "Rent"], ["buy", "Buy"]];
const GENRE_NAMES = { horror: "Horror", thriller: "Thriller", comedy: "Comedy", scifi: "Sci-fi", fantasy: "Fantasy",
  mystery: "Mystery", drama: "Drama", action: "Action", crime: "Crime", animation: "Animation", family: "Family",
  romance: "Romance", documentary: "Documentary" };
const TAG_NAMES = { halloween: "Halloween night", cozy: "Cozy", slasher: "Slasher", supernatural: "Supernatural",
  haunted: "Haunted house", folk: "Folk horror", creature: "Creature feature", zombie: "Zombies", vampire: "Vampires",
  witch: "Witches", psychological: "Psychological", "found-footage": "Found footage", "horror-comedy": "Horror-comedy",
  classic: "Classic (pre-1990)", international: "International" };
// Horror styles only make sense with Horror picked; Extras work with any genre.
const HORROR_STYLES = ["slasher", "supernatural", "haunted", "folk", "creature", "zombie", "vampire", "witch",
  "psychological", "found-footage", "horror-comedy"];
const EXTRAS = ["halloween", "classic", "international"];
const LENGTHS = [[0, "Any length"], [100, "Under 100 min"], [120, "Under 2 hrs"]];
const live = () => CFG.source === "tmdb";
const scares = () => live()
  ? [["any", "Any"], ["cozy", "Cozy (PG-13 & under)"], ["terrifying", "Rated R"]]
  : [["any", "Any"], ["cozy", "Cozy"], ["spooky", "Spooky"], ["terrifying", "Terrifying"]];

const PRESETS = [
  { id: "fright", name: "🎃 Fright Night", set: { genres: ["horror"], tags: [], scare: "any" } },
  { id: "halloween", name: "🕯️ Halloween", set: { genres: [], tags: ["halloween"], scare: "any" } },
  { id: "cozy", name: "🧙 Cozy spooky", set: { genres: ["horror", "fantasy"], tags: [], scare: "cozy" } },
  { id: "terror", name: "💀 Terrify me", set: { genres: ["horror"], tags: [], scare: "terrifying" } },
  { id: "free", name: "🆓 Free tonight", set: { access: { sub: false, free: true, rent: false, buy: false } } },
  { id: "any", name: "🎲 Anything", set: { genres: [], tags: [], scare: "any", kind: "both", maxMinutes: 0 } },
];

function defaults() {
  const ids = kind => CFG.services.filter(s => s.kind === kind).map(s => s.id);
  return { subs: [], free: ids("free"), stores: ids("store"), access: { sub: true, free: true, rent: false, buy: false },
    kind: "both", genres: [], tags: [], scare: "any", maxMinutes: 0, theme: "auto", preset: null, setUp: false };
}
function save() { saved.set("prefs", prefs); }

/* --- theme ---------------------------------------------------------------- */

function halloweenOn() {
  return prefs.theme === "halloween" || (prefs.theme === "auto" && new Date().getMonth() === 9);
}
function applyTheme() {
  const on = halloweenOn();
  document.documentElement.classList.toggle("halloween", on);
  $('meta[name="theme-color"]').content = on ? "#0C0A10" : "#0E0E11";
}

/* --- matching ------------------------------------------------------------- */

function mySubs() {
  const out = new Set(prefs.subs);
  for (const s of prefs.subs) for (const inc of CFG.includes[s] || []) out.add(inc);
  return out;
}
const svcName = id => (SVC[id] ? SVC[id].name : id);

// Ways I can actually watch this, in the order worth showing. Same rule as usable() in lib/core.py.
function offers(t) {
  const a = prefs.access, subs = mySubs(), out = [];
  if (a.sub) for (const s of t.subs) if (subs.has(s)) out.push({ kind: "sub", label: "On " + svcName(s) });
  if (a.free) for (const s of t.free) if (prefs.free.includes(s)) out.push({ kind: "free", label: "Free on " + svcName(s) });
  const rentAt = t.rent.filter(s => prefs.stores.includes(s));
  if (a.rent && rentAt.length) out.push({ kind: "rent", label: t.rentFrom ? `Rent from $${t.rentFrom.toFixed(2)}` : "Rent on " + svcName(rentAt[0]) });
  const buyAt = t.buy.filter(s => prefs.stores.includes(s));
  if (a.buy && buyAt.length) out.push({ kind: "buy", label: t.kind === "tv" ? "Buy by the season" : "Buy on " + svcName(buyAt[0]) });
  return out;
}

function query(seed) {
  return new URLSearchParams({
    kind: prefs.kind, access: ACCESS.map(([k]) => k).filter(k => prefs.access[k]).join(","),
    subs: [...prefs.subs].sort().join(","), free: [...prefs.free].sort().join(","), stores: [...prefs.stores].sort().join(","),
    genres: [...prefs.genres].sort().join(","), tags: [...prefs.tags].sort().join(","), scare: prefs.scare,
    max: prefs.maxMinutes, seed,
  }).toString();
}

async function fetchBatch(seed) {
  let r;
  try { r = await fetch("/api/spin?" + query(seed)); } catch { r = null; }
  if (!r || !r.ok) throw new Error("Couldn't reach the reels. Check your connection.");
  const data = await r.json();
  for (const t of data.titles) TITLES[t.id] = t;
  return data;
}

// The match count, fetched with seed 0 so it shares the edge cache with a first spin.
async function refreshCount() {
  const key = query(0);
  if (match.key === key && match.total != null) return paintCount();
  match = { total: null, source: null, key };
  paintCount();
  try {
    const d = await fetchBatch(0);
    if (match.key !== key) return;
    match = { total: d.total, source: d.source, key };
  } catch { match = { total: -1, source: null, key }; }
  paintCount();
}

function countText() {
  const n = match.total;
  if (n == null) return "Counting…";
  if (n < 0) return "Couldn't reach the reels. Check your connection.";
  const shown = match.source === "tmdb" && n >= 1000 ? (Math.floor(n / 100) * 100).toLocaleString() + "+" : n.toLocaleString();
  return `<b>${shown}</b> match${n === 1 ? "" : "es"}`;
}

function paintCount() {
  const n = match.total;
  document.querySelectorAll(".count").forEach(el => { el.innerHTML = countText(); });
  const btn = $("#spin");
  if (btn && !spin.rolling) btn.disabled = n === 0;
  const done = $("#sheetDone");
  if (done) done.textContent = n == null ? "Show titles" : n === 0 ? "Nothing matches" : `Show ${countText().replace(/<\/?b>/g, "").replace(/ match(es)?$/, "")} titles`;
  const hint = $("#hint");
  if (hint) hint.textContent = n === 0 ? loosenHint() : "";
}

function loosenHint() {
  const a = prefs.access;
  if (!Object.values(a).some(Boolean)) return "Turn on at least one way to watch.";
  if (a.sub && !a.free && !a.rent && !a.buy && !prefs.subs.length) return "Pick your subscriptions in Services, or allow free or rentals.";
  if (prefs.scare !== "any") return "Try a different scare level.";
  if (prefs.tags.length) return "Drop a style or extra or two.";
  if (prefs.genres.length) return "Add another genre.";
  return "Allow rentals to open up nearly everything.";
}

/* --- shared bits ---------------------------------------------------------- */

function scareIcons(n) {
  if (!n) return "";
  return ` · <span title="Scare level ${n} of 5" aria-label="Scare level ${n} of 5">${halloweenOn() ? "🎃" : "Scare"} ${n}/5</span>`;
}

function metaLine(t) {
  const len = t.kind === "movie" ? (t.minutes ? `${t.minutes} min` : "")
    : (t.seasons ? `${t.seasons} season${t.seasons > 1 ? "s" : ""}` : "");
  return [t.year, t.kind === "movie" ? "Movie" : "Series", len, t.rating].filter(Boolean).map(esc).join(" · ");
}

function whereTags(t, max = 2, also = false) {
  const os = offers(t);
  const tags = os.slice(0, max).map(o => `<span class="tag ${o.kind}">${esc(o.label)}</span>`);
  if (also) {
    const subs = mySubs();
    const others = [...t.subs.filter(s => !subs.has(s)).map(svcName), ...(t.others || [])];
    if (others.length) tags.push(`<span class="tag">Also on ${esc([...new Set(others)].slice(0, 3).join(", "))}</span>`);
  }
  return tags.length ? `<div class="where">${tags.join("")}</div>` : "";
}

const findLink = t => t.link || `https://www.justwatch.com/us/search?q=${encodeURIComponent(t.title)}`;
const poster = (t, cls = "") => t.poster
  ? `<img class="poster ${cls}" src="${esc(t.poster)}" alt="" loading="lazy" width="76" height="114">`
  : `<div class="poster ph ${cls}" aria-hidden="true">${esc((t.title || "?").trim()[0] || "?")}</div>`;

function titleCard(t, body = "") {
  return `<div class="face"><div class="tc">${poster(t)}<div class="tc-text">
    <h3>${esc(t.title)}</h3>
    <div class="meta">${metaLine(t)}${scareIcons(t.scare)}</div>
    ${whereTags(t)}
    <p class="blurb clamp">${esc(t.blurb)}</p>
  </div></div></div>${body}`;
}

function winnerCard(t, kicker, actions) {
  return `<div class="card reel winner winner-card">
    <div class="kicker">${esc(kicker)}</div>
    ${poster(t)}
    <h3>${esc(t.title)}</h3><div class="meta">${metaLine(t)}${scareIcons(t.scare)}</div>
    ${whereTags(t, 3, true)}
    <p class="blurb">${esc(t.blurb)}</p>
    <div class="actions">${actions}</div></div>`;
}

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toast.t);
  toast.t = setTimeout(() => { el.hidden = true; }, 2600);
}

/* --- Spin ----------------------------------------------------------------- */

function chip(group, value, label, on) {
  return `<button type="button" class="chip" data-chip="${group}" data-value="${esc(value)}" aria-pressed="${on}">${esc(label)}</button>`;
}
function seg(group, options, current) {
  return `<div class="seg" role="group">${options.map(([v, l]) =>
    `<button type="button" data-seg="${group}" data-value="${esc(v)}" aria-pressed="${String(v) === String(current)}">${esc(l)}</button>`).join("")}</div>`;
}

// What's narrowing the spin right now, as removable pills. Access ("how") is
// setup rather than mood, so it lives in the sheet and the count line.
function activePills() {
  const out = [];
  if (prefs.kind !== "both") out.push(["kind", "both", prefs.kind === "movie" ? "Movies" : "Shows"]);
  for (const g of prefs.genres) out.push(["genres", g, GENRE_NAMES[g] || g]);
  for (const t of prefs.tags) out.push(["tags", t, TAG_NAMES[t] || t]);
  const sc = scares().find(([v]) => v === prefs.scare);
  if (prefs.scare !== "any" && sc) out.push(["scare", "any", sc[1]]);
  if (prefs.maxMinutes) out.push(["maxMinutes", 0, LENGTHS.find(([v]) => v === prefs.maxMinutes)[1]]);
  return out;
}

function howLine() {
  const on = ACCESS.filter(([k]) => prefs.access[k]).map(([, l]) => l);
  return on.length ? on.join(" · ") : "No way to watch selected";
}

function renderSheet() {
  const body = $("#sheetBody");
  const horror = prefs.genres.includes("horror");
  const styles = CFG.tags.filter(t => HORROR_STYLES.includes(t));
  const extras = CFG.tags.filter(t => EXTRAS.includes(t));
  body.innerHTML = `
    <h2>Watch</h2>${seg("kind", [["both", "Both"], ["movie", "Movies"], ["tv", "Shows"]], prefs.kind)}
    <h2>How</h2><div class="chips">${ACCESS.map(([k, l]) => chip("access", k, l, prefs.access[k])).join("")}</div>
    <h2>Genre</h2><div class="chips">${CFG.genres.map(g => chip("genres", g, GENRE_NAMES[g] || g, prefs.genres.includes(g))).join("")}</div>
    ${horror && styles.length ? `<h2>Horror style</h2><div class="chips">${styles.map(g => chip("tags", g, TAG_NAMES[g] || g, prefs.tags.includes(g))).join("")}</div>` : ""}
    ${extras.length ? `<h2>Extras</h2><div class="chips">${extras.map(g => chip("tags", g, TAG_NAMES[g] || g, prefs.tags.includes(g))).join("")}</div>` : ""}
    <h2>Scare level</h2>${seg("scare", scares(), prefs.scare)}
    <h2>Movie length</h2>${seg("maxMinutes", LENGTHS, prefs.maxMinutes)}
    <p class="note" style="text-align:left">Your services are set on the <a href="#services">Services</a> tab.</p>`;
  paintCount();
}

function openSheet() {
  renderSheet();
  const d = $("#sheet");
  if (!d.open) d.showModal();
}

function renderSpin() {
  const spooky = halloweenOn();
  const pills = activePills();
  const banner = !prefs.setUp ? `<div class="banner"><span>Add your services so every pick is something you can watch.</span><a href="#services">Set up →</a></div>` : "";
  view.innerHTML = `
    <h1>Next Reel</h1>
    <p class="sub">${spooky ? "Pick your poison." : "Three come up. One gets watched."}</p>
    ${banner}
    <div class="moods" role="group" aria-label="Quick picks">${PRESETS.map(p =>
      `<button type="button" class="mood ${prefs.preset === p.id ? "on" : ""}" data-preset="${p.id}">${esc(p.name)}</button>`).join("")}</div>
    <div class="filterbar">
      ${pills.length ? "" : `<span class="muted small">Any genre</span>`}
      ${pills.map(([g, v, l]) => `<button type="button" class="pill" data-clear="${g}" data-value="${esc(v)}" aria-label="Remove ${esc(l)}">${esc(l)} <span aria-hidden="true">×</span></button>`).join("")}
      <button type="button" class="filters-btn" data-act="filters">Filters${pills.length ? ` <b>${pills.length}</b>` : ""}</button>
    </div>
    <button class="big" id="spin">${spooky ? "Spin if you dare" : "Spin"}</button>
    <p class="count"></p>
    <p class="note" id="hint"></p>
    <div class="reels" id="reels"></div>
    <p class="note">${esc(howLine())}${live() ? "" : ` · availability as of ${esc(CFG.snapshot)}`}</p>`;
  renderReels();
  refreshCount();
}

function renderReels() {
  const box = $("#reels");
  if (!box || spin.rolling) return;
  if (spin.winner) {
    const t = TITLES[spin.winner];
    box.innerHTML = winnerCard(t, halloweenOn() ? "Tonight's nightmare" : "Tonight's pick", `
      <a class="btn" href="${esc(findLink(t))}" target="_blank" rel="noopener noreferrer">Where to watch</a>
      <div class="row"><button class="ghost grow" data-act="watched" data-id="${esc(t.id)}">Mark watched</button>
      <button class="ghost grow" data-act="back">Back</button></div>`);
    return;
  }
  box.innerHTML = spin.picks.map(id => `<div class="card reel">${titleCard(TITLES[id], `<div class="card-actions">
      <button data-act="pick" data-id="${esc(id)}">Watch this</button>
      <div class="minor">
        <button class="text" data-act="swap" data-id="${esc(id)}">Swap</button>
        <button class="text" data-act="seen" data-id="${esc(id)}">Seen it</button>
        <button class="text" data-act="nope" data-id="${esc(id)}">Pass</button>
      </div></div>`)}</div>`).join("");
}
function rollInto(box, finals, blur, onDone) {
  box.innerHTML = finals.map(t => `<div class="card reel rolling">${titleCard(t)}</div>`).join("");
  const reels = [...box.children];
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const start = performance.now();
  const stopAt = finals.map((_, i) => (reduce ? 0 : 700 + i * 420));
  const tick = () => {
    const now = performance.now() - start;
    let still = false;
    reels.forEach((el, i) => {
      if (!el.classList.contains("rolling")) return;
      if (now >= stopAt[i]) {
        el.classList.remove("rolling");
        el.classList.add("landed");
        el.querySelector(".face").outerHTML = `<div class="face">${titleCard(finals[i])}</div>`;
      } else {
        still = true;
        el.querySelector(".face").innerHTML = titleCard(blur[Math.floor(Math.random() * blur.length)] || finals[i]);
      }
    });
    if (still) setTimeout(tick, 70);
    else onDone();
  };
  tick();
}

function shuffle(a) {
  a = [...a];
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
  return a;
}

// Ten seeds = ten different pages of results; go through them before repeating.
function nextSeed() {
  if (!spin.seeds.length) spin.seeds = shuffle([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
  return spin.seeds.pop();
}

async function doSpin() {
  if (spin.rolling) return;
  const btn = $("#spin");
  spin.rolling = true;
  btn.disabled = true;
  btn.textContent = "Spinning…";
  let fresh = [];
  try {
    for (let tries = 0; tries < 3 && fresh.length < 3; tries++) {
      const d = await fetchBatch(nextSeed());
      fresh = [...new Map([...fresh, ...d.titles.filter(t => !seen[t.id])].map(t => [t.id, t])).values()];
      if (d.total <= d.titles.length) break;      // that was everything there is
    }
  } catch (e) { toast(e.message); }
  if (!fresh.length) {
    spin.rolling = false;
    btn.disabled = false;
    btn.textContent = halloweenOn() ? "Spin if you dare" : "Spin";
    if (navigator.onLine !== false) toast(Object.keys(seen).length ? "You've seen everything that came up. Loosen a filter or clear Watched." : loosenHint());
    return;
  }
  const order = shuffle(fresh);
  const finals = order.slice(0, 3);
  spin = { ...spin, picks: finals.map(t => t.id), spares: order.slice(3).map(t => t.id), winner: null, rolling: true };
  rollInto($("#reels"), finals, fresh, () => {
    spin.rolling = false;
    btn.disabled = false;
    btn.textContent = halloweenOn() ? "Spin again… if you dare" : "Spin again";
    renderReels();
  });
  // After the reels exist (before, the page may be too short to scroll). Instant,
  // not smooth: the reels re-render every few frames and cancel a smooth scroll.
  window.scrollTo(0, btn.getBoundingClientRect().top + scrollY - 12);
}

function swap(id) {
  const next = spin.spares.find(x => !seen[x] && !spin.picks.includes(x));
  spin.spares = spin.spares.filter(x => x !== next);
  if (!next) { spin.picks = spin.picks.filter(x => x !== id); toast("That's the last of this batch. Spin again for more."); }
  else spin.picks = spin.picks.map(x => (x === id ? next : x));
  renderReels();
}

function markSeen(id, verdict) {
  const t = TITLES[id] || {};
  seen[id] = { verdict, at: Date.now(), title: t.title || id, year: t.year || "" };
  saved.set("seen", seen);
}

/* --- Party ---------------------------------------------------------------- */

async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json", "X-Next-Reel": "1" }, body: JSON.stringify(body) };
  let r;
  try { r = await fetch(path, opt); } catch { const e = new Error("You're offline, or the server is."); e.status = 0; throw e; }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { const e = new Error(data.error || "Something went wrong."); e.status = r.status; throw e; }
  return data;
}
const roomCall = (action, extra) => api("/api/rooms", { action, code: room && room.code, ...extra });

function setRoom(r) {
  room = r;
  if (r) saved.set("room", r); else saved.del("room");
}

// The server never says who voted for what, so this phone remembers its own vote.
function withMyVote(s) {
  if (room && room.vote && room.vote.round === s.round) s.myVote = room.vote.id;
  for (const t of s.candidates || []) TITLES[t.id] = t;
  return s;
}

function stopPoll() { clearInterval(pollTimer); pollTimer = null; }
function startPoll() {
  stopPoll();
  pollTimer = setInterval(async () => {
    if (!room || location.hash !== "#party" || document.hidden) return;
    try {
      const s = withMyVote(await api("/api/rooms?code=" + room.code));
      const changed = JSON.stringify(s) !== JSON.stringify(roomState);
      roomState = s;
      if (changed) renderParty();
    } catch (e) {
      if (e.status === 404) { setRoom(null); roomState = null; toast("That watch party has ended."); renderParty(); }
    }
  }, 1500);
}

function tied(tally) {
  const v = Object.values(tally), top = Math.max(...v);
  return v.filter(n => n === top).length > 1;
}

function joinFromLink() {
  const m = /[?&]join=([A-Za-z]{4})/.exec(location.search);
  return m ? m[1].toUpperCase() : null;
}

function renderParty() {
  if (!CFG.parties) {
    view.innerHTML = `<h1>Watch party</h1><div class="card empty"><h3>Almost ready</h3>
      <p class="muted">Watch parties switch on once this server's database is connected.</p></div>`;
    return;
  }
  if (!room) {
    stopPoll();
    view.innerHTML = `<h1>Watch party</h1>
      <p class="sub">Everyone votes from their own phone, and the winner reveals to the room at once.</p>
      <div class="card"><h3>Start one</h3>
        <p class="muted small">Your services and filters decide what comes up.</p>
        <input type="text" id="hostName" placeholder="Your name" maxlength="24" value="${esc(myName)}" autocomplete="nickname">
        <div style="height:10px"></div><button id="create" style="width:100%">Start a watch party</button></div>
      <div class="card"><h3>Join one</h3>
        <input type="text" id="joinCode" class="code" placeholder="CODE" maxlength="4" autocapitalize="characters" autocomplete="off" value="${esc(joinFromLink() || "")}">
        <div style="height:10px"></div>
        <input type="text" id="joinName" placeholder="Your name" maxlength="24" value="${esc(myName)}" autocomplete="nickname">
        <div style="height:10px"></div><button id="join" class="ghost" style="width:100%">Join</button></div>`;
    return;
  }
  const s = roomState;
  if (!s) { view.innerHTML = `<h1>Watch party</h1><p class="sub">Loading room…</p>`; return; }
  const host = !!room.host_token, me = room.player;
  const players = s.players.map(p => `<span class="player ${p.voted ? "voted" : ""}">${esc(p.name)}${p.id === s.host ? " ★" : ""}${p.id === me ? " (you)" : ""}</span>`).join("");
  let body = "";
  if (s.status === "lobby") {
    body = host
      ? `<button class="big" data-act="room-spin">Spin for the room</button>
         <p class="note">Your filters from the Spin tab decide what comes up. Everyone sees the same three.</p>`
      : `<div class="card empty"><h3>Waiting for the host to spin…</h3></div>`;
  } else if (s.status === "voting") {
    body = `<p class="count"><b>${s.voted}</b> of ${s.players.length} voted</p>` + s.candidates.map(t => `
      <div class="card reel ${s.myVote === t.id ? "winner" : ""}">${titleCard(t, `<div class="card-actions">
        <button data-act="vote" data-id="${esc(t.id)}" ${s.myVote === t.id ? "disabled" : ""}>${s.myVote === t.id ? "✓ Your vote" : "Vote for this"}</button></div>`)}</div>`).join("")
      + (host ? `<button class="big" data-act="reveal">Reveal the winner</button>
      <div style="height:8px"></div><button class="ghost" style="width:100%" data-act="room-spin">Spin three new ones</button>` : "");
  } else {
    const t = s.candidates.find(c => c.id === s.winner);
    const total = Object.values(s.tally).reduce((a, b) => a + b, 0) || 1;
    body = winnerCard(t, halloweenOn() ? "The room has chosen its fate" : "The room picked",
        `<a class="btn" href="${esc(findLink(t))}" target="_blank" rel="noopener noreferrer">Where to watch</a>`) + `
      <div class="card"><h2 style="margin-top:0">Votes</h2>${s.candidates.map(c => `
        <div style="margin-bottom:10px"><div class="row spread"><span>${esc(c.title)}</span><b>${s.tally[c.id]}</b></div>
        <div class="bar"><i style="width:${(100 * s.tally[c.id]) / total}%"></i></div></div>`).join("")}
        ${tied(s.tally) ? `<p class="small muted">A tie, so the wheel decided.</p>` : ""}</div>
      ${host ? `<button class="big" data-act="room-spin">Spin again</button>` : ""}`;
  }
  const link = `${location.origin}/?join=${s.code}`;
  view.innerHTML = `<h1>Watch party</h1>
    <div class="card"><div class="muted small" style="text-align:center">Room code</div>
      <div class="bigcode">${esc(s.code)}</div>
      <p class="small muted" style="text-align:center;margin:0 0 10px">Others open Next Reel → Party → Join, or tap your invite link.</p>
      <div class="row" style="justify-content:center;margin-bottom:12px"><button class="ghost small" data-act="share" data-link="${esc(link)}">Share invite link</button></div>
      <div class="players">${players}</div></div>
    ${body}
    <div style="height:14px"></div><button class="ghost" style="width:100%" data-act="leave">${host ? "End the party" : "Leave"}</button>`;
}

async function partyAction(act, el) {
  const id = el.dataset.id;
  try {
    if (act === "share") {
      const link = el.dataset.link;
      if (navigator.share) await navigator.share({ title: "Next Reel watch party", text: `Join my watch party: ${room.code}`, url: link }).catch(() => {});
      else { await navigator.clipboard.writeText(link); toast("Invite link copied."); }
      return;
    }
    if (act === "room-spin") {
      el.disabled = true;
      const d = await fetchBatch(nextSeed());
      const picks = shuffle(d.titles.filter(t => !seen[t.id])).slice(0, 3);
      if (!picks.length) { el.disabled = false; return toast(loosenHint()); }
      roomState = await roomCall("spin", { host_token: room.host_token, candidates: picks.map(t => t.id) });
    } else if (act === "vote") {
      roomState = await roomCall("vote", { player: room.player, pick: id });
      room.vote = { round: roomState.round, id };
      setRoom(room);
    } else if (act === "reveal") {
      roomState = await roomCall("reveal", { host_token: room.host_token });
    } else if (act === "leave") {
      if (room.host_token) await roomCall("end", { host_token: room.host_token }).catch(() => {});
      else await roomCall("leave", { player: room.player }).catch(() => {});
      setRoom(null); roomState = null;
    }
  } catch (e) {
    toast(e.message);
    if (e.status === 404) { setRoom(null); roomState = null; }
  }
  if (roomState) withMyVote(roomState);
  renderParty();
}

async function createRoom() {
  myName = $("#hostName").value.trim(); saved.set("name", myName);
  try {
    const r = await api("/api/rooms", { action: "create", name: myName });
    setRoom({ code: r.code, player: r.player, host_token: r.host_token });
    roomState = withMyVote(r.state);
    startPoll(); renderParty();
  } catch (e) { toast(e.message); }
}

async function joinRoom() {
  const code = $("#joinCode").value.trim().toUpperCase();
  myName = $("#joinName").value.trim(); saved.set("name", myName);
  if (!/^[A-Z]{4}$/.test(code)) return toast("Room codes are four letters.");
  try {
    const r = await api("/api/rooms", { action: "join", code, name: myName });
    setRoom({ code: r.code, player: r.player });
    roomState = withMyVote(r.state);
    history.replaceState(null, "", "/#party");
    startPoll(); renderParty();
  } catch (e) { toast(e.message); }
}

/* --- Services & Watched --------------------------------------------------- */

function svcGrid(kind, chosen) {
  return `<div class="svc">${CFG.services.filter(s => s.kind === kind).map(s =>
    `<label><input type="checkbox" data-svc="${kind}" value="${s.id}" ${chosen.includes(s.id) ? "checked" : ""}>${esc(s.name)}</label>`).join("")}</div>`;
}

function renderServices() {
  view.innerHTML = `<h1>Services</h1>
    <p class="sub">Saved on this device only.</p>
    <h2>Subscriptions you pay for</h2>${svcGrid("sub", prefs.subs)}
    <p class="note" style="text-align:left">AMC+ includes Shudder's library.</p>
    <h2>Free apps you'd use</h2>${svcGrid("free", prefs.free)}
    <h2>Stores you'd rent or buy from</h2>${svcGrid("store", prefs.stores)}
    <h2>Look</h2>${seg("theme", [["auto", "Auto"], ["halloween", "Halloween"], ["plain", "Classic"]], prefs.theme)}
    <p class="note" style="text-align:left">Auto turns spooky for October.</p>
    <div style="height:18px"></div><a class="btn full" href="#spin">Done</a>
    <p class="note">${live()
      ? `Titles, posters and descriptions come from <a href="https://www.themoviedb.org" target="_blank" rel="noopener noreferrer">TMDB</a>, and streaming availability from <a href="https://www.justwatch.com" target="_blank" rel="noopener noreferrer">JustWatch</a>. This product uses the TMDB API but is not endorsed or certified by TMDB.`
      : `Built-in catalog of ${esc(CFG.snapshot)} availability. Studio windows are steady (Universal → Peacock, Warner → HBO Max, Paramount → Paramount+), licensed titles move monthly.`}</p>`;
}

function renderWatched() {
  const ids = Object.keys(seen).sort((a, b) => seen[b].at - seen[a].at);
  view.innerHTML = `<h1>Watched</h1>
    <p class="sub">These never come up in a spin. Undo one to put it back in the pool.</p>
    ${ids.length ? `<div class="card list">${ids.map(id => `<div class="item"><div class="grow"><b>${esc(seen[id].title || id)}</b>
        <div class="meta">${seen[id].verdict === "nope" ? "Not for me" : "Watched"}${seen[id].year ? " · " + esc(seen[id].year) : ""}</div></div>
        <button class="ghost small" data-act="unsee" data-id="${esc(id)}">Undo</button></div>`).join("")}</div>
      <button class="ghost" style="width:100%" data-act="unsee-all">Clear the list</button>`
    : `<div class="card empty"><p class="muted">Nothing yet. "Seen it" and "Not for me" on a spin land here.</p></div>`}`;
}

/* --- routing & events ----------------------------------------------------- */

function route() {
  const tab = (location.hash || "#spin").slice(1);
  document.querySelectorAll(".tabbar a").forEach(a =>
    a.dataset.tab === tab ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
  if (tab === "party") { renderParty(); if (room && CFG.parties) { startPoll(); refreshRoom(); } }
  else { stopPoll(); if (tab === "services") renderServices(); else if (tab === "watched") renderWatched(); else renderSpin(); }
  window.scrollTo(0, 0);
}

async function refreshRoom() {
  try { roomState = withMyVote(await api("/api/rooms?code=" + room.code)); }
  catch (e) { if (e.status === 404) { setRoom(null); roomState = null; } }
  if (location.hash === "#party") renderParty();
}

function resetSpin() { spin = { picks: [], spares: [], winner: null, rolling: false, seeds: [] }; }

// After a filter change: inside the sheet, redraw the sheet and keep it open;
// on the page, redraw the page.
function filtersChanged(inSheet) {
  prefs.preset = null; save(); resetSpin();
  if (inSheet) { renderSheet(); refreshCount(); }
  else renderSpin();
}

function onClick(e) {
  const el = e.target.closest("[data-chip],[data-seg],[data-preset],[data-clear],[data-act],#spin,#create,#join");
  if (!el) return;
  const inSheet = !!el.closest("#sheet");
  if (el.id === "spin") return doSpin();
  if (el.id === "create") return createRoom();
  if (el.id === "join") return joinRoom();
  if (el.dataset.preset) {
    const p = PRESETS.find(x => x.id === el.dataset.preset);
    Object.assign(prefs, structuredClone(p.set));
    prefs.preset = p.id; save(); resetSpin();
    return renderSpin();
  }
  if (el.dataset.chip) {
    const g = el.dataset.chip, v = el.dataset.value;
    if (g === "access") prefs.access[v] = !prefs.access[v];
    else prefs[g] = prefs[g].includes(v) ? prefs[g].filter(x => x !== v) : [...prefs[g], v];
    if (!prefs.genres.includes("horror")) prefs.tags = prefs.tags.filter(t => !HORROR_STYLES.includes(t));
    return filtersChanged(inSheet);
  }
  if (el.dataset.seg) {
    const g = el.dataset.seg, v = el.dataset.value;
    prefs[g] = g === "maxMinutes" ? Number(v) : v;
    if (g === "theme") { save(); applyTheme(); return renderServices(); }
    return filtersChanged(inSheet);
  }
  if (el.dataset.clear) {
    const g = el.dataset.clear, v = el.dataset.value;
    if (g === "genres" || g === "tags") prefs[g] = prefs[g].filter(x => x !== v);
    if (!prefs.genres.includes("horror")) prefs.tags = prefs.tags.filter(t => !HORROR_STYLES.includes(t));
    else prefs[g] = g === "maxMinutes" ? 0 : v;
    return filtersChanged(false);
  }
  const act = el.dataset.act, id = el.dataset.id;
  if (act === "filters") return openSheet();
  if (act === "reset") {
    Object.assign(prefs, { kind: "both", genres: [], tags: [], scare: "any", maxMinutes: 0 });
    return filtersChanged(true);
  }
  if (["room-spin", "vote", "reveal", "leave", "share"].includes(act)) return partyAction(act, el);
  if (act === "pick") { spin.winner = id; renderReels(); return $("#reels").scrollIntoView({ block: "start" }); }
  if (act === "back") { spin.winner = null; return renderReels(); }
  if (act === "swap") return swap(id);
  if (act === "seen" || act === "nope") {
    markSeen(id, act === "seen" ? "watched" : "nope");
    toast(act === "seen" ? "Got it, it won't come up again." : "Passed. It won't come up again.");
    return swap(id);
  }
  if (act === "watched") { markSeen(id, "watched"); toast("Marked watched. Enjoy the show."); resetSpin(); return renderSpin(); }
  if (act === "unsee") { delete seen[id]; saved.set("seen", seen); return renderWatched(); }
  if (act === "unsee-all") { seen = {}; saved.set("seen", seen); return renderWatched(); }
}

view.addEventListener("click", onClick);
$("#sheet").addEventListener("click", e => {
  if (e.target === e.currentTarget) return e.currentTarget.close();   // tap on the backdrop
  if (e.target.closest('a[href^="#"]')) e.currentTarget.close();
  onClick(e);
});
$("#sheet").addEventListener("close", () => { if ((location.hash || "#spin") === "#spin") renderSpin(); });

view.addEventListener("change", e => {
  const el = e.target;
  if (!el.dataset.svc) return;
  const key = { sub: "subs", free: "free", store: "stores" }[el.dataset.svc];
  prefs[key] = el.checked ? [...new Set([...prefs[key], el.value])] : prefs[key].filter(x => x !== el.value);
  prefs.setUp = true; save(); resetSpin();
});

view.addEventListener("keydown", e => {
  if (e.key !== "Enter") return;
  if (e.target.id === "joinCode" || e.target.id === "joinName") joinRoom();
  if (e.target.id === "hostName") createRoom();
});

document.addEventListener("visibilitychange", () => { if (!document.hidden && room && location.hash === "#party") refreshRoom(); });
window.addEventListener("hashchange", route);

(async function boot() {
  try {
    CFG = await fetch("/api/config").then(r => { if (!r.ok) throw new Error(); return r.json(); });
  } catch {
    view.innerHTML = `<h1>Next Reel</h1><div class="card empty"><p>Couldn't reach the server. Check your connection and reload.</p></div>`;
    return;
  }
  SVC = Object.fromEntries(CFG.services.map(s => [s.id, s]));
  const d = defaults(), p = saved.get("prefs", {});
  prefs = { ...d, ...p, access: { ...d.access, ...(p.access || {}) } };
  // Drop anything this server no longer offers.
  for (const k of ["subs", "free", "stores"]) prefs[k] = prefs[k].filter(id => SVC[id]);
  prefs.genres = prefs.genres.filter(g => CFG.genres.includes(g));
  prefs.tags = prefs.tags.filter(g => CFG.tags.includes(g) && g !== "cozy");
  if (!scares().some(([v]) => v === prefs.scare)) prefs.scare = "any";
  applyTheme();
  if (joinFromLink() && !location.hash) location.hash = "#party";
  route();
})();
