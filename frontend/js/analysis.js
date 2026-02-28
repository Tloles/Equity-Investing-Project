/* analysis.js — renders the Analysis tab (bull/bear/risks/summary, meta bar, price widget) */

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function parseMarkdown(str) {
  return escapeHtml(str)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>');
}

/* ── Render: meta bar ── */
function renderMeta(data) {
  const bar = document.getElementById('meta-bar');
  const transcriptChip = data.transcript_available
    ? `<span class="meta-chip">Transcript <b>Q${data.transcript_quarter} ${data.transcript_year}</b></span>`
    : `<span class="meta-chip no-transcript"><b>No transcript available</b></span>`;

  const sectorChip = data.sector
    ? `<span class="meta-chip">Sector <b>${escapeHtml(data.sector)}</b></span>`
    : '';

  const industryChip = data.industry
    ? `<span class="meta-chip">${escapeHtml(data.industry)}</span>`
    : '';

  bar.innerHTML = `
    <span class="ticker-badge">${escapeHtml(data.ticker)}</span>
    <span class="meta-chip">10-K filed <b>${escapeHtml(data.filing_date)}</b></span>
    ${transcriptChip}
    ${sectorChip}
    ${industryChip}
  `;
}

/* ── Render: price widget ── */
function renderPriceWidget(data) {
  const widget = document.getElementById('price-widget');

  if (!data.dcf_available) {
    widget.innerHTML = '<p class="price-unavailable">Live price &amp; DCF valuation unavailable for this ticker.</p>';
    return;
  }

  const pct   = data.upside_downside;
  const isUp  = pct >= 0;
  const cls   = isUp ? 'up' : 'down';
  const arrow = isUp ? '\u25b2' : '\u25bc';
  const label = isUp ? 'Upside' : 'Downside';

  widget.innerHTML = `
    <div class="price-col">
      <div class="price-label">Current Price</div>
      <div class="price-value">$${data.current_price.toFixed(2)}</div>
    </div>
    <div class="price-divider"></div>
    <div class="upside-badge ${cls}">
      <div class="upside-pct">${arrow} ${Math.abs(pct).toFixed(1)}%</div>
      <div class="upside-sub">${label} to IV</div>
    </div>
    <div class="price-divider"></div>
    <div class="price-col">
      <div class="price-label">Intrinsic Value (DCF)</div>
      <div class="price-value">$${data.intrinsic_value.toFixed(2)}</div>
    </div>
  `;
}

/* ── Render: source document links ── */
function renderSourceDocs(data) {
  const el = document.getElementById('source-docs');

  const hasFilings    = data.filing_urls && data.filing_urls.length > 0;
  const hasTranscript = data.transcript_available && data.transcript_url;

  if (!hasFilings && !hasTranscript) {
    hide(el);
    return;
  }

  let html = '';

  if (hasFilings) {
    const links = data.filing_urls.map(f =>
      `<a class="source-link" href="${f.url}" target="_blank" rel="noopener noreferrer">FY${f.year} 10-K &#8599;</a>`
    ).join('');
    html += `<div class="source-group"><span class="source-label">10-K Filings</span>${links}</div>`;
  }

  if (hasTranscript) {
    const label = `Q${data.transcript_quarter} ${data.transcript_year}`;
    html += `<div class="source-group"><span class="source-label">Earnings Transcripts</span>` +
      `<a class="source-link" href="${data.transcript_url}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)} &#8599;</a></div>`;
  }

  el.innerHTML = html;
  show(el);
}

/* ── Render: analysis tab lists ── */
function renderList(listEl, items) {
  listEl.innerHTML = items.map((text, i) => `
    <li><span class="num">${i + 1}</span><span>${parseMarkdown(text)}</span></li>
  `).join('');
}
