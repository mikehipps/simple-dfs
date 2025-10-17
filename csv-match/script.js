
// ---------- helpers ----------

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
function initializeDataFromFallback() {
  NFL_CODE_BY_KEY = {};
  applyTeamOverrides(FALLBACK_NFL_CODE_BY_KEY);
  NFL_FULL_BY_CODE = {};
  applyTeamFullOverrides(FALLBACK_NFL_FULL_BY_CODE);
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
    const [teamData, dstData] = await Promise.all([
      fetchJSON(`data/${sport}_teams.json`),
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
  const parts = t.split(" ").filter(Boolean);
  return parts.join(" ");
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

function generateDynamicFilename() {
  const sport = sportSelect.value.toUpperCase();
  
  // Get first 3 letters from File A filename
  let fileAPrefix = "UNK";
  if (fileA.files.length > 0) {
    const fileNameA = fileA.files[0].name;
    fileAPrefix = fileNameA.substring(0, 3).toUpperCase();
  }
  
  // Get first 3 letters from File B filename
  let fileBPrefix = "UNK";
  if (fileB.files.length > 0) {
    const fileNameB = fileB.files[0].name;
    fileBPrefix = fileNameB.substring(0, 3).toUpperCase();
  }
  
  // Get current date/time in MMDD-HHMM format
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const timestamp = `${month}${day}-${hours}${minutes}`;
  
  return `${sport}-${fileAPrefix}-${fileBPrefix}-${timestamp}.csv`;
}
function getAliases() { try { return JSON.parse(localStorage.getItem("csvMatchAliases") || "{}"); } catch { return {}; } }
function setAliases(obj) { localStorage.setItem("csvMatchAliases", JSON.stringify(obj)); }

// Team mapping storage functions
function getTeamMappings(sport) {
  try {
    const mappings = JSON.parse(localStorage.getItem("csvMatchTeamMappings") || "{}");
    return mappings[sport] || {};
  } catch {
    return {};
  }
}
function setTeamMappings(sport, mappings) {
  try {
    const allMappings = JSON.parse(localStorage.getItem("csvMatchTeamMappings") || "{}");
    allMappings[sport] = mappings;
    localStorage.setItem("csvMatchTeamMappings", JSON.stringify(allMappings));
  } catch {}
}

// Team extraction and validation functions
function extractUniqueTeamCodes(rows, teamColumn, getName) {
  const teams = new Set();
  if (!rows || !teamColumn) {
    console.log(`❌ extractUniqueTeamCodes: Missing rows or teamColumn`, { rows: !!rows, teamColumn });
    return teams;
  }
  
  console.log(`🔍 extractUniqueTeamCodes: Processing ${rows.length} rows with team column '${teamColumn}'`);
  
  for (const row of rows) {
    const rawTeamValue = row[teamColumn];
    const teamCode = canonTeam(rawTeamValue);
    if (teamCode) {
      teams.add(teamCode);
      console.log(`   → Row team: '${rawTeamValue}' → '${teamCode}'`);
    }
  }
  
  console.log(`✅ extractUniqueTeamCodes: Found ${teams.size} unique teams:`, Array.from(teams));
  return teams;
}

function validateTeamMatches(teamsA, teamsB, manualMappings = {}) {
  console.log(`🔍 validateTeamMatches: teamsA=${teamsA.size}, teamsB=${teamsB.size}, manualMappings=${Object.keys(manualMappings).length}`);
  
  const unmatched = new Set();
  const matched = new Set();
  
  // Check exact matches
  for (const teamA of teamsA) {
    if (teamsB.has(teamA)) {
      matched.add(teamA);
      console.log(`   ✅ Exact match: ${teamA}`);
    } else if (manualMappings[teamA]) {
      // Check if manual mapping exists and target team is in Sheet 2
      if (teamsB.has(manualMappings[teamA])) {
        matched.add(teamA);
        console.log(`   ✅ Manual mapping: ${teamA} → ${manualMappings[teamA]}`);
      } else {
        unmatched.add(teamA);
        console.log(`   ❌ Manual mapping invalid: ${teamA} → ${manualMappings[teamA]} (target not in Sheet 2)`);
      }
    } else {
      unmatched.add(teamA);
      console.log(`   ❌ No match: ${teamA}`);
    }
  }
  
  const result = {
    allMatched: unmatched.size === 0,
    unmatched: Array.from(unmatched),
    matched: Array.from(matched)
  };
  
  console.log(`✅ validateTeamMatches result:`, result);
  return result;
}

function getAvailableSheet2Teams(teamsB) {
  return Array.from(teamsB).sort();
}


// ---------- configuration ----------
const REQUIRED_COLUMNS = ['Id', 'Position', 'First Name', 'Last Name', 'FPPG', 'Game', 'Team', 'Opponent', 'Salary', 'Injury Indicator'];

const OPTIONAL_COLUMNS = ['Max Exposure', 'Min Exposure', 'Roster Order', 'Projected Ownership', 'Min Deviation', 'Max Deviation', 'Projection Floor', 'Projection Ceil', 'Confirmed Starter', 'Progressive Scale'];

// ---------- state ----------
let A = null, B = null;
let headersA = [], headersB = [];
let mergedStore = null, manifest = null;
let reviewItems = [];
let columnMapping = { required: {}, optional: {} };
let teamValidationState = {
  teamsA: new Set(),
  teamsB: new Set(),
  manualMappings: {},
  validationComplete: false
};

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
const teamValidationSection = document.getElementById("teamValidationSection");
const teamValidationStatus = document.getElementById("teamValidationStatus");
const teamMappingSection = document.getElementById("teamMappingSection");
const teamMappingContainer = document.getElementById("teamMappingContainer");
const btnSaveTeamMappings = document.getElementById("btnSaveTeamMappings");
const btnSkipTeamValidation = document.getElementById("btnSkipTeamValidation");
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

// Smart defaults for Step 2: Name Mode and Team selection
function autoSelectNameAndTeamColumns(fileType, headers) {
  const nameModeSelect = fileType === "A" ? nameModeA : nameModeB;
  const nameComposeSelect = fileType === "A" ? nameACompose : nameBCompose;
  const teamSelect = fileType === "A" ? teamA : teamB;
  
  // Always default to "Compose from Columns" mode
  nameModeSelect.value = "compose";
  toggleNameMode(fileType);
  
  // Auto-select name columns using exact matching first, then fuzzy matching
  const selectedNameColumns = autoSelectNameColumns(headers);
  if (selectedNameColumns.length > 0) {
    // Clear current selection
    Array.from(nameComposeSelect.options).forEach(option => option.selected = false);
    
    // Select the matched columns
    selectedNameColumns.forEach(columnName => {
      const option = Array.from(nameComposeSelect.options).find(opt => opt.value === columnName);
      if (option) {
        option.selected = true;
      }
    });
    
    // Add visual indicator for auto-selected name columns
    addAutoSelectionIndicator(nameComposeSelect, "name");
  }
  
  // Auto-select team column using exact matching first, then fuzzy matching
  const selectedTeamColumn = autoSelectTeamColumn(headers);
  if (selectedTeamColumn) {
    teamSelect.value = selectedTeamColumn;
    // Add visual indicator for auto-selected team column
    addAutoSelectionIndicator(teamSelect, "team");
  }
}

function autoSelectNameColumns(headers) {
  const selectedColumns = [];
  
  // Exact match patterns for first name
  const firstNameExactPatterns = ["FirstName", "First_Name", "first_name", "First Name", "first name", "First", "first"];
  // Exact match patterns for last name
  const lastNameExactPatterns = ["LastName", "Last_Name", "last_name", "Last Name", "last name", "Last", "last"];
  
  // Try exact matching first
  let firstNameColumn = findExactMatch(headers, firstNameExactPatterns);
  let lastNameColumn = findExactMatch(headers, lastNameExactPatterns);
  
  // If exact matching fails, try fuzzy matching
  if (!firstNameColumn) {
    firstNameColumn = findFuzzyMatch(headers, firstNameExactPatterns);
  }
  if (!lastNameColumn) {
    lastNameColumn = findFuzzyMatch(headers, lastNameExactPatterns);
  }
  
  // Add matched columns to selection
  if (firstNameColumn) selectedColumns.push(firstNameColumn);
  if (lastNameColumn) selectedColumns.push(lastNameColumn);
  
  return selectedColumns;
}

function autoSelectTeamColumn(headers) {
  // Exact match patterns for team
  const teamExactPatterns = ["Team", "team", "TEAM", "Tm", "tm", "TM"];
  
  // Try exact matching first
  let teamColumn = findExactMatch(headers, teamExactPatterns);
  
  // If exact matching fails, try fuzzy matching
  if (!teamColumn) {
    teamColumn = findFuzzyMatch(headers, teamExactPatterns);
  }
  
  return teamColumn;
}

function findExactMatch(headers, patterns) {
  for (const pattern of patterns) {
    const exactMatch = headers.find(header => header === pattern);
    if (exactMatch) {
      return exactMatch;
    }
  }
  return null;
}

function findFuzzyMatch(headers, patterns) {
  // Use Fuse.js for fuzzy matching
  const fuse = new Fuse(headers, {
    threshold: 0.3, // Lower threshold for more strict matching
    includeScore: true
  });
  
  let bestMatch = null;
  let bestScore = 1; // Lower score is better
  
  for (const pattern of patterns) {
    const results = fuse.search(pattern);
    if (results.length > 0 && results[0].score < bestScore) {
      bestMatch = results[0].item;
      bestScore = results[0].score;
    }
  }
  
  // Only return if we have a reasonably good match
  return bestScore < 0.4 ? bestMatch : null;
}

function addAutoSelectionIndicator(element, type) {
  // Remove any existing indicators
  const existingIndicator = element.parentNode.querySelector('.auto-selected-indicator');
  if (existingIndicator) {
    existingIndicator.remove();
  }
  
  // Add new indicator
  const indicator = document.createElement('span');
  indicator.className = 'auto-selected-indicator';
  indicator.textContent = ` (auto-selected ${type})`;
  indicator.style.color = "#28a745";
  indicator.style.fontSize = "0.9em";
  indicator.style.fontWeight = "normal";
  indicator.style.marginLeft = "4px";
  
  element.parentNode.appendChild(indicator);
}
function fillMultiSelect(sel, headers) {
  sel.innerHTML = "";
  headers.forEach(h => {
    const o=document.createElement("option"); o.value=h; o.textContent=h; sel.appendChild(o);
  });
}
function fillRequiredMapping(headers) {
  requiredMapping.innerHTML = "";
  const requiredCols = REQUIRED_COLUMNS;
  
  // Auto-select logic: find exact matches between headers and required columns
  // Consider both sheets A and B separately for auto-selection
  const autoSelected = {};
  
  requiredCols.forEach(colName => {
    // Count exact matches in Sheet A headers (case-sensitive, space-sensitive)
    const exactMatchesA = headersA.filter(h => h === colName);
    // Count exact matches in Sheet B headers (case-sensitive, space-sensitive)
    const exactMatchesB = headersB.filter(h => h === colName);
    
    // Auto-select logic:
    // - Auto-select if exactly one sheet has the exact match and the other doesn't
    // - Don't auto-select if both sheets have the exact same column name (ambiguous)
    // - Don't auto-select if no exact matches exist
    if (exactMatchesA.length === 1 && exactMatchesB.length === 0) {
      // Only Sheet A has exact match - auto-select from Sheet A
      autoSelected[colName] = exactMatchesA[0];
    } else if (exactMatchesB.length === 1 && exactMatchesA.length === 0) {
      // Only Sheet B has exact match - auto-select from Sheet B
      autoSelected[colName] = exactMatchesB[0];
    }
    // If both sheets have exact match (exactMatchesA.length > 0 && exactMatchesB.length > 0), don't auto-select
    // If no exact matches exist, don't auto-select
  });
  
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
    
    // Auto-select if condition met
    if (autoSelected[colName]) {
      select.value = autoSelected[colName];
      columnMapping.required[colName] = autoSelected[colName];
      
      // Add visual indicator for auto-selected columns
      const indicator = document.createElement("span");
      indicator.textContent = " (auto-selected)";
      indicator.style.color = "#28a745";
      indicator.style.fontSize = "0.9em";
      indicator.style.fontWeight = "normal";
      label.appendChild(indicator);
    }
    
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
  const requiredCols = REQUIRED_COLUMNS;
  
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

// Set default name mode to "Compose from Columns" for both files
nameModeA.value = "compose";
nameModeB.value = "compose";
toggleNameMode("A");
toggleNameMode("B");

fileA.addEventListener("change", e => {
  const f = e.target.files[0]; if (!f) return;
  parseCSV(f, (err, res) => {
    if (err) { metaA.textContent = "Error parsing A: " + err; return; }
    A = res.data; headersA = res.meta.fields || [];
    metaA.textContent = `${f.name} — ${A.length} rows, ${headersA.length} columns`;
    fillSelect(nameA, headersA); fillSelect(teamA, headersA);
    fillMultiSelect(nameACompose, headersA);
    fillRequiredMapping([...headersA, ...headersB]);
    // Auto-select name and team columns for File A
    autoSelectNameAndTeamColumns("A", headersA);
    
    // Trigger team validation if both files are loaded
    if (A && B) {
      console.log("📥 File A loaded, triggering team validation...");
      triggerTeamValidation();
    }
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
    // Auto-select name and team columns for File B
    autoSelectNameAndTeamColumns("B", headersB);
    
    // Trigger team validation if both files are loaded
    if (A && B) {
      console.log("📥 File B loaded, triggering team validation...");
      triggerTeamValidation();
    }
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

function buildIndex(rows, getName, teamCol, manualTeamMappings = {}) {
  const aliases = getAliases();
  console.log(`🔍 buildIndex: Processing ${rows.length} rows with manualTeamMappings:`, manualTeamMappings);
  
  const items = rows.map(r => {
    let teamCode = canonTeam(r[teamCol]);
    const originalTeamCode = teamCode;
    
    // Apply manual team mapping if exists
    if (manualTeamMappings[teamCode]) {
      console.log(`   🔀 buildIndex mapping: ${teamCode} → ${manualTeamMappings[teamCode]}`);
      teamCode = manualTeamMappings[teamCode];
    }
    
    let nameRaw = getName(r);
    let n = normName(nameRaw);
    if (isDSTName(nameRaw, teamCode)) n = dstNormalizedName(nameRaw, teamCode);
    const aliasKey = teamCode + "::" + n;
    const aliased = aliases[aliasKey];
    const finalName = aliased || n;
    
    if (originalTeamCode !== teamCode) {
      console.log(`   ✅ buildIndex applied mapping: ${originalTeamCode} → ${teamCode} for player: ${nameRaw}`);
    }
    
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
    fuseByTeam.set(t, new Fuse(arr, {
      keys: ["_norm_name"],
      threshold: 0.4,
      includeScore: true,
      ignoreLocation: true,
      distance: 80,
    }));
  }
  return { items, map, fuseByTeam, byTeam };
}

// Remove old gatherKeep function - no longer needed

// Team validation functions
function runTeamValidation() {
  console.log("🔍 runTeamValidation() called");
  if (!A || !B) {
    console.log("❌ Validation failed: Missing A or B data");
    return false;
  }
  
  const primary = [...document.querySelectorAll('input[name="primary"]')].find(r => r.checked)?.value || "A";
  const teamP = primary === "A" ? teamA.value : teamB.value;
  const teamS = primary === "A" ? teamB.value : teamA.value;
  
  console.log(`📊 Primary: ${primary}, TeamP: ${teamP}, TeamS: ${teamS}`);
  
  if (!teamP || !teamS || teamP.startsWith("—") || teamS.startsWith("—")) {
    console.log("❌ Validation failed: Invalid team column selections");
    return false;
  }
  
  // Extract teams from both datasets
  const getNameA = buildNameGetter(nameModeA.value, nameA, nameACompose, nameASeparator.value);
  const getNameB = buildNameGetter(nameModeB.value, nameB, nameBCompose, nameBSeparator.value);
  
  const P = primary === "A" ? A : B;
  const S = primary === "A" ? B : A;
  
  console.log(`📊 Dataset sizes: P=${P.length}, S=${S.length}`);
  
  teamValidationState.teamsA = extractUniqueTeamCodes(P, teamP, getNameA);
  teamValidationState.teamsB = extractUniqueTeamCodes(S, teamS, getNameB);
  
  console.log(`🏈 Teams extracted - Sheet 1:`, Array.from(teamValidationState.teamsA));
  console.log(`🏈 Teams extracted - Sheet 2:`, Array.from(teamValidationState.teamsB));
  
  // Load existing manual mappings for this sport
  const sport = sportSelect.value;
  teamValidationState.manualMappings = getTeamMappings(sport);
  console.log(`💾 Loaded manual mappings for ${sport}:`, teamValidationState.manualMappings);
  
  // Validate team matches
  const validationResult = validateTeamMatches(
    teamValidationState.teamsA,
    teamValidationState.teamsB,
    teamValidationState.manualMappings
  );
  
  console.log(`✅ Validation result:`, validationResult);
  
  return validationResult;
}

function renderTeamMappingUI(validationResult) {
  console.log("🎨 renderTeamMappingUI called with:", validationResult);
  
  teamMappingContainer.innerHTML = "";
  
  if (validationResult.allMatched) {
    console.log("✅ All teams matched, hiding mapping section");
    teamMappingSection.style.display = "none";
    teamValidationStatus.innerHTML = `
      <span class="chip ok">✓ All teams matched</span>
      <span class="small muted">(${validationResult.matched.length} teams from Sheet 1 have matches in Sheet 2)</span>
    `;
    btnMerge.disabled = false;
    return;
  }
  
  // Show manual mapping interface
  console.log(`⚠️ Showing mapping interface for ${validationResult.unmatched.length} unmatched teams`);
  teamMappingSection.style.display = "block";
  teamValidationStatus.innerHTML = `
    <span class="chip warn">⚠ ${validationResult.unmatched.length} teams need mapping</span>
    <span class="small muted">(${validationResult.matched.length} teams matched automatically)</span>
  `;
  
  const availableTeams = getAvailableSheet2Teams(teamValidationState.teamsB);
  console.log(`📋 Available Sheet 2 teams:`, availableTeams);
  
  validationResult.unmatched.forEach(teamA => {
    console.log(`   🎯 Creating mapping row for: ${teamA}`);
    const row = document.createElement("div");
    row.className = "team-mapping-row";
    
    const teamLabel = document.createElement("span");
    teamLabel.className = "team-mapping-label";
    teamLabel.textContent = teamA;
    
    const arrow = document.createElement("span");
    arrow.className = "team-mapping-arrow";
    arrow.textContent = "→";
    
    const select = document.createElement("select");
    select.className = "team-mapping-select";
    
    // Add "Team missing" option for bigger slates
    const missingOpt = document.createElement("option");
    missingOpt.value = "";
    missingOpt.textContent = "— Team missing —";
    select.appendChild(missingOpt);
    
    // Add available teams from Sheet 2
    availableTeams.forEach(teamB => {
      const opt = document.createElement("option");
      opt.value = teamB;
      opt.textContent = teamB;
      select.appendChild(opt);
    });
    
    // Set current value if mapping exists
    if (teamValidationState.manualMappings[teamA]) {
      select.value = teamValidationState.manualMappings[teamA];
      console.log(`   💾 Restored mapping: ${teamA} → ${teamValidationState.manualMappings[teamA]}`);
    }

    select.addEventListener("change", () => {
      console.log(`   🔄 Mapping changed: ${teamA} → ${select.value}`);
      if (select.value) {
        teamValidationState.manualMappings[teamA] = select.value;
      } else {
        delete teamValidationState.manualMappings[teamA];
      }
      updateRunMatchButtonState();
    });
    
    row.appendChild(teamLabel);
    row.appendChild(arrow);
    row.appendChild(select);
    teamMappingContainer.appendChild(row);
  });
  
  console.log(`✅ renderTeamMappingUI completed, created ${validationResult.unmatched.length} mapping rows`);
  updateRunMatchButtonState();
}

function updateRunMatchButtonState() {
  // Re-validate with current manual mappings
  const validationResult = validateTeamMatches(
    teamValidationState.teamsA,
    teamValidationState.teamsB,
    teamValidationState.manualMappings
  );
  
  btnMerge.disabled = !validationResult.allMatched;
  
  if (validationResult.allMatched) {
    teamValidationStatus.innerHTML = `
      <span class="chip ok">✓ All teams mapped</span>
      <span class="small muted">Ready to run match</span>
    `;
  }
}

// Event listeners for team validation buttons
if (btnSaveTeamMappings) {
  btnSaveTeamMappings.addEventListener("click", () => {
    const sport = sportSelect.value;
    setTeamMappings(sport, teamValidationState.manualMappings);
    
    // Re-run validation with saved mappings
    const validationResult = runTeamValidation();
    if (validationResult) {
      renderTeamMappingUI(validationResult);
    }
    
    alert("Team mappings saved for future use.");
  });
}

if (btnSkipTeamValidation) {
  btnSkipTeamValidation.addEventListener("click", () => {
    teamValidationState.validationComplete = true;
    teamValidationSection.style.display = "none";
    btnMerge.disabled = false;
    status.textContent = "Team validation skipped. Proceed with caution.";
  });
}

document.getElementById("btnMerge").addEventListener("click", () => {
  if (!A || !B) { status.textContent = "Upload both files first."; return; }
  
  // Validate required columns
  const validationError = validateRequiredMapping();
  if (validationError) {
    status.textContent = validationError;
    return;
  }

  // Run team validation if not already completed
  if (!teamValidationState.validationComplete) {
    const validationResult = runTeamValidation();
    if (!validationResult) {
      status.textContent = "Team validation failed. Check team column selections.";
      return;
    }
    
    teamValidationSection.style.display = "block";
    renderTeamMappingUI(validationResult);
    
    if (!validationResult.allMatched) {
      status.textContent = "Please map all teams before running match.";
      return;
    }
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
  
  // Load manual team mappings for the current sport
  const sport = sportSelect.value;
  const manualTeamMappings = {
    ...getTeamMappings(sport),
    ...(teamValidationState?.manualMappings || {}),
  };
  console.log(`💾 Loaded manual team mappings for ${sport}:`, manualTeamMappings);
  
  const Sidx = buildIndex(S, nameGetterS, teamS, manualTeamMappings);
  console.log(`✅ Secondary index built with ${Sidx.items.length} items`);

  let auto=0, review=0, missing=0;
  let merged = [];
  reviewItems = [];

  for (let i=0;i<P.length;i++) {
    const pr = P[i];
    let teamCode = canonTeam(pr[teamP]);
    
    // Apply manual team mapping to primary dataset team code
    if (manualTeamMappings[teamCode]) {
      console.log(`🔀 Applying manual team mapping: ${teamCode} → ${manualTeamMappings[teamCode]}`);
      teamCode = manualTeamMappings[teamCode];
    }
    
    let rawName = nameGetterP(pr);
    let norm = normName(rawName);
    if (isDSTName(rawName, teamCode)) norm = dstNormalizedName(rawName, teamCode);

    const aliases = getAliases();
    const aliasKey = teamCode + "::" + norm;
    const aliasedNorm = aliases[aliasKey] || norm;

    let match = null, reason = "";
    const hard = Sidx.map.get(aliasedNorm + "||" + teamCode) || [];
    if (hard.length === 1) {
      match = hard[0].row;
      reason = "exact";
      auto++;
      console.log(`✅ Exact match found: ${rawName} (${teamCode})`);
    }
    else if (hard.length > 1) {
      match = hard[0].row;
      reason = "exact_multi";
      auto++;
      console.log(`✅ Exact match (multiple): ${rawName} (${teamCode})`);
    }
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
          console.log(`⚠️ Review needed: ${rawName} (${teamCode}) - ${res.length} candidates`);
        } else {
          reason = "missing"; missing++;
          reviewItems.push({ idx:i, projRow: pr, teamCode, candidates: [], choice: "", saveAlias: false, rawName });
          console.log(`❌ No match found: ${rawName} (${teamCode})`);
        }
      } else {
        reason = "missing"; missing++;
        reviewItems.push({ idx:i, projRow: pr, teamCode, candidates: [], choice: "", saveAlias: false, rawName });
        console.log(`❌ No team index: ${rawName} (${teamCode})`);
      }
    }

    const out = {};
    
    // Map required columns
    const requiredCols = REQUIRED_COLUMNS;
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
  const filename = generateDynamicFilename();
  download(filename, csv);
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

// Test function for auto-selection logic (for debugging)
function testAutoSelectionLogic() {
  console.log("Testing auto-selection logic...");
  
  // Test scenarios
  const testCases = [
    {
      name: "Sheet A has 'Position', Sheet B has 'positions'",
      headersA: ["Position", "First Name"],
      headersB: ["positions", "First Name"],
      expectedAutoSelected: {
        "Position": "Position" // Should auto-select from Sheet A
      }
    },
    {
      name: "Sheet A has 'Position', Sheet B has 'Position'",
      headersA: ["Position", "First Name"],
      headersB: ["Position", "First Name"],
      expectedAutoSelected: {} // Should NOT auto-select (ambiguous)
    },
    {
      name: "Sheet A has 'Position', Sheet B has 'Pos'",
      headersA: ["Position", "First Name"],
      headersB: ["Pos", "First Name"],
      expectedAutoSelected: {} // Should NOT auto-select (not exact match)
    },
    {
      name: "Sheet A has no match, Sheet B has 'Position'",
      headersA: ["First Name"],
      headersB: ["Position", "First Name"],
      expectedAutoSelected: {
        "Position": "Position" // Should auto-select from Sheet B
      }
    }
  ];
  
  testCases.forEach((testCase, index) => {
    console.log(`Test ${index + 1}: ${testCase.name}`);
    
    // Simulate the auto-selection logic
    const requiredCols = ["Position", "First Name", "Last Name"];
    const autoSelected = {};
    
    requiredCols.forEach(colName => {
      const exactMatchesA = testCase.headersA.filter(h => h === colName);
      const exactMatchesB = testCase.headersB.filter(h => h === colName);
      
      if (exactMatchesA.length === 1 && exactMatchesB.length === 0) {
        autoSelected[colName] = exactMatchesA[0];
      } else if (exactMatchesB.length === 1 && exactMatchesA.length === 0) {
        autoSelected[colName] = exactMatchesB[0];
      }
    });
    
    // Check if results match expected
    const passed = JSON.stringify(autoSelected) === JSON.stringify(testCase.expectedAutoSelected);
    console.log(`  Expected:`, testCase.expectedAutoSelected);
    console.log(`  Got:`, autoSelected);
    console.log(`  ${passed ? "✓ PASS" : "✗ FAIL"}`);
  });
}

// Uncomment the line below to run tests in browser console
// testAutoSelectionLogic();

// Test function for Step 2 smart defaults (for debugging)
function testStep2SmartDefaults() {
  console.log("Testing Step 2 smart defaults...");
  
  // Test scenarios for name and team column matching
  const testCases = [
    {
      name: "Standard column names",
      headers: ["FirstName", "LastName", "Team", "Position", "Salary"],
      expectedNameColumns: ["FirstName", "LastName"],
      expectedTeamColumn: "Team"
    },
    {
      name: "Underscore column names",
      headers: ["first_name", "last_name", "team", "position", "salary"],
      expectedNameColumns: ["first_name", "last_name"],
      expectedTeamColumn: "team"
    },
    {
      name: "Space separated column names",
      headers: ["First Name", "Last Name", "Team", "Position", "Salary"],
      expectedNameColumns: ["First Name", "Last Name"],
      expectedTeamColumn: "Team"
    },
    {
      name: "Mixed case column names",
      headers: ["FIRSTNAME", "LASTNAME", "TEAM", "POSITION", "SALARY"],
      expectedNameColumns: ["FIRSTNAME", "LASTNAME"],
      expectedTeamColumn: "TEAM"
    },
    {
      name: "Fuzzy matching fallback",
      headers: ["First", "Last", "Tm", "Pos", "Sal"],
      expectedNameColumns: ["First", "Last"],
      expectedTeamColumn: "Tm"
    },
    {
      name: "No matches found",
      headers: ["Player", "Pos", "Sal", "Opp"],
      expectedNameColumns: [],
      expectedTeamColumn: null
    }
  ];
  
  testCases.forEach((testCase, index) => {
    console.log(`Test ${index + 1}: ${testCase.name}`);
    
    // Test name column selection
    const selectedNameColumns = autoSelectNameColumns(testCase.headers);
    const namePassed = JSON.stringify(selectedNameColumns) === JSON.stringify(testCase.expectedNameColumns);
    
    // Test team column selection
    const selectedTeamColumn = autoSelectTeamColumn(testCase.headers);
    const teamPassed = selectedTeamColumn === testCase.expectedTeamColumn;
    
    console.log(`  Headers:`, testCase.headers);
    console.log(`  Expected Name Columns:`, testCase.expectedNameColumns);
    console.log(`  Got Name Columns:`, selectedNameColumns);
    console.log(`  Expected Team Column:`, testCase.expectedTeamColumn);
    console.log(`  Got Team Column:`, selectedTeamColumn);
    console.log(`  Name Selection: ${namePassed ? "✓ PASS" : "✗ FAIL"}`);
    console.log(`  Team Selection: ${teamPassed ? "✓ PASS" : "✗ FAIL"}`);
    console.log(`  Overall: ${namePassed && teamPassed ? "✓ PASS" : "✗ FAIL"}`);
    console.log("---");
  });
}

// Uncomment the line below to run tests in browser console
// testStep2SmartDefaults();

// Team validation trigger function
function triggerTeamValidation() {
  console.log("🚀 triggerTeamValidation() called");
  
  if (!A || !B) {
    console.log("❌ triggerTeamValidation: Missing A or B data");
    return;
  }
  
  const primary = [...document.querySelectorAll('input[name="primary"]')].find(r => r.checked)?.value || "A";
  const teamP = primary === "A" ? teamA.value : teamB.value;
  const teamS = primary === "A" ? teamB.value : teamA.value;
  
  console.log(`📊 triggerTeamValidation - Primary: ${primary}, TeamP: ${teamP}, TeamS: ${teamS}`);
  
  if (!teamP || !teamS || teamP.startsWith("—") || teamS.startsWith("—")) {
    console.log("❌ triggerTeamValidation: Invalid team column selections");
    return;
  }
  
  // Run team validation
  const validationResult = runTeamValidation();
  if (validationResult) {
    console.log("✅ triggerTeamValidation: Validation completed, rendering UI");
    renderTeamMappingUI(validationResult);
    teamValidationSection.style.display = "block";
  } else {
    console.log("❌ triggerTeamValidation: Validation failed");
  }
}

// Add event listeners for team column changes
if (teamA) {
  teamA.addEventListener("change", () => {
    console.log("🔄 Team A column changed, triggering validation");
    if (A && B) triggerTeamValidation();
  });
}

if (teamB) {
  teamB.addEventListener("change", () => {
    console.log("🔄 Team B column changed, triggering validation");
    if (A && B) triggerTeamValidation();
  });
}

// Add event listener for primary file selection changes
document.querySelectorAll('input[name="primary"]').forEach(radio => {
  radio.addEventListener("change", () => {
    console.log("🔄 Primary file selection changed, triggering validation");
    if (A && B) triggerTeamValidation();
  });
});

// Test function for manual team mapping integration
function testManualTeamMappingIntegration() {
  console.log("🧪 Testing manual team mapping integration...");
  
  // Test scenario: Manual mapping of "NYG" to "NYJ"
  const testManualMappings = {
    "NYG": "NYJ"
  };
  
  // Create test data
  const testRows = [
    { Name: "Saquon Barkley", Team: "NYG" },
    { Name: "Aaron Rodgers", Team: "NYJ" },
    { Name: "Daniel Jones", Team: "NYG" }
  ];
  
  const getName = (row) => row.Name;
  const teamCol = "Team";
  
  console.log("📋 Test data:", testRows);
  console.log("🗺️ Manual mappings:", testManualMappings);
  
  // Test buildIndex with manual mappings
  const index = buildIndex(testRows, getName, teamCol, testManualMappings);
  
  console.log("🔍 Index items:");
  index.items.forEach(item => {
    console.log(`   - ${item.row.Name} (${item.row.Team}) → ${item._norm_team}`);
  });
  
  // Verify mappings were applied
  const nygPlayers = index.items.filter(item => item.row.Team === "NYG");
  const nyjPlayers = index.items.filter(item => item.row.Team === "NYJ");
  
  console.log("✅ Verification:");
  console.log(`   - NYG players (${nygPlayers.length}):`, nygPlayers.map(p => p.row.Name));
  console.log(`   - NYJ players (${nyjPlayers.length}):`, nyjPlayers.map(p => p.row.Name));
  
  // Check if NYG players were mapped to NYJ
  const mappedPlayers = nygPlayers.filter(p => p._norm_team === "NYJ");
  console.log(`   - NYG → NYJ mappings: ${mappedPlayers.length}/${nygPlayers.length}`);
  
  if (mappedPlayers.length === nygPlayers.length) {
    console.log("🎉 SUCCESS: All manual team mappings were properly applied in buildIndex!");
  } else {
    console.log("❌ FAILURE: Manual team mappings were not properly applied.");
  }
  
  return mappedPlayers.length === nygPlayers.length;
}

// Uncomment the line below to run the test in browser console
// testManualTeamMappingIntegration();
