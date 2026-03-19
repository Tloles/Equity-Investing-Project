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

/* ── Upside badge helper ── */
function _upsideBadge(el, pct, suffix) {
  const isUp  = pct >= 0;
  const label = suffix || (isUp ? 'UPSIDE' : 'DOWNSIDE');
  el.className   = `val-upside ${isUp ? 'positive' : 'negative'}`;
  el.textContent = `${isUp ? '\u25b2' : '\u25bc'} ${Math.abs(pct).toFixed(1)}% ${label}`;
}

/* ── Render: price / valuation banner ── */
function renderPriceWidget(data) {
  const priceEl   = document.getElementById('current-price');
  const unavailEl = document.getElementById('price-unavailable');
  const dcfCard   = document.getElementById('dcf-val-card');
  const ddmCard   = document.getElementById('ddm-val-card');
  const compsCard = document.getElementById('comps-val-card');

  dcfCard.hidden   = true;
  ddmCard.hidden   = true;
  compsCard.hidden = true;
  unavailEl.hidden = true;

  if (!data.current_price) {
    unavailEl.hidden = false;
    return;
  }

  priceEl.textContent = `$${data.current_price.toFixed(2)}`;

  // DCF card
  if (data.dcf_available && data.intrinsic_value != null) {
    document.getElementById('dcf-iv').textContent = `$${data.intrinsic_value.toFixed(2)}`;
    _upsideBadge(document.getElementById('dcf-upside'), data.upside_downside);
    dcfCard.hidden = false;
  }

  // DDM card
  if (data.ddm_available && data.ddm_model && data.ddm_model.ggm_intrinsic_value) {
    const ggmIv  = data.ddm_model.ggm_intrinsic_value;
    const ddmPct = (ggmIv / data.current_price - 1) * 100;
    document.getElementById('ddm-iv').textContent = `$${ggmIv.toFixed(2)}`;
    _upsideBadge(document.getElementById('ddm-upside'), ddmPct);
    ddmCard.hidden = false;
  }

  // Comps card
  if (data.comps_available && data.comps && data.comps.implied_prices) {
    const ip   = data.comps.implied_prices;
    const vals = [ip.pe_implied, ip.ev_ebitda_implied, ip.ps_implied, ip.pb_implied]
                   .filter(v => v != null && v > 0);
    if (vals.length >= 1) {
      const lo  = Math.min(...vals);
      const hi  = Math.max(...vals);
      const mid = (lo + hi) / 2;
      document.getElementById('comps-iv-range').textContent = vals.length >= 2
        ? `$${Math.round(lo)} \u2013 $${Math.round(hi)}`
        : `$${lo.toFixed(2)}`;
      _upsideBadge(document.getElementById('comps-upside'), (mid / data.current_price - 1) * 100, 'TO MIDPOINT');
      compsCard.hidden = false;
    }
  }

  if (dcfCard.hidden && ddmCard.hidden && compsCard.hidden) {
    unavailEl.hidden = false;
  }
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


/* ── Render: valuation context banner ── */
function renderValuationContext(data) {
  const container = document.getElementById('valuation-context');

  if (!data.dcf_available) {
    hide(container);
    return;
  }

  const QUALITY_SCORE = {
    'Strong Buy':   2,
    'Bullish':      1,
    'Neutral':      0,
    'Bearish':     -1,
    'Strong Sell': -2,
  };

  const rating    = data.overall_rating || 'Neutral';
  const pct       = data.upside_downside;
  const score     = QUALITY_SCORE[rating] ?? 0;
  const valSignal = pct > 20 ? 'undervalued' : pct < -20 ? 'overvalued' : 'fairly valued';

  const bullishOvervalued  = score > 0 && valSignal === 'overvalued';
  const bearishUndervalued = score < 0 && valSignal === 'undervalued';

  if (!bullishOvervalued && !bearishUndervalued) {
    hide(container);
    return;
  }

  const ticker = escapeHtml(data.ticker);
  const absPct = Math.abs(pct).toFixed(1);

  let explanation;
  if (bullishOvervalued) {
    explanation = `Our fundamental analysis rates ${ticker} as <strong>${escapeHtml(rating)}</strong> based on business quality, but the DCF model suggests the stock trades ${absPct}% above intrinsic value. Strong fundamentals are already priced in — investors are paying a premium for quality. Consider whether the moat justifies the premium, similar to how Morningstar separates its Economic Moat rating from its star rating.`;
  } else {
    explanation = `Our fundamental analysis rates ${ticker} as <strong>${escapeHtml(rating)}</strong>, but the DCF model suggests ${absPct}% upside to intrinsic value. The market may be pricing in risks that our model doesn't fully capture, or this could represent a contrarian opportunity.`;
  }

  const ratingStyle = RATING_STYLES[rating] || RATING_STYLES['Neutral'];
  const valLabel    = valSignal === 'overvalued'  ? 'Overvalued'
                    : valSignal === 'undervalued' ? 'Undervalued'
                    : 'Fair Value';
  const valColor    = valSignal === 'overvalued'  ? '#ef4444'
                    : valSignal === 'undervalued' ? '#059669'
                    : '#6b7280';
  const valSign     = pct >= 0 ? '+' : '';

  container.innerHTML = `
    <div class="valuation-context-banner">
      <div class="vc-header">
        <span>&#9889;</span>
        <span>VALUATION DISCONNECT</span>
      </div>
      <p class="vc-explanation">${explanation}</p>
      <div class="vc-cards">
        <div class="vc-card">
          <div class="vc-card-label">BUSINESS QUALITY</div>
          <div class="vc-card-value">
            <span class="rating-badge" style="background:${ratingStyle.bg};color:${ratingStyle.text}">${escapeHtml(rating)}</span>
          </div>
        </div>
        <div class="vc-card">
          <div class="vc-card-label">VALUATION</div>
          <div class="vc-card-value" style="color:${valColor}">${valSign}${pct.toFixed(1)}%</div>
          <div style="font-size:0.8rem;color:${valColor};margin-top:4px;font-weight:600">${valLabel}</div>
        </div>
      </div>
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


/* ── Render: structured bull/bear lists ── */
function renderStructuredList(listEl, items) {
  if (!items || items.length === 0) {
    listEl.innerHTML = '<li>No data available.</li>';
    return;
  }

  listEl.innerHTML = items.map((item, i) => {
    if (typeof item === 'object' && item.headline) {
      return `
        <li class="structured-item">
          <span class="num">${i + 1}</span>
          <div class="item-content">
            <div class="headline-text">${parseMarkdown(item.headline)}</div>
            <div class="item-detail">${parseMarkdown(item.detail)}</div>
          </div>
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


/* ── Relative date helper ── */
function _relativeDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return '';
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7)  return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return `${Math.floor(days / 30)}mo ago`;
}


