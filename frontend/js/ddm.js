/* ddm.js — Dividend Discount Model tab: history table, GGM, and Two-Stage DDM */

/* ── Module state ── */

let _ddmState = null;
let _ddmFullData = null;


/* ── Format helpers (reuse from dcf.js where available) ── */

function ddmFmtPct(decimal) {
  return (decimal * 100).toFixed(1) + '%';
}

function ddmFmtDollar(value) {
  return '$' + value.toFixed(2);
}

function ddmFmtDollar4(value) {
  return '$' + value.toFixed(4);
}

function ddmDash(value, formatFn) {
  return (value == null || isNaN(value)) ? '—' : formatFn(value);
}


/* ── State management ── */

function initDDMState(data) {
  const d = data.ddm_model;
  _ddmFullData = data;

  _ddmState = {
    ticker: data.ticker,
    currentPrice: data.current_price,
    costOfEquity: d.cost_of_equity,
    latestDps: d.latest_annual_dps,
    history: d.history,

    /* GGM editable */
    ggmGrowthRate: d.ggm_growth_rate,

    /* Two-Stage editable */
    tsHighGrowthRate: d.ts_high_growth_rate,
    tsHighGrowthYears: d.ts_high_growth_years,
    tsTerminalGrowthRate: d.ts_terminal_growth_rate,

    /* Track overrides */
    overridden: {
      ggmGrowthRate: false,
      tsHighGrowthRate: false,
      tsHighGrowthYears: false,
      tsTerminalGrowthRate: false,
    },

    /* Defaults snapshot */
    defaults: {
      ggmGrowthRate: d.ggm_growth_rate,
      tsHighGrowthRate: d.ts_high_growth_rate,
      tsHighGrowthYears: d.ts_high_growth_years,
      tsTerminalGrowthRate: d.ts_terminal_growth_rate,
    },
  };
}


/* ── Computation ── */

function computeGGM(s) {
  const d1 = s.latestDps * (1 + s.ggmGrowthRate);
  const denom = s.costOfEquity - s.ggmGrowthRate;
  const iv = (denom > 0 && d1 > 0) ? d1 / denom : 0;
  const upside = (s.currentPrice > 0 && iv > 0)
    ? (iv - s.currentPrice) / s.currentPrice * 100 : 0;
  return { d1, iv, upside };
}

function computeTwoStage(s) {
  const re = s.costOfEquity;
  let pvStage1 = 0;
  let div = s.latestDps;

  for (let t = 1; t <= s.tsHighGrowthYears; t++) {
    div *= (1 + s.tsHighGrowthRate);
    pvStage1 += div / Math.pow(1 + re, t);
  }

  const dTerminal = div * (1 + s.tsTerminalGrowthRate);
  const denom = re - s.tsTerminalGrowthRate;
  let pvTerminal = 0;
  if (denom > 0) {
    const tv = dTerminal / denom;
    pvTerminal = tv / Math.pow(1 + re, s.tsHighGrowthYears);
  }

  const iv = pvStage1 + pvTerminal;
  const upside = (s.currentPrice > 0 && iv > 0)
    ? (iv - s.currentPrice) / s.currentPrice * 100 : 0;
  return { pvStage1, pvTerminal, iv, upside };
}


/* ── Render: dividend history + projection table ── */

