(() => {
  const toast = (message) => { const node = document.querySelector('#toast'); if (!node) return; node.textContent = message; node.classList.add('show'); setTimeout(() => node.classList.remove('show'), 3200); };
  document.querySelectorAll('[data-demo]').forEach(button => button.addEventListener('click', async () => {
    button.disabled = true;
    try { const response = await fetch('/api/experiments/demo', {method: 'POST'}); const data = await response.json(); toast(data.inserted ? `${data.inserted} demo experiments loaded.` : 'Demo experiments are already available.'); setTimeout(() => location.href = '/experiments', 500); }
    catch { toast('Could not load demo experiments.'); } finally { button.disabled = false; }
  }));
  const form = document.querySelector('#experiment-form');
  if (form) form.addEventListener('submit', async event => {
    event.preventDefault(); const error = form.querySelector('.form-error'); const button = form.querySelector('button'); button.disabled = true; button.textContent = 'Saving experiment…'; error.hidden = true;
    try { const payload = Object.fromEntries(new FormData(form)); const response = await fetch('/api/experiments', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)}); const data = await response.json(); if (!response.ok) throw new Error(data.error); location.href = data.analysis_url; }
    catch (err) { error.textContent = err.message || 'Unable to save the experiment.'; error.hidden = false; button.disabled = false; button.textContent = 'Save Experiment →'; }
  });
  document.querySelectorAll('[data-delete]').forEach(button => button.addEventListener('click', async () => {
    if (!confirm('Delete this experiment record? This cannot be undone.')) return;
    const response = await fetch(`/api/experiments/${button.dataset.delete}`, {method:'DELETE'}); if (response.ok) { button.closest('.history-card').remove(); toast('Experiment deleted.'); } else toast('Unable to delete experiment.');
  }));
  const search = document.querySelector('#history-search'), filter = document.querySelector('#history-filter');
  const refresh = async () => { if (!search || !filter) return; const list = document.querySelector('#history-list'); const p = new URLSearchParams({q:search.value, result:filter.value}); const items = await (await fetch('/api/experiments?' + p)).json(); list.querySelectorAll('.history-card').forEach(card => { const item = items.find(x => x.id === card.dataset.id); card.hidden = !item; }); };
  [search, filter].filter(Boolean).forEach(node => node.addEventListener('input', refresh));
})();
