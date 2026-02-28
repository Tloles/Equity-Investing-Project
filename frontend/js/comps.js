/* comps.js — Comparable Company Analysis tab */


/* ── Format helpers ── */

function compFmt(value, type) {
  if (value == null || isNaN(value)) return '—';
  switch (type) {
    case 'multiple': return value.toFixed(1) + 'x';
    case 'pct':      return (value * 100).toFixed(1) + '%';
    case 'dollar':   return '$' + value.toFixed(2);
    case 'mcap':
      if (value >= 1e12) return '$' + (value / 1e12).toFixed(2) + 'T';
      if (value >= 1e9)  return '$' + (value / 1e9).toFixed(1) + 'B';
      if (value >= 1e6)  return '$' + (value / 1e6).toFixed(0) + 'M';
      return '$' + value.toFixed(0);
    default: return String(value);
  }
}


/* ── Sub-tab state ── */
let _compActiveView = 'valuation';


/* ── Build table ── */

function compTable(peers, columns, medians) {
  let header = '<th class="col-label">Company</th>';
  for (const col of columns) {
    header += `<th>${col.label}</th>`;
  }

  let rows = '';
  for (const p of peers) {
    const cls = p.is_target ? ' class="row-highlight"' : '';
    let row = `<td>${p.is_target ? '<strong>' + p.ticker + '</strong>' : p.ticker}`;
    row += `<span style="display:block;font-size:.72rem;color:var(--muted);font-weight:400;">${escapeHtml(p.company_name)}</span></td>`;
    for (const col of columns) {
      row += `<td>${compFmt(p[col.field], col.format)}</td>`;
    }
    rows += `<tr${cls}>${row}</tr>`;
  }

  /* Median row */
  if (medians) {
    let medRow = '<td><strong>Peer Median</strong></td>';
    for (const col of columns) {
      const medKey = col.medianKey;
      const medVal = medKey ? medians[medKey] : null;
      medRow += `<td><strong>${compFmt(medVal, col.format)}</strong></td>`;
    }
    rows += `<tr class="row-fcf">${medRow}</tr>`;
  }

  return `
    <div class="proj-table-scroll">
      <table class="dcf-proj-table">
        <thead><tr>${header}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}


/* ── View definitions ── */

const COMP_VIEWS = {
  valuation: {
    columns: [
      { label: 'Mkt Cap',     field: 'market_cap',     format: 'mcap',     medianKey: null },
      { label: 'Price',       field: 'price',          format: 'dollar',   medianKey: null },
      { label: 'P/E',         field: 'pe_ratio',       format: 'multiple', medianKey: 'median_pe' },
      { label: 'EV/EBITDA',   field: 'ev_to_ebitda',   format: 'multiple', medianKey: 'median_ev_ebitda' },
      { label: 'P/S',         field: 'price_to_sales', format: 'multiple', medianKey: 'median_ps' },
      { label: 'P/B',         field: 'price_to_book',  format: 'multiple', medianKey: 'median_pb' },
      { label: 'EV/Revenue',  field: 'ev_to_revenue',  format: 'multiple', medianKey: null },
      { label: 'PEG',         field: 'peg_ratio',      format: 'multiple', medianKey: null },
    ],
  },
  profitability: {
    columns: [
      { label: 'Gross Margin',   field: 'gross_margin',     format: 'pct', medianKey: null },
      { label: 'Op Margin',      field: 'operating_margin', format: 'pct', medianKey: null },
      { label: 'Net Margin',     field: 'net_margin',       format: 'pct', medianKey: null },
      { label: 'ROE',            field: 'roe',              format: 'pct', medianKey: null },
      { label: 'ROIC',           field: 'roic',             format: 'pct', medianKey: null },
    ],
  },
  growth: {
    columns: [
      { label: 'Mkt Cap',        field: 'market_cap',      format: 'mcap',     medianKey: null },
      { label: 'Revenue Growth',  field: 'revenue_growth',  format: 'pct',      medianKey: null },
      { label: 'EPS Growth',      field: 'eps_growth',      format: 'pct',      medianKey: null },
      { label: 'Div Yield',       field: 'dividend_yield',  format: 'pct',      medianKey: null },
      { label: 'D/E',             field: 'debt_to_equity',  format: 'multiple', medianKey: null },
    ],
  },
};


/* ── Switch sub-view ── */

function switchCompView(which, comps) {
  _compActiveView = which;
  document.querySelectorAll('#comp-sub-tabs .fin-sub-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === which);
  });

  const view = COMP_VIEWS[which];
  const container = document.getElementById('comp-table-body');
  container.innerHTML = compTable(
    comps.peers,
    view.columns,
    which === 'valuation' ? comps : null,
  );
}


/* ── Main entry point ── */

function renderComps(data) {
  const unavailable = document.getElementById('comps-unavailable');
  const content = document.getElementById('comps-content');

  if (!data.comps_available || !data.comps || !data.comps.peers || data.comps.peers.length < 2) {
    show(unavailable);
    hide(content);
    return;
  }

  hide(unavailable);
  show(content);

  const comps = data.comps;

  // Wire sub-tab buttons
  document.querySelectorAll('#comp-sub-tabs .fin-sub-btn').forEach(btn => {
    btn.onclick = () => switchCompView(btn.dataset.view, comps);
  });

  // Render implied value cards
  renderImpliedValues(data, comps);

  // Render default view
  _compActiveView = 'valuation';
  document.querySelectorAll('#comp-sub-tabs .fin-sub-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === 'valuation');
  });
  switchCompView('valuation', comps);
}


/* ── Implied valuation from peer medians ── */

function renderImpliedValues(data, comps) {
  const container = document.getElementById('comp-implied');
  if (!comps.median_pe && !comps.median_ev_ebitda) {
    container.innerHTML = '';
    return;
  }

  const target = comps.peers.find(p => p.is_target);
  if (!target) { container.innerHTML = ''; return; }

  const currentPrice = data.current_price || target.price;

  // Find target's financials for implied calculations
  const fins = data.financials;
  let latestEps = null;
  let latestRevPerShare = null;
  if (fins && fins.length > 0) {
    const latest = fins[fins.length - 1];
    latestEps = latest.eps;
    if (latest.revenue && latest.diluted_shares && latest.diluted_shares > 0) {
      latestRevPerShare = latest.revenue / latest.diluted_shares;
    }
  }

  let cards = '';

  if (comps.median_pe && latestEps && latestEps > 0) {
    const implied = comps.median_pe * latestEps;
    const upside = ((implied - currentPrice) / currentPrice * 100);
    const cls = upside >= 0 ? 'up' : 'down';
    const arrow = upside >= 0 ? '\u25b2' : '\u25bc';
    cards += `
      <div class="comp-implied-card">
        <div class="comp-implied-label">Implied by Peer Median P/E</div>
        <div class="comp-implied-calc">${comps.median_pe.toFixed(1)}x × $${latestEps.toFixed(2)} EPS</div>
        <div class="ddm-iv-badge ${cls}" style="margin-top:8px;">
          <div class="ddm-iv-value">${compFmt(implied, 'dollar')}</div>
          <div class="ddm-iv-label">${arrow} ${Math.abs(upside).toFixed(1)}% ${upside >= 0 ? 'Upside' : 'Downside'}</div>
        </div>
      </div>
    `;
  }

  if (comps.median_ps && latestRevPerShare && latestRevPerShare > 0) {
    const implied = comps.median_ps * latestRevPerShare;
    const upside = ((implied - currentPrice) / currentPrice * 100);
    const cls = upside >= 0 ? 'up' : 'down';
    const arrow = upside >= 0 ? '\u25b2' : '\u25bc';
    cards += `
      <div class="comp-implied-card">
        <div class="comp-implied-label">Implied by Peer Median P/S</div>
        <div class="comp-implied-calc">${comps.median_ps.toFixed(1)}x × $${latestRevPerShare.toFixed(2)} Rev/Share</div>
        <div class="ddm-iv-badge ${cls}" style="margin-top:8px;">
          <div class="ddm-iv-value">${compFmt(implied, 'dollar')}</div>
          <div class="ddm-iv-label">${arrow} ${Math.abs(upside).toFixed(1)}% ${upside >= 0 ? 'Upside' : 'Downside'}</div>
        </div>
      </div>
    `;
  }

  container.innerHTML = cards;
}
