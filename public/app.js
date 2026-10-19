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
const TAG_NAMES = {
  halloween: "Halloween night", slasher: "Slasher", supernatural: "Supernatural", haunted: "Haunted house",
  folk: "Folk horror", creature: "Creature feature", zombie: "Zombies", vampire: "Vampires", witch: "Witches",
  psychological: "Psychological", "found-footage": "Found footage", "horror-comedy": "Horror-comedy",
  "psych-thriller": "Psychological", conspiracy: "Conspiracy", survival: "Survival", "serial-killer": "Serial killer",
  heist: "Heist", whodunit: "Whodunit", detective: "Detective", "dark-comedy": "Dark comedy", parody: "Parody",
  romcom: "Rom-com", buddy: "Buddy comedy", "time-travel": "Time travel", space: "Space", dystopia: "Dystopia",
  ai: "AI & robots", alien: "Aliens", magic: "Magic", "fairy-tale": "Fairy tale", dragon: "Dragons",
  superhero: "Superhero", "martial-arts": "Martial arts", spy: "Spy", "true-story": "True story",
  "coming-of-age": "Coming of age", sports: "Sports", "based-on-book": "Based on a book", anime: "Anime",
  "stop-motion": "Stop-motion", christmas: "Christmas", "true-crime": "True crime", nature: "Nature",
  music: "Music", classic: "Classics (pre-1990)", international: "International", cozy: "Cozy",
};
// Rating chips; TV ratings count with their film equivalent (TV-14 is PG-13, TV-MA is R).
const RATING_HINT = { G: "G · TV-G", PG: "PG · TV-PG", "PG-13": "PG-13 · TV-14", R: "R · TV-MA" };
const LENGTHS = [[0, "Any length"], [100, "Under 100 min"], [120, "Under 2 hrs"]];
const live = () => CFG.source === "tmdb";

// Styles that belong to the picked genres, in order, without repeats.
function visibleStyles() {
  const out = [];
  for (const g of prefs.genres) for (const t of CFG.styles[g] || []) if (!out.includes(t)) out.push(t);
  return out;
}

const PRESETS = [
  { id: "fright", name: "🎃 Fright Night", set: { genres: ["horror"], tags: [], ratings: [] } },
  { id: "halloween", name: "🕯️ Halloween", set: { genres: [], tags: ["halloween"], ratings: [] } },
  { id: "cozy", name: "🧙 Cozy spooky", set: { genres: ["horror", "fantasy"], tags: [], ratings: ["PG", "PG-13"] } },
  { id: "terror", name: "💀 Terrify me", set: { genres: ["horror"], tags: [], ratings: ["R"] } },
  { id: "free", name: "🆓 Free tonight", set: { access: { sub: false, free: true, rent: false, buy: false } } },
  { id: "any", name: "🎲 Anything", set: { genres: [], tags: [], ratings: [], kind: "both", maxMinutes: 0 } },
];

function defaults() {
  const ids = kind => CFG.services.filter(s => s.kind === kind).map(s => s.id);
  return { subs: [], free: ids("free"), stores: ids("store"), access: { sub: true, free: true, rent: false, buy: false },
    kind: "both", genres: [], tags: [], ratings: [], maxMinutes: 0, tv: "other", preset: null, setUp: false };
}
function save() { saved.set("prefs", prefs); }

/* --- theme ---------------------------------------------------------------- */

