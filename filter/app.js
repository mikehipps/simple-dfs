// Minimal offline NFL 150 MME picker
// - Parses two CSVs (lineups + projections)
// - Header mapping UI
// - Sends normalized data to Web Worker for greedy selection
// - Displays selected 150 and exports CSV

const els = {
  pickLineups: document.getElementById('pick-lineups'),
  pickProj: document.getElementById('pick-proj'),
  lineupsFile: document.getElementById('lineups-file'),
  projFile: document.getElementById('proj-file'),
  lineupsName: document.getElementById('lineups-name'),
  projName: document.getElementById('proj-name'),
  loadSamples: document.getElementById('load-samples'),
  mapping: document.getElementById('mapping'),
  mLineupId: document.getElementById('m-lineup-id'),
  mSalary: document.getElementById('m-salary'),
  mPlayers: document.getElementById('m-players'),
  mPlayerId: document.getElementById('m-player-id'),
  mProj: document.getElementById('m-proj'),
  mPos: document.getElementById('m-pos'),
  mTeam: document.getElementById('m-team'),
  mOpp: document.getElementById('m-opp'),
  capPct: document.getElementById('cap-pct'),
  maxRepeat: document.getElementById('max-repeat'),
  nLineups: document.getElementById('n-lineups'),
  mix: document.getElementById('mix'),
  mixLabel: document.getElementById('mix-label'),
  bQB2: document.getElementById('b-qb2'),
  bBring: document.getElementById('b-bring'),
  penLam: document.getElementById('pen-lam'),
  buildBtn: document.getElementById('build-btn'),
  exportBtn: document.getElementById('export-btn'),
  status: document.getElementById('status'),
  tblBody: document.querySelector('#tbl tbody'),
  summary: document.getElementById('summary'),
};

let lineupsCSV, projCSV;
let lineupsData = null, projData = null;
let selected = [];
let worker = new Worker('picker.worker.js', { type:'module' });

function readFile(file) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(new TextDecoder().decode(fr.result));
    fr.onerror = reject;
    fr.readAsArrayBuffer(file);
  });
}

// Basic CSV parser (handles quotes and commas)
function parseCSV(text) {
  const rows = [];
  let i=0, field='', row=[], inQuotes=false;
  while (i < text.length) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i+1] === '"') { field += '"'; i++; }
        else { inQuotes = false; }
      } else { field += c; }
    } else {
      if (c === ',') { row.push(field); field=''; }
      else if (c === '\n' || c === '\r') {
        if (c === '\r' && text[i+1] === '\n') i++;
        row.push(field); field=''; if (row.length>1 || row[0] !== '') rows.push(row); row=[];
      } else if (c === '"') { inQuotes = true; }
      else { field += c; }
    }
    i++;
  }
  if (field.length || row.length) { row.push(field); rows.push(row); }
  // Trim trailing empty lines
  return rows.filter(r => r.some(x => x !== ''));
}

function headerOptions(headers) {
  return headers.map(h => `<option value="${h}">${h}</option>`).join('');
}

function populateMappingUI(headersA, headersB) {
  els.mLineupId.innerHTML = headerOptions(headersA);
  els.mSalary.innerHTML = headerOptions(headersA);
  els.mPlayers.innerHTML = headerOptions(headersA);
  els.mPlayers.size = Math.min(8, headersA.length);
  els.mPlayerId.innerHTML = headerOptions(headersB);
  els.mProj.innerHTML = headerOptions(headersB);
  els.mPos.innerHTML = headerOptions(headersB);
  els.mTeam.innerHTML = headerOptions(headersB);
  els.mOpp.innerHTML = headerOptions(headersB);
  els.mapping.classList.remove('hidden');
  els.buildBtn.disabled = false;
}

function getSelectedOptions(sel) {
  return Array.from(sel.selectedOptions).map(o => o.value);
}

