/* Ctrl/Cmd+K quick add. Include once in base.html: <script src="/static/ui/js/quickadd.js" defer></script> */
(function(){
  if(window.__qa) return; window.__qa=1;
  const css=`.qa-back{position:fixed;inset:0;background:rgba(0,0,0,.45);display:none;align-items:flex-start;justify-content:center;padding-top:18vh;z-index:200}
.qa-back.on{display:flex}.qa{width:min(560px,92vw);background:var(--panel,#16181b);color:var(--text,#e8e8e8);border:1px solid var(--line,#2a2d31);border-radius:12px;box-shadow:0 20px 60px rgba(0,0,0,.5);overflow:hidden}
.qa input{width:100%;box-sizing:border-box;border:0;outline:0;background:transparent;color:inherit;font:500 16px/1.4 Inter,system-ui,sans-serif;padding:16px 18px}
.qa-foot{display:flex;gap:8px;align-items:center;padding:10px 14px;border-top:1px solid var(--line,#2a2d31);font-size:12px;color:var(--muted,#8a8f98)}
.qa-foot button{background:transparent;border:1px solid var(--line,#2a2d31);color:inherit;border-radius:6px;padding:3px 8px;cursor:pointer;font:inherit}.qa-foot button.on{border-color:var(--accent,#3ddc84);color:var(--accent,#3ddc84)}
.qa-hint{margin-left:auto}.qa-err{padding:0 18px 10px;color:var(--danger,#e5484d);font-size:13px}.qa-err:empty{display:none}.qa kbd{font:inherit;border:1px solid var(--line,#2a2d31);border-radius:4px;padding:0 4px}`;
  const s=document.createElement('style');s.textContent=css;document.head.appendChild(s);
  const b=document.createElement('div');b.className='qa-back';b.innerHTML='<div class="qa" role="dialog" aria-label="Quick add"><input placeholder="Add a task… e.g. Read ch 4 due fri #CSC4710" maxlength="300" aria-describedby="qaErr"><div class="qa-err" id="qaErr" role="alert"></div><div class="qa-foot"><button data-k="task" class="on">Task</button><button data-k="deadline">Deadline</button><span class="qa-hint"><kbd>Enter</kbd> to add · <kbd>Esc</kbd> to close</span></div></div>';
  document.addEventListener('DOMContentLoaded',()=>document.body.appendChild(b));
  const inp=b.querySelector('input'),err=b.querySelector('.qa-err');inp.addEventListener('input',()=>{err.textContent=''});let kind='task';
  b.querySelectorAll('[data-k]').forEach(x=>x.onclick=()=>{kind=x.dataset.k;b.querySelectorAll('[data-k]').forEach(y=>y.classList.toggle('on',y===x));inp.focus()});
  const open=()=>{b.classList.add('on');inp.value='';err.textContent='';setTimeout(()=>inp.focus(),0)}, close=()=>b.classList.remove('on');
  window.prodyQuickAdd=open;
  document.addEventListener('keydown',e=>{
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();b.classList.contains('on')?close():open()}
    else if(e.key.toLowerCase()==='n'&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&!b.classList.contains('on')&&!e.target.closest('input,textarea,select,[contenteditable],[contenteditable=""]')&&!e.target.isContentEditable){e.preventDefault();open()}
    else if(e.key==='Escape'&&b.classList.contains('on'))close();
  });
  b.addEventListener('mousedown',e=>{if(e.target===b)close()});
  inp.addEventListener('keydown',e=>{
    if(e.key!=='Enter'||!inp.value.trim())return;
    const tok=document.querySelector('meta[name=csrf-token]');
    fetch('/quick-add',{method:'POST',headers:{'Content-Type':'application/json',...(tok?{'X-CSRFToken':tok.content}:{})},body:JSON.stringify({text:inp.value,kind})})
      .then(r=>r.json().catch(()=>({ok:false}))).then(d=>{
        if(!d.ok){err.textContent=d.error||'Could not add that.';inp.focus();return;} /* keep typed text */
        const msg=`Added ${d.kind==='deadline'?'deadline':'task'}: ${d.name}${d.due?' · due '+d.due:''}${d.nudge?' · '+d.nudge:''}`;
        window.prodyToast?prodyToast(msg,'success'):0; if(d.ok){close(); if(/todo|calendar|dashboard|^\/$/.test(location.pathname)) setTimeout(()=>location.reload(),600)}
      }).catch(()=>{err.textContent='Could not reach Prody. Try again.'});
  });
})();