// One look all year, plus a Halloween skin that switches itself on for October.
function halloweenOn() {
  return new Date().getMonth() === 9;
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
    genres: [...prefs.genres].sort().join(","), tags: [...prefs.tags].sort().join(","), ratings: [...prefs.ratings].sort().join(","),
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
  if (prefs.ratings.length) return "Add another rating.";
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

// "Open in" links for services whose web links reliably hand off to their phone app.
const OPEN_IN = {
  netflix: q => `https://www.netflix.com/search?q=${q}`, hulu: q => `https://www.hulu.com/search?q=${q}`,
  disney: q => `https://www.disneyplus.com/search?q=${q}`, prime: q => `https://www.amazon.com/gp/video/search?phrase=${q}`,
  appletv: q => `https://tv.apple.com/search?term=${q}`, youtube: q => `https://www.youtube.com/results?search_query=${q}`,
  tubi: q => `https://tubitv.com/search/${q}`, roku: q => `https://therokuchannel.roku.com/search/${q}`,
  apple: q => `https://tv.apple.com/search?term=${q}`, amazon: q => `https://www.amazon.com/gp/video/search?phrase=${q}`,
};

// The first way I can actually watch it, as a service id.
function bestService(t) {
  const a = prefs.access, subs = mySubs();
  if (a.sub) { const s = t.subs.find(x => subs.has(x)); if (s) return s; }
  if (a.free) { const s = t.free.find(x => prefs.free.includes(x)); if (s) return s; }
  if (a.rent || a.buy) { const s = [...t.rent, ...t.buy].find(x => prefs.stores.includes(x)); if (s) return s; }
  return null;
}

function tvActions(t) {
  const svc = bestService(t), q = encodeURIComponent(t.title);
  const open = svc && OPEN_IN[svc]
    ? `<a class="btn" href="${esc(OPEN_IN[svc](q))}" target="_blank" rel="noopener noreferrer">Open in ${esc(svcName(svc))}</a>`
    : `<a class="btn" href="${esc(findLink(t))}" target="_blank" rel="noopener noreferrer">Where to watch</a>`;
  const roku = prefs.tv === "roku" && svc && ROKU[svc]
    ? `<button class="ghost" data-act="roku" data-svc="${svc}">Open ${esc(svcName(svc))} on the Roku</button>` : "";
  return open + roku;
}

function runShortcut(path) {
  location.href = `shortcuts://run-shortcut?name=${encodeURIComponent(SHORTCUT)}&input=text&text=${encodeURIComponent(path)}`;
}

function burst() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const card = $(".winner-card .poster") || $(".winner-card");
  if (!card) return;
  const r = card.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  const icons = halloweenOn() ? ["🎃", "🦇", "👻", "🍬"] : ["🍿", "🎬", "⭐", "🍿"];
  for (let i = 0; i < 18; i++) {
    const el = document.createElement("span");
    el.className = "burst";
    el.textContent = icons[i % icons.length];
    const a = (Math.PI * 2 * i) / 18 + Math.random() * .4, d = 90 + Math.random() * 90;
    el.style.setProperty("--x0", `${cx - 11}px`); el.style.setProperty("--y0", `${cy - 11}px`);
    el.style.setProperty("--x1", `${cx - 11 + Math.cos(a) * d}px`); el.style.setProperty("--y1", `${cy - 11 + Math.sin(a) * d}px`);
    el.style.setProperty("--r", `${Math.random() * 360 - 180}deg`);
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 1100);
  }
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
  for (const r of prefs.ratings) out.push(["ratings", r, r]);
  if (prefs.maxMinutes) out.push(["maxMinutes", 0, LENGTHS.find(([v]) => v === prefs.maxMinutes)[1]]);
  return out;
}

function howLine() {
  const on = ACCESS.filter(([k]) => prefs.access[k]).map(([, l]) => l);
  return on.length ? on.join(" · ") : "No way to watch selected";
}