function renderDividendHistory() {
  const container = document.getElementById('ddm-history');
  const s = _ddmState;
  const history = s.history;

  if (!history || history.length === 0) {
    container.innerHTML = '<p style="color:var(--muted);font-size:.9rem;">No dividend history available.</p>';
    return;
  }

  /* ── Compute projected dividends using Two-Stage assumptions ── */
  const projYears = s.tsHighGrowthYears;
  const lastHistYear = history[history.length - 1].year;
  let prevDps = s.latestDps;
  const projections = [];

  for (let t = 1; t <= projYears; t++) {
    const g = s.tsHighGrowthRate;
    const dps = prevDps * (1 + g);
    const pv = dps / Math.pow(1 + s.costOfEquity, t);
    projections.push({
      year: lastHistYear + t,
      dps: dps,
      growth: g,
      pv: pv,
    });
    prevDps = dps;
  }

  /* ── Build header ── */
  let headerCells = '<th class="col-label">Metric</th>';
  for (const h of history) {
    headerCells += `<th class="col-actual">FY${h.year}</th>`;
  }
  for (const p of projections) {
    headerCells += `<th>FY${p.year}E</th>`;
  }

  /* ── DPS row ── */
  let dpsRow = '<td>Dividend / Share</td>';
  for (const h of history) {
    dpsRow += `<td class="col-actual">${ddmFmtDollar(h.annual_dps)}</td>`;
  }
  for (const p of projections) {
    dpsRow += `<td>${ddmFmtDollar(p.dps)}</td>`;
  }

  /* ── Growth row ── */
  let growthRow = '<td>DPS Growth (y/y)</td>';
  for (const h of history) {
    growthRow += `<td class="col-actual">${ddmDash(h.dps_growth, ddmFmtPct)}</td>`;
  }
  for (const p of projections) {
    growthRow += `<td>${ddmFmtPct(p.growth)}</td>`;
  }

  /* ── Payout ratio row (historical only) ── */
  let payoutRow = '<td>Payout Ratio</td>';
  for (const h of history) {
    payoutRow += `<td class="col-actual">${ddmDash(h.payout_ratio, ddmFmtPct)}</td>`;
  }
  for (const p of projections) {
    payoutRow += `<td>—</td>`;
  }

  /* ── PV of dividend row (projections only) ── */
  let pvRow = '<td>PV of Dividend</td>';
  for (const h of history) {
    pvRow += `<td class="col-actual">—</td>`;
  }
  for (const p of projections) {
    pvRow += `<td>${ddmFmtDollar(p.pv)}</td>`;
  }

  container.innerHTML = `
    <div class="dcf-proj-wrapper">
      <div class="proj-table-scroll">
        <table class="dcf-proj-table">
          <thead><tr>${headerCells}</tr></thead>
          <tbody>
            <tr class="row-bold">${dpsRow}</tr>
            <tr class="row-italic">${growthRow}</tr>
            <tr class="row-italic">${payoutRow}</tr>
            <tr class="row-fcf">${pvRow}</tr>
          </tbody>
        </table>
      </div>
    </div>
  `;
}


/* ── Render: assumption cards ── */

function renderDDMAssumptions(d) {
  document.getElementById('ddm-assumptions').innerHTML = `
    <div class="assumption-card">
      <div class="assumption-label">Latest Annual DPS</div>
      <div class="assumption-value">${ddmFmtDollar(d.latest_annual_dps)}</div>
    </div>
    <div class="assumption-card">
      <div class="assumption-label">Dividend Yield</div>
      <div class="assumption-value">${ddmFmtPct(d.current_yield)}</div>
    </div>
    <div class="assumption-card">
      <div class="assumption-label">Avg Payout Ratio</div>
      <div class="assumption-value">${d.avg_payout_ratio > 0 ? ddmFmtPct(d.avg_payout_ratio) : '—'}</div>
    </div>
    <div class="assumption-card">
      <div class="assumption-label">Cost of Equity (Re)</div>
      <div class="assumption-value">${ddmFmtPct(d.cost_of_equity)}</div>
    </div>
  `;
}


/* ── Render: Gordon Growth Model card ── */

function renderGGMCard() {
  const s = _ddmState;
  const ggm = computeGGM(s);

  const isUp = ggm.upside >= 0;
  const cls = isUp ? 'up' : 'down';
  const arrow = isUp ? '\u25b2' : '\u25bc';
  const label = isUp ? 'Upside' : 'Downside';

  const gOverridden = s.overridden.ggmGrowthRate ? ' cell-overridden' : '';

  document.getElementById('ddm-ggm').innerHTML = `
    <div class="ddm-model-card">
      <div class="ddm-model-header">
        <div>
          <div class="ddm-model-title">Gordon Growth Model</div>
          <div class="ddm-model-formula">P = D\u2081 / (Re \u2212 g)</div>
        </div>
        <div class="ddm-iv-badge ${cls}">
          <div class="ddm-iv-value">${ddmFmtDollar(ggm.iv)}</div>
          <div class="ddm-iv-label">${arrow} ${Math.abs(ggm.upside).toFixed(1)}% ${label}</div>
        </div>
      </div>

      <div class="ddm-inputs-grid">
        <div class="ddm-input-row">
          <span class="ddm-input-label">Stable Growth Rate (g)</span>
          <span class="ddm-input-value ddm-editable${gOverridden}"
                data-field="ggmGrowthRate">${ddmFmtPct(s.ggmGrowthRate)}</span>
        </div>
        <div class="ddm-input-row">
          <span class="ddm-input-label">Expected Dividend (D\u2081)</span>
          <span class="ddm-input-value">${ddmFmtDollar4(ggm.d1)}</span>
        </div>
        <div class="ddm-input-row">
          <span class="ddm-input-label">Cost of Equity (Re)</span>
          <span class="ddm-input-value">${ddmFmtPct(s.costOfEquity)}</span>
        </div>
        <div class="ddm-input-row">
          <span class="ddm-input-label">Spread (Re \u2212 g)</span>
          <span class="ddm-input-value">${ddmFmtPct(s.costOfEquity - s.ggmGrowthRate)}</span>
        </div>
      </div>
    </div>
  `;

  /* Attach click handlers for editable cells */
  document.querySelectorAll('#ddm-ggm .ddm-editable').forEach(el => {
    el.addEventListener('click', () => handleDDMEdit(el));
  });
}