function normalize(lineupsRows, projRows, map) {
  // Build projection map
  const idxP = {
    id: projRows.headers.indexOf(map.playerId),
    pr: projRows.headers.indexOf(map.proj),
    pos: projRows.headers.indexOf(map.pos),
    team: projRows.headers.indexOf(map.team),
    opp: projRows.headers.indexOf(map.opp),
  };
  const proj = new Map();
  const meta = new Map();
  for (const r of projRows.data) {
    const id = r[idxP.id];
    const p = parseFloat(r[idxP.pr] || '0') || 0;
    proj.set(id, p);
    meta.set(id, { pos: r[idxP.pos]||'', team: r[idxP.team]||'', opp: r[idxP.opp]||'' });
  }

  // Normalize lineups
  const idxL = {
    id: lineupsRows.headers.indexOf(map.lineupId),
    sal: lineupsRows.headers.indexOf(map.salary),
    players: map.players.map(h => lineupsRows.headers.indexOf(h)),
  };
  const lineups = [];
  for (const r of lineupsRows.data) {
    const id = r[idxL.id];
    const salary = parseInt(r[idxL.sal] || '0', 10) || 0;
    const players = idxL.players.map(i => r[i]).filter(Boolean);
    // compute projection sum
    let projSum = 0;
    for (const pid of players) projSum += (proj.get(pid) || 0);
    // QB stack + bringback heuristics
    let qbCountSameTeam = 0, bringBack = 0;
    let qbTeam = null, oppTeam = null;
    for (const pid of players) {
      const m = meta.get(pid);
      if (!m) continue;
      if (m.pos === 'QB') { qbTeam = m.team; oppTeam = m.opp; }
    }
    if (qbTeam) {
      for (const pid of players) {
        const m = meta.get(pid); if (!m) continue;
        if (m.team === qbTeam && (m.pos === 'WR' || m.pos === 'TE' || m.pos === 'RB')) qbCountSameTeam++;
        if (m.team === oppTeam) bringBack++;
      }
    }
    lineups.push({ id, salary, players, proj: projSum, qb2: qbCountSameTeam >= 2, bringback: bringBack >= 1 });
  }
  return lineups;
}

function summarize(selected, capCount, playerCounts) {
  const totalProj = selected.reduce((a, x) => a + x.proj, 0).toFixed(2);
  const maxExp = Math.max(...Object.values(playerCounts||{0:0}));
  const line = `Picked ${selected.length} | Total proj ${totalProj} | Max player exposure ${maxExp}/${capCount} (${((maxExp/selected.length)*100).toFixed(1)}%)`;
  els.summary.textContent = line;
}

