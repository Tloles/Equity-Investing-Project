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
document.querySelectorAll('.tab-btn').forEach(tabBtn => {
  tabBtn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-analysis').hidden = true;
    document.getElementById('tab-dcf').hidden = true;
    tabBtn.classList.add('active');
    document.getElementById('tab-' + tabBtn.dataset.tab).hidden = false;
  });
});

function resetTabs() {
  document.querySelectorAll('.tab-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.tab === 'analysis'));
  document.getElementById('tab-analysis').hidden = false;
  document.getElementById('tab-dcf').hidden = true;
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
    renderPriceWidget(data);
    renderList(document.getElementById('bull-list'),  data.bull_case);
    renderList(document.getElementById('bear-list'),  data.bear_case);
    renderList(document.getElementById('risks-list'), data.downplayed_risks);
    document.getElementById('summary-text').innerHTML = parseMarkdown(data.analyst_summary);
    renderDCF(data);
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