/* ── Render: Two-Stage DDM card ── */

function renderTwoStageCard() {
  const s = _ddmState;
  const ts = computeTwoStage(s);

  const isUp = ts.upside >= 0;
  const cls = isUp ? 'up' : 'down';
  const arrow = isUp ? '\u25b2' : '\u25bc';
  const label = isUp ? 'Upside' : 'Downside';

  const g1Ov = s.overridden.tsHighGrowthRate ? ' cell-overridden' : '';
  const nOv  = s.overridden.tsHighGrowthYears ? ' cell-overridden' : '';
  const g2Ov = s.overridden.tsTerminalGrowthRate ? ' cell-overridden' : '';

  document.getElementById('ddm-twostage').innerHTML = `
    <div class="ddm-model-card">
      <div class="ddm-model-header">
        <div>
          <div class="ddm-model-title">Two-Stage DDM</div>
          <div class="ddm-model-formula">High-growth phase \u2192 Terminal perpetuity</div>
        </div>
        <div class="ddm-iv-badge ${cls}">
          <div class="ddm-iv-value">${ddmFmtDollar(ts.iv)}</div>
          <div class="ddm-iv-label">${arrow} ${Math.abs(ts.upside).toFixed(1)}% ${label}</div>
        </div>
      </div>

      <div class="ddm-inputs-grid">
        <div class="ddm-input-row">
          <span class="ddm-input-label">Stage 1 Growth Rate (g\u2081)</span>
          <span class="ddm-input-value ddm-editable${g1Ov}"
                data-field="tsHighGrowthRate">${ddmFmtPct(s.tsHighGrowthRate)}</span>
        </div>
        <div class="ddm-input-row">
          <span class="ddm-input-label">High-Growth Years (N)</span>
          <span class="ddm-input-value ddm-editable${nOv}"
                data-field="tsHighGrowthYears">${s.tsHighGrowthYears}</span>
        </div>
        <div class="ddm-input-row">
          <span class="ddm-input-label">Terminal Growth (g\u2082)</span>
          <span class="ddm-input-value ddm-editable${g2Ov}"
                data-field="tsTerminalGrowthRate">${ddmFmtPct(s.tsTerminalGrowthRate)}</span>
        </div>
        <div class="ddm-input-row">
          <span class="ddm-input-label">Cost of Equity (Re)</span>
          <span class="ddm-input-value">${ddmFmtPct(s.costOfEquity)}</span>
        </div>
      </div>

      <div class="ddm-bridge">
        <div class="bridge-row">
          <span><span class="bridge-sign">+</span> PV of Stage 1 Dividends</span>
          <span>${ddmFmtDollar(ts.pvStage1)}</span>
        </div>
        <div class="bridge-row">
          <span><span class="bridge-sign">+</span> PV of Terminal Value</span>
          <span>${ddmFmtDollar(ts.pvTerminal)}</span>
        </div>
        <div class="bridge-row total">
          <span>Intrinsic Value / Share</span>
          <span>${ddmFmtDollar(ts.iv)}</span>
        </div>
      </div>
    </div>
  `;

  /* Attach click handlers */
  document.querySelectorAll('#ddm-twostage .ddm-editable').forEach(el => {
    el.addEventListener('click', () => handleDDMEdit(el));
  });
}


/* ── Inline editing ── */

function _ddmParseInput(field, rawStr) {
  const stripped = rawStr.replace(/[%$,\s]/g, '');
  const num = parseFloat(stripped);
  if (isNaN(num)) return null;

  if (field === 'tsHighGrowthYears') {
    const n = Math.round(num);
    return (n >= 1 && n <= 15) ? n : null;
  }
  /* All other fields are percentages stored as decimals */
  return num / 100;
}