function renderTable(rows) {
  const tb = els.tblBody;
  tb.innerHTML = '';
  rows.forEach((r, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${i+1}</td><td>${r.id}</td><td>${r.proj.toFixed(2)}</td><td>${r.salary}</td><td>${r.qb2 ? 'QB+2' : '-'}</td><td>${r.bringback ? 'Y' : '-'}</td><td class="muted">${r.players.join(' | ')}</td>`;
    tb.appendChild(tr);
  });
}

function downloadCSV(filename, rows) {
  const headers = ['lineup_id','salary','proj','players'];
  const lines = [headers.join(',')];
  for (const r of rows) lines.push([r.id, r.salary, r.proj.toFixed(2), '"' + r.players.join('|') + '"'].join(','));
  const blob = new Blob([lines.join('\n')], { type:'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// Wire up UI
els.pickLineups.onclick = () => els.lineupsFile.click();
els.pickProj.onclick = () => els.projFile.click();

els.loadSamples.onclick = async () => {
  // Provide small inline samples for quick demo
  const l = `lineup_id,salary,p1,p2,p3,p4,p5,p6,p7,p8,p9
L1,49500,AQB,AWR1,AWR2,ARB1,ARB2,ATE1,AFLEX1,AFLEX2,ADST
L2,50000,BQB,BWR1,BWR2,BRB1,BRB2,BTE1,BFLEX1,BFLEX2,BDST
L3,49200,CQB,CWR1,CWR2,CRB1,CRB2,CTE1,CFLEX1,CFLEX2,CDST`;
  const p = `player_id,proj,pos,team,opp
AQB,20.5,QB,ARI,SF
AWR1,15.2,WR,ARI,SF
AWR2,12.1,WR,ARI,SF
ARB1,14.0,RB,ARI,SF
ARB2,9.3,RB,ARI,SF
ATE1,8.2,TE,ARI,SF
AFLEX1,7.0,WR,ARI,SF
AFLEX2,6.5,RB,ARI,SF
ADST,5.0,DST,ARI,SF
BQB,21.0,QB,BUF,MIA
BWR1,14.0,WR,BUF,MIA
BWR2,12.5,WR,BUF,MIA
BRB1,11.0,RB,BUF,MIA
BRB2,8.0,RB,BUF,MIA
BTE1,7.0,TE,BUF,MIA
BFLEX1,6.0,WR,BUF,MIA
BFLEX2,6.0,RB,BUF,MIA
BDST,4.5,DST,BUF,MIA
CQB,19.5,QB,CLE,BAL
CWR1,13.5,WR,CLE,BAL
CWR2,11.0,WR,CLE,BAL
CRB1,10.0,RB,CLE,BAL
CRB2,7.5,RB,CLE,BAL
CTE1,6.5,TE,CLE,BAL
CFLEX1,5.5,WR,CLE,BAL
CFLEX2,5.5,RB,CLE,BAL
CDST,5.0,DST,CLE,BAL`;
  lineupsCSV = l; projCSV = p;
  els.lineupsName.textContent = '(sample loaded)'; els.projName.textContent = '(sample loaded)';
  const lRows = parseCSV(lineupsCSV); const pRows = parseCSV(projCSV);
  const lHeaders = lRows[0]; const pHeaders = pRows[0];
  populateMappingUI(lHeaders, pHeaders);
};

els.lineupsFile.onchange = async (e) => {
  const f = e.target.files[0]; if (!f) return;
  els.lineupsName.textContent = f.name;
  lineupsCSV = await readFile(f);
  maybeShowMapping();
};
els.projFile.onchange = async (e) => {
  const f = e.target.files[0]; if (!f) return;
  els.projName.textContent = f.name;
  projCSV = await readFile(f);
  maybeShowMapping();
};

function maybeShowMapping() {
  if (!lineupsCSV || !projCSV) return;
  const lRows = parseCSV(lineupsCSV); const pRows = parseCSV(projCSV);
  lineupsData = { headers: lRows[0], data: lRows.slice(1) };
  projData = { headers: pRows[0], data: pRows.slice(1) };
  populateMappingUI(lineupsData.headers, projData.headers);
}

els.mix.oninput = () => { els.mixLabel.textContent = parseFloat(els.mix.value).toFixed(2); };

els.buildBtn.onclick = async () => {
  if (!lineupsData || !projData) return;
  const map = {
    lineupId: els.mLineupId.value,
    salary: els.mSalary.value,
    players: getSelectedOptions(els.mPlayers),
    playerId: els.mPlayerId.value,
    proj: els.mProj.value,
    pos: els.mPos.value,
    team: els.mTeam.value,
    opp: els.mOpp.value,
  };
  if (!map.lineupId || !map.salary || map.players.length < 7) {
    alert('Please map lineup id, salary, and select all player columns.'); return;
  }
  if (!map.playerId || !map.proj) {
    alert('Please map player id and projection columns.'); return;
  }
  els.status.textContent = 'Normalizing...';
  const lineups = normalize(lineupsData, projData, map);
  els.status.textContent = `Lineups ready: ${lineups.length}. Picking...`;

  const params = {
    n: parseInt(els.nLineups.value,10)||150,
    capPct: parseFloat(els.capPct.value)||25,
    maxRepeat: parseInt(els.maxRepeat.value,10)||4,
    mix: parseFloat(els.mix.value)||0.2,
    bonusQB2: parseFloat(els.bQB2.value)||6,
    bonusBring: parseFloat(els.bBring.value)||3,
    lambda: parseFloat(els.penLam.value)||2,
  };
  const t0 = performance.now();
  worker.onmessage = (ev) => {
    const { type, payload } = ev.data;
    if (type === 'SELECTION') {
      selected = payload.selected;
      renderTable(selected);
      summarize(selected, payload.capCount, payload.playerCounts);
      els.exportBtn.disabled = selected.length === 0;
      const dt = (performance.now() - t0).toFixed(0);
      els.status.textContent = `Done in ${dt} ms`;
    } else if (type === 'ERROR') {
      els.status.textContent = payload.message;
    }
  };
  worker.postMessage({ type:'PICK', payload: { lineups, params } });
};

els.exportBtn.onclick = () => {
  if (!selected.length) return;
  downloadCSV('mme150_selected.csv', selected);
};
