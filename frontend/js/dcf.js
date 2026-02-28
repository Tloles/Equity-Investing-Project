/* dcf.js — renders the DCF tab (table, cost of capital cards, valuation bridge) */

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

/* ── Render: DCF model tab ── */
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

  const d = data.dcf_model;

  /* Assumptions */
  document.getElementById('dcf-assumptions').innerHTML = `
    <div class="assumption-card">
      <div class="assumption-label">Revenue Growth</div>
      <div class="assumption-value">${fmtPct(d.revenue_growth_rate)}</div>
    </div>
    <div class="assumption-card">
      <div class="assumption-label">FCF Margin</div>
      <div class="assumption-value">${fmtPct(d.fcf_margin)}</div>
    </div>
    <div class="assumption-card">
      <div class="assumption-label">WACC</div>
      <div class="assumption-value">${fmtPct(d.wacc)}</div>
    </div>
    <div class="assumption-card">
      <div class="assumption-label">Terminal Growth</div>
      <div class="assumption-value">${fmtPct(d.terminal_growth_rate)}</div>
    </div>
  `;

  /* Cost of capital breakdown */
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

  /* FCF projection table */
  document.getElementById('dcf-table-body').innerHTML =
    d.projected_fcf.map((fcf, i) => `
      <tr>
        <td>Year ${i + 1}</td>
        <td>${fmtUSD(fcf)}</td>
        <td>${fmtUSD(d.pv_projected_fcf[i])}</td>
      </tr>
    `).join('');

  /* Value bridge */
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
      <span>$${data.intrinsic_value.toFixed(2)}</span>
    </div>
  `;
}
