/* api.js — all fetch calls to the backend */

function fetchAnalysisStream(ticker, onProgress) {
  return new Promise((resolve, reject) => {
    fetch('/analyze-stream/' + encodeURIComponent(ticker))
      .then(res => {
        if (!res.ok) {
          return res.json().then(d => {
            throw new Error(d.detail || 'Stream error (HTTP ' + res.status + ')');
          });
        }

        const reader  = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer    = '';

        function processBuffer() {
          const parts = buffer.split('\n\n');
          buffer = parts.pop(); // keep any incomplete trailing chunk

          for (const part of parts) {
            const line = part.trim();
            if (!line.startsWith('data: ')) continue;
            let evt;
            try { evt = JSON.parse(line.slice(6)); } catch { continue; }

            if (evt.type === 'progress') {
              onProgress({ step: evt.step, total: evt.total, label: evt.label });
            } else if (evt.type === 'done') {
              resolve(evt.payload);
              return true;
            } else if (evt.type === 'error') {
              reject(new Error(evt.message));
              return true;
            }
          }
          return false;
        }

        function pump() {
          return reader.read().then(({ done, value }) => {
            if (done) {
              reject(new Error('Stream ended without a done event'));
              return;
            }
            buffer += decoder.decode(value, { stream: true });
            if (processBuffer()) return;
            return pump();
          });
        }

        return pump();
      })
      .catch(reject);
  });
}

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

async function fetchDDMRecalculate(ticker, overrides) {
  const res  = await fetch('/ddm/recalculate/' + encodeURIComponent(ticker), {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(overrides),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'DDM recalculate error (HTTP ' + res.status + ')');
  return data;
}
