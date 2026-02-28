/* api.js — all fetch calls to the backend */

async function fetchAnalysis(ticker) {
  const res  = await fetch('/analyze/' + encodeURIComponent(ticker));
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Unexpected error (HTTP ' + res.status + ')');
  return data;
}
