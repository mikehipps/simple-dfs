
// ---------- helpers ----------
const FALLBACK_SUFFIXES = ["jr","sr","ii","iii","iv","v"];
const FALLBACK_NICK = {
  "mike":"michael","tony":"anthony","aj":"a j","a.j.":"a j","jd":"j d","j.d.":"j d",
  "rob":"robert","bob":"robert","rick":"richard","dave":"david","chris":"christopher",
  "drew":"andrew","andy":"andrew","bill":"william","billy":"william","will":"william",
  "alex":"alexander","sasha":"alexander"
};

const FALLBACK_NFL_CODE_BY_KEY = {
  "ari":"ARI","arizona":"ARI","arizona cardinals":"ARI","cardinals":"ARI",
  "atl":"ATL","atlanta":"ATL","atlanta falcons":"ATL","falcons":"ATL",
  "bal":"BAL","baltimore":"BAL","baltimore ravens":"BAL","ravens":"BAL",
  "buf":"BUF","buffalo":"BUF","buffalo bills":"BUF","bills":"BUF","buffallo":"BUF",
  "car":"CAR","carolina":"CAR","carolina panthers":"CAR","panthers":"CAR",
  "chi":"CHI","chicago":"CHI","chicago bears":"CHI","bears":"CHI",
  "cin":"CIN","cincinnati":"CIN","cincinnati bengals":"CIN","bengals":"CIN",
  "cle":"CLE","cleveland":"CLE","cleveland browns":"CLE","browns":"CLE",
  "dal":"DAL","dallas":"DAL","dallas cowboys":"DAL","cowboys":"DAL",
  "den":"DEN","denver":"DEN","denver broncos":"DEN","broncos":"DEN",
  "det":"DET","detroit":"DET","detroit lions":"DET","lions":"DET",
  "gb":"GB","gnb":"GB","green bay":"GB","green bay packers":"GB","packers":"GB",
  "hou":"HOU","houston":"HOU","houston texans":"HOU","texans":"HOU",
  "ind":"IND","indianapolis":"IND","indianapolis colts":"IND","colts":"IND",
  "jax":"JAX","jac":"JAX","jacksonville":"JAX","jacksonville jaguars":"JAX","jaguars":"JAX",
  "kc":"KC","kan":"KC","kansas city":"KC","kansas city chiefs":"KC","chiefs":"KC",
  "lv":"LV","las vegas":"LV","oak":"LV","rai":"LV","las vegas raiders":"LV","raiders":"LV",
  "lac":"LAC","sd":"LAC","los angeles chargers":"LAC","chargers":"LAC",
  "lar":"LAR","los angeles rams":"LAR","rams":"LAR",
  "mia":"MIA","miami":"MIA","miami dolphins":"MIA","dolphins":"MIA",
  "min":"MIN","minnesota":"MIN","minnesota vikings":"MIN","vikings":"MIN",
  "ne":"NE","nwe":"NE","new england":"NE","new england patriots":"NE","patriots":"NE",
  "no":"NO","nor":"NO","new orleans":"NO","new orleans saints":"NO","saints":"NO",
  "nyg":"NYG","new york giants":"NYG","giants":"NYG",
  "nyj":"NYJ","new york jets":"NYJ","jets":"NYJ",
  "phi":"PHI","philadelphia":"PHI","philadelphia eagles":"PHI","eagles":"PHI",
  "pit":"PIT","pittsburgh":"PIT","pittsburgh steelers":"PIT","steelers":"PIT",
  "sf":"SF","sfo":"SF","san francisco":"SF","san francisco 49ers":"SF","49ers":"SF","niners":"SF",
  "sea":"SEA","seattle":"SEA","seattle seahawks":"SEA","seahawks":"SEA",
  "tb":"TB","tampa":"TB","tampa bay":"TB","tampa bay buccaneers":"TB","bucs":"TB","buccaneers":"TB",
  "ten":"TEN","tens":"TEN","tennessee":"TEN","tennessee titans":"TEN","titans":"TEN",
  "was":"WAS","wsh":"WAS","washington":"WAS","washington commanders":"WAS","commanders":"WAS","football team":"WAS","redskins":"WAS"
};
const FALLBACK_NFL_FULL_BY_CODE = {
  "ARI":"Arizona Cardinals","ATL":"Atlanta Falcons","BAL":"Baltimore Ravens","BUF":"Buffalo Bills",
  "CAR":"Carolina Panthers","CHI":"Chicago Bears","CIN":"Cincinnati Bengals","CLE":"Cleveland Browns",
  "DAL":"Dallas Cowboys","DEN":"Denver Broncos","DET":"Detroit Lions","GB":"Green Bay Packers",
  "HOU":"Houston Texans","IND":"Indianapolis Colts","JAX":"Jacksonville Jaguars","KC":"Kansas City Chiefs",
  "LV":"Las Vegas Raiders","LAC":"Los Angeles Chargers","LAR":"Los Angeles Rams","MIA":"Miami Dolphins",
  "MIN":"Minnesota Vikings","NE":"New England Patriots","NO":"New Orleans Saints","NYG":"New York Giants",
  "NYJ":"New York Jets","PHI":"Philadelphia Eagles","PIT":"Pittsburgh Steelers","SF":"San Francisco 49ers",
  "SEA":"Seattle Seahawks","TB":"Tampa Bay Buccaneers","TEN":"Tennessee Titans","WAS":"Washington Commanders"
};
const FALLBACK_DST_PATTERNS = ["d/st","dst","defense","def"];

