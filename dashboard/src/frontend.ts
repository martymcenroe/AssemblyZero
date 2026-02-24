/**
 * Dashboard frontend — static HTML served by the Worker.
 *
 * MVP approach: single HTML page with CDN dependencies.
 * All dynamic content uses esc() for XSS prevention.
 */

export const DASHBOARD_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AssemblyZero Telemetry</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    .sparkline { display: flex; align-items: end; gap: 2px; height: 40px; }
    .sparkline-bar { width: 16px; border-radius: 2px 2px 0 0; min-height: 2px; transition: height 0.3s; }
    .tab-active { border-bottom: 2px solid #3b82f6; color: #3b82f6; font-weight: 600; }
    .event-row:hover { background: #f8fafc; }
  </style>
</head>
<body class="bg-gray-50 text-gray-900 font-sans">
  <div id="app" class="max-w-6xl mx-auto px-4 py-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">AssemblyZero Telemetry</h1>
      <div class="flex items-center gap-3">
        <input id="api-key" type="password" placeholder="API Key" class="border rounded px-3 py-1 text-sm w-64" />
        <button id="btn-connect" class="bg-blue-500 text-white px-4 py-1 rounded text-sm hover:bg-blue-600">Connect</button>
      </div>
    </div>

    <div id="nav-tabs" class="flex gap-4 border-b mb-6">
      <button class="tab px-3 py-2 text-sm tab-active" data-tab="overview">Overview</button>
      <button class="tab px-3 py-2 text-sm" data-tab="events">Events</button>
      <button class="tab px-3 py-2 text-sm" data-tab="errors">Errors</button>
      <button class="tab px-3 py-2 text-sm" data-tab="comparison">Comparison</button>
    </div>

    <div id="tab-overview" class="tab-content">
      <div class="grid grid-cols-4 gap-4 mb-6">
        <div class="bg-white rounded-lg shadow p-4"><div class="text-sm text-gray-500">Today's Events</div><div id="stat-total" class="text-3xl font-bold mt-1">-</div></div>
        <div class="bg-white rounded-lg shadow p-4"><div class="text-sm text-gray-500">Human</div><div id="stat-human" class="text-3xl font-bold mt-1 text-green-600">-</div></div>
        <div class="bg-white rounded-lg shadow p-4"><div class="text-sm text-gray-500">Claude</div><div id="stat-claude" class="text-3xl font-bold mt-1 text-purple-600">-</div></div>
        <div class="bg-white rounded-lg shadow p-4"><div class="text-sm text-gray-500">Errors</div><div id="stat-errors" class="text-3xl font-bold mt-1 text-red-600">-</div></div>
      </div>
      <div class="bg-white rounded-lg shadow p-4 mb-6">
        <div class="text-sm text-gray-500 mb-2">Last 7 Days</div>
        <div id="sparkline" class="sparkline"></div>
      </div>
      <div class="bg-white rounded-lg shadow p-4">
        <div class="text-sm text-gray-500 mb-2">Recent Errors</div>
        <div id="recent-errors" class="text-sm text-gray-400">Loading...</div>
      </div>
    </div>

    <div id="tab-events" class="tab-content hidden">
      <div class="flex gap-3 mb-4">
        <select id="event-filter-actor" class="border rounded px-3 py-1 text-sm">
          <option value="">All Actors</option>
          <option value="human">Human</option>
          <option value="claude">Claude</option>
        </select>
        <select id="event-filter-repo" class="border rounded px-3 py-1 text-sm">
          <option value="AssemblyZero">AssemblyZero</option>
          <option value="unleashed">unleashed</option>
          <option value="Talos">Talos</option>
          <option value="Aletheia">Aletheia</option>
        </select>
      </div>
      <div class="bg-white rounded-lg shadow">
        <table class="w-full text-sm">
          <thead class="bg-gray-50"><tr>
            <th class="text-left px-4 py-2">Time</th>
            <th class="text-left px-4 py-2">Type</th>
            <th class="text-left px-4 py-2">Actor</th>
            <th class="text-left px-4 py-2">Repo</th>
            <th class="text-left px-4 py-2">Details</th>
          </tr></thead>
          <tbody id="events-table"></tbody>
        </table>
      </div>
    </div>

    <div id="tab-errors" class="tab-content hidden">
      <div class="bg-white rounded-lg shadow">
        <table class="w-full text-sm">
          <thead class="bg-gray-50"><tr>
            <th class="text-left px-4 py-2">Time</th>
            <th class="text-left px-4 py-2">Error Type</th>
            <th class="text-left px-4 py-2">Actor</th>
            <th class="text-left px-4 py-2">Repo</th>
            <th class="text-left px-4 py-2">Message</th>
          </tr></thead>
          <tbody id="errors-table"></tbody>
        </table>
      </div>
    </div>

    <div id="tab-comparison" class="tab-content hidden">
      <div class="grid grid-cols-2 gap-6">
        <div class="bg-white rounded-lg shadow p-4">
          <h3 class="text-lg font-semibold text-green-600 mb-3">Human</h3>
          <div id="comparison-human" class="space-y-2 text-sm">Loading...</div>
        </div>
        <div class="bg-white rounded-lg shadow p-4">
          <h3 class="text-lg font-semibold text-purple-600 mb-3">Claude</h3>
          <div id="comparison-claude" class="space-y-2 text-sm">Loading...</div>
        </div>
      </div>
    </div>
  </div>

  <script>
    // XSS prevention — all dynamic content goes through esc()
    function esc(s) { const d = document.createElement('div'); d.textContent = String(s ?? ''); return d.innerHTML; }

    const BASE = location.origin;
    let apiKey = '';
    function getKey() { return apiKey || document.getElementById('api-key').value; }

    async function apiFetch(path) {
      const res = await fetch(BASE + path, { headers: { 'X-API-Key': getKey() } });
      if (!res.ok) throw new Error(res.status + ' ' + res.statusText);
      return res.json();
    }

    function switchTab(tab) {
      document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
      document.querySelectorAll('.tab').forEach(el => el.classList.remove('tab-active'));
      document.getElementById('tab-' + tab).classList.remove('hidden');
      document.querySelector('[data-tab="' + tab + '"]').classList.add('tab-active');
      if (tab === 'events') loadEvents();
      if (tab === 'errors') loadErrorsTab();
      if (tab === 'comparison') loadComparison();
    }

    function fmtTime(ts) { return ts ? new Date(ts).toLocaleTimeString() : '-'; }

    function actorBadge(actor) {
      const s = esc(actor);
      if (actor === 'human') return '<span class="bg-green-50 text-green-700 rounded px-2 py-0.5 text-xs">' + s + '</span>';
      if (actor === 'claude') return '<span class="bg-purple-50 text-purple-700 rounded px-2 py-0.5 text-xs">' + s + '</span>';
      return s;
    }

    // Tab navigation
    document.getElementById('nav-tabs').addEventListener('click', function(e) {
      const tab = e.target.dataset?.tab;
      if (tab) switchTab(tab);
    });

    // Connect button
    document.getElementById('btn-connect').addEventListener('click', loadDashboard);

    // Filter changes
    document.getElementById('event-filter-actor').addEventListener('change', loadEvents);
    document.getElementById('event-filter-repo').addEventListener('change', loadEvents);

    async function loadDashboard() {
      apiKey = document.getElementById('api-key').value;
      try {
        const overview = await apiFetch('/api/dashboard/overview');
        document.getElementById('stat-total').textContent = overview.today.total;
        document.getElementById('stat-human').textContent = overview.today.human;
        document.getElementById('stat-claude').textContent = overview.today.claude;
        document.getElementById('stat-errors').textContent = overview.today.errors;

        const errDiv = document.getElementById('recent-errors');
        if (overview.recent_errors.length === 0) {
          errDiv.textContent = 'No errors today';
          errDiv.className = 'text-sm text-green-500';
        } else {
          errDiv.textContent = '';
          overview.recent_errors.forEach(function(e) {
            const row = document.createElement('div');
            row.className = 'py-1 border-b';
            const badge = document.createElement('span');
            badge.className = 'bg-red-50 text-red-600 rounded px-2 py-0.5 text-xs';
            badge.textContent = e.event_type || 'error';
            const time = document.createElement('span');
            time.className = 'text-gray-500 ml-2';
            time.textContent = fmtTime(e.timestamp);
            const msg = document.createElement('span');
            msg.className = 'ml-2';
            msg.textContent = (e.metadata && e.metadata.error_message) || '';
            row.append(badge, time, msg);
            errDiv.appendChild(row);
          });
        }

        const weekly = await apiFetch('/api/summary/weekly');
        const spark = document.getElementById('sparkline');
        spark.textContent = '';
        const maxVal = Math.max(...weekly.days.map(function(d) { return d.total; }), 1);
        weekly.days.reverse().forEach(function(d) {
          const col = document.createElement('div');
          col.style.cssText = 'display:flex;flex-direction:column;align-items:center;gap:1px';
          const cBar = document.createElement('div');
          cBar.className = 'sparkline-bar';
          cBar.style.cssText = 'background:#8b5cf6;height:' + Math.max(1, (d.claude/maxVal)*40) + 'px';
          cBar.title = 'Claude: ' + d.claude;
          const hBar = document.createElement('div');
          hBar.className = 'sparkline-bar';
          hBar.style.cssText = 'background:#10b981;height:' + Math.max(1, (d.human/maxVal)*40) + 'px';
          hBar.title = 'Human: ' + d.human;
          const label = document.createElement('div');
          label.className = 'text-xs text-gray-400 mt-1';
          label.textContent = d.date.slice(5);
          col.append(cBar, hBar, label);
          spark.appendChild(col);
        });
      } catch (e) {
        document.getElementById('stat-total').textContent = 'ERR';
      }
    }

    function buildEventRow(item) {
      const tr = document.createElement('tr');
      tr.className = 'event-row border-b';
      const cells = [
        fmtTime(item.timestamp),
        null, // event_type gets special handling
        null, // actor badge
        esc(item.repo || '-'),
        esc(item.metadata ? JSON.stringify(item.metadata).slice(0, 80) : '-')
      ];
      cells.forEach(function(text, i) {
        const td = document.createElement('td');
        td.className = 'px-4 py-2' + (i === 1 ? ' font-mono text-xs' : '') + (i === 4 ? ' text-gray-500 text-xs' : '');
        if (i === 1) { td.textContent = item.event_type || '-'; }
        else if (i === 2) { td.innerHTML = actorBadge(item.actor); }
        else { td.textContent = text; }
        tr.appendChild(td);
      });
      return tr;
    }

    async function loadEvents() {
      const actor = document.getElementById('event-filter-actor').value;
      const repo = document.getElementById('event-filter-repo').value;
      const tbody = document.getElementById('events-table');
      tbody.textContent = '';
      try {
        const data = actor
          ? await apiFetch('/api/events/by-actor?actor=' + encodeURIComponent(actor) + '&limit=50')
          : await apiFetch('/api/events?repo=' + encodeURIComponent(repo) + '&limit=50');
        if (data.items.length === 0) {
          const tr = document.createElement('tr');
          const td = document.createElement('td');
          td.colSpan = 5; td.className = 'px-4 py-8 text-center text-gray-400';
          td.textContent = 'No events';
          tr.appendChild(td); tbody.appendChild(tr);
        } else {
          data.items.forEach(function(item) { tbody.appendChild(buildEventRow(item)); });
        }
      } catch (e) {
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = 5; td.className = 'px-4 py-4 text-red-500';
        td.textContent = 'Error: ' + e.message;
        tr.appendChild(td); tbody.appendChild(tr);
      }
    }

    async function loadErrorsTab() {
      const tbody = document.getElementById('errors-table');
      tbody.textContent = '';
      try {
        const data = await apiFetch('/api/errors');
        if (data.items.length === 0) {
          const tr = document.createElement('tr');
          const td = document.createElement('td');
          td.colSpan = 5; td.className = 'px-4 py-8 text-center text-gray-400';
          td.textContent = 'No errors';
          tr.appendChild(td); tbody.appendChild(tr);
        } else {
          data.items.forEach(function(item) {
            const tr = document.createElement('tr');
            tr.className = 'event-row border-b';
            [fmtTime(item.timestamp), item.event_type, null, item.repo, (item.metadata && item.metadata.error_message) || '-'].forEach(function(text, i) {
              const td = document.createElement('td');
              td.className = 'px-4 py-2' + (i === 4 ? ' text-xs' : '');
              if (i === 1) {
                const badge = document.createElement('span');
                badge.className = 'bg-red-50 text-red-600 rounded px-2 py-0.5 text-xs';
                badge.textContent = text || '-';
                td.appendChild(badge);
              } else if (i === 2) {
                td.innerHTML = actorBadge(item.actor);
              } else {
                td.textContent = esc(text || '-');
              }
              tr.appendChild(td);
            });
            tbody.appendChild(tr);
          });
        }
      } catch (e) {
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = 5; td.className = 'px-4 py-4 text-red-500';
        td.textContent = 'Error: ' + e.message;
        tr.appendChild(td); tbody.appendChild(tr);
      }
    }

    async function loadComparison() {
      try {
        const [human, claude] = await Promise.all([
          apiFetch('/api/events/by-actor?actor=human&limit=100'),
          apiFetch('/api/events/by-actor?actor=claude&limit=100'),
        ]);
        function renderSummary(items, containerId) {
          const types = {};
          items.forEach(function(i) { types[i.event_type] = (types[i.event_type] || 0) + 1; });
          const el = document.getElementById(containerId);
          el.textContent = '';
          const count = document.createElement('div');
          count.className = 'text-2xl font-bold mb-3';
          count.textContent = items.length + ' events';
          el.appendChild(count);
          Object.entries(types).sort(function(a,b) { return b[1] - a[1]; }).forEach(function(pair) {
            const row = document.createElement('div');
            row.className = 'flex justify-between py-1 border-b';
            const name = document.createElement('span');
            name.className = 'font-mono text-xs';
            name.textContent = pair[0];
            const val = document.createElement('span');
            val.className = 'font-semibold';
            val.textContent = pair[1];
            row.append(name, val);
            el.appendChild(row);
          });
          if (Object.keys(types).length === 0) {
            const empty = document.createElement('div');
            empty.className = 'text-gray-400';
            empty.textContent = 'No events';
            el.appendChild(empty);
          }
        }
        renderSummary(human.items, 'comparison-human');
        renderSummary(claude.items, 'comparison-claude');
      } catch (e) {
        document.getElementById('comparison-human').textContent = 'Error: ' + e.message;
      }
    }

    // Auto-load if key in URL hash
    if (location.hash) {
      document.getElementById('api-key').value = location.hash.slice(1);
      loadDashboard();
    }
  </script>
</body>
</html>`;
