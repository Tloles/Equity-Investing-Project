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
  const r = rating.toLowerCase();
  if (r === 'low')    return 'low';
  if (r === 'medium') return 'medium';
  return 'high';
}

/* ── Render: Porter's Five Forces grid ── */
function renderPorterGrid(ia) {
  const grid = document.getElementById('porter-grid');
  grid.innerHTML = PORTER_FORCES.map(({ key, label }) => {
    const force = ia[key] || {};
    const cls   = _ratingClass(force.rating);
    return `
      <div class="porter-card">
        <div class="porter-force-name">${escapeHtml(label)}</div>
        <div class="porter-rating ${cls}">${escapeHtml(force.rating || '—')}</div>
        <div class="porter-explanation">${escapeHtml(force.explanation || '')}</div>
      </div>`;
  }).join('');
}

/* ── Render: Industry Structure (multi-paragraph) ── */
function renderIndustryStructure(text) {
  const el = document.getElementById('industry-structure');
  const paras = (text || '').split(/\n\n+/).filter(Boolean);
  el.innerHTML = paras.map(p => `<p>${escapeHtml(p.trim())}</p>`).join('');
}

/* ── Render: Key KPIs ── */
function renderKPIs(kpis) {
  const list = document.getElementById('kpi-list');
  list.innerHTML = (kpis || []).map(k => `
    <li class="kpi-item">
      <span class="kpi-metric">${escapeHtml(k.metric)}</span>
      <span class="kpi-sep">—</span>
      <span class="kpi-why">${escapeHtml(k.why_it_matters)}</span>
    </li>`).join('');
}

/* ── Render: Industry tab ── */
function renderIndustry(data) {
  const unavailable = document.getElementById('industry-unavailable');
  const content     = document.getElementById('industry-content');

  if (!data.industry_analysis) {
    show(unavailable);
    hide(content);
    return;
  }

  hide(unavailable);
  show(content);

  const ia = data.industry_analysis;

  renderPorterGrid(ia);
  renderIndustryStructure(ia.industry_structure);

  document.getElementById('competitive-position').textContent =
    ia.competitive_position || '';

  renderKPIs(ia.key_kpis);

  renderList(document.getElementById('tailwinds-list'), ia.tailwinds || []);
  renderList(document.getElementById('headwinds-list'), ia.headwinds || []);
}
