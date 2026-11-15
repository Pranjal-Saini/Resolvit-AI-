/* DOM + real HTTP login check. Default target is the isolated UI fixture. */
const {JSDOM,VirtualConsole}=require('jsdom');
const fs=require('fs'),assert=require('node:assert/strict');
const base=process.env.UI_TEST_BASE||'http://127.0.0.1:8011';
(async()=>{
 const html=await(await fetch(base+'/review')).text();
 const consoleErrors=[];const vc=new VirtualConsole();vc.on('jsdomError',e=>consoleErrors.push(e.message));
 const dom=new JSDOM(html,{runScripts:'outside-only',url:base+'/ui/design-preview.html?review=1',virtualConsole:vc});
 const w=dom.window,d=w.document;let cookie='';
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
 w.HTMLDialogElement.prototype.close=function(){this.open=false;};
 w.fetch=async(path,opts={})=>{const r=await fetch(new URL(path,base),{...opts,headers:{...opts.headers,...(cookie?{Cookie:cookie}:{})}});const set=r.headers.get('set-cookie');if(set)cookie=set.split(';')[0];return r;};
 const inline=[...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)].filter(m=>!m[1].includes('src=')).map(m=>m[2]).join('\n');
 w.eval(fs.readFileSync('ui/demo-scenarios.js','utf8')+'\n'+inline+'\n'+fs.readFileSync('ui/demo-panel.js','utf8')+'\n'+fs.readFileSync('ui/review-access.js','utf8'));
 async function until(fn,label){for(let i=0;i<200;i++){if(fn())return;await new Promise(r=>setTimeout(r,25));}throw Error('Timeout: '+label);}
 await until(()=>d.querySelector('#review-login').open,'login gate');
 assert(!d.querySelector('#review-tab').classList.contains('active'));
 assert.equal((await w.fetch('/review/queue')).status,401);
 d.querySelector('#review-username').value=process.env.UI_REVIEW_USER||'ui-approver';
 d.querySelector('#review-password').value='incorrect-test-password';
 d.querySelector('#review-login-form').dispatchEvent(new w.Event('submit',{cancelable:true}));
 await until(()=>d.querySelector('#review-login-error').textContent.includes('Incorrect'),'bad-password rejection');
 d.querySelector('#review-password').value=process.env.UI_REVIEW_PASSWORD||'ui-test-password';
 d.querySelector('#review-login-form').dispatchEvent(new w.Event('submit',{cancelable:true}));
 await until(()=>d.querySelector('#review-tab').classList.contains('active'),'signed-in queue');
 assert.equal((await w.fetch('/review/queue')).status,200);
 assert.equal(d.querySelector('#review-password').value,'');
 d.querySelector('#demo-cases').click();d.querySelector('#check-all-scenarios').click();
 await until(()=>d.querySelector('#demo-check-summary').textContent.startsWith('20/20'),'signed-in judge catalogue');
 d.querySelector('#catalog-close').click();d.querySelector('#review-signout').click();
 await until(()=>d.querySelector('#agent-tab').classList.contains('active'),'logout');
 assert.equal((await w.fetch('/review/queue')).status,401);
 assert.deepEqual(consoleErrors,[]);
 console.log('PASS: direct-link gate, unauthorized API, wrong password, valid login, password clearing, all 20 authenticated judge checks, logout and no JS errors.');
 dom.window.close();
})().catch(e=>{console.error(e);process.exitCode=1;});
