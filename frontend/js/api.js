/* api.js — all fetch calls to the backend */

async function fetchAnalysis(ticker) {
  const res  = await fetch('/analyze/' + encodeURIComponent(ticker));
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Unexpected error (HTTP ' + res.status + ')');
  return data;
}

async function fetchRecalculate(ticker, overrides) {
  const res  = await fetch('/dcf/recalculate/' + encodeURIComponent(ticker), {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(overrides),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Recalculate error (HTTP ' + res.status + ')');
  return data;
}