let SUFFIXES;
let NICK;
let NFL_CODE_BY_KEY;
let NFL_FULL_BY_CODE;
let DST_PATTERNS;
let DST_REGEX = /(?!)/i;
let sportLoadToken = 0;

function isPlainObject(value) {
  return !!value && typeof value === "object" && !Array.isArray(value);
}
function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
function dstPatternToRegexSource(pattern) {
  const escaped = escapeRegex(pattern);
  const withSlash = escaped.replace(/\\\//g, "\\s*\\/\\s*");
  return withSlash.replace(/\s+/g, "\\s*");
}
function buildDSTRegex(patterns) {
  const sources = (Array.isArray(patterns) ? patterns : [])
    .map(p => (p ?? "").toString().trim().toLowerCase())
    .filter(Boolean)
    .map(dstPatternToRegexSource);
  if (!sources.length) {
    return /(?!)/i;
  }
  return new RegExp("(?:" + sources.join("|") + ")\\b", "i");
}
function sanitizeStringList(list) {
  return (Array.isArray(list) ? list : [])
    .map(item => (item ?? "").toString().trim().toLowerCase())
    .filter(Boolean);
}
function buildSuffixSet(list) {
  return new Set(sanitizeStringList(list));
}
function applyTeamOverrides(map) {
  if (!isPlainObject(map)) return;
  Object.entries(map).forEach(([key, value]) => {
    if (typeof value !== "string") return;
    NFL_CODE_BY_KEY[key.toLowerCase()] = value.toUpperCase();
  });
}
function applyTeamFullOverrides(map) {
  if (!isPlainObject(map)) return;
  Object.entries(map).forEach(([key, value]) => {
    if (typeof value !== "string") return;
    NFL_FULL_BY_CODE[key.toUpperCase()] = value;
  });
}
function applyNicknameOverrides(source) {
  if (!isPlainObject(source)) return;
  Object.entries(source).forEach(([key, value]) => {
    if (typeof value !== "string") return;
    const k = key.toLowerCase();
    const v = value.toLowerCase();
    if (k && v) NICK[k] = v;
  });
}
function initializeDataFromFallback() {
  NFL_CODE_BY_KEY = {};
  applyTeamOverrides(FALLBACK_NFL_CODE_BY_KEY);
  NFL_FULL_BY_CODE = {};
  applyTeamFullOverrides(FALLBACK_NFL_FULL_BY_CODE);
  NICK = {};
  applyNicknameOverrides(FALLBACK_NICK);
  SUFFIXES = buildSuffixSet(FALLBACK_SUFFIXES);
  DST_PATTERNS = sanitizeStringList(FALLBACK_DST_PATTERNS);
  DST_REGEX = buildDSTRegex(DST_PATTERNS);
}
async function fetchJSON(path) {
  try {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}
async function loadDataSeeds(sport) {
  const requestId = ++sportLoadToken;
  try {
    const [teamData, nickData, suffixData, dstData] = await Promise.all([
      fetchJSON(`data/${sport}_teams.json`),
      fetchJSON("data/nicknames_common.json"),
      fetchJSON("data/suffixes.json"),
      fetchJSON("data/dst_patterns.json")
    ]);
    if (requestId !== sportLoadToken) return;

    initializeDataFromFallback();

    if (teamData && isPlainObject(teamData.map)) {
      applyTeamOverrides(teamData.map);
    }
    if (teamData && isPlainObject(teamData.fullByCode)) {
      applyTeamFullOverrides(teamData.fullByCode);
    }
    if (isPlainObject(nickData)) {
      applyNicknameOverrides(nickData);
    }
    if (Array.isArray(suffixData) && suffixData.length) {
      SUFFIXES = buildSuffixSet(suffixData);
    }
    if (Array.isArray(dstData) && dstData.length) {
      DST_PATTERNS = sanitizeStringList(dstData);
      DST_REGEX = buildDSTRegex(DST_PATTERNS);
    }
  } catch (err) {
    if (requestId !== sportLoadToken) return;
    console.warn("Failed to load data seeds", err);
    initializeDataFromFallback();
  }
}

initializeDataFromFallback();

function normText(x) {
  if (x == null) return "";
  return (x+"")
    .normalize("NFKD").replace(/[^\u0000-\u007E]/g, "")
    .replace(/[^a-zA-Z0-9\s]/g, " ").toLowerCase().replace(/\s+/g, " ").trim();
}
function normName(name) {
  const t = normText(name);
  const parts = t.split(" ").filter(Boolean).map(w => NICK[w] || w).join(" ").split(" ");
  const cleaned = parts.filter(w => !SUFFIXES.has(w));
  return cleaned.join(" ");
}
function canonTeam(t) {
  const k = normText(t);
  return NFL_CODE_BY_KEY[k] || k.toUpperCase();
}
function isDSTName(n, teamCode) {
  // Check for explicit D/ST patterns
  if (DST_REGEX.test(n || "")) return true;
  
  // Check if name is just a team name (common for defense teams)
  if (teamCode) {
    const normalized = normText(n);
    const teamFullName = normText(teamFullNameFromCode(teamCode));
    const teamShortNames = Object.keys(NFL_CODE_BY_KEY).filter(key =>
      NFL_CODE_BY_KEY[key] === teamCode && key !== teamFullName
    );
    
    // If the normalized name matches any team short name, treat as D/ST
    return teamShortNames.some(shortName => shortName === normalized);
  }
  
  return false;
}
function teamFullNameFromCode(code) { return NFL_FULL_BY_CODE[code] || code; }
function dstNormalizedName(name, teamCode) {
  if (!teamCode) return normName(name);
  return normText(teamFullNameFromCode(teamCode)).split(" ").join(" ");
}
function download(filename, text) {
  const blob = new Blob([text], {type: "text/plain;charset=utf-8"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function getAliases() { try { return JSON.parse(localStorage.getItem("csvMatchAliases") || "{}"); } catch { return {}; } }
function setAliases(obj) { localStorage.setItem("csvMatchAliases", JSON.stringify(obj)); }

// ---------- configuration ----------
const REQUIRED_COLUMNS = {
  nfl: ['Id', 'Position', 'First Name', 'Last Name', 'FPPG', 'Game', 'Team', 'Opponent', 'Salary', 'Injury Indicator']
};

const OPTIONAL_COLUMNS = ['Max Exposure', 'Min Exposure', 'Roster Order', 'Projected Ownership', 'Min Deviation', 'Max Deviation', 'Projection Floor', 'Projection Ceil', 'Confirmed Starter', 'Progressive Scale'];

// ---------- state ----------
let A = null, B = null;
let headersA = [], headersB = [];
let mergedStore = null, manifest = null;
let reviewItems = [];
let columnMapping = { required: {}, optional: {} };

// ---------- UI refs ----------
const themeToggle = document.getElementById("themeToggle");
const sportSelect = document.getElementById("sportSelect");
const fileA = document.getElementById("fileA");
const fileB = document.getElementById("fileB");
const metaA = document.getElementById("metaA");
const metaB = document.getElementById("metaB");
const nameModeA = document.getElementById("nameModeA");
const nameModeB = document.getElementById("nameModeB");
const nameASingleWrap = document.getElementById("nameASingleWrap");
const nameAComposeWrap = document.getElementById("nameAComposeWrap");
const nameBSingleWrap = document.getElementById("nameBSingleWrap");
const nameBComposeWrap = document.getElementById("nameBComposeWrap");
const nameA = document.getElementById("nameA");
const teamA = document.getElementById("teamA");
const nameB = document.getElementById("nameB");
const teamB = document.getElementById("teamB");
const nameACompose = document.getElementById("nameACompose");
const nameBCompose = document.getElementById("nameBCompose");
const nameASeparator = document.getElementById("nameASeparator");
const nameBSeparator = document.getElementById("nameBSeparator");
const requiredMapping = document.getElementById("requiredMapping");
const optionalMapping = document.getElementById("optionalMapping");
const addOptionalColumn = document.getElementById("addOptionalColumn");
const btnMerge = document.getElementById("btnMerge");
const btnExportCSV = document.getElementById("btnExportCSV");
const btnExportManifest = document.getElementById("btnExportManifest");
const status = document.getElementById("status");
const summary = document.getElementById("summary");
const reviewSection = document.getElementById("reviewSection");
const reviewBody = document.getElementById("reviewBody");
const btnApplyReview = document.getElementById("btnApplyReview");

function applyTheme(theme) {
  const next = theme === "theme-light" ? "theme-light" : "theme-dark";
  document.body.classList.remove("theme-light", "theme-dark");
  document.body.classList.add(next);
  if (themeToggle) {
    themeToggle.textContent = next === "theme-dark" ? "Switch to Light Mode" : "Switch to Dark Mode";
  }
  localStorage.setItem("csvMatchTheme", next);
}

const preferredTheme = localStorage.getItem("csvMatchTheme") || (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "theme-dark" : "theme-light");
applyTheme(preferredTheme);

if (themeToggle) {
  themeToggle.addEventListener("click", () => {
    const next = document.body.classList.contains("theme-dark") ? "theme-light" : "theme-dark";
    applyTheme(next);
  });
}

function fillSelect(sel, headers) {
  sel.innerHTML = "";
  const opt = (v) => { const o=document.createElement("option"); o.value=v; o.textContent=v; return o; };
  sel.appendChild(opt("— choose —"));
  headers.forEach(h => sel.appendChild(opt(h)));
}
function fillMultiSelect(sel, headers) {
  sel.innerHTML = "";
  headers.forEach(h => {
    const o=document.createElement("option"); o.value=h; o.textContent=h; sel.appendChild(o);
  });
}
function fillRequiredMapping(headers) {
  requiredMapping.innerHTML = "";
  const sport = sportSelect.value;
  const requiredCols = REQUIRED_COLUMNS[sport] || [];
  
  requiredCols.forEach(colName => {
    const label = document.createElement("label");
    label.textContent = `*${colName}:`;
    label.style.fontWeight = "600";
    
    const select = document.createElement("select");
    select.dataset.column = colName;
    
    // Add empty option
    const emptyOpt = document.createElement("option");
    emptyOpt.value = "";
    emptyOpt.textContent = "— choose —";
    select.appendChild(emptyOpt);
    
    // Add header options
    headers.forEach(h => {
      const opt = document.createElement("option");
      opt.value = h;
      opt.textContent = h;
      select.appendChild(opt);
    });
    
    select.addEventListener("change", () => {
      columnMapping.required[colName] = select.value;
    });
    
    requiredMapping.appendChild(label);
    requiredMapping.appendChild(select);
  });
}

function addOptionalDropdown() {
  const container = document.createElement("div");
  container.style.display = "flex";
  container.style.gap = "8px";
  container.style.alignItems = "center";
  container.style.margin

  container.style.marginBottom = "8px";
  
  // Output name dropdown
  const outputSelect = document.createElement("select");
  outputSelect.style.flex = "1";
  
  const emptyOpt = document.createElement("option");
  emptyOpt.value = "";
  emptyOpt.textContent = "— choose output —";
  outputSelect.appendChild(emptyOpt);
  
  OPTIONAL_COLUMNS.forEach(col => {
    const opt = document.createElement("option");
    opt.value = col;
    opt.textContent = col;
    outputSelect.appendChild(opt);
  });
  
  // Source column dropdown
  const sourceSelect = document.createElement("select");
  sourceSelect.style.flex = "1";
  
  const sourceEmptyOpt = document.createElement("option");
  sourceEmptyOpt.value = "";
  sourceEmptyOpt.textContent = "— choose source —";
  sourceSelect.appendChild(sourceEmptyOpt);
  
  const allHeaders = [...headersA, ...headersB];
  allHeaders.forEach(h => {
    const opt = document.createElement("option");
    opt.value = h;
    opt.textContent = h;
    sourceSelect.appendChild(opt);
  });
  
  // Remove button
  const removeBtn = document.createElement("button");
  removeBtn.textContent = "×";
  removeBtn.type = "button";
  removeBtn.style.padding = "2px 6px";
  removeBtn.addEventListener("click", () => {
    container.remove();
    // Remove from mapping
    if (outputSelect.value) {
      delete columnMapping.optional[outputSelect.value];
    }
  });
  
  // Event listeners
  outputSelect.addEventListener("change", () => {
    if (outputSelect.value && sourceSelect.value) {
      columnMapping.optional[outputSelect.value] = sourceSelect.value;
    }
  });
  
  sourceSelect.addEventListener("change", () => {
    if (outputSelect.value && sourceSelect.value) {
      columnMapping.optional[outputSelect.value] = sourceSelect.value;
    }
  });
  
  container.appendChild(outputSelect);
  container.appendChild(sourceSelect);
  container.appendChild(removeBtn);
  optionalMapping.appendChild(container);
}

function validateRequiredMapping() {
  const sport = sportSelect.value;
  const requiredCols = REQUIRED_COLUMNS[sport] || [];
  
  for (const col of requiredCols) {
    if (!columnMapping.required[col]) {
      return `Required column "${col}" is not mapped`;
    }
  }
  return null;
}
function parseCSV(file, cb) {
  Papa.parse(file, { header: true, skipEmptyLines: true, complete: r => cb(null, r), error: e => cb(e, null) });
}

function toggleNameMode(which) {
  if (which === "A") {
    const mode = nameModeA.value;
    nameASingleWrap.style.display = mode === "single" ? "inline-block" : "none";
    nameAComposeWrap.style.display = mode === "compose" ? "flex" : "none";
  } else {
    const mode = nameModeB.value;
    nameBSingleWrap.style.display = mode === "single" ? "inline-block" : "none";
    nameBComposeWrap.style.display = mode === "compose" ? "flex" : "none";
  }
}
nameModeA.addEventListener("change", () => toggleNameMode("A"));
nameModeB.addEventListener("change", () => toggleNameMode("B"));

fileA.addEventListener("change", e => {
  const f = e.target.files[0]; if (!f) return;
  parseCSV(f, (err, res) => {
    if (err) { metaA.textContent = "Error parsing A: " + err; return; }
    A = res.data; headersA = res.meta.fields || [];
    metaA.textContent = `${f.name} — ${A.length} rows, ${headersA.length} columns`;
    fillSelect(nameA, headersA); fillSelect(teamA, headersA);
    fillMultiSelect(nameACompose, headersA);
    fillRequiredMapping([...headersA, ...headersB]);
  });
});
fileB.addEventListener("change", e => {
  const f = e.target.files[0]; if (!f) return;
  parseCSV(f, (err, res) => {
    if (err) { metaB.textContent = "Error parsing B: " + err; return; }
    B = res.data; headersB = res.meta.fields || [];
    metaB.textContent = `${f.name} — ${B.length} rows, ${headersB.length} columns`;
    fillSelect(nameB, headersB); fillSelect(teamB, headersB);
    fillMultiSelect(nameBCompose, headersB);
    fillRequiredMapping([...headersA, ...headersB]);
  });
});

function buildNameGetter(mode, singleSel, composeSel, sep) {
  if (mode === "compose") {
    return (row) => {
      const cols = [...composeSel.selectedOptions].map(o => o.value);
      const pieces = cols.map(c => (row[c] ?? "").toString().trim()).filter(Boolean);
      return pieces.join(sep || " ");
    };
  } else {
    return (row) => (row[singleSel.value] ?? "").toString();
  }
}

function buildIndex(rows, getName, teamCol) {
  const aliases = getAliases();
  const items = rows.map(r => {
    const teamCode = canonTeam(r[teamCol]);
    let nameRaw = getName(r);
    let n = normName(nameRaw);
    if (isDSTName(nameRaw, teamCode)) n = dstNormalizedName(nameRaw, teamCode);
    const aliasKey = teamCode + "::" + n;
    const aliased = aliases[aliasKey];
    const finalName = aliased || n;
    return { row:r, _norm_name:finalName, _norm_team:teamCode };
  });
  const map = new Map();
  for (const it of items) {
    const key = it._norm_name + "||" + it._norm_team;
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(it);
  }
  const byTeam = new Map();
  for (const it of items) {
    if (!byTeam.has(it._norm_team)) byTeam.set(it._norm_team, []);
    byTeam.get(it._norm_team).push(it);
  }
  const fuseByTeam = new Map();
  for (const [t, arr] of byTeam.entries()) {
    fuseByTeam.set(t, new Fuse(arr, { keys: ["_norm_name"], threshold: 0.12, includeScore: true }));
  }
  return { items, map, fuseByTeam };
}

// Remove old gatherKeep function - no longer needed

document.getElementById("btnMerge").addEventListener("click", () => {
  if (!A || !B) { status.textContent = "Upload both files first."; return; }
  
  // Validate required columns
  const validationError = validateRequiredMapping();
  if (validationError) {
    status.textContent = validationError;
    return;
  }

  const primary = [...document.querySelectorAll('input[name="primary"]')].find(r => r.checked)?.value || "A";

  const getNameA = buildNameGetter(nameModeA.value, nameA, nameACompose, nameASeparator.value);
  const getNameB = buildNameGetter(nameModeB.value, nameB, nameBCompose, nameBSeparator.value);

  const P = primary === "A" ? A : B;
  const S = primary === "A" ? B : A;
  const nameGetterP = primary === "A" ? getNameA : getNameB;
  const nameGetterS = primary === "A" ? getNameB : getNameA;
  const teamP = primary === "A" ? teamA.value : teamB.value;
  const teamS = primary === "A" ? teamB.value : teamA.value;

  if (!teamP || !teamS || teamP.startsWith("—") || teamS.startsWith("—")) {
    status.textContent = "Pick Team columns for both files."; return;
  }

  status.textContent = "Matching...";
  const Sidx = buildIndex(S, nameGetterS, teamS);

  let auto=0, review=0, missing=0;
  let merged = [];
  reviewItems = [];

  for (let i=0;i<P.length;i++) {
    const pr = P[i];
    const teamCode = canonTeam(pr[teamP]);
    let rawName = nameGetterP(pr);
    let norm = normName(rawName);
    if (isDSTName(rawName, teamCode)) norm = dstNormalizedName(rawName, teamCode);

    const aliases = getAliases();
    const aliasKey = teamCode + "::" + norm;
    const aliasedNorm = aliases[aliasKey] || norm;

    let match = null, reason = "";
    const hard = Sidx.map.get(aliasedNorm + "||" + teamCode) || [];
    if (hard.length === 1) { match = hard[0].row; reason = "exact"; auto++; }
    else if (hard.length > 1) { match = hard[0].row; reason = "exact_multi"; auto++; }
    else {
      const fuse = Sidx.fuseByTeam.get(teamCode);
      if (fuse) {
        let res = fuse.search(aliasedNorm).slice(0,3); // strict
        if (!(res.length && res[0].score <= 0.12)) {
          res = fuse.search(aliasedNorm).slice(0,3);   // still show top 3
        }
        if (res.length) {
          reason = "review"; review++;
          const cands = res.map(x => ({ name: x.item._norm_name, row: x.item.row }));
          reviewItems.push({ idx:i, projRow: pr, teamCode, candidates: cands, choice: cands[0]?.name || "", saveAlias: true, rawName });
        } else {
          reason = "missing"; missing++;
          reviewItems.push({ idx:i, projRow: pr, teamCode, candidates: [], choice: "", saveAlias: false, rawName });
        }
      } else {
        reason = "missing"; missing++;
        reviewItems.push({ idx:i, projRow: pr, teamCode, candidates: [], choice: "", saveAlias: false, rawName });
      }
    }

    const out = {};
    
    // Map required columns
    const sport = sportSelect.value;
    const requiredCols = REQUIRED_COLUMNS[sport] || [];
    requiredCols.forEach(colName => {
      const sourceCol = columnMapping.required[colName];
      if (sourceCol) {
        // Try to find the value from primary or secondary file
        let value = pr[sourceCol];
        if (value === undefined && match) {
          value = match[sourceCol];
        }
        out[colName] = value || "";
      } else {
        out[colName] = "";
      }
    });
    
    // Map optional columns
    OPTIONAL_COLUMNS.forEach(colName => {
      const sourceCol = columnMapping.optional[colName];
      if (sourceCol) {
        // Try to find the value from primary or secondary file
        let value = pr[sourceCol];
        if (value === undefined && match) {
          value = match[sourceCol];
        }
        out[colName] = value || "";
      } else {
        out[colName] = "";
      }
    });
    
    out["_match_reason"] = match ? reason : (reason || "missing");
    merged.push(out);
  }

  mergedStore = merged;
  manifest = { counts:{ auto, review, missing }, primary };
  status.textContent = "Done.";
  summary.innerHTML = `
    <span class="chip ok">auto: ${auto}</span>
    <span class="chip warn">review: ${review}</span>
    <span class="chip bad">missing: ${missing}</span>
    <span class="muted">(${mergedStore.length} rows)</span>
  `;
  renderReviewTable();
});

function renderReviewTable() {
  reviewBody.innerHTML = "";
  if (!reviewItems.length) { reviewSection.style.display = "none"; btnExportCSV.disabled = false; btnExportManifest.disabled = false; return; }
  reviewSection.style.display = "block";
  reviewItems.slice(0, 500).forEach((it, idx) => {
    const tr = document.createElement("tr");
    const sel = document.createElement("select");
    sel.innerHTML = "";
    const optNone = document.createElement("option"); optNone.value=""; optNone.textContent="— No match —"; sel.appendChild(optNone);
    it.candidates.forEach(c => {
      const o = document.createElement("option"); o.value = c.name; o.textContent = c.name; sel.appendChild(o);
    });
    sel.value = it.choice || "";
    sel.addEventListener("change", () => it.choice = sel.value);
    const chk = document.createElement("input"); chk.type="checkbox"; chk.checked = !!it.saveAlias;
    chk.addEventListener("change", () => it.saveAlias = chk.checked);

    const td0 = document.createElement("td"); td0.textContent = (idx+1);
    const td1 = document.createElement("td"); td1.textContent = it.rawName || "";
    const td2 = document.createElement("td"); td2.textContent = it.teamCode;
    const td3 = document.createElement("td"); td3.appendChild(sel);
    const td4 = document.createElement("td"); td4.appendChild(chk);
    tr.appendChild(td0); tr.appendChild(td1); tr.appendChild(td2); tr.appendChild(td3); tr.appendChild(td4);
    reviewBody.appendChild(tr);
  });

  btnApplyReview.onclick = () => {
    const aliases = getAliases();
    for (const it of reviewItems) {
      if (it.choice && it.saveAlias) {
        let norm = normName(it.rawName);
        if (isDSTName(it.rawName, it.teamCode)) norm = dstNormalizedName(it.rawName, it.teamCode);
        aliases[it.teamCode + "::" + norm] = it.choice;
      }
    }
    setAliases(aliases);
    btnExportCSV.disabled = false;
    btnExportManifest.disabled = false;
    alert("Review applied. You can now export.");
  };
}

document.getElementById("btnExportCSV").addEventListener("click", () => {
  if (!mergedStore) return;
  const csv = Papa.unparse(mergedStore);
  download("merged.csv", csv);
});
document.getElementById("btnExportManifest").addEventListener("click", () => {
  if (!manifest) return;
  download("manifest.json", JSON.stringify(manifest, null, 2));
});

sportSelect.addEventListener("change", () => {
  loadDataSeeds(sportSelect.value);
});
loadDataSeeds(sportSelect.value);

// Add event listener for optional column button
if (addOptionalColumn) {
  addOptionalColumn.addEventListener("click", addOptionalDropdown);
}
