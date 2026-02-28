/* industry.js — renders the Industry tab (Porter's Five Forces, structure,
   competitive position, KPIs, tailwinds/headwinds) */

const PORTER_FORCES = [
  { key: 'threat_of_new_entrants',        label: 'Threat of New Entrants' },
  { key: 'bargaining_power_of_suppliers', label: 'Bargaining Power of Suppliers' },
  { key: 'bargaining_power_of_buyers',    label: 'Bargaining Power of Buyers' },
  { key: 'threat_of_substitutes',         label: 'Threat of Substitutes' },
  { key: 'competitive_rivalry',           label: 'Competitive Rivalry' },
];

function _ratingClass(rating) {
  if (!rating) return '';
  const r = String(rating).toLowerCase();
  if (r === 'low')    return 'low';
  if (r === 'medium') return 'medium';
  return 'high';
}

/* ── Render: Porter's Five Forces grid ── */
function renderPorterGrid(ia) {
  const grid = document.getElementById('porter-grid');
  grid.innerHTML = PORTER_FORCES.map(({ key, label }) => {
    const force = (ia && ia[key]) ? ia[key] : {};
    const cls   = _ratingClass(force.rating);
    const rating      = force.rating      ? String(force.rating)      : '—';
    const explanation = force.explanation ? String(force.explanation) : '';
    return `
      <div class="porter-card">
        <div class="porter-force-name">${escapeHtml(label)}</div>
        <div class="porter-rating ${cls}">${escapeHtml(rating)}</div>
        <div class="porter-explanation">${escapeHtml(explanation)}</div>
      </div>`;
  }).join('');
}

/* ── Render: Industry Structure (multi-paragraph) ── */
function renderIndustryStructure(text) {
  const el = document.getElementById('industry-structure');
  const str = text ? String(text) : '';
  const paras = str.split(/\n\n+/).map(p => p.trim()).filter(Boolean);
  if (paras.length === 0) {
    el.innerHTML = '';
  } else {
    el.innerHTML = paras.map(p => `<p>${escapeHtml(p)}</p>`).join('');
  }
}

/* ── Render: Key KPIs ── */
function renderKPIs(kpis) {
  const list = document.getElementById('kpi-list');
  const items = Array.isArray(kpis) ? kpis : [];
  if (items.length === 0) {
    list.innerHTML = '';
    return;
  }
  list.innerHTML = items.map(k => {
    const metric = k && k.metric           ? String(k.metric)           : '';
    const why    = k && k.why_it_matters   ? String(k.why_it_matters)   : '';
    if (!metric) return '';
    return `
      <li class="kpi-item">
        <span class="kpi-metric">${escapeHtml(metric)}</span>
        <span class="kpi-sep">—</span>
        <span class="kpi-why">${escapeHtml(why)}</span>
      </li>`;
  }).filter(Boolean).join('');
}

/* ── Render: a numbered list of strings (tailwinds or headwinds) ── */
function _renderStringList(listEl, items) {
  const arr = Array.isArray(items) ? items : [];
  if (arr.length === 0) {
    listEl.innerHTML = '';
    return;
  }
  listEl.innerHTML = arr.map((text, i) => {
    const str = text ? String(text) : '';
    return `<li><span class="num">${i + 1}</span><span>${escapeHtml(str)}</span></li>`;
  }).join('');
}

/* ── Render: Industry tab ── */
function renderIndustry(data) {
  const unavailable = document.getElementById('industry-unavailable');
  const content     = document.getElementById('industry-content');

  if (!data || !data.industry_analysis) {
    show(unavailable);
    hide(content);
    return;
  }

  hide(unavailable);
  show(content);

  const ia = data.industry_analysis;

  renderPorterGrid(ia);
  renderIndustryStructure(ia.industry_structure);

  const posEl = document.getElementById('competitive-position');
  posEl.textContent = ia.competitive_position ? String(ia.competitive_position) : '';

  renderKPIs(ia.key_kpis);

  _renderStringList(
    document.getElementById('tailwinds-list'),
    ia.tailwinds,
  );
  _renderStringList(
    document.getElementById('headwinds-list'),
    ia.headwinds,
  );
}
