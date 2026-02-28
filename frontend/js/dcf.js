/* dcf.js — renders the DCF tab: projection table, cost of capital, valuation bridge */

/* ── Format helpers ── */

function fmtUSD(value) {
  const sign = value < 0 ? '-' : '';
  const abs  = Math.abs(value);
  if (abs >= 1e12) return sign + '$' + (abs / 1e12).toFixed(2) + 'T';
  if (abs >= 1e9)  return sign + '$' + (abs / 1e9).toFixed(2)  + 'B';
  if (abs >= 1e6)  return sign + '$' + (abs / 1e6).toFixed(2)  + 'M';
  return sign + '$' + abs.toFixed(0);
}

function fmtShares(value) {
  const abs = Math.abs(value);
  if (abs >= 1e9) return (value / 1e9).toFixed(2) + 'B';
  if (abs >= 1e6) return (value / 1e6).toFixed(2) + 'M';
  return value.toFixed(0);
}

function fmtPct(decimal) {
  return (decimal * 100).toFixed(1) + '%';
}

/* Format a raw USD value as millions with comma separators, e.g. 385600000000 → "385,600" */
function fmtM(rawUSD) {
  const m = rawUSD / 1e6;
  const abs = Math.abs(m);
  const sign = m < 0 ? '-' : '';
  const rounded = Math.round(abs);
  return sign + rounded.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/* Cost values shown in (parentheses) */
function fmtMParen(rawUSD) {
  return '(' + fmtM(Math.abs(rawUSD)) + ')';
}


/* ── Module state ── */

let _dcfState  = null;   // projection table state
let _fullData  = null;   // original full API response (preserved for bridge re-render)


/* ── State initialisation ── */

function initState(data) {
  const d = data.dcf_model;
  const bRev  = d.base_revenue;
  const bGP   = d.base_gross_profit;
  const bOpex = d.base_operating_expenses;
  const bEbit = d.base_ebit;
  const bTax  = d.base_tax_expense;

  const defaultGpMargin  = bRev  > 0 ? bGP   / bRev  : 0.5;
  const defaultOpexPct   = bRev  > 0 ? bOpex / bRev  : 0.15;
  const defaultTaxRate   = bEbit > 0 ? bTax  / bEbit : 0.21;

  _fullData  = data;
  _dcfState  = {
    ticker:    data.ticker,
    baseYear:  d.base_year,

    /* base-year actuals (raw USD) */
    baseRevenue:           d.base_revenue,
    baseCostOfRevenue:     d.base_cost_of_revenue,
    baseGrossProfit:       d.base_gross_profit,
    baseOpex:              d.base_operating_expenses,
    baseEbit:              d.base_ebit,
    baseTax:               d.base_tax_expense,
    baseFcf:               d.base_fcf_actual,

    /* per-year projection assumptions (5 values each) */
    growthRates: Array(5).fill(d.revenue_growth_rate),
    gpMargins:   Array(5).fill(defaultGpMargin),
    opexPcts:    Array(5).fill(defaultOpexPct),
    taxRates:    Array(5).fill(defaultTaxRate),
    fcfMargins:  Array(5).fill(d.fcf_margin),

    /* which cells have been manually overridden */
    overridden: {
      growthRates: Array(5).fill(false),
      gpMargins:   Array(5).fill(false),
      opexPcts:    Array(5).fill(false),
      taxRates:    Array(5).fill(false),
      fcfMargins:  Array(5).fill(false),
    },

    /* constants passed to /dcf/recalculate */
    wacc:               d.wacc,
    terminalGrowthRate: d.terminal_growth_rate,
    netCash:            d.net_cash,
    sharesOutstanding:  d.shares_outstanding,
    currentPrice:       data.current_price,
  };
}


/* ── Projection computation ── */

function computeProjections(s) {
  const rows = [];
  let prevRevenue = s.baseRevenue;
  for (let i = 0; i < 5; i++) {
    const revenue     = prevRevenue * (1 + s.growthRates[i]);
    const grossProfit = revenue * s.gpMargins[i];
    const cor         = revenue - grossProfit;
    const opex        = revenue * s.opexPcts[i];
    const ebit        = grossProfit - opex;
    const taxExpense  = ebit > 0 ? ebit * s.taxRates[i] : 0;
    const fcf         = revenue * s.fcfMargins[i];
    rows.push({
      revenue, grossProfit, cor, opex, ebit, taxExpense, fcf,
      growthRate:  s.growthRates[i],
      corPct:      1 - s.gpMargins[i],
      gpMargin:    s.gpMargins[i],
      opexPct:     s.opexPcts[i],
      ebitMargin:  revenue > 0 ? ebit / revenue : 0,
      taxRate:     s.taxRates[i],
      fcfMargin:   s.fcfMargins[i],
    });
    prevRevenue = revenue;
  }
  return rows;
}


/* ── Cell helpers ── */

function getCellPct(field, year) {
  const s = _dcfState;
  switch (field) {
    case 'growthRate':  return s.growthRates[year];
    case 'corPct':      return 1 - s.gpMargins[year];
    case 'gpMargin':    return s.gpMargins[year];
    case 'opexPct':     return s.opexPcts[year];
    case 'ebitMargin':  return s.gpMargins[year] - s.opexPcts[year];
    case 'taxRate':     return s.taxRates[year];
    case 'fcfMargin':   return s.fcfMargins[year];
    default:            return 0;
  }
}

function applyCellEdit(field, year, value) {
  const s = _dcfState;
  switch (field) {
    case 'growthRate':
      s.growthRates[year] = value;
      s.overridden.growthRates[year] = true;
      break;
    case 'corPct':
      s.gpMargins[year] = 1 - value;            // edit CoR% → sets GP margin
      s.overridden.gpMargins[year] = true;
      break;
    case 'gpMargin':
      s.gpMargins[year] = value;
      s.overridden.gpMargins[year] = true;
      break;
    case 'opexPct':
      s.opexPcts[year] = value;
      s.overridden.opexPcts[year] = true;
      break;
    case 'ebitMargin':
      s.opexPcts[year] = s.gpMargins[year] - value;   // edit EBIT% → adjusts OpEx%
      s.overridden.opexPcts[year] = true;
      break;
    case 'taxRate':
      s.taxRates[year] = value;
      s.overridden.taxRates[year] = true;
      break;
    case 'fcfMargin':
      s.fcfMargins[year] = value;
      s.overridden.fcfMargins[year] = true;
      break;
  }
}

function isCellOverridden(field, year) {
  const ov = _dcfState.overridden;
  switch (field) {
    case 'growthRate':  return ov.growthRates[year];
    case 'corPct':
    case 'gpMargin':    return ov.gpMargins[year];
    case 'opexPct':
    case 'ebitMargin':  return ov.opexPcts[year];
    case 'taxRate':     return ov.taxRates[year];
    case 'fcfMargin':   return ov.fcfMargins[year];
    default:            return false;
  }
}

function editableTd(field, year, displayPct) {
  const overridden = isCellOverridden(field, year);
  const cls = 'cell-editable' + (overridden ? ' cell-overridden' : '');
  return `<td class="${cls}" data-field="${field}" data-year="${year}">${fmtPct(displayPct)}</td>`;
}

function actualTd(content) {
  return `<td class="col-actual">${content}</td>`;
}


/* ── Table row builders ── */

function buildTableRows(s, projs) {
  const years = projs.map((_, i) => s.baseYear + 1 + i);

  /* helpers for projected columns */
  const projTds = (fn) => projs.map((p, i) => fn(p, i)).join('');

  return `
    <!-- ── Revenue ── -->
    <tr class="row-bold">
      <td>Revenue</td>
      ${actualTd(fmtM(s.baseRevenue))}
      ${projTds((p) => `<td>${fmtM(p.revenue)}</td>`)}
    </tr>
    <tr class="row-italic">
      <td>% Growth</td>
      ${actualTd('—')}
      ${projTds((p, i) => editableTd('growthRate', i, p.growthRate))}
    </tr>

    <!-- ── Cost of Revenue ── -->
    <tr class="row-body row-cost">
      <td>Cost of Revenue</td>
      ${actualTd(fmtMParen(s.baseCostOfRevenue))}
      ${projTds((p) => `<td>${fmtMParen(p.cor)}</td>`)}
    </tr>
    <tr class="row-italic">
      <td>% of Revenue</td>
      ${actualTd(fmtPct(s.baseRevenue > 0 ? s.baseCostOfRevenue / s.baseRevenue : 0))}
      ${projTds((p, i) => editableTd('corPct', i, p.corPct))}
    </tr>

    <!-- ── Gross Profit ── -->
    <tr class="row-bold">
      <td>Gross Profit</td>
      ${actualTd(fmtM(s.baseGrossProfit))}
      ${projTds((p) => `<td>${fmtM(p.grossProfit)}</td>`)}
    </tr>
    <tr class="row-italic">
      <td>% Margin</td>
      ${actualTd(fmtPct(s.baseRevenue > 0 ? s.baseGrossProfit / s.baseRevenue : 0))}
      ${projTds((p, i) => editableTd('gpMargin', i, p.gpMargin))}
    </tr>

    <!-- ── Operating Expenses ── -->
    <tr class="row-body row-cost">
      <td>Operating Expenses</td>
      ${actualTd(fmtMParen(s.baseOpex))}
      ${projTds((p) => `<td>${fmtMParen(p.opex)}</td>`)}
    </tr>
    <tr class="row-italic">
      <td>% of Revenue</td>
      ${actualTd(fmtPct(s.baseRevenue > 0 ? s.baseOpex / s.baseRevenue : 0))}
      ${projTds((p, i) => editableTd('opexPct', i, p.opexPct))}
    </tr>

    <!-- ── EBIT ── -->
    <tr class="row-bold">
      <td>EBIT</td>
      ${actualTd(fmtM(s.baseEbit))}
      ${projTds((p) => `<td>${fmtM(p.ebit)}</td>`)}
    </tr>
    <tr class="row-italic">
      <td>% Margin</td>
      ${actualTd(fmtPct(s.baseRevenue > 0 ? s.baseEbit / s.baseRevenue : 0))}
      ${projTds((p, i) => editableTd('ebitMargin', i, p.ebitMargin))}
    </tr>

    <!-- ── Tax Expense ── -->
    <tr class="row-body row-cost">
      <td>Tax Expense</td>
      ${actualTd(fmtMParen(s.baseTax))}
      ${projTds((p) => `<td>${fmtMParen(p.taxExpense)}</td>`)}
    </tr>
    <tr class="row-italic">
      <td>Tax Rate</td>
      ${actualTd(fmtPct(s.baseEbit > 0 ? s.baseTax / s.baseEbit : 0))}
      ${projTds((p, i) => editableTd('taxRate', i, p.taxRate))}
    </tr>

    <!-- ── Free Cash Flow ── -->
    <tr class="row-bold row-fcf">
      <td>Free Cash Flow</td>
      ${actualTd(fmtM(s.baseFcf))}
      ${projTds((p) => `<td>${fmtM(p.fcf)}</td>`)}
    </tr>
    <tr class="row-italic row-fcf-italic">
      <td>% Margin</td>
      ${actualTd(fmtPct(s.baseRevenue > 0 ? s.baseFcf / s.baseRevenue : 0))}
      ${projTds((p, i) => editableTd('fcfMargin', i, p.fcfMargin))}
    </tr>
  `;
}


/* ── Projection table render ── */

function renderProjectionTable() {
  const s     = _dcfState;
  const projs = computeProjections(s);
  const years = projs.map((_, i) => s.baseYear + 1 + i);

  document.getElementById('dcf-projection').innerHTML = `
    <div class="dcf-proj-wrapper">
      <div class="dcf-proj-header">
        <div>
          <div class="dcf-proj-title">${escapeHtml(s.ticker)} DCF Valuation: Revenue &amp; Expenses Forecast</div>
          <div class="dcf-proj-subtitle">(USD in millions)</div>
        </div>
        <button id="recalc-btn" class="btn-recalc">Recalculate Intrinsic Value</button>
      </div>
      <div class="table-card">
        <div class="proj-table-scroll">
          <table class="dcf-proj-table">
            <thead>
              <tr>
                <th class="col-label"></th>
                <th class="col-actual">FY${s.baseYear}</th>
                ${years.map(y => `<th>FY${y}E</th>`).join('')}
              </tr>
            </thead>
            <tbody>
              ${buildTableRows(s, projs)}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;

  document.getElementById('recalc-btn').addEventListener('click', handleRecalculate);

  /* event delegation — survives re-renders since we re-attach each time */
  document.querySelector('#dcf-projection tbody')
    .addEventListener('click', handleCellClick);
}


/* ── Inline cell editing ── */

function handleCellClick(e) {
  const td = e.target.closest('td.cell-editable');
  if (!td || td.querySelector('input')) return;   // already editing

  const field = td.dataset.field;
  const year  = parseInt(td.dataset.year, 10);
  const currentPct = getCellPct(field, year);

  td.classList.add('cell-editing');
  td.innerHTML = `<input type="text" value="${(currentPct * 100).toFixed(1)}" autocomplete="off" />`;

  const input = td.querySelector('input');
  input.focus();
  input.select();

  let committed = false;

  const commit = () => {
    if (committed) return;
    committed = true;
    const raw = parseFloat(input.value.replace('%', '').trim());
    if (!isNaN(raw)) {
      applyCellEdit(field, year, raw / 100);
    }
    renderProjectionTable();
  };

  const cancel = () => {
    if (committed) return;
    committed = true;
    renderProjectionTable();
  };

  input.addEventListener('blur', commit);
  input.addEventListener('keydown', ev => {
    if (ev.key === 'Enter')  { ev.preventDefault(); commit(); }
    if (ev.key === 'Escape') { ev.preventDefault(); cancel(); }
  });
}


/* ── Recalculate button ── */

async function handleRecalculate() {
  const s   = _dcfState;
  const btn = document.getElementById('recalc-btn');
  btn.disabled    = true;
  btn.textContent = 'Recalculating\u2026';

  try {
    const result = await fetchRecalculate(s.ticker, {
      base_revenue:        s.baseRevenue,
      growth_rates:        s.growthRates,
      fcf_margins:         s.fcfMargins,
      wacc:                s.wacc,
      terminal_growth_rate: s.terminalGrowthRate,
      net_cash:            s.netCash,
      shares_outstanding:  s.sharesOutstanding,
      current_price:       s.currentPrice,
    });

    /* update price widget */
    updatePriceWidgetFromRecalc(result, s.currentPrice);

    /* update valuation bridge with revised values */
    const updatedModel = Object.assign({}, _fullData.dcf_model, {
      pv_fcfs:           result.pv_fcfs,
      pv_terminal_value: result.pv_terminal_value,
      enterprise_value:  result.enterprise_value,
      equity_value:      result.equity_value,
    });
    renderValuationBridge(updatedModel, result.intrinsic_value);

  } catch (err) {
    alert('Recalculate failed: ' + err.message);
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Recalculate Intrinsic Value';
  }
}


/* ── Price widget update after recalculate ── */

function updatePriceWidgetFromRecalc(result, currentPrice) {
  const widget = document.getElementById('price-widget');
  const pct    = result.upside_downside;
  const isUp   = pct >= 0;
  const cls    = isUp ? 'up' : 'down';
  const arrow  = isUp ? '\u25b2' : '\u25bc';
  const label  = isUp ? 'Upside' : 'Downside';

  widget.innerHTML = `
    <div class="price-col">
      <div class="price-label">Current Price</div>
      <div class="price-value">$${currentPrice.toFixed(2)}</div>
    </div>
    <div class="price-divider"></div>
    <div class="upside-badge ${cls}">
      <div class="upside-pct">${arrow} ${Math.abs(pct).toFixed(1)}%</div>
      <div class="upside-sub">${label} to IV</div>
    </div>
    <div class="price-divider"></div>
    <div class="price-col">
      <div class="price-label">Intrinsic Value (DCF)</div>
      <div class="price-value">$${result.intrinsic_value.toFixed(2)}</div>
    </div>
  `;
}


/* ── Cost of Capital cards ── */

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
      <div class="assumption-label">Cost of Equity</div>
      <div class="assumption-value">${fmtPct(d.cost_of_equity)}</div>
    </div>
    <div class="assumption-card">
      <div class="assumption-label">Cost of Debt</div>
      <div class="assumption-value">${fmtPct(d.cost_of_debt)}</div>
    </div>
    <div class="assumption-card">
      <div class="assumption-label">WACC</div>
      <div class="assumption-value">${fmtPct(d.wacc)}</div>
    </div>
  `;
}


/* ── Valuation Bridge ── */

function renderValuationBridge(d, intrinsicValue) {
  const netCashLabel = d.net_cash >= 0 ? '+ Net Cash' : '\u2212 Net Debt';
  const netCashSign  = d.net_cash >= 0 ? '+' : '\u2212';

  document.getElementById('dcf-bridge').innerHTML = `
    <div class="bridge-row">
      <span><span class="bridge-sign">+</span> PV of FCFs (Years 1&ndash;5)</span>
      <span>${fmtUSD(d.pv_fcfs)}</span>
    </div>
    <div class="bridge-row">
      <span><span class="bridge-sign">+</span> PV of Terminal Value</span>
      <span>${fmtUSD(d.pv_terminal_value)}</span>
    </div>
    <div class="bridge-row subtotal">
      <span>Enterprise Value</span>
      <span>${fmtUSD(d.enterprise_value)}</span>
    </div>
    <div class="bridge-row">
      <span><span class="bridge-sign">${netCashSign}</span> ${netCashLabel} (Cash &minus; Debt)</span>
      <span>${fmtUSD(Math.abs(d.net_cash))}</span>
    </div>
    <div class="bridge-row subtotal">
      <span>Equity Value</span>
      <span>${fmtUSD(d.equity_value)}</span>
    </div>
    <div class="bridge-row">
      <span><span class="bridge-sign">&divide;</span> Shares Outstanding</span>
      <span>${fmtShares(d.shares_outstanding)} shares</span>
    </div>
    <div class="bridge-row total">
      <span>Intrinsic Value / Share</span>
      <span>$${intrinsicValue.toFixed(2)}</span>
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
  renderValuationBridge(data.dcf_model, data.intrinsic_value);
}
