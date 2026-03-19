/* app.js — main entry point: initializes everything, handles ticker input and analyze button */

/* ── DOM refs ── */
const form          = document.getElementById('search-form');
const input         = document.getElementById('ticker-input');
const btn           = document.getElementById('analyze-btn');
const emptyState    = document.getElementById('empty-state');
const loadingEl     = document.getElementById('loading');
const errorState    = document.getElementById('error-state');
const errorMsg      = document.getElementById('error-msg');
const resultsEl     = document.getElementById('results');
const analysisStatus = document.getElementById('analysis-status');
const statusSteps   = document.getElementById('status-steps');

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

/* ── Step-based status indicator ── */
const STEP_LABELS = [
  'Classifying sector',
  'Fetching SEC filings & financial data',
  'Loading 10-K filing',
  'Loading earnings transcripts',
  'Crunching financials (DCF, DDM, comps)',
  'Running AI analysis',
  'Finalizing report',
];

let _stepQueue     = [];
let _stepProcessing = false;
let _currentStep   = 0;   // 1-based index of the active step (0 = none started)
let _doneCallback  = null; // called after queue drains on "done"

function initStatusSteps() {
  _stepQueue      = [];
  _stepProcessing = false;
  _currentStep    = 0;
  _doneCallback   = null;

  statusSteps.innerHTML = STEP_LABELS.map((label, i) => `
    <div class="status-step step-pending" id="sstep-${i}">
      <span class="step-icon">&#9675;</span>
      <span class="step-label">${label}</span>
    </div>
  `).join('');

  show(analysisStatus);
}

function _applyStepState(stepIndex /* 1-based */) {
  STEP_LABELS.forEach((_, i) => {
    const el   = document.getElementById('sstep-' + i);
    const icon = el.querySelector('.step-icon');
    const oneBasedI = i + 1;

    if (oneBasedI < stepIndex) {
      el.className  = 'status-step step-complete';
      icon.innerHTML = '&#10003;'; // ✓
    } else if (oneBasedI === stepIndex) {
      el.className  = 'status-step step-active';
      icon.innerHTML = '<span class="step-spinner"></span>';
    } else {
      el.className  = 'status-step step-pending';
      icon.innerHTML = '&#9675;'; // ○
    }
  });
}

function _markAllComplete() {
  STEP_LABELS.forEach((_, i) => {
    const el   = document.getElementById('sstep-' + i);
    const icon = el.querySelector('.step-icon');
    el.className  = 'status-step step-complete';
    icon.innerHTML = '&#10003;';
  });
}

function _processQueue() {
  if (_stepQueue.length === 0) {
    _stepProcessing = false;
    return;
  }

  _stepProcessing = true;
  const { step, isDone, delay } = _stepQueue.shift();

  if (isDone) {
    _markAllComplete();
    _stepProcessing = false;
    if (_doneCallback) setTimeout(_doneCallback, 600);
    return;
  }

  _currentStep = step;
  _applyStepState(step);

  setTimeout(_processQueue, delay);
}

function _enqueue(item) {
  _stepQueue.push(item);
  if (!_stepProcessing) _processQueue();
}

function onProgress({ step, total, label }) {
  _enqueue({ step, isDone: false, delay: 800 });
}

function onStreamDone(callback) {
  // Speed up any remaining queued steps, then call callback
  const remaining = _stepQueue.length;
  for (let i = 0; i < remaining; i++) {
    _stepQueue[i].delay = 400;
  }
  _doneCallback = callback;
  _enqueue({ isDone: true, delay: 0 });
}

function markStepError() {
  const i = _currentStep > 0 ? _currentStep - 1 : 0;
  const el   = document.getElementById('sstep-' + i);
  const icon = el.querySelector('.step-icon');
  if (el) {
    el.className  = 'status-step step-error';
    icon.innerHTML = '&#10007;'; // ✗
  }
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
  initStatusSteps();

  try {
    let data;
    try {
      data = await new Promise((resolve, reject) => {
        fetchAnalysisStream(ticker, onProgress)
          .then(result => {
            onStreamDone(() => resolve(result));
          })
          .catch(reject);
      });
    } catch (_streamErr) {
      hide(analysisStatus);
      data = await fetchAnalysis(ticker);
    }

    renderMeta(data);
    renderSourceDocs(data);
    renderPriceWidget(data);
    renderRatingBadge(data);
    renderKeyMetrics(data);
    renderValuationContext(data);
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

    setTimeout(() => {
      hide(analysisStatus);
      hide(loadingEl);
      show(resultsEl);
    }, 1000);

  } catch (err) {
    markStepError();
    errorMsg.textContent = err.message;
    setTimeout(() => {
      hide(analysisStatus);
      hide(loadingEl);
      show(errorState);
    }, 800);
  } finally {
    setLoading(false);
  }
});
