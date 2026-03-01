/* analysis.js — renders the Analysis tab (rating, thesis, metrics, bull/bear, catalysts, summary) */

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

  const hasFilings     = data.filing_urls && data.filing_urls.length > 0;
  const hasTranscripts = data.transcript_urls && data.transcript_urls.length > 0;

  if (!hasFilings && !hasTranscripts) {
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

  if (hasTranscripts) {
    const links = data.transcript_urls.map(t => {
      const label = (t.quarter && t.year) ? `Q${t.quarter} ${t.year}` : 'Transcript';
      return `<a class="source-link" href="${t.url}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)} &#8599;</a>`;
    }).join('');
    html += `<div class="source-group"><span class="source-label">Earnings Transcripts</span>${links}</div>`;
  }

  el.innerHTML = html;
  show(el);
}


/* ── Rating badge color map ── */
const RATING_STYLES = {
  'Strong Buy':  { bg: '#059669', text: '#fff' },
  'Bullish':     { bg: '#10b981', text: '#fff' },
  'Neutral':     { bg: '#6b7280', text: '#fff' },
  'Bearish':     { bg: '#ef4444', text: '#fff' },
  'Strong Sell': { bg: '#991b1b', text: '#fff' },
};


/* ── Render: rating badge + thesis ── */
function renderRatingBadge(data) {
  const container = document.getElementById('rating-thesis');
  const rating = data.overall_rating || 'Neutral';
  const thesis = data.thesis_statement || '';
  const style = RATING_STYLES[rating] || RATING_STYLES['Neutral'];

  if (!rating && !thesis) {
    hide(container);
    return;
  }

  container.innerHTML = `
    <div class="rating-thesis-row">
      <span class="rating-badge" style="background:${style.bg};color:${style.text}">
        ${escapeHtml(rating)}
      </span>
      <span class="thesis-text">${escapeHtml(thesis)}</span>
    </div>
  `;
  show(container);
}


/* ── Render: key metrics strip ── */
function renderKeyMetrics(data) {
  const container = document.getElementById('key-metrics-strip');
  const metrics = data.key_metrics;

  if (!metrics || metrics.length === 0) {
    hide(container);
    return;
  }

  const trendIcon = (t) => {
    if (t === 'up') return '<span class="trend-icon trend-up">\u25b2</span>';
    if (t === 'down') return '<span class="trend-icon trend-down">\u25bc</span>';
    return '<span class="trend-icon trend-flat">\u25b6</span>';
  };

  const cards = metrics.map(m => `
    <div class="metric-card">
      <div class="metric-label">${escapeHtml(m.label)}</div>
      <div class="metric-value">${trendIcon(m.trend)} ${escapeHtml(m.value)}</div>
    </div>
  `).join('');

  container.innerHTML = `<div class="metrics-strip">${cards}</div>`;
  show(container);
}


/* ── Render: structured bull/bear lists (collapsible) ── */
function renderStructuredList(listEl, items) {
  if (!items || items.length === 0) {
    listEl.innerHTML = '<li>No data available.</li>';
    return;
  }

  listEl.innerHTML = items.map((item, i) => {
    if (typeof item === 'object' && item.headline) {
      return `
        <li class="structured-item">
          <div class="item-headline" onclick="this.parentElement.classList.toggle('expanded')">
            <span class="num">${i + 1}</span>
            <span class="headline-text">${parseMarkdown(item.headline)}</span>
            <span class="expand-icon">&#9662;</span>
          </div>
          <div class="item-detail">${parseMarkdown(item.detail)}</div>
        </li>
      `;
    }
    // Legacy plain string fallback
    const text = typeof item === 'string' ? item : JSON.stringify(item);
    return `<li><span class="num">${i + 1}</span><span>${parseMarkdown(text)}</span></li>`;
  }).join('');
}


/* ── Render: plain list (risks, etc.) ── */
function renderList(listEl, items) {
  listEl.innerHTML = items.map((text, i) => `
    <li><span class="num">${i + 1}</span><span>${parseMarkdown(text)}</span></li>
  `).join('');
}


/* ── Render: catalysts & sentiment ── */
function renderCatalysts(data) {
  const section = document.getElementById('catalysts-section');
  const hasCatalysts = data.recent_catalysts && data.recent_catalysts.length > 0;
  const hasSentiment = data.sentiment_summary && data.sentiment_summary.length > 0;

  if (!hasCatalysts && !hasSentiment) {
    hide(section);
    return;
  }

  show(section);

  if (hasCatalysts) {
    renderList(document.getElementById('catalysts-list'), data.recent_catalysts);
  }

  if (hasSentiment) {
    document.getElementById('sentiment-text').innerHTML = parseMarkdown(data.sentiment_summary);
  } else {
    document.getElementById('sentiment-text').innerHTML =
      '<span style="color:var(--muted);font-style:italic;">No social media data available.</span>';
  }
}