function renderSheet() {
  const body = $("#sheetBody");
  const styleChips = list => list.map(g => chip("tags", g, TAG_NAMES[g] || g, prefs.tags.includes(g))).join("");
  // One "<Genre> style" row per picked genre that has styles; a style shared by
  // two genres shows under the first.
  const shown = [];
  const styleRows = prefs.genres.map(g => {
    const own = (CFG.styles[g] || []).filter(t => !shown.includes(t));
    shown.push(...own);
    return own.length ? `<h2>${esc(GENRE_NAMES[g] || g)} style</h2><div class="chips">${styleChips(own)}</div>` : "";
  }).join("");
  // Classics apply to anything. A picked style whose genre isn't picked (the Halloween quick pick) shows here too, so it can be turned off.
  const more = [...CFG.general, ...prefs.tags.filter(t => !shown.includes(t) && !CFG.general.includes(t))];
  body.innerHTML = `
    <h2>Watch</h2>${seg("kind", [["both", "Both"], ["movie", "Movies"], ["tv", "Shows"]], prefs.kind)}
    <h2>How</h2><div class="chips">${ACCESS.map(([k, l]) => chip("access", k, l, prefs.access[k])).join("")}</div>
    <h2>Genre</h2><div class="chips">${CFG.genres.map(g => chip("genres", g, GENRE_NAMES[g] || g, prefs.genres.includes(g))).join("")}</div>
    ${styleRows || (prefs.genres.length ? "" : `<p class="note" style="text-align:left;margin-top:10px">Pick a genre to see its styles.</p>`)}
    <h2>Rating</h2><div class="chips">${CFG.ratings.map(r => `<button type="button" class="chip" data-chip="ratings" data-value="${r}" aria-pressed="${prefs.ratings.includes(r)}" title="${esc(RATING_HINT[r] || r)}">${r}</button>`).join("")}</div>
    <p class="tv-hint">Pick one or more. TV-14 counts as PG-13 and TV-MA as R.</p>
    ${more.length ? `<h2>More</h2><div class="chips">${styleChips(more)}</div>` : ""}
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
      ${tvActions(t)}
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
  btn.classList.add("spinning");
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
    btn.classList.remove("spinning");
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
    btn.classList.remove("spinning");
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
        tvActions(t)) + `
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
      setTimeout(burst, 80);
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

const MONO = { netflix: "N", hulu: "hu", max: "max", disney: "D+", prime: "pv", appletv: "tv+", peacock: "P",
  paramount: "P+", shudder: "S", amcplus: "A+", mgmplus: "M+", starz: "St", mubi: "Mu", tubi: "T", pluto: "Pl",
  roku: "R", kanopy: "K", plex: "Px", youtube: "YT", apple: "tv", amazon: "a", google: "G", fandango: "F" };

function svcGrid(kind, chosen) {
  return `<div class="svc">${CFG.services.filter(s => s.kind === kind).map(s => {
    const on = chosen.includes(s.id);
    return `<button type="button" class="tile" data-svc="${kind}" data-value="${s.id}" aria-pressed="${on}">
      <span class="mono" aria-hidden="true">${esc(MONO[s.id] || s.name[0])}</span><span class="name">${esc(s.name.replace(" (free)", ""))}</span><span class="tick" aria-hidden="true"></span></button>`;
  }).join("")}</div>`;
}

// Roku apps on the Roku itself. Only ids we're sure of; anything else falls back to "open on your phone".
const ROKU = { netflix: 12, prime: 13, youtube: 837, hulu: 2285, disney: 291097, max: 61322, peacock: 593099,
  paramount: 31440, appletv: 551012, tubi: 41468, pluto: 74519, roku: 151908, plex: 13535, starz: 65067 };
const SHORTCUT = "Next Reel to Roku";

function renderServices() {
  const tv = prefs.tv || "other";
  view.innerHTML = `<h1>Services</h1>
    <p class="sub">Tap what you have. Saved on this device only.</p>
    <div class="section"><h2>Subscriptions</h2>${svcGrid("sub", prefs.subs)}
      <p class="note" style="text-align:left">AMC+ includes Shudder's library.</p></div>
    <div class="section"><h2>Free apps</h2>${svcGrid("free", prefs.free)}</div>
    <div class="section"><h2>Rent or buy from</h2>${svcGrid("store", prefs.stores)}</div>
    <div class="section"><h2>Your TV</h2>
      ${seg("tv", [["other", "Cast from my phone"], ["roku", "Roku + iPhone"]], tv)}
      ${tv === "roku" ? `
        <ol class="steps">
          <li>On the Roku: <b>Settings → System → Advanced system settings → Control by mobile apps</b> → Enabled. Note its IP under <b>Settings → Network → About</b>.</li>
          <li>On your iPhone, open <b>Shortcuts</b> → <b>+</b>. Name it <code>${SHORTCUT}</code>.</li>
          <li>Tap the <b>ⓘ</b> → turn on <b>Show in Share Sheet</b>, so it receives text.</li>
          <li>Add <b>URL</b>: <code>http://YOUR-ROKU-IP:8060/</code> then insert the <b>Shortcut Input</b> variable right after the slash.</li>
          <li>Add <b>Get Contents of URL</b>, set Method to <b>POST</b>. Done.</li>
        </ol>
        <div class="tv-row"><button class="ghost" data-act="roku-test">Test: go to the Roku home screen</button></div>
        <p class="tv-hint">Roku doesn't let anyone open a specific movie from outside, so this opens the right app on the TV. Then pick the title with your remote or the Roku app.</p>`
      : `<p class="tv-hint" style="margin-top:10px">After you pick, tap "Open in Netflix" (or whichever service), then use the Cast or AirPlay button in that app. Most Roku, Fire TV, Google TV and smart TVs accept one of the two.</p>`}
    </div>
    <a class="btn full" href="#spin">Done</a>
    <p class="note">${live()
      ? `Titles and posters from <a href="https://www.themoviedb.org" target="_blank" rel="noopener noreferrer">TMDB</a>, streaming data from <a href="https://www.justwatch.com" target="_blank" rel="noopener noreferrer">JustWatch</a>. This product uses the TMDB API but is not endorsed or certified by TMDB.`
      : `Built-in catalog, availability as of ${esc(CFG.snapshot)}.`}</p>`;
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

// Turning a genre off drops the styles only it offered.
function dropOrphanStyles(genre) {
  if (prefs.genres.includes(genre)) return;
  const still = new Set(visibleStyles());
  prefs.tags = prefs.tags.filter(t => still.has(t) || CFG.general.includes(t) || !(CFG.styles[genre] || []).includes(t));
}

function onClick(e) {
  const el = e.target.closest("[data-chip],[data-seg],[data-preset],[data-clear],[data-svc],[data-act],#spin,#create,#join");
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
  if (el.dataset.svc && !el.dataset.act) {
    const key = { sub: "subs", free: "free", store: "stores" }[el.dataset.svc], v = el.dataset.value;
    prefs[key] = prefs[key].includes(v) ? prefs[key].filter(x => x !== v) : [...prefs[key], v];
    prefs.setUp = true; save(); resetSpin();
    el.setAttribute("aria-pressed", String(prefs[key].includes(v)));
    return;
  }
  if (el.dataset.chip) {
    const g = el.dataset.chip, v = el.dataset.value;
    if (g === "access") prefs.access[v] = !prefs.access[v];
    else prefs[g] = prefs[g].includes(v) ? prefs[g].filter(x => x !== v) : [...prefs[g], v];
    if (g === "genres") dropOrphanStyles(v);
    return filtersChanged(inSheet);
  }
  if (el.dataset.seg) {
    const g = el.dataset.seg, v = el.dataset.value;
    prefs[g] = g === "maxMinutes" ? Number(v) : v;
    if (g === "tv") { save(); return renderServices(); }
    return filtersChanged(inSheet);
  }
  if (el.dataset.clear) {
    const g = el.dataset.clear, v = el.dataset.value;
    if (["genres", "tags", "ratings"].includes(g)) prefs[g] = prefs[g].filter(x => x !== v);
    else prefs[g] = g === "maxMinutes" ? 0 : v;
    if (g === "genres") dropOrphanStyles(v);
    return filtersChanged(false);
  }
  const act = el.dataset.act, id = el.dataset.id;
  if (act === "filters") return openSheet();
  if (act === "reset") {
    Object.assign(prefs, { kind: "both", genres: [], tags: [], ratings: [], maxMinutes: 0 });
    return filtersChanged(true);
  }
  if (["room-spin", "vote", "reveal", "leave", "share"].includes(act)) return partyAction(act, el);
  if (act === "pick") { spin.winner = id; renderReels(); $("#reels").scrollIntoView({ block: "start" }); return setTimeout(burst, 60); }
  if (act === "roku") return runShortcut(`launch/${ROKU[el.dataset.svc]}`);
  if (act === "roku-test") return runShortcut("keypress/Home");
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

view.addEventListener("keydown", e => {
  if (e.key !== "Enter") return;
  if (e.target.id === "joinCode" || e.target.id === "joinName") joinRoom();
  if (e.target.id === "hostName") createRoom();
});

document.addEventListener("visibilitychange", () => { if (!document.hidden && room && location.hash === "#party") refreshRoom(); });
window.addEventListener("hashchange", route);

(async function boot() {
  try {
    CFG = await fetch("/api/config", { cache: "no-cache" }).then(r => { if (!r.ok) throw new Error(); return r.json(); });
    // Tolerate an older server for the minute a deploy takes to settle.
    CFG.styles = CFG.styles || {}; CFG.general = CFG.general || []; CFG.ratings = CFG.ratings || ["G", "PG", "PG-13", "R"];
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
  prefs.tags = prefs.tags.filter(g => CFG.tags.includes(g));
  prefs.ratings = (prefs.ratings || []).filter(r => CFG.ratings.includes(r));
  delete prefs.scare;
  applyTheme();
  if (joinFromLink() && !location.hash) location.hash = "#party";
  route();
})();