function _ddmInputDisplay(field, value) {
  if (field === 'tsHighGrowthYears') return String(value);
  return (value * 100).toFixed(1);
}

function handleDDMEdit(el) {
  const field = el.dataset.field;
  const s = _ddmState;
  const originalValue = s[field];
  const wasOverridden = s.overridden[field];

  el.classList.add('cell-editing');
  el.innerHTML = `<input type="text" value="${_ddmInputDisplay(field, originalValue)}" autocomplete="off" />`;

  const input = el.querySelector('input');
  input.focus();
  input.select();

  let committed = false;

  /* Live update while typing */
  input.addEventListener('input', () => {
    const value = _ddmParseInput(field, input.value);
    if (value === null) return;
    s[field] = value;
    s.overridden[field] = true;
    /* Don't re-render the card being edited — just update the other card */
    if (field === 'ggmGrowthRate') {
      renderTwoStageCard();
    } else {
      renderGGMCard();
    }
  });

  const commit = () => {
    if (committed) return;
    committed = true;
    const value = _ddmParseInput(field, input.value);
    if (value !== null) {
      s[field] = value;
      s.overridden[field] = true;
    } else {
      s[field] = originalValue;
      s.overridden[field] = wasOverridden;
    }
    renderDividendHistory();
    renderGGMCard();
    renderTwoStageCard();
  };

  const cancel = () => {
    if (committed) return;
    committed = true;
    s[field] = originalValue;
    s.overridden[field] = wasOverridden;
    renderDividendHistory();
    renderGGMCard();
    renderTwoStageCard();
  };

  input.addEventListener('blur', commit);
  input.addEventListener('keydown', ev => {
    if (ev.key === 'Enter')  { ev.preventDefault(); commit(); }
    if (ev.key === 'Escape') { ev.preventDefault(); cancel(); }
  });
}


/* ── Reset button ── */

function handleDDMReset() {
  const s = _ddmState;
  const d = s.defaults;
  s.ggmGrowthRate = d.ggmGrowthRate;
  s.tsHighGrowthRate = d.tsHighGrowthRate;
  s.tsHighGrowthYears = d.tsHighGrowthYears;
  s.tsTerminalGrowthRate = d.tsTerminalGrowthRate;
  s.overridden = {
    ggmGrowthRate: false,
    tsHighGrowthRate: false,
    tsHighGrowthYears: false,
    tsTerminalGrowthRate: false,
  };
  renderDividendHistory();
  renderGGMCard();
  renderTwoStageCard();
}


/* ── Recalculate (server-side validation) ── */

async function handleDDMRecalculate() {
  const s = _ddmState;
  const btn = document.getElementById('ddm-recalc-btn');
  btn.disabled = true;
  btn.textContent = 'Recalculating\u2026';

  try {
    const result = await fetchDDMRecalculate(s.ticker, {
      latest_annual_dps: s.latestDps,
      current_price: s.currentPrice,
      cost_of_equity: s.costOfEquity,
      ggm_growth_rate: s.ggmGrowthRate,
      ts_high_growth_rate: s.tsHighGrowthRate,
      ts_high_growth_years: s.tsHighGrowthYears,
      ts_terminal_growth_rate: s.tsTerminalGrowthRate,
    });

    /* Update the cards with server-validated values */
    renderGGMCard();
    renderTwoStageCard();

  } catch (err) {
    alert('DDM recalculate failed: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Recalculate';
  }
}


/* ── Main entry point ── */

function renderDDM(data) {
  const unavailable = document.getElementById('ddm-unavailable');
  const content = document.getElementById('ddm-content');

  if (!data.ddm_available || !data.ddm_model || !data.ddm_model.pays_dividends) {
    show(unavailable);
    hide(content);
    return;
  }

  hide(unavailable);
  show(content);

  initDDMState(data);

  /* Wire up buttons */
  const resetBtn = document.getElementById('ddm-reset-btn');
  const recalcBtn = document.getElementById('ddm-recalc-btn');
  if (resetBtn) {
    resetBtn.onclick = handleDDMReset;
  }
  if (recalcBtn) {
    recalcBtn.onclick = handleDDMRecalculate;
  }

  renderDividendHistory();
  renderDDMAssumptions(data.ddm_model);
  renderGGMCard();
  renderTwoStageCard();
}
