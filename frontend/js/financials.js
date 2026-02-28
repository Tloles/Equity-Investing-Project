/* financials.js — Financials tab: statements, ratios, and key metrics */


/* ── Format helpers ── */

function finFmt(value, type) {
  if (value == null || isNaN(value)) return '—';
  switch (type) {
    case 'dollar':
      // Millions with 1 decimal
      if (Math.abs(value) >= 1e9) return '$' + (value / 1e9).toFixed(1) + 'B';
      if (Math.abs(value) >= 1e6) return '$' + (value / 1e6).toFixed(1) + 'M';
      if (Math.abs(value) >= 1e3) return '$' + (value / 1e3).toFixed(1) + 'K';
      return '$' + value.toFixed(0);
    case 'pct':
      return (value * 100).toFixed(1) + '%';
    case 'ratio':
      return value.toFixed(2) + 'x';
    case 'per_share':
      return '$' + value.toFixed(2);
    case 'shares':
      if (Math.abs(value) >= 1e9) return (value / 1e9).toFixed(2) + 'B';
      if (Math.abs(value) >= 1e6) return (value / 1e6).toFixed(1) + 'M';
      return value.toFixed(0);
    case 'coverage':
      return value.toFixed(1) + 'x';
    default:
      return String(value);
  }
}


/* ── Statement sub-tab state ── */

let _finActiveStatement = 'income';


/* ── Build table row ── */

function finRow(label, years, field, format, rowClass) {
  let cls = rowClass ? ` class="${rowClass}"` : '';
  let html = `<tr${cls}><td>${label}</td>`;
  for (const y of years) {
    const val = y[field];
    html += `<td>${finFmt(val, format)}</td>`;
  }
  return html + '</tr>';
}


/* ── Render: income statement table ── */

function renderIncomeStatement(years) {
  return `
    <table class="dcf-proj-table">
      <thead><tr>
        <th class="col-label">Metric</th>
        ${years.map(y => `<th>FY${y.year}</th>`).join('')}
      </tr></thead>
      <tbody>
        ${finRow('Revenue', years, 'revenue', 'dollar', 'row-bold')}
        ${finRow('Revenue Growth', years, 'revenue_growth', 'pct', 'row-italic')}
        ${finRow('Cost of Revenue', years, 'cost_of_revenue', 'dollar', 'row-cost')}
        ${finRow('Gross Profit', years, 'gross_profit', 'dollar', 'row-bold')}
        ${finRow('Gross Margin', years, 'gross_margin', 'pct', 'row-italic')}
        <tr class="section-header"><td colspan="${years.length + 1}">Operating Expenses</td></tr>
        ${finRow('R&D', years, 'rd_expenses', 'dollar', 'row-cost')}
        ${finRow('SG&A', years, 'sga_expenses', 'dollar', 'row-cost')}
        ${finRow('Total OpEx', years, 'operating_expenses', 'dollar', 'row-cost')}
        ${finRow('Operating Income', years, 'operating_income', 'dollar', 'row-bold')}
        ${finRow('Operating Margin', years, 'operating_margin', 'pct', 'row-italic')}
        <tr class="section-header"><td colspan="${years.length + 1}">Below the Line</td></tr>
        ${finRow('Interest Expense', years, 'interest_expense', 'dollar', 'row-cost')}
        ${finRow('Pretax Income', years, 'pretax_income', 'dollar', '')}
        ${finRow('Tax Expense', years, 'tax_expense', 'dollar', 'row-cost')}
        ${finRow('Net Income', years, 'net_income', 'dollar', 'row-highlight')}
        ${finRow('Net Margin', years, 'net_margin', 'pct', 'row-italic')}
        <tr class="section-header"><td colspan="${years.length + 1}">Per Share</td></tr>
        ${finRow('EPS (Diluted)', years, 'eps', 'per_share', 'row-bold')}
        ${finRow('EPS Growth', years, 'eps_growth', 'pct', 'row-italic')}
        ${finRow('Diluted Shares', years, 'diluted_shares', 'shares', '')}
        ${finRow('EBITDA', years, 'ebitda', 'dollar', 'row-bold')}
      </tbody>
    </table>
  `;
}


/* ── Render: balance sheet table ── */

function renderBalanceSheet(years) {
  return `
    <table class="dcf-proj-table">
      <thead><tr>
        <th class="col-label">Metric</th>
        ${years.map(y => `<th>FY${y.year}</th>`).join('')}
      </tr></thead>
      <tbody>
        <tr class="section-header"><td colspan="${years.length + 1}">Assets</td></tr>
        ${finRow('Cash & Equivalents', years, 'cash', 'dollar', '')}
        ${finRow('Total Current Assets', years, 'total_current_assets', 'dollar', '')}
        ${finRow('Total Assets', years, 'total_assets', 'dollar', 'row-bold')}
        <tr class="section-header"><td colspan="${years.length + 1}">Liabilities</td></tr>
        ${finRow('Total Current Liabilities', years, 'total_current_liabilities', 'dollar', '')}
        ${finRow('Total Debt', years, 'total_debt', 'dollar', '')}
        ${finRow('Total Liabilities', years, 'total_liabilities', 'dollar', 'row-bold')}
        <tr class="section-header"><td colspan="${years.length + 1}">Equity</td></tr>
        ${finRow("Shareholders' Equity", years, 'total_equity', 'dollar', 'row-bold')}
      </tbody>
    </table>
  `;
}