/* ── Render: catalysts, sentiment & top news ── */
function renderCatalysts(data) {
  const section = document.getElementById('catalysts-section');
  const hasCatalysts = data.recent_catalysts && data.recent_catalysts.length > 0;
  const hasSentiment = data.sentiment_summary && data.sentiment_summary.length > 0;
  const hasNews      = data.news_headlines && data.news_headlines.length > 0;

  if (!hasCatalysts && !hasSentiment && !hasNews) {
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

  // ── Top news section ──────────────────────────────────────────────────────
  let newsEl = document.getElementById('news-headlines-section');
  if (!newsEl) {
    newsEl = document.createElement('div');
    newsEl.id = 'news-headlines-section';
    section.appendChild(newsEl);
  }

  if (!hasNews) {
    newsEl.hidden = true;
    return;
  }

  const indices = (data.top_news_indices && data.top_news_indices.length > 0)
    ? data.top_news_indices
    : [0, 1, 2, 3, 4];

  const selected = indices
    .map(i => data.news_headlines[i])
    .filter(Boolean)
    .slice(0, 5);

  const rows = selected.map(item => `
    <a class="news-link-row" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">
      <span class="news-source-badge">${escapeHtml(item.source || 'News')}</span>
      <span class="news-headline-text">${escapeHtml(item.headline)}</span>
      <span class="news-date">${_relativeDate(item.date)}</span>
    </a>
  `).join('');

  newsEl.className = 'news-headlines-section';
  newsEl.innerHTML = `
    <div class="card-header" style="margin-bottom:12px">
      <div class="card-icon">&#9889;</div>
      <span class="card-title">TOP NEWS</span>
    </div>
    ${rows}
  `;
  newsEl.hidden = false;
}
