const {JSDOM, VirtualConsole} = require('jsdom');
const fs = require('fs');
const assert = require('node:assert/strict');
const base = process.env.UI_TEST_BASE || 'http://127.0.0.1:8011';

function browserSession() {
  const cookies = new Map();
  async function request(path, options = {}) {
    const response = await fetch(new URL(path, base), {...options, headers:{...options.headers,
      Cookie:[...cookies].map(([key,value]) => key+'='+value).join('; ')}});
    const values = response.headers.getSetCookie ? response.headers.getSetCookie() : [response.headers.get('set-cookie')].filter(Boolean);
    for (const value of values) {
      const pair = value.split(';')[0], position = pair.indexOf('=');
      const name = pair.slice(0,position), content = pair.slice(position+1);
      if (content) cookies.set(name,content); else cookies.delete(name);
    }
    return response;
  }
  async function login(role) {
    const agent = role === 'agent';
    const response = await request((agent ? '/agent' : '/review')+'/login', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify({
        username:agent ? 'ui-support' : 'ui-approver', password:agent ? 'ui-support-password' : 'ui-test-password'})});
    assert.equal(response.status,200,await response.clone().text());
    return response;
  }
  return {request, login, cookies};
}
async function until(predicate, label) {
  for (let i=0;i<240;i++) {
    if (predicate()) return;
    await new Promise(resolve => setTimeout(resolve,25));
  }
  throw Error('Timeout: '+label);
}
async function workspace(session, role) {
  const response = await session.request(role === 'agent' ? '/agent' : '/review');
  const html = await response.text();
  assert(html.includes('id="workspace"'),'Expected authenticated workspace');
  const errors = [], vc = new VirtualConsole();
  vc.on('jsdomError', error => errors.push(error.message));
  const dom = new JSDOM(html,{runScripts:'outside-only',url:base+(role === 'agent' ? '/agent' : '/review'),virtualConsole:vc});
  const w = dom.window;
  w.AbortSignal = globalThis.AbortSignal;
  w.HTMLDialogElement.prototype.showModal = function(){this.open=true;};
  w.HTMLDialogElement.prototype.close = function(){this.open=false;};
  w.setInterval = () => 0; // Tests explicitly refresh; no clock-dependent network traffic.
  let calls = 0;
  w.fetch = (...args) => {calls++;return session.request(...args);};
  w.eval(fs.readFileSync('ui/demo-scenarios.js','utf8'));
  w.eval(fs.readFileSync('ui/role-workspace.js','utf8'));
  try {
    await until(()=>w.document.querySelector('#account-name').textContent.startsWith('ui-'),'session load');
    await until(()=>!w.document.querySelector('#case-content').textContent.includes('Loading'),'queue load');
  } catch (error) { const detail=w.document.querySelector('#workspace-error')?.textContent;dom.window.close();throw Error(error.message+': '+detail); }
  return {dom,w,d:w.document,errors,calls:()=>calls};
}
module.exports = {browserSession, until, workspace, base};
