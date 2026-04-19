(function() {
  let builderId = document.querySelector('.dashboard-room')?.dataset.builderId || 'anonymous';
  let intentsCache = [];
  let dismissedConvergence = sessionStorage.getItem('convergence_dismissed') === 'true';

  async function fetchState() {
    try {
      const res = await fetch('/api/state');
      const data = await res.json();
      document.getElementById('live-tick').innerText = data.tick || '—';
      return data;
    } catch(e) { console.warn('[greg/dashboard] state fetch failed', e); }
  }

  async function fetchIntents() {
    try {
      const res = await fetch(`/pikkaio/status?builder_id=${builderId}`);
      const data = await res.json();
      intentsCache = data.intents || [];
      renderIntents(intentsCache);
      updateStats(intentsCache);
      checkConvergence(intentsCache);
    } catch(e) { console.warn('[greg/dashboard] intents fetch failed', e); }
  }

  function updateStats(intents) {
    const count = intents.length;
    const avgDrift = intents.reduce((sum, i) => sum + (i.drift_score || 0), 0) / (count || 1);
    const converged = intents.filter(i => i.status === 'converged').length;

    animateNumber('stat-intents', 0, count);
    animateNumber('stat-avg-drift', 0, avgDrift, 2);
    animateNumber('stat-convergences', 0, converged);
  }

  function animateNumber(elementId, start, end, decimals = 0) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const duration = 800;
    const stepTime = 20;
    const steps = duration / stepTime;
    const increment = (end - start) / steps;
    let current = start;
    const interval = setInterval(() => {
      current += increment;
      if ((increment > 0 && current >= end) || (increment < 0 && current <= end)) {
        current = end;
        clearInterval(interval);
      }
      el.innerText = decimals ? current.toFixed(decimals) : Math.round(current);
    }, stepTime);
  }

  function renderIntents(intents) {
    const grid = document.getElementById('intents-grid');
    if (!intents.length) {
      grid.innerHTML = '<div class="empty">No intents declared yet. The field is open.</div>';
      return;
    }
    grid.innerHTML = intents.map(intent => {
      const drift = intent.drift_score || 0;
      let borderColor = 'var(--accent)';
      if (drift > 0.7) borderColor = 'var(--danger)';
      else if (drift > 0.3) borderColor = 'var(--warn)';
      const driftColor = borderColor;
      return `
        <div class="intent-card" data-id="${intent.id}" style="border-left-color: ${borderColor};">
          <div class="intent-card-header">
            <span class="intent-title">${escapeHtml(intent.text || 'Untitled')}</span>
            <span class="intent-drift" style="color: ${driftColor};">${drift.toFixed(2)}</span>
          </div>
          <div class="intent-body" data-fulltext="${escapeHtml(intent.text || '')}">
            ${escapeHtml(intent.text || '').substring(0, 120)}${(intent.text || '').length > 120 ? '…' : ''}
          </div>
          <div class="intent-footer">
            <span>Declared ${daysAgo(intent.declared_at)} days ago</span>
            <span class="intent-intervention">${intent.last_intervention ? `Greg: ${escapeHtml(intent.last_intervention.substring(0, 60))}` : ''}</span>
          </div>
        </div>
      `;
    }).join('');

    document.querySelectorAll('.intent-card').forEach(card => {
      card.addEventListener('click', (e) => {
        e.stopPropagation();
        const body = card.querySelector('.intent-body');
        body.classList.toggle('expanded');
      });
    });
  }

  function checkConvergence(intents) {
    const converged = intents.find(i => i.status === 'converged');
    if (converged && !dismissedConvergence) {
      const overlay = document.getElementById('convergence-overlay');
      document.getElementById('convergence-intent-text').innerText = converged.text || 'Unnamed intent';
      overlay.style.display = 'flex';
    }
  }

  function daysAgo(dateStr) {
    if (!dateStr) return '?';
    const days = Math.floor((new Date() - new Date(dateStr)) / (1000*60*60*24));
    return days;
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function(m) {
      if (m === '&') return '&';
      if (m === '<') return '<';
      if (m === '>') return '>';
      return m;
    });
  }

  document.getElementById('convergence-dismiss')?.addEventListener('click', () => {
    document.getElementById('convergence-overlay').style.display = 'none';
    sessionStorage.setItem('convergence_dismissed', 'true');
  });

  fetchState();
  fetchIntents();
  setInterval(fetchIntents, 10000);
  setInterval(fetchState, 3000);
})();
