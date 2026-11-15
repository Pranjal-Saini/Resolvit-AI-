'use strict';
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels = {open:'Open',need_info:'Needs information',resolved:'Resolved',awaiting_approval:'Awaiting approval',escalated:'Escalated',rejected:'Rejected',needs_approval:'Needs approval',executed:'Executed',replayed:'Replayed',blocked:'Blocked',error:'Error',ok:'Completed'};
const badge = status => `<span class="badge ${esc(status)}">${esc(labels[status] || status)}</span>`;
const currency = amount => new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0}).format(amount);
const time = value => { if (!value) return '—'; const d = new Date(value); return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('en-IN',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}); };
const empty = (title,description) => `<div class="empty"><span class="empty-symbol">◇</span><strong>${esc(title)}</strong>${esc(description)}</div>`;
let customers = [], cases = [], audits = [], tools = [], conversations = new Map(), currentCustomer = '', sending = false, refreshing = false;
let activeCase = null, reviewerToken = '', reviewerName = ''; 
function conversation() {
  if (!conversations.has(currentCustomer)) conversations.set(currentCustomer,{id:crypto.randomUUID(),messages:[]});
  return conversations.get(currentCustomer);
}
function showError(error) { $('#alert').textContent = error.message || String(error); $('#alert').hidden = false; }
function clearError() { $('#alert').hidden = true; }
async function api(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.method ? 240000 : 15000);
  try {
    const response = await fetch(path,{...options,headers:{'Content-Type':'application/json',...(reviewerToken?{Authorization:'Bearer '+reviewerToken}:{}),...options.headers},signal:controller.signal});
    let body;
    try { body = await response.json(); } catch { throw new Error('The server returned an unreadable response. Refresh and try again.'); }
    if (!response.ok) {
      const detail = typeof body.detail === 'string' ? body.detail : `Request failed (${response.status}).`;
      const error=new Error(detail === 'need_otp' ? 'Customer verification failed. Select a demo customer and start a new conversation.' : detail);
      error.status=response.status;throw error;
    }
    return body;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('The request timed out. Check the case and audit trail before resending; the action may already have completed.');
    if (error instanceof TypeError) throw new Error('Cannot reach the backend. Check the connection, then refresh.');
    throw error;
  } finally { clearTimeout(timer); }
}
function navigate(page) {
  if (!['overview','chat','cases','audit','tools'].includes(page)) page = 'overview';
  document.querySelectorAll('.page').forEach(el => el.classList.toggle('active',el.id === `page-${page}`));
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active',el.dataset.page === page));
  $('#breadcrumb').textContent = {overview:'Overview',chat:'Customer support',cases:'Cases & approvals',audit:'Audit trail',tools:'Tool registry'}[page];
  history.replaceState(null,'',`#${page}`);
  if (page === 'chat') renderMessages();
}
function customerName(id) { return customers.find(c => c.id === id)?.name || id; }
function initials(name) { return name.split(' ').map(x=>x[0]).slice(0,2).join(''); }
function renderMetrics(metrics) {
  const cards = [ ['◫',metrics.total,'Total cases','ALL TIME'], ['✓',`${Math.round(metrics.auto_resolution_rate * 100)}%`,'Automatic resolution','RESOLVED / TOTAL'], ['◷',metrics.awaiting_approval,'Awaiting approval','HUMAN REVIEW'], ['↗',metrics.escalated,'Escalated cases','SPECIALIST SUPPORT'] ];
  $('#metrics').innerHTML = cards.map(([icon,value,label,note])=>`<article class="metric"><div class="metric-top"><span class="metric-icon">${icon}</span><span class="metric-note">${note}</span></div><strong>${esc(value)}</strong><p>${label}</p></article>`).join('');
  $('#queue-count').textContent = metrics.awaiting_approval;
  $('#review-total').textContent = metrics.awaiting_approval;
  const groups = [ ['Resolved',metrics.resolved,'#3459bc'],['Awaiting review',metrics.awaiting_approval,'#f1b24a'],['Escalated',metrics.escalated,'#e17b87'],['Other active / closed',Math.max(0,metrics.total-metrics.resolved-metrics.awaiting_approval-metrics.escalated),'#bdcce8'] ];
  let cursor = 0;
  const stops = groups.map(([,n,color])=>{const start=cursor;cursor+= metrics.total ? n/metrics.total*100 : 0; return `${color} ${start}% ${cursor}%`;});
  $('#donut').style.background = metrics.total ? `conic-gradient(${stops.join(',')})` : '#e8edf7';
  $('#donut-total').textContent = metrics.total;
  $('#chart-legend').innerHTML = groups.map(([label,n,color])=>`<div class="legend-row"><i style="background:${color}"></i><span>${label}</span><b>${n}</b></div>`).join('');
}
function renderCases() {
  const recent = cases.slice(0,5);
  $('#recent-cases').innerHTML = recent.length ? recent.map(c=>`<tr><td><strong>${esc(c.id)}</strong><small>${esc(customerName(c.customer_id))}</small></td><td>${esc(c.summary || 'Customer support conversation')}</td><td>${badge(c.status)}</td><td>${time(c.created_at)}</td><td><button class="text-button" data-case="${esc(c.id)}">Open →</button></td></tr>`).join('') : `<tr><td colspan="5">${empty('No cases yet','Start a customer conversation to see its resolution here.')}</td></tr>`;
  const pending = cases.filter(c=>c.status==='awaiting_approval');
  $('#review-preview').innerHTML = pending.length ? pending.slice(0,3).map(c=>`<article class="card queue-card"><div class="queue-card-top"><span class="initials">${esc(initials(customerName(c.customer_id)))}</span><div><strong>${esc(customerName(c.customer_id))}</strong><small>${esc(c.id)}</small></div></div><p>${esc(c.summary || 'An action is waiting for a support reviewer.')}</p><button class="text-button" data-case="${esc(c.id)}">Review request →</button></article>`).join('') : `<article class="card">${empty('You’re all caught up','Requests needing your approval will appear here.')}</article>`;
  const filter = $('#case-filter').value;
  const filtered = cases.filter(c=>!filter || c.status===filter);
  $('#case-list').innerHTML = filtered.length ? filtered.map(c=>`<article class="card case-tile"><div class="tile-top"><strong>${esc(c.id)}</strong>${badge(c.status)}</div><h3>${esc(customerName(c.customer_id))}</h3><p>${esc(c.summary || 'Open the case to view its conversation, actions and audit trail.')}</p><small>${time(c.created_at)}</small><div style="margin-top:15px"><button class="button secondary" data-case="${esc(c.id)}">${c.status==='awaiting_approval'?'Review request':'View case'} →</button></div></article>`).join('') : empty('No matching cases','Cases will appear here as customers ask for help.');
  const selection = $('#audit-filter').value;
  $('#audit-filter').innerHTML = '<option value="">All cases</option>'+cases.map(c=>`<option value="${esc(c.id)}">${esc(c.id)} · ${esc(customerName(c.customer_id))}</option>`).join('');
  if (cases.some(c=>c.id===selection)) $('#audit-filter').value = selection;
}
function renderAudits() {
  $('#activity').innerHTML = audits.length ? audits.slice(0,5).map(a=>`<div class="activity-row"><span class="activity-dot"></span><div><strong>${esc(a.tool.replaceAll('_',' '))}</strong><p>${esc(a.case_id)} · ${esc(labels[a.decision] || a.decision)}</p><small>${time(a.ts)}</small></div></div>`).join('') : empty('Nothing to trace yet','Every tool decision will be recorded here.');
  const filter = $('#audit-filter').value;
  const rows = audits.filter(a=>!filter || a.case_id===filter);
  $('#audit-table').innerHTML = rows.length ? rows.map(a=>`<tr><td>${time(a.ts)}<small>${esc(a.case_id)}</small></td><td>${esc(a.tool)}<small>${esc(a.tier)}</small></td><td>${badge(a.decision)}</td><td>${esc(a.actor)}</td><td>${esc(a.policy_ref || a.reason || '—')}</td></tr>`).join('') : `<tr><td colspan="5">${empty('No audit entries','Tool decisions will appear after a conversation.')}</td></tr>`;
}
function renderTools() {
  $('#tool-list').innerHTML = tools.map(t=>`<article class="card tool-tile"><code>${esc(t.name)}</code>${badge(t.tier)}<p>${esc(t.description)}</p><div class="params">${Object.entries(t.args || {}).map(([key,value])=>`${esc(key)} <span>· ${esc(value.type)}${value.required?' · required':''}</span>`).join('<br>') || 'No arguments required'}${t.cap_inr?`<br>Auto-reversal limit: ${currency(t.cap_inr)}`:''}</div></article>`).join('');
}
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  document.querySelectorAll('.reload').forEach(b=>b.disabled=true);
  try {
    const [metrics,allCases,allAudit,registry,allCustomers] = await Promise.all([api('/metrics'),api('/cases'),api('/audit'),api('/tools'),api('/customers')]);
    cases=allCases;audits=allAudit;tools=registry.tools;customers=allCustomers;
    if(!customers.some(c=>c.id===currentCustomer))currentCustomer=customers[0]?.id || '';
    $('#customer').innerHTML=customers.map(c=>`<option value="${esc(c.id)}">${esc(c.name)} · ${esc(c.id)}</option>`).join('');
    $('#customer').value=currentCustomer;
    if(!customers.length)showError(new Error('No customers found. Seed the demo database before starting a conversation.'));
    if(!sending)renderMessages();
    renderMetrics(metrics);renderCases();renderAudits();renderTools();
    $('#connection').textContent='Backend connected';$('#connection').classList.remove('offline');
  } catch (error) { $('#connection').textContent='Backend unavailable';$('#connection').classList.add('offline');showError(error); }
  finally { refreshing=false;document.querySelectorAll('.reload').forEach(b=>b.disabled=false); }
}
function renderMessages() {
  if (!currentCustomer) return;
  const messages = conversation().messages;
  $('#messages').innerHTML = messages.length ? messages.map(m=>{
    if (m.role==='user') return `<div class="message user"><div class="message-label">${esc(customerName(currentCustomer))}</div><div class="bubble">${esc(m.content)}</div></div>`;
    if (m.role==='review') return `<div class="message review"><div class="message-label">Support review</div><div class="bubble">${esc(m.content)}</div><div class="message-meta">${badge(m.status)}<button class="case-link" data-case="${esc(m.case_id)}">${esc(m.case_id)} ↗</button></div></div>`;
    if (m.role==='error') return `<div class="message-error">${esc(m.content)}</div>`;
    const r=m.response;
    return `<div class="message assistant"><div class="message-label">ResolveAI assistant</div><div class="bubble">${esc(r.reply)}</div><div class="message-meta">${badge(r.status)}<button class="case-link" data-case="${esc(r.case_id)}">${esc(r.case_id)} ↗</button></div><details><summary>Actions & policy citations</summary>${r.actions.map(a=>`<div class="tool-result"><strong>${esc(a.tool)}</strong> ${badge(a.status)}<div>${esc(a.summary)}</div></div>`).join('') || '<p>No tool actions were taken.</p>'}${r.citations.map(c=>`<div class="tool-result"><div class="policy-source">${esc(c.source)}#${esc(c.section)}</div><p>${esc(c.rule_text)}</p><small>Match: ${Math.round(c.score*100)}%${c.low_confidence?' · Low confidence':''}</small></div>`).join('') || '<p>No policy citations returned.</p>'}</details></div>`;
  }).join('') : `<div class="welcome"><span class="welcome-symbol">✦</span><h2>Hi, ${esc(customerName(currentCustomer).split(' ')[0])}. How can we help?</h2><p>Payment stuck? Bill not updated? Tell us what happened, and we’ll find the next safe step.</p></div>`;
  if (sending) $('#messages').insertAdjacentHTML('beforeend','<div class="thinking" role="status">Checking your payment and the relevant policy…</div>');
  $('#messages').scrollTop=$('#messages').scrollHeight;
}
function setBusy(busy) {
  sending=busy;$('#send').disabled=busy;$('#send').textContent=busy?'Working…':'Send message ↗';
  $('#customer').disabled=busy;$('#new-conversation').disabled=busy;
  document.querySelectorAll('.scenario').forEach(b=>b.disabled=busy);
}
async function sendMessage(event) {
  event.preventDefault();
  const message=$('#message').value.trim();if(!message || sending || !currentCustomer)return;
  clearError();const conv=conversation();conv.messages.push({role:'user',content:message});$('#message').value='';setBusy(true);renderMessages();
  try {
    const response=await api('/chat',{method:'POST',body:JSON.stringify({session_id:conv.id,customer_id:currentCustomer,token:`demo-${currentCustomer}`,message})});
    conv.messages.push({role:'assistant',response});
  } catch(error) { conv.messages.push({role:'error',content:error.message}); }
  finally { setBusy(false);renderMessages();await refresh(); }
}
async function openCase(id) {
  clearError();
  try {
    const c=await api(`/cases/${encodeURIComponent(id)}`);activeCase=c;
    const approval=c.pending_approval;
    let args={};if(approval){try{args=JSON.parse(approval.args_json);}catch{args={};}}
    $('#case-detail').innerHTML=`<div class="detail-header"><h2>${esc(c.id)}</h2>${badge(c.status)}</div><p class="subtle">${esc(customerName(c.customer_id))} · ${time(c.created_at)}</p><p class="detail-summary" style="margin-top:15px">${esc(c.summary || '')}</p>${approval?`<div class="detail-section"><h3>Pending approval</h3><div class="approval-box"><strong>${esc(approval.tool)}</strong><p>${args.amount?currency(args.amount)+' · ':''}${esc(args.txn_id || '')}</p><p>Policy: ${esc(approval.policy_ref || 'No citation supplied')}</p><p>Arguments: ${esc(JSON.stringify(args))}</p><label for="reviewer">Reviewer name</label><div class="approval-controls"><input id="reviewer" placeholder="Your name" autocomplete="name" value="${esc(reviewerName)}" required><input id="reviewer-key" type="password" placeholder="Reviewer access key" autocomplete="current-password" aria-label="Reviewer access key">${approval.tool==='update_contact'?'<input id="step-up-code" type="password" placeholder="Demo verification code" aria-label="Demo step-up verification code">':''}<button class="button primary" id="approve-action">Approve action</button></div><div style="margin-top:15px"><label for="reject-note">Reason for rejection</label><div class="approval-controls"><input id="reject-note" placeholder="Explain why this should not proceed"><button class="button danger" id="reject-action">Reject request</button></div></div><div id="review-feedback" role="status"></div></div></div>`:''}<div class="detail-section"><h3>Conversation</h3>${c.messages.map(m=>`<div class="detail-message"><strong>${m.role==='assistant'?'ResolveAI':'Customer'}</strong><br>${esc(m.content)}</div>`).join('')||'<p class="subtle">No messages recorded.</p>'}</div><div class="detail-section"><h3>Audit trail</h3>${c.audit.map(a=>`<div class="tool-result"><strong>${esc(a.tool)}</strong> ${badge(a.decision)}<p class="subtle">${esc(a.reason || a.policy_ref || 'Action recorded')} · ${time(a.ts)}</p></div>`).join('')||'<p class="subtle">No actions recorded.</p>'}</div>`;
    if(!$('#case-dialog').open)$('#case-dialog').showModal();
    if(approval){$('#approve-action').onclick=()=>reviewCase('approve');$('#reject-action').onclick=()=>reviewCase('reject');}
  }catch(error){showError(error);}
}
async function reviewCase(action) {
  const reviewer=$('#reviewer').value.trim(),note=$('#reject-note').value.trim();
  const feedback=$('#review-feedback');
  if(!reviewer || (action==='reject'&&!note)){feedback.textContent='Enter your name'+(action==='reject'?' and a rejection reason.':'.');return;}
  $('#approve-action').disabled=true;$('#reject-action').disabled=true;feedback.textContent='Saving the review…';
  try {
    if(!reviewerToken || reviewerName!==reviewer){
      const key=$('#reviewer-key').value;
      if(!key)throw new Error('Enter your reviewer access key to sign in.');
      const login=await api('/reviewer/login',{method:'POST',body:JSON.stringify({reviewer,access_key:key})});
      reviewerToken=login.access_token;reviewerName=login.reviewer;
      $('#reviewer-key').value='';
    }
    if(action==='approve' && activeCase.pending_approval.tool==='update_contact'){
      const code=$('#step-up-code').value;
      if(!code)throw new Error('Enter the demo step-up verification code before approving a contact change.');
      await api(`/cases/${encodeURIComponent(activeCase.id)}/verify`,{method:'POST',body:JSON.stringify({reviewer,code})});
    }
    const result=await api(`/cases/${encodeURIComponent(activeCase.id)}/${action}`,{method:'POST',body:JSON.stringify({reviewer,...(action==='reject'?{note}:{})})});
    if(result.result && result.result.status!=='ok')throw new Error(result.result.reason || 'The gateway did not complete this action.');
    await refresh();await openCase(activeCase.id);
    const conv=conversations.get(activeCase.customer_id);
    const last=activeCase.messages.at(-1);
    if(conv && last?.role==='assistant'){
      conv.messages.push({role:'review',content:last.content,status:activeCase.status,case_id:activeCase.id});
      renderMessages();
    }
  }catch(error){if(error.status===401)reviewerToken='';feedback.textContent=error.message;$('#approve-action').disabled=false;$('#reject-action').disabled=false;await refresh();}
}
document.addEventListener('click',event=>{
  const page=event.target.closest('[data-page]');if(page)navigate(page.dataset.page);
  const caseButton=event.target.closest('[data-case]');if(caseButton)openCase(caseButton.dataset.case);
  const scenario=event.target.closest('.scenario');if(scenario&&!sending){
    currentCustomer=scenario.dataset.customer;$('#customer').value=currentCustomer;
    conversations.set(currentCustomer,{id:crypto.randomUUID(),messages:[]});renderMessages();
    $('#message').value=scenario.dataset.message;$('#message').focus();
  }
});
$('#chat-form').addEventListener('submit',sendMessage);
$('#message').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();$('#chat-form').requestSubmit();}});
$('#customer').addEventListener('change',()=>{currentCustomer=$('#customer').value;$('#message').value='';renderMessages();});
$('#new-conversation').addEventListener('click',()=>{if(!currentCustomer)return;conversations.set(currentCustomer,{id:crypto.randomUUID(),messages:[]});$('#message').value='';renderMessages();});
$('#case-filter').addEventListener('change',renderCases);
$('#audit-filter').addEventListener('change',renderAudits);
$('#close-dialog').addEventListener('click',()=>$('#case-dialog').close());
document.querySelectorAll('.reload').forEach(b=>b.addEventListener('click',()=>{clearError();refresh();}));
async function init(){
  navigate(location.hash.slice(1)||'overview');
  await refresh();
}
init();