/* ── Render: cash flow table ── */

function renderCashFlow(years) {
  return `
    <table class="dcf-proj-table">
      <thead><tr>
        <th class="col-label">Metric</th>
        ${years.map(y => `<th>FY${y.year}</th>`).join('')}
      </tr></thead>
      <tbody>
        ${finRow('Operating Cash Flow', years, 'operating_cash_flow', 'dollar', 'row-bold')}
        ${finRow('D&A', years, 'da', 'dollar', '')}
        ${finRow('Capital Expenditures', years, 'capex', 'dollar', 'row-cost')}
        ${finRow('Free Cash Flow', years, 'free_cash_flow', 'dollar', 'row-fcf')}
        ${finRow('FCF / Share', years, 'fcf_per_share', 'per_share', 'row-italic')}
        <tr class="section-header"><td colspan="${years.length + 1}">Capital Return</td></tr>
        ${finRow('Dividends Paid', years, 'dividends_paid', 'dollar', '')}
        ${finRow('Share Repurchases', years, 'share_repurchases', 'dollar', '')}
      </tbody>
    </table>
  `;
}


/* ── Render: ratios dashboard ── */

function renderRatiosDashboard(years) {
  return `
    <table class="dcf-proj-table">
      <thead><tr>
        <th class="col-label">Ratio</th>
        ${years.map(y => `<th>FY${y.year}</th>`).join('')}
      </tr></thead>
      <tbody>
        <tr class="section-header"><td colspan="${years.length + 1}">Profitability</td></tr>
        ${finRow('Gross Margin', years, 'gross_margin', 'pct', '')}
        ${finRow('Operating Margin', years, 'operating_margin', 'pct', '')}
        ${finRow('Net Margin', years, 'net_margin', 'pct', '')}
        ${finRow('ROE', years, 'roe', 'pct', '')}
        ${finRow('ROA', years, 'roa', 'pct', '')}
        ${finRow('ROIC', years, 'roic', 'pct', '')}
        <tr class="section-header"><td colspan="${years.length + 1}">Liquidity</td></tr>
        ${finRow('Current Ratio', years, 'current_ratio', 'ratio', '')}
        <tr class="section-header"><td colspan="${years.length + 1}">Leverage</td></tr>
        ${finRow('Debt / Equity', years, 'debt_to_equity', 'ratio', '')}
        ${finRow('Interest Coverage', years, 'interest_coverage', 'coverage', '')}
        <tr class="section-header"><td colspan="${years.length + 1}">Efficiency</td></tr>
        ${finRow('Asset Turnover', years, 'asset_turnover', 'ratio', '')}
        <tr class="section-header"><td colspan="${years.length + 1}">Growth</td></tr>
        ${finRow('Revenue Growth', years, 'revenue_growth', 'pct', '')}
        ${finRow('Net Income Growth', years, 'net_income_growth', 'pct', '')}
        ${finRow('EPS Growth', years, 'eps_growth', 'pct', '')}
      </tbody>
    </table>
  `;
}


/* ── Statement sub-tab switching ── */

function switchFinStatement(which, years) {
  _finActiveStatement = which;

  // Update sub-tab buttons
  document.querySelectorAll('#fin-sub-tabs .fin-sub-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.stmt === which);
  });

  // Render the selected statement
  const container = document.getElementById('fin-statement-body');
  let html = '';
  switch (which) {
    case 'income':   html = renderIncomeStatement(years); break;
    case 'balance':  html = renderBalanceSheet(years);    break;
    case 'cashflow': html = renderCashFlow(years);        break;
    case 'ratios':   html = renderRatiosDashboard(years); break;
  }
  container.innerHTML = `<div class="proj-table-scroll">${html}</div>`;
}


/* ── Main entry point ── */

function renderFinancials(data) {
  const unavailable = document.getElementById('fin-unavailable');
  const content = document.getElementById('fin-content');

  if (!data.financials_available || !data.financials || data.financials.length === 0) {
    show(unavailable);
    hide(content);
    return;
  }

  hide(unavailable);
  show(content);

  const years = data.financials;

  // Wire sub-tab buttons
  document.querySelectorAll('#fin-sub-tabs .fin-sub-btn').forEach(btn => {
    btn.onclick = () => switchFinStatement(btn.dataset.stmt, years);
  });

  // Render default (income statement)
  _finActiveStatement = 'income';
  document.querySelectorAll('#fin-sub-tabs .fin-sub-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.stmt === 'income');
  });
  switchFinStatement('income', years);
}
