/* Prototype-only catalogue. Expected routes are scripted fixtures, not AI classifications. */
let activeDemo=null;
const demoResults=new Map(),originalCases=JSON.parse(JSON.stringify(cases));
const routeLabel={ai:'AI handles automatically',human:'Human escalation',review:'Approver decision'};
const paymentLabel={failed_debited:'Failed · funds debited',pending:'Pending',success:'Successful',reversed:'Already reversed'};
const originalHumanCases=humanCases,originalAgent=renderAgent,originalReview=renderReview,originalReset=$('#reset').onclick;
humanCases=function(){if(!activeDemo)return originalHumanCases();if(activeDemo.route==='human'&&!returned.priya)return ['priya'];if(decision==='info'&&!returned.rahul)return ['rahul'];return [];};
function demoFacts(){return `<div class="scenario-meta"><details><summary>Demo expectation & integration scope</summary><p><strong>Expected:</strong> ${escape(activeDemo.expected)}</p><p class="${activeDemo.gap?'cap-gap':''}"><strong>${activeDemo.gap?'Integration gap':'Mock scope'}:</strong> ${escape(activeDemo.capability)}</p><p>Scripted UI fixture. This does not test the real agent, policy retrieval or Paytm APIs.</p></details></div>`;}
renderAgent=function(){
 if(!activeDemo){originalAgent();return;}
 if(activeDemo.route==='ai'){
  $('#content').innerHTML=`<div class="case-header"><div><h2>AI-managed conversation · demo observation</h2><small>${escape(activeDemo.customer)} · scenario ${activeDemo.id}</small></div><span class="status done">No human takeover</span></div><div class="scenario-observation"><strong>This case stays out of the human queue.</strong><p>You are viewing a test observation, not an extra customer-support persona.</p></div><div class="thread"><div class="message"><div class="label">Customer · sample query</div><div class="bubble">${escape(activeDemo.query)}</div></div><div class="message outgoing"><div class="label">ResolveAI · scripted automatic response</div><div class="bubble">${escape(activeDemo.aiReply)}</div></div><div class="event">Human queue entries: 0 · No human composer · No approval action</div></div>${demoFacts()}`;
  return;
 }
 originalAgent();
 if(humanCases().includes(selected)){
  const aiBubble=$('#content .message.outgoing .bubble');if(aiBubble)aiBubble.textContent=activeDemo.aiReply;
  const reason=$('#content .action-strip p');if(reason)reason.textContent=decision==='info'?decisionNote:activeDemo.reason;
  $('#content').insertAdjacentHTML('beforeend',demoFacts());
 }
};
renderReview=function(){
 if(!activeDemo){originalReview();return;}
 if(!pending){
  const outcome=decision==='approved'?(activeDemo.action==='contact'?'The mock contact change was approved. AI automatically sends the confirmed outcome.':`The mock ${activeDemo.amount?currencyForDemo(activeDemo.amount):''} reversal was approved. AI automatically sends the confirmed outcome.`):decision==='rejected'?'AI sends the rejection outcome and reason.':decision==='info'?'A human must collect the requested information. The case appears in Escalated chats.':'This scenario does not need an approver.';
  $('#content').innerHTML=`<div class="review-content empty" style="padding-top:100px"><h3>${decision?'Decision recorded.':'No pending approval.'}</h3><p>${escape(outcome)}</p><button class="button back-to-agent" id="go-agent">Open escalated chats →</button></div>${demoFacts()}`;
  return;
 }
 const c=cases.rahul,label=activeDemo.action==='contact'?'Approve contact change':`Approve ${currencyForDemo(activeDemo.amount)} refund`;
 $('#content').innerHTML=header(c)+`<div class="review-content"><div class="review-label">SCRIPTED REVIEW SCENARIO ${activeDemo.id}</div><h3>${escape(activeDemo.title)}</h3><p>${escape(activeDemo.query)}</p><dl class="decision-facts"><div class="fact"><dt>Customer / case</dt><dd>${escape(c.name)} · ${escape(c.id)}</dd></div><div class="fact"><dt>Payment / request</dt><dd>${escape(c.payee)}${activeDemo.amount?' · '+currencyForDemo(activeDemo.amount):''}${activeDemo.txn?' · '+escape(activeDemo.txn):''}</dd></div><div class="fact"><dt>Current state</dt><dd>${escape(c.payment)}</dd></div><div class="fact"><dt>Why review is needed</dt><dd>${escape(activeDemo.reason)}</dd></div></dl><div class="policy"><strong>Demo rule</strong><br>${activeDemo.action==='contact'?'Sensitive contact changes require a human decision. No OTP or access key is requested.':'Eligible reversals must equal the failed debit. Amounts above the demo ₹2,000 cap are held for human approval.'}</div><textarea class="internal-note" id="decision-note" aria-label="Decision note" placeholder="Reason (required for rejection or information request)…"></textarea></div><div class="decision-footer"><small>Preview state only · No live customer or funds</small><div class="decision-buttons"><button class="button" data-decision="info">Request information</button><button class="button danger" data-decision="rejected">Reject</button><button class="button primary" data-decision="approved">${escape(label)}</button></div></div>${demoFacts()}`;
};
function currencyForDemo(value){return new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0}).format(value);}
function loadScenario(id){
 activeDemo=window.DEMO_SCENARIOS.find(s=>s.id===id);if(!activeDemo)throw Error('Unknown demo scenario');
 pending=activeDemo.route==='review';decision=null;decisionNote='';claimed={};sent={};returned={};
 const c={name:activeDemo.customer,id:'DEMO-'+activeDemo.id,issue:activeDemo.title,amount:activeDemo.amount?currencyForDemo(activeDemo.amount):null,payee:activeDemo.payee,payment:activeDemo.frozen?'Wallet frozen · '+(paymentLabel[activeDemo.status]||'contact blocked'):paymentLabel[activeDemo.status]||'No linked payment',time:'1 min',message:activeDemo.query};
 if(activeDemo.route==='human')cases.priya=c;else cases.rahul=c;
 setRole(activeDemo.route==='review'?'review':'agent');
 $('#demo-active').textContent='Scenario '+activeDemo.id+' · '+activeDemo.title;
}
function checkScenario(id){
 loadScenario(id);
 const failures=[];const count=$('#queue .case-row')?document.querySelectorAll('#queue .case-row').length:0;
 if(activeDemo.route==='ai'){
  if(count!==0)failures.push('Routine case leaked into human queue');
  if($('#reply')||$('#takeover')||$('[data-decision="approved"]'))failures.push('Routine case has a human action');
  if(!$('#content').textContent.includes(activeDemo.aiReply))failures.push('AI response not visible');
 }else if(activeDemo.route==='human'){
  if(count!==1||!$('#takeover'))failures.push('Escalation takeover missing');
  if($('#reply'))failures.push('Human can reply before takeover');
  if($('[data-decision="approved"]'))failures.push('Human investigation incorrectly offers approval');
 }else{
  if(count!==1||!$('[data-decision="approved"]'))failures.push('Approver action missing');
  if($('#reply'))failures.push('Approval incorrectly requires human chat');
  if(activeDemo.amount&&!$('#content').textContent.includes(currencyForDemo(activeDemo.amount)))failures.push('Wrong displayed amount');
 }
 if(!$('#content').textContent.includes(activeDemo.query))failures.push('Customer query context missing');
 const result={id,passed:!failures.length,failures,route:activeDemo.route,integrationGap:Boolean(activeDemo.gap),scope:'Scripted UI routing only'};
 demoResults.set(id,result);return result;
}
function renderCatalog(){
 const filter=$('#demo-filter').value;const rows=window.DEMO_SCENARIOS.filter(s=>!filter||s.category===filter);
 $('#demo-scenario-list').innerHTML=rows.map(s=>{const result=demoResults.get(s.id);return `<article class="scenario-row"><div class="scenario-row-top"><div><h3>${s.id} · ${escape(s.title)}</h3><small>${escape(s.category)} · ${escape(s.customerId)}${s.txn?' · '+escape(s.txn):''}</small></div><div class="catalog-buttons"><span class="catalog-route">${routeLabel[s.route]}</span><button class="button" data-check-scenario="${s.id}">Check UI</button><button class="button primary" data-load-scenario="${s.id}">Load case</button></div></div><details><summary>Query, expected behavior & compatibility</summary><p><strong>Customer:</strong> ${escape(s.query)}</p><p><strong>Expected:</strong> ${escape(s.expected)}</p><p><strong>${s.gap?'Backend gap':'Scope'}:</strong> ${escape(s.capability)}</p></details>${result?`<div class="demo-result">${result.passed?'UI check passed':'UI check failed: '+escape(result.failures.join('; '))} · ${s.gap?'Backend integration gap remains':'Mock-only validation'}</div>`:''}</article>`;}).join('');
 const checked=[...demoResults.values()];$('#demo-check-summary').textContent=`${checked.filter(r=>r.passed).length}/${window.DEMO_SCENARIOS.length} UI checks passed · ${window.DEMO_SCENARIOS.filter(s=>s.gap).length} scenarios flag integration gaps · No live Paytm compatibility claimed`;
}
const dialog=document.createElement('dialog');dialog.id='demo-catalog';dialog.innerHTML=`<div class="catalog-heading"><h2>20 live-demo test cases</h2><button id="catalog-close" aria-label="Close scenario catalogue">×</button></div><p class="catalog-note">Choose a customer query to preview the expected route. <strong>AI handles routine issues; humans join only escalations; approvers decide exceptions.</strong> All outcomes here are scripted fixtures. No real agent, backend payment tool or Paytm API is called.</p><div class="catalog-controls"><label for="demo-filter">Category</label><select id="demo-filter"><option value="">All 20 cases</option><option>UPI & transfers</option><option>Recharges & bills</option><option>Wallet & account</option></select><button class="button primary" id="check-all-scenarios">Run 20 UI checks</button></div><div class="catalog-results" id="demo-check-summary"></div><div id="demo-scenario-list"></div>`;document.body.appendChild(dialog);
$('#demo-cases').onclick=()=>{renderCatalog();dialog.showModal();};$('#catalog-close').onclick=()=>dialog.close();$('#demo-filter').onchange=renderCatalog;
$('#check-all-scenarios').onclick=async()=>{if(window.ReviewAccess&&!await window.ReviewAccess.ensure())return;const saved=activeDemo?.id;window.DEMO_SCENARIOS.forEach(s=>checkScenario(s.id));if(saved)loadScenario(saved);renderCatalog();};
dialog.addEventListener('click',async event=>{const load=event.target.closest('[data-load-scenario]');if(load){const item=window.DEMO_SCENARIOS.find(s=>s.id===load.dataset.loadScenario);if(item.route==='review'&&window.ReviewAccess&&!await window.ReviewAccess.ensure())return;loadScenario(load.dataset.loadScenario);dialog.close();}const check=event.target.closest('[data-check-scenario]');if(check){const item=window.DEMO_SCENARIOS.find(s=>s.id===check.dataset.checkScenario);if(item.route==='review'&&window.ReviewAccess&&!await window.ReviewAccess.ensure())return;checkScenario(check.dataset.checkScenario);renderCatalog();}});
$('#reset').onclick=()=>{activeDemo=null;Object.keys(originalCases).forEach(k=>cases[k]=JSON.parse(JSON.stringify(originalCases[k])));$('#demo-active').textContent='';originalReset();};
window.ResolveAIDemo={load:loadScenario,check:checkScenario,results:()=>[...demoResults.values()]};
if(new URLSearchParams(location.search).get('demo')==='1'){renderCatalog();dialog.showModal();}
