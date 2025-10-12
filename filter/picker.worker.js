// picker.worker.js
// Greedy selection with breadth and stack bonuses

self.onmessage = (ev) => {
  const { type, payload } = ev.data || {};
  try {
    if (type === 'PICK') {
      const { lineups, params } = payload;
      const result = pickMME(lineups, params);
      self.postMessage({ type:'SELECTION', payload: result });
    }
  } catch (e) {
    self.postMessage({ type:'ERROR', payload:{ message: String(e) } });
  }
};

function pickMME(lineups, params) {
  const N = params.n || 150;
  const capPct = params.capPct || 25;
  const maxRepeatInit = params.maxRepeat || 4;
  const mix = clamp(params.mix ?? 0.2, 0, 1);
  const bonusQB2 = params.bonusQB2 || 6;
  const bonusBring = params.bonusBring || 3;
  const lambda = params.lambda || 2;

  // Pre-score by projection + stack bonus
  const scored = lineups.map((L, idx) => {
    const stackBonus = (L.qb2 ? bonusQB2 : 0) + (L.bringback ? bonusBring : 0);
    return { idx, id:L.id, proj:L.proj, salary:L.salary, players:L.players, qb2:L.qb2, bringback:L.bringback, base: L.proj + stackBonus };
  });

  // Sort by base score desc
  scored.sort((a,b) => b.base - a.base);

  // Exposure cap in counts
  const capCount = Math.floor((capPct/100) * N + 1e-6); // e.g., 25% of 150 => 37
  const playerCounts = Object.create(null);
  const chosen = [];
  let maxRepeat = maxRepeatInit;

  // For diversity, track popularity estimates (start equal, update as picked)
  const pop = Object.create(null);

  const consider = scored.slice(); // copy
  let itersWithoutPick = 0;

  while (chosen.length < N && consider.length) {
    // Rescore top slice periodically
    const slice = consider.slice(0, 5000); // evaluate window
    let best = null, bestScore = -Infinity, bestIdx = -1;

    for (let i=0;i<slice.length;i++) {
      const cand = slice[i];
      if (!passesCaps(cand, chosen, playerCounts, capCount, maxRepeat)) continue;
      const divPenalty = diversityPenalty(cand, playerCounts, capCount, lambda, pop);
      // blended score: (1-mix)*base - mix*penalty
      const score = (1-mix)*cand.base - mix*divPenalty;
      if (score > bestScore) { bestScore = score; best = cand; bestIdx = i; }
    }

    if (best) {
      chosen.push(best);
      // update counts & pop
      for (const pid of best.players) {
        playerCounts[pid] = (playerCounts[pid] || 0) + 1;
        pop[pid] = (pop[pid] || 0) + 1;
      }
      // remove best from consideration
      const globalIdx = consider.findIndex(x => x.idx === best.idx);
      if (globalIdx >= 0) consider.splice(globalIdx,1);
      itersWithoutPick = 0;
    } else {
      // If stuck, relax maxRepeat a bit
      itersWithoutPick++;
      if (itersWithoutPick > 3 && maxRepeat < 6) { maxRepeat++; itersWithoutPick = 0; }
      // Also widen the window by dropping some head elements to avoid local traps
      consider.splice(0, Math.min(500, consider.length));
    }
  }

  // Materialize chosen objects
  const selected = chosen.map(c => ({
    id: c.id,
    salary: c.salary,
    proj: c.proj,
    qb2: c.qb2,
    bringback: c.bringback,
    players: c.players
  }));

  return { selected, capCount, playerCounts };
}

function passesCaps(cand, chosen, playerCounts, capCount, maxRepeat) {
  // Exposure: no player can exceed capCount if chosen
  for (const pid of cand.players) {
    const next = (playerCounts[pid] || 0) + 1;
    if (next > capCount) return false;
  }
  // Max repeating players with any already chosen lineup
  for (const ch of chosen) {
    const overlap = countOverlap(ch.players, cand.players);
    if (overlap > maxRepeat) return false;
  }
  return true;
}

function countOverlap(a, b) {
  let cnt = 0;
  const set = new Set(a);
  for (const x of b) if (set.has(x)) cnt++;
  return cnt;
}

function diversityPenalty(cand, playerCounts, capCount, lambda, pop) {
  // Penalize using how close each player's usage is to cap; earlier picks should spread ownership
  // penalty per player ~ (current_usage / cap)^2
  let pen = 0;
  for (const pid of cand.players) {
    const u = (playerCounts[pid] || 0) / Math.max(1, capCount);
    pen += u*u;
  }
  // small penalty for being very similar to many already-chosen players
  // proportional to average popularity among its players
  let avgPop = 0;
  for (const pid of cand.players) avgPop += (pop[pid] || 0);
  avgPop /= Math.max(1, cand.players.length);
  return lambda * (pen + 0.02*avgPop);
}

function clamp(x, lo, hi){ return Math.max(lo, Math.min(hi, x)); }
