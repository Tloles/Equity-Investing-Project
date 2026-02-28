/* dcf.js — financial model: Income Statement, FCF, Balance Sheet, Terminal Value */

/* ── Format helpers ── */

function fmtUSD(value) {
  const sign = value < 0 ? '-' : '';
  const abs  = Math.abs(value);
  if (abs >= 1e12) return sign + '$' + (abs / 1e12).toFixed(2) + 'T';
  if (abs >= 1e9)  return sign + '$' + (abs / 1e9).toFixed(2)  + 'B';
  if (abs >= 1e6)  return sign + '$' + (abs / 1e6).toFixed(2)  + 'M';
  return sign + '$' + abs.toFixed(0);
}

function fmtPct(decimal) {
  return (decimal * 100).toFixed(1) + '%';
}

/* Raw USD → millions with comma separators, e.g. 385_600_000_000 → "385,600" */
function fmtM(rawUSD) {
  const m       = rawUSD / 1e6;
  const sign    = m < 0 ? '-' : '';
  const rounded = Math.round(Math.abs(m));
  return sign + rounded.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/* Cost values shown in (parentheses) */
function fmtMParen(rawUSD) {
  return '(' + fmtM(Math.abs(rawUSD)) + ')';
}

/* Diluted shares shown in millions */
function fmtSharesM(shares) {
  if (shares == null) return '—';
  const m = Math.round(Math.abs(shares) / 1e6);
  return m.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/* EPS in dollars per share */
function fmtEPS(eps) {
  if (eps == null) return '—';
  const abs = Math.abs(eps);
  return (eps < 0 ? '($' : '$') + abs.toFixed(2) + (eps < 0 ? ')' : '');
}

/* P/E exit multiple */
function fmtMultiple(value) {
  return value.toFixed(1) + 'x';
}

/* Return '—' when value is null/undefined/NaN, else apply formatFn */
function dash(value, formatFn) {
  return (value == null || isNaN(value)) ? '—' : formatFn(value);
}


/* ── Module state ── */

let _dcfState = null;   // projection table state + defaults snapshot
let _fullData  = null;  // original full API response


/* ── State initialisation ── */

function _defaultAssumptions(d) {
  return {
    growthRates:   Array(5).fill(d.base_revenue_growth),
    opMargins:     Array(5).fill(d.base_op_margin),
    taxRates:      Array(5).fill(d.base_tax_rate),
    capexPcts:     Array(5).fill(d.base_capex_pct),
    daPcts:        Array(5).fill(d.base_da_pct),
    sharesGrowths: Array(5).fill(d.base_shares_growth),
    exitPeMultiple: d.exit_pe_multiple,
  };
}

function initState(data) {
  const d        = data.dcf_model;
  const defaults = _defaultAssumptions(d);

  _fullData = data;
  _dcfState = {
    ticker:  data.ticker,
    actuals: d.actuals,          // historical year objects (oldest → newest)

    /* base values — last actual year, used as Year-0 for projections */
    baseRevenue:        d.actuals[d.actuals.length - 1].revenue,
    baseDilutedShares:  d.base_diluted_shares,
    interestExpense:    d.base_interest_expense,  // fixed in projections
    costOfEquity:       d.cost_of_equity,
    currentPrice:       data.current_price,

    /* per-year projection assumptions — deep-copied so defaults snapshot is safe */
    growthRates:    [...defaults.growthRates],
    opMargins:      [...defaults.opMargins],
    taxRates:       [...defaults.taxRates],
    capexPcts:      [...defaults.capexPcts],
    daPcts:         [...defaults.daPcts],
    sharesGrowths:  [...defaults.sharesGrowths],
    exitPeMultiple: defaults.exitPeMultiple,

    /* which cells the user has manually overridden */
    overridden: {
      growthRates:   Array(5).fill(false),
      opMargins:     Array(5).fill(false),
      taxRates:      Array(5).fill(false),
      capexPcts:     Array(5).fill(false),
      daPcts:        Array(5).fill(false),
      sharesGrowths: Array(5).fill(false),
      exitPe:        false,
    },

    /* saved defaults for Reset — never mutated after this point */
    defaults,
  };
}


/* ── Projection computation ── */

/*
 * Computes all 5 projection years from current state.
 * Returns { rows, tv, pvTv, pvFcfs, equityValue, iv, upside }.
 */
function computeProjections(s) {
  let prevRev    = s.baseRevenue;
  let prevShares = s.baseDilutedShares;
  const rows     = [];
  let pvFcfs     = 0.0;

  for (let i = 0; i < 5; i++) {
    const revenue   = prevRev * (1 + s.growthRates[i]);
    const opIncome  = revenue * s.opMargins[i];
    const intExp    = s.interestExpense;                          // fixed
    const pretax    = opIncome - intExp;
    const tax       = pretax > 0 ? pretax * s.taxRates[i] : 0;
    const netIncome = pretax - tax;
    const shares    = prevShares * (1 + s.sharesGrowths[i]);
    const eps       = shares > 0 ? netIncome / shares : 0;
    const capex     = revenue * s.capexPcts[i];
    const da        = revenue * s.daPcts[i];
    const fcf       = netIncome + da - capex;
    const pv        = fcf / Math.pow(1 + s.costOfEquity, i + 1);
    pvFcfs         += pv;

    rows.push({
      revenue, opIncome, intExp, pretax, tax, netIncome, shares, eps,
      capex, da, fcf,
      /* ratios for editable cell display */
      growthRate:   s.growthRates[i],
      opMargin:     s.opMargins[i],
      taxRate:      s.taxRates[i],
      capexPct:     s.capexPcts[i],
      daPct:        s.daPcts[i],
      sharesGrowth: s.sharesGrowths[i],
    });

    prevRev    = revenue;
    prevShares = shares;
  }

  /* Terminal value = Year-5 Net Income × P/E exit multiple */
  const tv          = rows[4].netIncome * s.exitPeMultiple;
  const pvTv        = tv / Math.pow(1 + s.costOfEquity, 5);
  const equityValue = pvFcfs + pvTv;
  const iv          = s.baseDilutedShares > 0 ? equityValue / s.baseDilutedShares : 0;
  const upside      = s.currentPrice > 0 ? (iv - s.currentPrice) / s.currentPrice * 100 : 0;

  return { rows, tv, pvTv, pvFcfs, equityValue, iv, upside };
}


/* ── State mutation ── */

/* Returns the current value of an editable cell (decimal for %, raw for P/E) */
function getCellValue(field, year) {
  const s = _dcfState;
  switch (field) {
    case 'growthRate':   return s.growthRates[year];
    case 'opMargin':     return s.opMargins[year];
    case 'taxRate':      return s.taxRates[year];
    case 'capexPct':     return s.capexPcts[year];
    case 'daPct':        return s.daPcts[year];
    case 'sharesGrowth': return s.sharesGrowths[year];
    case 'exitPe':       return s.exitPeMultiple;
    default:             return 0;
  }
}

/* Applies a committed edit to state */
function applyCellEdit(field, year, value) {
  const s = _dcfState;
  switch (field) {
    case 'growthRate':   s.growthRates[year]   = value; s.overridden.growthRates[year]   = true; break;
    case 'opMargin':     s.opMargins[year]     = value; s.overridden.opMargins[year]     = true; break;
    case 'taxRate':      s.taxRates[year]      = value; s.overridden.taxRates[year]      = true; break;
    case 'capexPct':     s.capexPcts[year]     = value; s.overridden.capexPcts[year]     = true; break;
    case 'daPct':        s.daPcts[year]        = value; s.overridden.daPcts[year]        = true; break;
    case 'sharesGrowth': s.sharesGrowths[year] = value; s.overridden.sharesGrowths[year] = true; break;
    case 'exitPe':       s.exitPeMultiple      = value; s.overridden.exitPe              = true; break;
  }
}

/* Is this specific cell overridden by the user? */
function isCellOverridden(field, year) {
  const ov = _dcfState.overridden;
  switch (field) {
    case 'growthRate':   return ov.growthRates[year];
    case 'opMargin':     return ov.opMargins[year];
    case 'taxRate':      return ov.taxRates[year];
    case 'capexPct':     return ov.capexPcts[year];
    case 'daPct':        return ov.daPcts[year];
    case 'sharesGrowth': return ov.sharesGrowths[year];
    case 'exitPe':       return ov.exitPe;
    default:             return false;
  }
}

/* Maps field name to the key inside s.overridden */
function _overriddenKey(field) {
  switch (field) {
    case 'growthRate':   return 'growthRates';
    case 'opMargin':     return 'opMargins';
    case 'taxRate':      return 'taxRates';
    case 'capexPct':     return 'capexPcts';
    case 'daPct':        return 'daPcts';
    case 'sharesGrowth': return 'sharesGrowths';
    case 'exitPe':       return 'exitPe';   // boolean, not array
    default:             return 'growthRates';
  }
}

/* Is this field a percentage (true) or a raw numeric multiple (false)? */
function _isPctField(field) { return field !== 'exitPe'; }

/* Format a cell value for display */
function _formatCellValue(field, value) {
  return _isPctField(field) ? fmtPct(value) : fmtMultiple(value);
}

/* Parse user input to the stored decimal/number value */
function _parseInput(field, rawStr) {
  const cleaned = rawStr.replace('%', '').replace('x', '').trim();
  const num = parseFloat(cleaned);
  if (isNaN(num)) return null;
  return _isPctField(field) ? num / 100 : num;
}

/* Initial input display value (without % or x suffix) */
function _inputDisplayValue(field, value) {
  return _isPctField(field)
    ? (value * 100).toFixed(1)
    : value.toFixed(1);
}


/* ── Surgical DOM update (no full re-render while input is active) ── */

/* Update a value cell in a projection column by data-val + data-year */
function setVal(valType, year, content) {
  const cell = document.querySelector(
    `#dcf-projection [data-val="${valType}"][data-year="${year}"]`
  );
  if (cell) cell.textContent = content;
}

/* Update an editable italic cell — skips if an <input> is currently open */
function setEditable(field, year, content, overridden) {
  const cell = document.querySelector(
    `#dcf-projection [data-field="${field}"][data-year="${year}"]`
  );
  if (!cell || cell.querySelector('input')) return;
  cell.className = 'cell-editable' + (overridden ? ' cell-overridden' : '');
  cell.textContent = content;
}

/* Push all computed values to the DOM without rebuilding the HTML structure */
function updateTableCells(result) {
  const s = _dcfState;
  for (let i = 0; i < 5; i++) {
    const p = result.rows[i];

    /* value cells */
    setVal('revenue',   i, fmtM(p.revenue));
    setVal('opIncome',  i, fmtM(p.opIncome));
    setVal('intExp',    i, fmtMParen(p.intExp));
    setVal('pretax',    i, fmtM(p.pretax));
    setVal('tax',       i, fmtMParen(p.tax));
    setVal('netIncome', i, fmtM(p.netIncome));
    setVal('shares',    i, fmtSharesM(p.shares));
    setVal('eps',       i, fmtEPS(p.eps));
    setVal('capex',     i, fmtMParen(p.capex));
    setVal('da',        i, fmtM(p.da));
    setVal('fcf',       i, fmtM(p.fcf));

    /* editable cells — active <input> is safely skipped by setEditable */
    setEditable('growthRate',   i, fmtPct(p.growthRate),   isCellOverridden('growthRate',   i));
    setEditable('opMargin',     i, fmtPct(p.opMargin),     isCellOverridden('opMargin',     i));
    setEditable('taxRate',      i, fmtPct(p.taxRate),      isCellOverridden('taxRate',      i));
    setEditable('capexPct',     i, fmtPct(p.capexPct),     isCellOverridden('capexPct',     i));
    setEditable('daPct',        i, fmtPct(p.daPct),        isCellOverridden('daPct',        i));
    setEditable('sharesGrowth', i, fmtPct(p.sharesGrowth), isCellOverridden('sharesGrowth', i));
  }
  /* P/E exit multiple (year index 4) and terminal value */
  setEditable('exitPe', 4, fmtMultiple(s.exitPeMultiple), s.overridden.exitPe);
  setVal('terminalValue', 4, fmtUSD(result.tv));

  /* Live price widget and bridge update */
  _updatePriceWidget(result.iv, result.upside, s.currentPrice);
  renderValuationBridge(result.pvFcfs, result.pvTv, result.equityValue,
                        s.baseDilutedShares, result.iv);
}


/* ── Cell builder helpers ── */

function editableTd(field, year, value) {
  const ovr = isCellOverridden(field, year);
  const cls = 'cell-editable' + (ovr ? ' cell-overridden' : '');
  return `<td class="${cls}" data-field="${field}" data-year="${year}">${_formatCellValue(field, value)}</td>`;
}

function actTd(content) {
  return `<td class="col-actual">${content}</td>`;
}

function actTds(actuals, valueFn) {
  return actuals.map(valueFn).map(actTd).join('');
}

function projValTd(type, i, content) {
  return `<td data-val="${type}" data-year="${i}">${content}</td>`;
}


/* ── Table section builders ── */

function _sectionHeader(label, numCols) {
  return `<tr class="section-header"><td colspan="${numCols}">${label}</td></tr>`;
}

function _incomeRows(s, projs) {
  const act = s.actuals;
  return `
    <tr class="row-bold">
      <td>Revenue</td>
      ${actTds(act, a => fmtM(a.revenue))}
      ${projs.map((p, i) => projValTd('revenue', i, fmtM(p.revenue))).join('')}
    </tr>
    <tr class="row-italic">
      <td>% Growth</td>
      ${actTds(act, a => dash(a.revenue_growth, fmtPct))}
      ${projs.map((p, i) => editableTd('growthRate', i, p.growthRate)).join('')}
    </tr>

    <tr class="row-bold">
      <td>Operating Income</td>
      ${actTds(act, a => fmtM(a.operating_income))}
      ${projs.map((p, i) => projValTd('opIncome', i, fmtM(p.opIncome))).join('')}
    </tr>
    <tr class="row-italic">
      <td>Operating Margin %</td>
      ${actTds(act, a => a.revenue > 0 ? fmtPct(a.operating_income / a.revenue) : '—')}
      ${projs.map((p, i) => editableTd('opMargin', i, p.opMargin)).join('')}
    </tr>

    <tr class="row-body row-cost">
      <td>Interest Expense</td>
      ${actTds(act, a => fmtMParen(a.interest_expense))}
      ${projs.map((p, i) => projValTd('intExp', i, fmtMParen(p.intExp))).join('')}
    </tr>

    <tr class="row-bold">
      <td>Pre-tax Income</td>
      ${actTds(act, a => fmtM(a.pretax_income))}
      ${projs.map((p, i) => projValTd('pretax', i, fmtM(p.pretax))).join('')}
    </tr>

    <tr class="row-body row-cost">
      <td>Tax Expense</td>
      ${actTds(act, a => fmtMParen(a.tax_expense))}
      ${projs.map((p, i) => projValTd('tax', i, fmtMParen(p.tax))).join('')}
    </tr>
    <tr class="row-italic">
      <td>Tax Rate %</td>
      ${actTds(act, a => a.pretax_income > 0 ? fmtPct(a.tax_expense / a.pretax_income) : '—')}
      ${projs.map((p, i) => editableTd('taxRate', i, p.taxRate)).join('')}
    </tr>

    <tr class="row-bold row-highlight">
      <td>Net Income</td>
      ${actTds(act, a => fmtM(a.net_income))}
      ${projs.map((p, i) => projValTd('netIncome', i, fmtM(p.netIncome))).join('')}
    </tr>

    <tr class="row-body">
      <td>Diluted Shares (M)</td>
      ${actTds(act, a => fmtSharesM(a.diluted_shares))}
      ${projs.map((p, i) => projValTd('shares', i, fmtSharesM(p.shares))).join('')}
    </tr>
    <tr class="row-italic">
      <td>y/y % Change</td>
      ${actTds(act, a => dash(a.shares_growth, fmtPct))}
      ${projs.map((p, i) => editableTd('sharesGrowth', i, p.sharesGrowth)).join('')}
    </tr>

    <tr class="row-bold row-highlight">
      <td>GAAP EPS (Diluted)</td>
      ${actTds(act, a => fmtEPS(a.eps))}
      ${projs.map((p, i) => projValTd('eps', i, fmtEPS(p.eps))).join('')}
    </tr>
  `;
}

function _fcfRows(s, projs) {
  const act = s.actuals;
  return `
    <tr class="row-body row-cost">
      <td>Capital Expenditures</td>
      ${actTds(act, a => fmtMParen(a.capex))}
      ${projs.map((p, i) => projValTd('capex', i, fmtMParen(p.capex))).join('')}
    </tr>
    <tr class="row-italic">
      <td>% of Revenue</td>
      ${actTds(act, a => a.revenue > 0 ? fmtPct(a.capex / a.revenue) : '—')}
      ${projs.map((p, i) => editableTd('capexPct', i, p.capexPct)).join('')}
    </tr>

    <tr class="row-body">
      <td>Depreciation &amp; Amortization</td>
      ${actTds(act, a => fmtM(a.da))}
      ${projs.map((p, i) => projValTd('da', i, fmtM(p.da))).join('')}
    </tr>
    <tr class="row-italic">
      <td>% of Revenue</td>
      ${actTds(act, a => a.revenue > 0 ? fmtPct(a.da / a.revenue) : '—')}
      ${projs.map((p, i) => editableTd('daPct', i, p.daPct)).join('')}
    </tr>

    <tr class="row-bold row-fcf">
      <td>Free Cash Flow</td>
      ${actTds(act, a => fmtM(a.fcf))}
      ${projs.map((p, i) => projValTd('fcf', i, fmtM(p.fcf))).join('')}
    </tr>
  `;
}

function _balanceSheetRows(s) {
  const act    = s.actuals;
  const nProj  = 5;
  const blanks = Array(nProj).fill('<td>—</td>').join('');
  return `
    <tr class="row-body">
      <td>Cash</td>
      ${actTds(act, a => fmtM(a.cash))}
      ${blanks}
    </tr>
    <tr class="row-body row-cost">
      <td>Long-Term Debt</td>
      ${actTds(act, a => fmtMParen(a.long_term_debt))}
      ${blanks}
    </tr>
    <tr class="row-body row-cost">
      <td>Short-Term Debt</td>
      ${actTds(act, a => fmtMParen(a.short_term_debt))}
      ${blanks}
    </tr>
    <tr class="row-bold">
      <td>Net Debt</td>
      ${actTds(act, a => fmtM(a.net_debt))}
      ${blanks}
    </tr>
  `;
}

function _terminalValueRows(s, result) {
  const act      = s.actuals;
  const actBlanks = act.map(() => '<td class="col-actual">—</td>').join('');
  const proj14   = Array(4).fill('<td>—</td>').join('');   // years 0-3
  const peClass  = 'cell-editable' + (s.overridden.exitPe ? ' cell-overridden' : '');
  return `
    <tr class="row-italic">
      <td>P/E Exit Multiple</td>
      ${actBlanks}
      ${proj14}
      <td class="${peClass}" data-field="exitPe" data-year="4">${fmtMultiple(s.exitPeMultiple)}</td>
    </tr>
    <tr class="row-body">
      <td>Terminal Equity Value</td>
      ${actBlanks}
      ${proj14}
      <td data-val="terminalValue" data-year="4">${fmtUSD(result.tv)}</td>
    </tr>
  `;
}

function _buildAllRows(s, result) {
  const numCols = 1 + s.actuals.length + 5;
  return (
    _sectionHeader('Income Statement', numCols) +
    _incomeRows(s, result.rows) +
    _sectionHeader('Free Cash Flow', numCols) +
    _fcfRows(s, result.rows) +
    _sectionHeader('Balance Sheet', numCols) +
    _balanceSheetRows(s) +
    _sectionHeader('Terminal Value', numCols) +
    _terminalValueRows(s, result)
  );
}


/* ── Full projection table render ── */

function renderProjectionTable() {
  const s       = _dcfState;
  const result  = computeProjections(s);
  const baseYr  = s.actuals[s.actuals.length - 1].year;
  const projYrs = Array.from({ length: 5 }, (_, i) => baseYr + 1 + i);

  document.getElementById('dcf-projection').innerHTML = `
    <div class="dcf-proj-wrapper">
      <div class="dcf-proj-header">
        <div>
          <div class="dcf-proj-title">${escapeHtml(s.ticker)} DCF Valuation Model</div>
          <div class="dcf-proj-subtitle">(USD in millions, except per share data)</div>
        </div>
        <div class="proj-buttons">
          <button id="reset-btn"  class="btn-reset">Reset to Defaults</button>
          <button id="recalc-btn" class="btn-recalc">Recalculate</button>
        </div>
      </div>
      <div class="table-card">
        <div class="proj-table-scroll">
          <table class="dcf-proj-table">
            <thead>
              <tr>
                <th class="col-label"></th>
                ${s.actuals.map(a => `<th class="col-actual">FY${a.year}</th>`).join('')}
                ${projYrs.map(y => `<th>FY${y}E</th>`).join('')}
              </tr>
            </thead>
            <tbody>
              ${_buildAllRows(s, result)}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;

  /* Sync the valuation bridge on every full re-render (commit / reset). */
  renderValuationBridge(result.pvFcfs, result.pvTv, result.equityValue,
                        s.baseDilutedShares, result.iv);

  document.getElementById('recalc-btn').addEventListener('click', handleRecalculate);
  document.getElementById('reset-btn').addEventListener('click', handleReset);

  /* Event delegation on tbody — re-attached after every full re-render */
  document.querySelector('#dcf-projection tbody')
    .addEventListener('click', handleCellClick);
}


/* ── Inline cell editing with live cascade ── */

function handleCellClick(e) {
  const td = e.target.closest('td.cell-editable');
  if (!td || td.querySelector('input')) return;

  const field         = td.dataset.field;
  const year          = parseInt(td.dataset.year, 10);
  const originalValue = getCellValue(field, year);
  const wasOverridden = isCellOverridden(field, year);

  /* Open the input */
  td.classList.add('cell-editing');
  td.innerHTML = `<input type="text" value="${_inputDisplayValue(field, originalValue)}" autocomplete="off" />`;

  const input = td.querySelector('input');
  input.focus();
  input.select();

  let committed = false;

  /* ── Live update while typing ──
   * Applies the edit to state and surgically updates all downstream cells
   * in the DOM without replacing the active <input>. */
  input.addEventListener('input', () => {
    const value = _parseInput(field, input.value);
    if (value === null) return;
    applyCellEdit(field, year, value);
    updateTableCells(computeProjections(_dcfState));
  });

  /* ── Commit on Enter or blur ──
   * Locks in the value and does a full re-render. */
  const commit = () => {
    if (committed) return;
    committed = true;
    const value = _parseInput(field, input.value);
    if (value !== null) {
      applyCellEdit(field, year, value);
    } else {
      /* Invalid input — revert */
      applyCellEdit(field, year, originalValue);
      if (field === 'exitPe') {
        _dcfState.overridden.exitPe = wasOverridden;
      } else {
        _dcfState.overridden[_overriddenKey(field)][year] = wasOverridden;
      }
    }
    renderProjectionTable();
  };

  const cancel = () => {
    if (committed) return;
    committed = true;
    applyCellEdit(field, year, originalValue);
    if (field === 'exitPe') {
      _dcfState.overridden.exitPe = wasOverridden;
    } else {
      _dcfState.overridden[_overriddenKey(field)][year] = wasOverridden;
    }
    renderProjectionTable();
  };

  input.addEventListener('blur',    commit);
  input.addEventListener('keydown', ev => {
    if (ev.key === 'Enter')  { ev.preventDefault(); commit(); }
    if (ev.key === 'Escape') { ev.preventDefault(); cancel(); }
  });
}


/* ── Reset to Defaults ── */

function handleReset() {
  const s = _dcfState;
  const d = s.defaults;
  /* Restore per-year assumptions from snapshot (array copies, not references) */
  s.growthRates    = [...d.growthRates];
  s.opMargins      = [...d.opMargins];
  s.taxRates       = [...d.taxRates];
  s.capexPcts      = [...d.capexPcts];
  s.daPcts         = [...d.daPcts];
  s.sharesGrowths  = [...d.sharesGrowths];
  s.exitPeMultiple = d.exitPeMultiple;
  s.overridden = {
    growthRates:   Array(5).fill(false),
    opMargins:     Array(5).fill(false),
    taxRates:      Array(5).fill(false),
    capexPcts:     Array(5).fill(false),
    daPcts:        Array(5).fill(false),
    sharesGrowths: Array(5).fill(false),
    exitPe:        false,
  };
  renderProjectionTable();
  /* Restore price widget to exact server-computed values */
  renderPriceWidget(_fullData);
  renderValuationBridge(
    _fullData.dcf_model.pv_fcfs,
    _fullData.dcf_model.pv_terminal_value,
    _fullData.dcf_model.equity_value,
    _fullData.dcf_model.base_diluted_shares,
    _fullData.intrinsic_value,
  );
}


/* ── Recalculate button (server-side validation) ── */

async function handleRecalculate() {
  const s   = _dcfState;
  const btn = document.getElementById('recalc-btn');
  btn.disabled    = true;
  btn.textContent = 'Recalculating\u2026';

  try {
    const result = await fetchRecalculate(s.ticker, {
      base_revenue:        s.baseRevenue,
      base_diluted_shares: s.baseDilutedShares,
      interest_expense:    s.interestExpense,
      growth_rates:        s.growthRates,
      op_margins:          s.opMargins,
      tax_rates:           s.taxRates,
      capex_pcts:          s.capexPcts,
      da_pcts:             s.daPcts,
      shares_growths:      s.sharesGrowths,
      exit_pe_multiple:    s.exitPeMultiple,
      cost_of_equity:      s.costOfEquity,
      current_price:       s.currentPrice,
    });

    _updatePriceWidget(result.intrinsic_value, result.upside_downside, s.currentPrice);
    renderValuationBridge(result.pv_fcfs, result.pv_terminal_value,
                          result.equity_value, s.baseDilutedShares, result.intrinsic_value);

  } catch (err) {
    alert('Recalculate failed: ' + err.message);
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Recalculate';
  }
}


/* ── Price widget helpers ── */

function _updatePriceWidget(iv, upside, currentPrice) {
  const widget = document.getElementById('price-widget');
  if (!widget) return;
  const isUp  = upside >= 0;
  const cls   = isUp ? 'up' : 'down';
  const arrow = isUp ? '\u25b2' : '\u25bc';
  const label = isUp ? 'Upside' : 'Downside';
  widget.innerHTML = `
    <div class="price-col">
      <div class="price-label">Current Price</div>
      <div class="price-value">$${currentPrice.toFixed(2)}</div>
    </div>
    <div class="price-divider"></div>
    <div class="upside-badge ${cls}">
      <div class="upside-pct">${arrow} ${Math.abs(upside).toFixed(1)}%</div>
      <div class="upside-sub">${label} to IV</div>
    </div>
    <div class="price-divider"></div>
    <div class="price-col">
      <div class="price-label">Intrinsic Value (DCF)</div>
      <div class="price-value">$${iv.toFixed(2)}</div>
    </div>
  `;
}


/* ── CAPM cards ── */

function renderCostOfCapital(d) {
  document.getElementById('dcf-wacc').innerHTML = `
    <div class="assumption-card">
      <div class="assumption-label">Risk-Free Rate</div>
      <div class="assumption-value">${fmtPct(d.risk_free_rate)}</div>
    </div>
    <div class="assumption-card">
      <div class="assumption-label">Equity Risk Premium</div>
      <div class="assumption-value">${fmtPct(d.equity_risk_premium)}</div>
    </div>
    <div class="assumption-card">
      <div class="assumption-label">Beta</div>
      <div class="assumption-value">${d.beta.toFixed(2)}</div>
    </div>
    <div class="assumption-card">
      <div class="assumption-label">Cost of Equity (Re)</div>
      <div class="assumption-value">${fmtPct(d.cost_of_equity)}</div>
    </div>
  `;
}


/* ── Valuation Bridge ── */

function renderValuationBridge(pvFcfs, pvTv, equityValue, dilutedShares, iv) {
  document.getElementById('dcf-bridge').innerHTML = `
    <div class="bridge-row">
      <span><span class="bridge-sign">+</span> PV of FCFs (Years 1&ndash;5)</span>
      <span>${fmtUSD(pvFcfs)}</span>
    </div>
    <div class="bridge-row">
      <span><span class="bridge-sign">+</span> PV of Terminal Value (P/E Exit)</span>
      <span>${fmtUSD(pvTv)}</span>
    </div>
    <div class="bridge-row subtotal">
      <span>Equity Value</span>
      <span>${fmtUSD(equityValue)}</span>
    </div>
    <div class="bridge-row">
      <span><span class="bridge-sign">&divide;</span> Diluted Shares Outstanding</span>
      <span>${fmtSharesM(dilutedShares)}M shares</span>
    </div>
    <div class="bridge-row total">
      <span>Intrinsic Value / Share</span>
      <span>$${iv.toFixed(2)}</span>
    </div>
  `;
}


/* ── Main entry point ── */

function renderDCF(data) {
  const unavailable = document.getElementById('dcf-unavailable');
  const content     = document.getElementById('dcf-content');

  if (!data.dcf_available) {
    show(unavailable);
    hide(content);
    return;
  }

  hide(unavailable);
  show(content);

  const warningEl = document.getElementById('dcf-warning');
  if (data.dcf_warning) {
    warningEl.textContent = data.dcf_warning;
    show(warningEl);
  } else {
    hide(warningEl);
  }

  initState(data);
  renderProjectionTable();
  renderCostOfCapital(data.dcf_model);
  /* Bridge rendered inside renderProjectionTable; no separate call needed. */
}
