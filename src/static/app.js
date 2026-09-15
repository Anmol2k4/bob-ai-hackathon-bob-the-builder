const $ = (selector) => document.querySelector(selector);

async function getJson(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error('Request failed');
  return response.json();
}

function renderOverview(data) {
  $('#metrics').innerHTML = [
    ['VERIFIED RULES', data.verified_rules, 'protocol intelligence'],
    ['OPEN DEVIATIONS', data.open_deviations, 'evidence-linked'],
    ['EMERGING SITES', data.emerging_sites, 'velocity above baseline'],
    ['MONITORING PERIOD', data.period, 'synthetic demo set'],
  ].map(([label, value, note]) => `<div class="metric"><span>${label}</span><strong>${value}</strong><small>${note}</small></div>`).join('');
  $('#site-list').innerHTML = data.sites.map((site, index) => `<div class="site ${index === 0 ? 'selected' : ''}" data-site="${site.id}"><div><div class="site-id">${site.id}</div><div class="site-state">${site.status} · ${site.velocity > 0 ? '+' : ''}${site.velocity} velocity</div></div><div><div class="site-bar"><i style="width:${site.risk}%"></i></div></div><div class="site-risk">${site.risk}</div></div>`).join('');
}

function renderDetail(data) {
  $('#risk-score').textContent = data.risk_index;
  $('#sparkline').innerHTML = [49, 55, 61, 70, 79, 87].map(value => `<i style="height:${value}%"></i>`).join('');
  $('#drivers').innerHTML = data.drivers.map(driver => `<div class="driver"><strong>${driver.label}</strong><b>${driver.share}%</b><small>${driver.rule} · ${driver.detail}</small><div class="driver-bar"><i style="width:${driver.share}%"></i></div></div>`).join('');
  $('#evidence').innerHTML = data.evidence.map(item => `<span title="${item.finding}">${item.id}</span>`).join('');
}

async function run() {
  const overview = await getJson('/api/overview');
  const detail = await getJson('/api/sites/S037/intelligence');
  renderOverview(overview);
  renderDetail(detail);
  const bob = await getJson('/api/bob/investigate');
  $('#bob-answer').textContent = bob.answer;
  $('#bob-sources').innerHTML = bob.sources.map(source => `<span>${source}</span>`).join('');
  $('#site-list').addEventListener('click', event => {
    const site = event.target.closest('.site');
    if (!site) return;
    document.querySelectorAll('.site').forEach(item => item.classList.remove('selected'));
    site.classList.add('selected');
  });
}

$('#reduction').addEventListener('input', event => { $('#reduction-value').textContent = `${event.target.value}%`; });
$('#simulate').addEventListener('click', async () => {
  const reduction = Number($('#reduction').value);
  const result = await getJson('/api/sites/S037/simulate', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({reduction}) });
  $('#simulation-result').innerHTML = `<strong>${result.projected_risk}/100 projected risk</strong> · ${result.status} · ${result.impact}`;
});

run().catch(() => { $('#bob-answer').textContent = 'The local intelligence service is unavailable. Start the app with python src/app.py.'; });