(function() {
  let builderId = document.querySelector('.revenue-room')?.dataset.builderId || 'anonymous';
  let dismissedConvergence = sessionStorage.getItem('convergence_dismissed_revenue') === 'true';

  async function fetchRevenue() {
    try {
      const res = await fetch(`/revenue/data?builder_id=${builderId}`);
      const data = await res.json();
      updateSummary(data);
      renderTable(data.intents || []);
      checkConvergence(data.intents || []);
    } catch(e) {
      console.warn('[greg/revenue] fetch failed', e);
      document.getElementById('revenue-table-body').innerHTML = '<tr><td colspan="5">Unable to load ledger.</td></tr>';
    }
  }

  function updateSummary(data) {
    animateCurrency('confirmed-revenue', 0, data.confirmed_revenue || 0);
    animateCurrency('pending-revenue', 0, data.pending_revenue || 0);
    animateCurrency('greg-confirmed', 0, data.greg_confirmed_share || 0);
    animateCurrency('greg-projected', 0, data.greg_projected_share || 0);
  }

  function animateCurrency(elementId, start, end) {
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
      el.innerText = `$${current.toFixed(2)}`;
    }, stepTime);
  }

  function renderTable(intents) {
    const tbody = document.getElementById('revenue-table-body');
    if (!intents.length) {
      tbody.innerHTML = '<tr><td colspan="5">No revenue data yet. Greg is measuring.</td></tr>';
      return;
    }
    tbody.innerHTML = intents.map(i => `
      <tr>
        <td>${escapeHtml(i.text || 'Untitled').substring(0, 60)}</td>
        <td class="status-${i.status || 'escaped'}">${(i.status || 'escaped').toUpperCase()}</td>
        <td>$${(i.revenue || 0).toFixed(2)}</td>
        <td>$${(i.greg_share || 0).toFixed(2)}</td>
        <td>${i.updated_at ? new Date(i.updated_at).toLocaleDateString() : '—'}</td>
      </tr>
    `).join('');
  }

  function checkConvergence(intents) {
    const converged = intents.find(i => i.status === 'converged');
    if (converged && !dismissedConvergence) {
      const overlay = document.getElementById('convergence-overlay');
      document.getElementById('convergence-intent-text').innerText = converged.text || 'Unnamed intent';
      document.getElementById('convergence-share').innerText = `$${(converged.greg_share || 0).toFixed(2)}`;
      overlay.style.display = 'flex';
    }
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
    sessionStorage.setItem('convergence_dismissed_revenue', 'true');
  });

  fetchRevenue();
  setInterval(fetchRevenue, 10000);
})();
