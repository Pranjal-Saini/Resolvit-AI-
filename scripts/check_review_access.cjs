/* Login and session isolation check; does not mutate payment/case data. */
const assert=require('node:assert/strict');
const {browserSession,until,base}=require('./ui_test_helpers.cjs');
const {JSDOM,VirtualConsole}=require('jsdom');
const fs=require('fs');
(async()=>{
 const session=browserSession();
 assert.equal((await session.request('/cases')).status,401);
 assert.equal((await session.request('/review/queue')).status,401);
 const wrong=await session.request('/agent/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'ui-approver',password:'ui-test-password'})});
 assert.equal(wrong.status,401);
 const agent=await session.login('agent');assert(agent.headers.get('set-cookie').includes('HttpOnly'));
 assert.equal((await session.request('/review/queue')).status,403);
 const review=await session.login('approver');assert(review.headers.get('set-cookie').includes('SameSite=strict'));
 assert.equal((await session.request('/cases')).status,400); // Both sessions need an explicit role.
 assert.equal((await session.request('/agent/session',{headers:{'X-Workspace-Role':'agent'}})).status,200);
 assert.equal((await session.request('/review/session',{headers:{'X-Workspace-Role':'approver'}})).status,200);
 await session.request('/review/logout',{method:'POST'});
 assert.equal((await session.request('/agent/session')).status,200);
 assert.equal((await session.request('/review/session')).status,403);
 await session.request('/agent/logout',{method:'POST'});
 assert.equal((await session.request('/cases')).status,401);
 for(const role of ['agent','approver']){
  const page=browserSession(),html=await(await page.request('/login/'+role)).text(),errors=[],vc=new VirtualConsole();
  vc.on('jsdomError',error=>errors.push(error.message));
  const dom=new JSDOM(html,{runScripts:'outside-only',url:base+'/login/'+role,virtualConsole:vc});
  try{
   const w=dom.window,d=w.document;w.AbortSignal=globalThis.AbortSignal;w.fetch=page.request;
   w.eval(fs.readFileSync('ui/login.js','utf8'));
   d.querySelector('#username').value='incorrect-account';d.querySelector('#password').value='incorrect-password';
   d.querySelector('#login-form').dispatchEvent(new w.Event('submit',{cancelable:true}));
   await until(()=>d.querySelector('#login-error').textContent.includes('Incorrect'),'login form rejection');
   assert.equal(d.querySelector('#password').value,'');assert.equal(d.querySelector('#login-submit').disabled,false);
   assert.equal(d.body.dataset.role,role);assert.deepEqual(errors,[]);
  }finally{dom.window.close();}
 }
 console.log('PASS: both login forms, password clearing, anonymous gate, wrong-role credentials, separate HttpOnly sessions and independent logout.');
})().catch(error=>{console.error(error);process.exitCode=1;});
