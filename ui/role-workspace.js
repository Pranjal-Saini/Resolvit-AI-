(() => {
  'use strict';
  const role = document.body.dataset.role;
  const base = role === 'agent' ? '/agent' : '/review';
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const currency = value => new Intl.NumberFormat('en-IN', {style:'currency', currency:'INR', maximumFractionDigits:2}).format(value);
  const state = {cases:[], selected:null, detail:null, demo:null, busy:false, refreshing:false};
  const routeLabel = route => ({ai:'AI handles automatically', human:'Human support', review:'Approver'})[route];
  const ownsDemo = scenario => scenario.route === (role === 'agent' ? 'human' : 'review');

  async function api(path, options = {}) {
    const response = await fetch(path, {...options, credentials:'same-origin',
      headers:{'Content-Type':'application/json', 'X-Workspace-Role':role}, signal:AbortSignal.timeout(30000)});
    const result = await response.json();
    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        $('#workspace').replaceChildren();
        window.location.assign('/login/' + role);
      }
      throw new Error(typeof result.detail === 'string' ? result.detail : 'The request could not be completed.');
    }
    return result;
  }
  function error(failure) { $('#workspace-error').textContent = failure.message || String(failure); }
  function notice(message) { $('#workspace-notice').textContent = message; $('#workspace-notice').hidden = false; }
  function filteredCases() {
    const current = role === 'agent' ? 'escalated' : 'awaiting_approval';
    const history = $('#queue-filter').value === 'history';
    const query = $('#search').value.toLowerCase();
    return state.cases.filter(item => (history ? item.status !== current : item.status === current) &&
      (item.id + ' ' + item.customer_name + ' ' + (item.summary || '')).toLowerCase().includes(query));
  }
  function renderQueue() {
    const rows = filteredCases();
    $('#queue-count').textContent = rows.length;
    $('#case-list').innerHTML = rows.map(item => `<button class="case-row ${!state.demo && item.id === state.selected ? 'selected' : ''}" data-case="${esc(item.id)}"><strong>${esc(item.customer_name)}</strong><p>${esc(item.summary || 'Open case to view the details.')}</p><small><span>${esc(item.id)}</span><span>${esc(item.status.replaceAll('_',' '))}</span></small></button>`).join('') || '<div class="empty">No cases in this view.</div>';
  }
  function messagesMarkup(messages) {
    return `<div class="thread">${messages.map(message => `<div class="message ${message.role === 'user' ? '' : 'outgoing'}"><small>${message.role === 'user' ? 'Customer' : 'Support / AI'}</small><div class="bubble">${esc(message.content)}</div></div>`).join('') || '<p class="subtle">No case-specific messages are recorded. Older session-wide history is withheld to preserve workspace privacy.</p>'}</div>`;
  }
  function header(name, id, status) {
    return `<div class="case-header"><div><h2>${esc(name)}</h2><p>${esc(id)}</p></div><span class="status ${status === 'resolved' ? 'done' : 'wait'}">${esc(status.replaceAll('_',' '))}</span></div>`;
  }
  function renderDetail(item) {
    state.detail = item;
    const active = item.status === (role === 'agent' ? 'escalated' : 'awaiting_approval');
    const audit = `<details><summary>Case activity</summary>${item.audit.map(event => `<div class="audit-entry"><strong>${esc(event.tool)}</strong> · ${esc(event.decision)}<br>${esc(event.reason || event.policy_ref || '')}</div>`).join('') || '<p>No recorded tool activity.</p>'}</details>`;
    if (role === 'agent') {
      $('#case-content').innerHTML = header(item.customer_name, item.id, item.status) + `<div class="case-inner"><p class="summary">${esc(item.summary || 'This conversation needs human support.')}</p>${messagesMarkup(item.messages)}${active ? `<label class="composer-label" for="case-note">Reply to the customer</label><textarea id="case-note" placeholder="Write your reply…"></textarea><div class="case-actions"><button class="button primary" data-live-action="message">Send reply</button>${item.review_requested ? '<button class="button" data-live-action="return-review">Return information to approver</button>' : '<button class="button" data-live-action="resolve">Send and resolve</button>'}</div>` : '<p class="notice">This support case is complete.</p>'}${audit}</div>`;
      return;
    }
    const approval = item.pending_approval;
    let args = {};
    if (approval) { try { args = JSON.parse(approval.args_json); } catch { /* The raw record remains on the server. */ } }
    const action = approval?.tool === 'trigger_reversal' ? `Reverse ${currency(args.amount)} failed payment` : approval?.tool === 'update_contact' ? 'Approve registered contact change' : approval?.tool || 'Decision recorded';
    $('#case-content').innerHTML = header(item.customer_name, item.id, item.status) + `<div class="case-inner"><p class="summary">${esc(item.summary || 'Review this exception before a sensitive action proceeds.')}</p><dl class="facts"><div class="fact"><dt>Requested action</dt><dd>${esc(action)}</dd></div>${args.txn_id ? `<div class="fact"><dt>Transaction</dt><dd>${esc(args.txn_id)}</dd></div>` : ''}<div class="fact"><dt>Payment action</dt><dd>${active ? 'Held pending your decision' : esc(item.status)}</dd></div></dl>${approval ? `<div class="policy"><strong>Policy reference</strong>${esc(approval.policy_ref || 'No policy citation attached; inspect the case before deciding.')}</div>` : ''}<details><summary>Customer conversation for this case</summary>${messagesMarkup(item.messages)}</details>${audit}${active && approval ? '<label class="composer-label" for="case-note">Decision note</label><textarea id="case-note" placeholder="Required for rejection or an information request…"></textarea><div class="case-actions"><button class="button" data-live-action="request-info">Request information</button><button class="button danger" data-live-action="reject">Reject</button><button class="button primary" data-live-action="approve">Approve action</button></div>' : '<p class="notice">The decision has been recorded.</p>'}</div>`;
  }
  async function openCase(id) {
    state.demo = null;
    state.selected = id;
    renderQueue();
    $('#case-content').innerHTML = '<div class="empty">Loading case…</div>';
    try {
      const item = await api('/cases/' + encodeURIComponent(id));
      if (state.selected === id && !state.demo) renderDetail(item);
    } catch (failure) {
      $('#case-content').innerHTML = '<div class="empty">This case is unavailable in your workspace. Refresh your queue.</div>';
      error(failure);
    }
  }
  async function refresh(silent = false) {
    if (state.refreshing || state.busy) return;
    state.refreshing = true;
    try {
      const rows = await api('/cases');
      const old = state.cases.find(item => item.id === state.selected);
      state.cases = rows;
      renderQueue();
      $('#workspace-error').textContent = '';
      if (state.demo) return;
      const visible = filteredCases();
      const chosen = visible.find(item => item.id === state.selected) || visible[0];
      if (!chosen) {
        state.selected = null; state.detail = null;
        $('#case-content').innerHTML = '<div class="empty"><h2>You’re all caught up.</h2><p>New work permitted for your role will appear here.</p></div>';
      } else if (!silent || chosen.id !== state.selected || old?.status !== chosen.status || old?.summary !== chosen.summary) {
        await openCase(chosen.id);
      }
      $('#workspace-error').textContent = '';
    } catch (failure) { error(failure); }
    finally { state.refreshing = false; }
  }
  async function performAction(action) {
    if (state.busy || state.demo || !state.selected) return;
    const note = $('#case-note')?.value.trim() || '';
    if (action !== 'approve' && !note) { error(new Error('Enter a message or note before continuing.')); $('#case-note')?.focus(); return; }
    state.busy = true;
    document.querySelectorAll('[data-live-action]').forEach(button => button.disabled = true);
    try {
      const result = await api('/cases/' + encodeURIComponent(state.selected) + '/' + action, {
        method:'POST', body:JSON.stringify(action === 'message' ? {message:note} : {note})
      });
      if (result.result && result.result.status !== 'ok') throw new Error(result.result.reason || 'The gateway blocked this action.');
      notice(action === 'message' ? 'Reply sent to the customer.' : action === 'request-info' ? 'Handed to human support. It has left your review queue.' : action === 'return-review' ? 'Information returned to the approver. It has left your support queue.' : 'Action recorded.');
      if ($('#case-note')) $('#case-note').value = '';
      state.busy = false;
      await refresh();
    } catch (failure) { error(failure); }
    finally { state.busy = false; document.querySelectorAll('[data-live-action]').forEach(button => button.disabled = false); }
  }

  // Judge fixtures are deliberately separate from live records and never call api().
  function scenarioMarkup(scenario) {
    const owns = ownsDemo(scenario);
    const facts = `<dl class="facts"><div class="fact"><dt>Expected route</dt><dd>${esc(routeLabel(scenario.route))}</dd></div><div class="fact"><dt>Expected behavior</dt><dd>${esc(scenario.expected)}</dd></div>${scenario.amount != null ? `<div class="fact"><dt>Amount</dt><dd>${currency(scenario.amount)}</dd></div>` : ''}</dl><div class="policy"><strong>Integration scope${scenario.gap ? ' · missing provider integration' : ''}</strong>${esc(scenario.capability)}</div>`;
    let controls = '';
    if (owns && role === 'agent') controls = '<label class="composer-label" for="demo-note">Simulated support reply</label><textarea id="demo-note" placeholder="No real customer will receive this reply…"></textarea><div class="case-actions"><button class="button primary" data-demo-action="reply">Simulate reply</button></div>';
    if (owns && role === 'approver') controls = `<label class="composer-label" for="demo-note">Simulated decision note</label><textarea id="demo-note" placeholder="Required for rejection or information request…"></textarea><div class="case-actions"><button class="button" data-demo-action="info">Simulate information request</button><button class="button danger" data-demo-action="reject">Simulate rejection</button><button class="button primary" data-demo-action="approve">${scenario.action === 'contact' ? 'Simulate contact approval' : 'Simulate approval of ' + currency(scenario.amount)}</button></div>`;
    return header(scenario.customer, 'DEMO-' + scenario.id + ' · ' + scenario.title, 'scripted example') + `<div class="case-inner"><div class="demo-banner">SCRIPTED DEMO · No live payment or customer action.<br>${owns ? 'The interactive controls below belong to your signed-in role.' : 'Read-only observation. This scenario is handled by ' + esc(routeLabel(scenario.route)) + '; your workspace cannot perform those actions.'}</div>${messagesMarkup([{role:'user',content:scenario.query},{role:'assistant',content:scenario.aiReply}])}${facts}${controls}<div id="demo-result" role="status"></div><div class="case-actions"><button class="button" id="back-live">Return to live queue</button></div></div>`;
  }
  function loadDemo(id) {
    const scenario = window.DEMO_SCENARIOS.find(item => item.id === id);
    if (!scenario) return;
    state.demo = scenario;
    state.detail = null;
    $('#case-content').innerHTML = scenarioMarkup(scenario);
    renderQueue();
    if ($('#catalog').open) $('#catalog').close();
  }
  function runChecks() {
    const ids = new Set();
    const results = window.DEMO_SCENARIOS.map(scenario => {
      const view = document.createElement('div'); view.innerHTML = scenarioMarkup(scenario);
      const actions = [...view.querySelectorAll('[data-demo-action]')].map(button => button.dataset.demoAction);
      const passed = !ids.has(scenario.id) && Boolean(scenario.query && scenario.expected && scenario.capability) &&
        ['ai','human','review'].includes(scenario.route) &&
        (ownsDemo(scenario) ? actions.length > 0 : actions.length === 0) &&
        (role !== 'agent' || !actions.includes('approve')) && (role !== 'approver' || !actions.includes('reply'));
      ids.add(scenario.id);
      return {id:scenario.id, passed};
    });
    $('#check-summary').textContent = `${results.filter(item => item.passed).length}/${results.length} scripted UI checks passed for this role. This does not test the live rule engine or Paytm.`;
    return results;
  }
  function renderCatalogue() {
    const category = $('#category-filter').value;
    $('#scenario-list').innerHTML = window.DEMO_SCENARIOS.filter(item => !category || item.category === category).map(item => `<article class="scenario"><div class="scenario-top"><div><h3>${esc(item.id)} · ${esc(item.title)}</h3><small>${esc(item.category)} · ${esc(routeLabel(item.route))}${ownsDemo(item) ? ' · your role' : ' · read-only'}</small></div><button class="button" data-demo-id="${esc(item.id)}">${ownsDemo(item) ? 'Try this scenario' : 'View expected outcome'}</button></div><p>${esc(item.query)}</p><details><summary>Expected behavior and compatibility</summary><p>${esc(item.expected)}</p><p class="${item.gap ? 'gap' : ''}">${esc(item.capability)}</p></details></article>`).join('');
  }
  document.addEventListener('click', event => {
    const row = event.target.closest('[data-case]');
    if (row && !state.busy) openCase(row.dataset.case);
    const scenario = event.target.closest('[data-demo-id]');
    if (scenario) loadDemo(scenario.dataset.demoId);
    const action = event.target.closest('[data-live-action]');
    if (action) performAction(action.dataset.liveAction);
    const demoAction = event.target.closest('[data-demo-action]');
    if (demoAction && state.demo && ownsDemo(state.demo)) {
      const note = $('#demo-note')?.value.trim();
      const kind = demoAction.dataset.demoAction;
      if (kind !== 'approve' && !note) { error(new Error('Enter a note or reply for this simulation.')); return; }
      $('#demo-result').className = 'decision-result';
      $('#demo-result').textContent = kind === 'reply' ? 'Simulated reply recorded. No real customer was contacted.' : kind === 'info' ? 'Simulated handoff to human support. Your approver account cannot open their private workspace.' : 'Simulated ' + (kind === 'approve' ? 'approval' : 'rejection') + ' recorded. No database or payment changed.';
      document.querySelectorAll('[data-demo-action]').forEach(button => button.disabled = true);
      $('#workspace-error').textContent = '';
    }
    if (event.target.closest('#back-live')) { state.demo = null; refresh(); }
  });
  $('#signout').onclick = async () => {
    try { await api(base + '/logout', {method:'POST'}); $('#workspace').replaceChildren(); window.location.assign('/login/' + role); }
    catch (failure) { error(failure); }
  };
  $('#refresh').onclick = () => refresh();
  $('#search').oninput = renderQueue;
  $('#queue-filter').onchange = () => { state.demo = null; refresh(); };
  $('#demo-cases').onclick = () => { renderCatalogue(); $('#catalog').showModal(); };
  $('#catalog-close').onclick = () => $('#catalog').close();
  $('#category-filter').onchange = renderCatalogue;
  $('#check-scenarios').onclick = runChecks;
  window.WorkspaceDemo = {load:loadDemo, runChecks};
  async function start() {
    try {
      const identity = await api(base + '/session');
      $('#account-name').textContent = identity.username || identity.reviewer;
      $('#workspace-title').textContent = role === 'agent' ? 'Only conversations that need you.' : 'One request. An informed decision.';
      $('#workspace-description').textContent = role === 'agent' ? 'AI handles routine chats. Your queue contains human escalations.' : 'Review exceptions and authorize sensitive actions.';
      $('#queue-title').textContent = role === 'agent' ? 'Escalated to support' : 'Awaiting a decision';
      await refresh();
      if (new URLSearchParams(location.search).has('demo')) $('#demo-cases').click();
    } catch (failure) { error(failure); }
  }
  start();
  setInterval(() => { if (!document.hidden && !$('#case-note')?.value.trim()) refresh(true); }, 15000);
})();
