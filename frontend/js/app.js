/* app.js — main entry point: initializes everything, handles ticker input and analyze button */

/* ── DOM refs ── */
const form       = document.getElementById('search-form');
const input      = document.getElementById('ticker-input');
const btn        = document.getElementById('analyze-btn');
const emptyState = document.getElementById('empty-state');
const loadingEl  = document.getElementById('loading');
const errorState = document.getElementById('error-state');
const errorMsg   = document.getElementById('error-msg');
const resultsEl  = document.getElementById('results');

/* ── Visibility helpers (also used by dcf.js at call time) ── */
const show = el => { el.hidden = false; };
const hide = el => { el.hidden = true; };

/* ── Loading state ── */
function setLoading(on) {
  btn.disabled = on;
  btn.textContent = on ? 'Analyzing\u2026' : 'Analyze \u2192';
}

/* ── Tab switching ── */
const TAB_IDS = ['analysis', 'financials', 'industry', 'dcf', 'ddm', 'comps'];

document.querySelectorAll('.tab-btn').forEach(tabBtn => {
  tabBtn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    TAB_IDS.forEach(id => { document.getElementById('tab-' + id).hidden = true; });
    tabBtn.classList.add('active');
    document.getElementById('tab-' + tabBtn.dataset.tab).hidden = false;
  });
});

function resetTabs() {
  document.querySelectorAll('.tab-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.tab === 'analysis'));
  document.getElementById('tab-analysis').hidden = false;
  TAB_IDS.filter(id => id !== 'analysis').forEach(id => {
    document.getElementById('tab-' + id).hidden = true;
  });
}

/* ── Form submit ── */
form.addEventListener('submit', async e => {
  e.preventDefault();

  const ticker = input.value.trim().toUpperCase();
  if (!ticker) return;

  hide(emptyState);
  hide(errorState);
  hide(resultsEl);
  show(loadingEl);
  setLoading(true);

  try {
    const data = await fetchAnalysis(ticker);

    renderMeta(data);
    renderSourceDocs(data);
    renderPriceWidget(data);
    renderRatingBadge(data);
    renderKeyMetrics(data);
    renderStructuredList(document.getElementById('bull-list'),  data.bull_case);
    renderStructuredList(document.getElementById('bear-list'),  data.bear_case);
    renderList(document.getElementById('risks-list'), data.downplayed_risks);
    renderCatalysts(data);
    document.getElementById('summary-text').innerHTML = parseMarkdown(data.analyst_summary);
    renderIndustry(data);
    renderFinancials(data);
    renderDCF(data);
    renderDDM(data);
    renderComps(data);
    resetTabs();

    hide(loadingEl);
    show(resultsEl);

  } catch (err) {
    errorMsg.textContent = err.message;
    hide(loadingEl);
    show(errorState);
  } finally {
    setLoading(false);
  }
});
