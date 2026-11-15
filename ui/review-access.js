/* Review access is checked by the server. No credentials are embedded here. */
(()=>{
 let reviewer=null;
 const modal=document.createElement('dialog');modal.id='review-login';modal.innerHTML=`<form id="review-login-form" style="min-width:260px"><button type="button" id="review-login-close" aria-label="Close login" style="float:right;border:0;background:none;font-size:22px">×</button><h2 style="font-size:20px;margin:0 0 10px">Review queue sign-in</h2><p style="font-size:12px;color:#7c8ba0;line-height:1.7;margin-bottom:18px">Only authorized approvers can enter the queue and make decisions.</p><label for="review-username" style="display:block;font-size:12px;margin-bottom:6px">Username</label><input id="review-username" autocomplete="username" required style="width:100%;padding:11px;border:1px solid #dfe6f0;border-radius:6px;margin-bottom:14px"><label for="review-password" style="display:block;font-size:12px;margin-bottom:6px">Password</label><input id="review-password" type="password" autocomplete="current-password" required style="width:100%;padding:11px;border:1px solid #dfe6f0;border-radius:6px;margin-bottom:14px"><p id="review-login-error" role="alert" style="color:#bd5365;font-size:12px;margin-bottom:12px"></p><button class="button primary" id="review-login-submit" type="submit" style="width:100%">Sign in to review queue</button></form>`;document.body.appendChild(modal);
 let pending=null;
 async function request(path,body){const r=await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Review access unavailable');return d;}
 function finish(value){modal.close();$('#review-password').value='';if(pending){pending(value);pending=null;}}
 async function ensure(){try{const s=await request('/review/session');reviewer=s.reviewer;update();return reviewer;}catch{reviewer=null;update();}if(pending)return null;$('#review-login-error').textContent='';modal.showModal();return new Promise(resolve=>{pending=resolve;});}
 function update(){const b=document.getElementById('review-signout');if(b)b.hidden=!reviewer;}
 $('#review-login-form').onsubmit=async e=>{e.preventDefault();$('#review-login-submit').disabled=true;try{const result=await request('/review/login',{username:$('#review-username').value.trim(),password:$('#review-password').value});reviewer=result.reviewer;update();finish(reviewer);}catch(error){$('#review-login-error').textContent=error.message;}finally{$('#review-login-submit').disabled=false;}};
 $('#review-login-close').onclick=()=>finish(null);modal.addEventListener('cancel',()=>{if(pending){pending(null);pending=null;}});
 const logout=document.createElement('button');logout.id='review-signout';logout.className='text-button';logout.textContent='Sign out';logout.hidden=true;
 const host=document.querySelector('.profile')||document.querySelector('.header-right')||document.body;host.appendChild(logout);
 logout.onclick=async()=>{try{await request('/review/logout',{});reviewer=null;update();if(typeof setRole==='function')originalRole('agent');if(typeof navigate==='function')navigate('chat');}catch(error){alert('Could not sign out. Please retry.');}};
 let originalRole;
 if(typeof setRole==='function'){
  originalRole=setRole;
  setRole=value=>{if(value==='review'&&!reviewer){ensure().then(name=>{if(name)originalRole(value);});return;}originalRole(value);};
 }
 window.ReviewAccess={ensure,reviewer:()=>reviewer};
 if(new URLSearchParams(location.search).get('review')==='1')ensure().then(name=>{if(name&&originalRole)originalRole('review');});
})();
