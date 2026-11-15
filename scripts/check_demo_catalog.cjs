/* Both roles must see the 20 scripted fixtures with only their own interactive controls. */
const fs=require('fs'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
(async()=>{
 const results=[];
 for(const role of ['agent','approver']){
  const html=fs.readFileSync('ui/role-workspace.html','utf8').replaceAll('__ROLE__',role).replaceAll('__LABEL__',role);
  const dom=new JSDOM(html,{runScripts:'outside-only',url:'http://127.0.0.1:8011/'+role});
  const w=dom.window,d=w.document;let calls=0;
  w.setInterval=()=>0;
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
  w.fetch=async path=>{calls++;return {ok:true,status:200,json:async()=>path==='/cases'?[]:{username:role}};};
  w.eval(fs.readFileSync('ui/demo-scenarios.js','utf8'));w.eval(fs.readFileSync('ui/role-workspace.js','utf8'));
  await new Promise(resolve=>setTimeout(resolve,10));
  assert.equal(w.DEMO_SCENARIOS.length,20);
  const before=calls;
  assert(w.WorkspaceDemo.runChecks().every(result=>result.passed));
  for(const scenario of w.DEMO_SCENARIOS){
   w.WorkspaceDemo.load(scenario.id);
   const own=scenario.route===(role==='agent'?'human':'review');
   assert.equal(Boolean(d.querySelector('[data-demo-action]')),own);
   if(role==='agent')assert.equal(d.querySelector('[data-demo-action="approve"]'),null);
   if(role==='approver')assert.equal(d.querySelector('[data-demo-action="reply"]'),null);
   if(scenario.id==='20')assert(d.querySelector('#case-content').textContent.includes('Contact changes are blocked'));
  }
  d.querySelector('#demo-cases').click();assert.equal(d.querySelectorAll('.scenario').length,20);
  d.querySelector('#category-filter').value='Recharges & bills';d.querySelector('#category-filter').dispatchEvent(new w.Event('change'));
  assert.equal(d.querySelectorAll('.scenario').length,6);
  assert.equal(calls,before);
  assert.equal(d.querySelector('#review-tab'),null);assert.equal(d.querySelector('#agent-tab'),null);
  results.push({role,passed:20,providerIntegrationGaps:w.DEMO_SCENARIOS.filter(s=>s.gap).length});dom.window.close();
 }
 console.log(JSON.stringify({results,noLiveScenarioRequests:true},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
